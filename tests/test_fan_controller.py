"""Adapter tests with a fake backend: no GPIO, sensor or GUI access."""

import pytest
import json
from types import SimpleNamespace
from src import live_monitor as monitor
from src import live_tflite_fan_control as demo


class FakePWM:
    def __init__(self, **kwargs):
        self.calls = []
        self.fail_enter = False
        self.fail_write = False

    def __enter__(self):
        self.calls.append("enter")
        if self.fail_enter:
            raise RuntimeError("lock busy")
        return self

    def set_percent(self, percent):
        self.calls.append(("set", percent))
        if self.fail_write:
            raise RuntimeError("unconfirmed readback")

    def stop(self):
        self.set_percent(0)

    def close(self):
        self.calls.append("release_without_change")


@pytest.fixture
def backend(monkeypatch):
    fake = FakePWM()
    monkeypatch.setattr(monitor, "FanPWM", lambda **kwargs: fake)
    return fake


@pytest.mark.parametrize("kwargs", [
    {"pin": 12}, {"pin": 24}, {"pin": True},
    {"run_percent": float("nan")}, {"run_percent": float("inf")},
    {"run_percent": -1}, {"run_percent": 101}, {"run_percent": True},
])
def test_invalid_configuration_cannot_touch_backend(monkeypatch, kwargs):
    def forbidden(**arguments):
        pytest.fail("Invalid settings must not construct a hardware backend")
    monkeypatch.setattr(monitor, "FanPWM", forbidden)
    with pytest.raises(ValueError):
        monitor.FanController(**{"pin": 18, **kwargs})


def test_constant_intermediate_point_and_explicit_close(backend):
    fan = monitor.FanController(18, run_percent=25)
    assert fan.enabled and fan.is_running
    for amplitude in (0, 2, 100, float("nan")):
        assert fan.update(amplitude) is True
    assert backend.calls == ["enter", ("set", 25)]
    fan.close()
    assert backend.calls[-2:] == [("set", 0), "release_without_change"]
    assert not fan.enabled and fan.is_running is False
    before = list(backend.calls)
    fan.close()
    assert backend.calls == before
    with pytest.raises(RuntimeError, match="closed"):
        fan.set_state(True)


@pytest.mark.parametrize("kwargs", [{"default_on": False}, {"run_percent": 0}])
def test_zero_setting_does_not_claim_commanded_activity(backend, kwargs):
    fan = monitor.FanController(18, **kwargs)
    assert backend.calls == ["enter", ("set", 0)]
    assert fan.enabled and fan.is_running is False
    fan.close()


def test_busy_backend_aborts_without_fallback_or_stop(backend):
    backend.fail_enter = True
    with pytest.raises(RuntimeError, match="lock busy"):
        monitor.FanController(18, run_percent=25)
    assert backend.calls == ["enter", "release_without_change"]


def test_failed_initial_setting_has_no_fallback(backend):
    backend.fail_write = True
    with pytest.raises(RuntimeError, match="unconfirmed"):
        monitor.FanController(18, run_percent=25)
    assert backend.calls == ["enter", ("set", 25), "release_without_change"]


def test_failed_stop_keeps_state_unknown_and_releases_on_close(backend):
    fan = monitor.FanController(18, run_percent=25)
    backend.fail_write = True
    with pytest.raises(RuntimeError, match="unconfirmed"):
        fan.set_state(False)
    assert not fan.enabled and fan.is_running is None
    assert "release_without_change" not in backend.calls
    with pytest.raises(RuntimeError, match="unconfirmed"):
        fan.close()
    assert fan.is_running is None
    assert backend.calls[-1] == "release_without_change"


def test_development_shutdown_is_opt_in_and_never_restarts(backend):
    fan = monitor.FanController(18, run_percent=25, allow_shutdown=True)
    assert fan.update(2) is False
    assert fan.update(0) is False
    assert backend.calls == ["enter", ("set", 25), ("set", 0)]
    fan.close()


@pytest.mark.parametrize("fail_capture", [False, True])
def test_demo_always_stops_and_releases_after_capture(monkeypatch, tmp_path, backend, fail_capture):
    fan = monitor.FanController(18, run_percent=100)
    actuator = demo.ExistingFanActuator(fan, 18, "100% setting", "0% setting", "fake")
    monkeypatch.setattr(demo, "acquisition_options", lambda args: {})
    monkeypatch.setattr(demo, "validate_acquisition_options", lambda *args, **kwargs: None)
    monkeypatch.setattr(demo, "allocate_run_paths", lambda path: (None, tmp_path / "run.csv", tmp_path / "event.json"))
    monkeypatch.setattr(demo, "initialize_fan_actuator", lambda dry_run: actuator)
    monkeypatch.setattr(demo, "print_run_summary", lambda *args: None)

    def measurements(*args, before_acquisition, **kwargs):
        before_acquisition()
        if fail_capture:
            raise RuntimeError("capture failed")
        yield from ()

    monkeypatch.setattr(demo, "iter_live_measurements", measurements)
    kwargs = dict(arguments=SimpleNamespace(consecutive_anomalies=2, dry_run=False, max_windows=1),
                  configuration=None, profile_metadata={}, runtime_metadata=None, scaler=None, runtime=None)
    if fail_capture:
        with pytest.raises(RuntimeError, match="capture failed"):
            demo.run_fan_control(**kwargs)
    else:
        demo.run_fan_control(**kwargs)
    assert backend.calls[-2:] == [("set", 0), "release_without_change"]
    assert not fan.enabled


@pytest.mark.parametrize("fail_acquisition,fail_fan", [(True, False), (True, True), (False, True)])
def test_monitor_cleanup_reaches_fan_bus_and_journal_on_errors(tmp_path, backend, fail_acquisition, fail_fan):
    fan = monitor.FanController(18, run_percent=25)
    backend.fail_write = fail_fan
    bus_closed = []

    def stop():
        if fail_acquisition:
            raise RuntimeError("reader did not stop")

    acquisition = SimpleNamespace(stop=stop, snapshot=lambda: {"fixture": True})
    bus = SimpleNamespace(close=lambda: bus_closed.append(True))
    events = (tmp_path / "events.jsonl").open("x")
    manifest = {}
    stem = tmp_path / "run"
    with pytest.raises(RuntimeError):
        monitor.close_live_run(acquisition, fan, bus, events, manifest, stem)
    assert backend.calls[-2:] == [("set", 0), "release_without_change"]
    assert bus_closed == [True] and events.closed
    report = json.loads(stem.with_suffix(".run.json").read_text())
    assert ("acquisition_close_error" in report) is fail_acquisition
    assert ("fan_close_error" in report) is fail_fan
    assert "ended_utc" in report


@pytest.mark.parametrize("dry_run,executed", [(True, False), (False, False), (False, True)])
def test_shutdown_evidence_distinguishes_dry_run_failed_command_and_motion(tmp_path, dry_run, executed):
    configuration = SimpleNamespace(profile_name="fixture", threshold=1,
                                    threshold_path=tmp_path / "threshold.json",
                                    scaler_path=tmp_path / "scaler.pkl", model_path=tmp_path / "model.tflite")
    metadata = SimpleNamespace(profile_version=1, profile_root=tmp_path, sampling_rate_hz=200)
    state = demo.AnomalyConfirmationState(2)
    state.first_anomaly_monotonic = 1.0
    state.first_anomaly_window_start_monotonic = 0.5
    state.first_anomaly_window_index = 1
    profile = {"autoencoder": {"tflite_model_sha256": "fixture"},
               "scaler": {"sha256": "fixture"}, "threshold": {"sha256": "fixture"}}
    event = demo.build_shutdown_event(
        configuration=configuration, profile_metadata=profile, runtime_metadata=metadata,
        state=state, window_index=2, confirmed_timestamp="fixture", confirmed_monotonic=2.0,
        action_started_timestamp="fixture", action_started_monotonic=2.1,
        action_completed_timestamp="fixture", action_duration_ms=1,
        hardware_stop_executed=executed, fan_action="fixture",
        stop_error=None if dry_run or executed else "unconfirmed readback", dry_run=dry_run,
        inference_time_ms=1, window_formation_time_ms=640, total_window_pipeline_time_ms=641,
        confirming_sampling_rate_hz=200, consecutive_sampling_rates_hz=[200, 200])
    assert ("dry-run" in event["reaction_time_basis"]) is dry_run
    assert event["mechanical_state"] == "not_measured"
    assert event["hardware_stop_confirmation"] == ("pwm_command_and_readback_only" if executed else "not_confirmed")


def test_demo_summary_describes_explicit_stop_policy_without_claiming_standstill(tmp_path, capsys):
    demo.print_run_summary(demo.LiveSummary(), tmp_path / "run.csv", None, False, False)
    output = capsys.readouterr().out
    assert "0-%-PWM anfordern" in output
    assert "Stillstand ist nicht gemessen" in output
    assert "nicht durch Cleanup" not in output
