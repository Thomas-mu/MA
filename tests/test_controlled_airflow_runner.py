"""No hardware, real waiting, or measurements: explicit-release runner safety."""

from copy import deepcopy
import json
from pathlib import Path

import pandas as pd
import pytest

from src import run_controlled_airflow_test as runner


BOOT = "test-boot"
PROTOCOL_ID = "independent-normal-fixture"
MOUNTING_ID = "fan_upright_position_v4_20260911_103726"
SECOND = 1_000_000_000


def zero_readback():
    return {
        "gpio_bcm": 18,
        "physical_pin": 12,
        "pwm_chip": 0,
        "pwm_channel": 2,
        "pwm_mux_confirmed": True,
        "pwm_configuration": {
            "period_ns": 40000,
            "duty_cycle_ns": 0,
            "enable": 1,
            "polarity": "normal",
            "configured_frequency_hz": 25000,
            "configured_duty_percent": 0,
        },
        "pin_readback": {"mux": "a3", "function": "PWM0_CHAN2"},
        "electrical_waveform_measured": False,
        "measured_rpm": None,
        "mechanical_state": "not_measured",
    }


def protocol():
    return {
        "protocol_id": PROTOCOL_ID,
        "mounting_id": MOUNTING_ID,
        "boot_id": BOOT,
        "frozen_at_monotonic_ns": 10 * SECOND,
        "planned_runs": ["normal_before", "airflow_modified", "normal_after"],
        "frozen_bundle": {"sha256": runner.FROZEN_BUNDLE_SHA256},
    }


def plate_geometry():
    return {
        "source": "operator_report", "width_mm": 120, "height_mm": 120,
        "distance_mm": 100,
        "distance_reference": "outlet_frame_plane_to_nearest_plate_face",
        "outlet_identification": "Fixture operator read airflow arrow pointing towards plate",
        "parallel_to_outlet": True, "centered_on_outlet": True,
        "separate_stable_holder": True, "no_contact": True,
        "independently_measured": False,
    }


def release(phase="normal_before"):
    return {
        "source": "explicit_user_message",
        "released": True,
        "phase": phase,
        "authorized_phases": [phase],
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": "a" * 64,
        "mounting_id": MOUNTING_ID,
        "boot_id": BOOT,
        "accepted_monotonic_ns": 50 * SECOND,
        "ready": True,
        "plate_absent": phase != "airflow_modified",
        "plate_present": phase == "airflow_modified",
        "plate_geometry": None if phase != "airflow_modified" else plate_geometry(),
        "manual_change_power_disconnected": phase != "normal_before",
        "no_fan_sensor_movement": True,
        "external_supply_connected": True,
        "mechanical_standstill_confirmed": True,
        "mounting_unchanged": True,
        "operator_message": "Lüfter steht, nächster Lauf freigegeben",
    }


def previous(phase="normal_before"):
    return {
        "phase": phase,
        "status": "completed",
        "boot_id": BOOT,
        "protocol_id": PROTOCOL_ID,
        "mounting_id": MOUNTING_ID,
        "final_readback": zero_readback(),
        "zero_command_completed_monotonic_ns": 40 * SECOND,
    }


def validate(value=None, prior=None, plan=None, **kwargs):
    return runner.validate_release(
        protocol() if plan is None else plan,
        release() if value is None else value,
        prior,
        boot_id=kwargs.pop("boot_id", BOOT),
        now_ns=kwargs.pop("now_ns", 51 * SECOND),
        **kwargs,
    )


def test_first_release_validates_without_modifying_evidence():
    plan, value = protocol(), release()
    original = deepcopy((plan, value))
    assert validate(value, plan=plan) is None
    assert (plan, value) == original


@pytest.mark.parametrize("phase,prior_phase", [
    ("airflow_modified", "normal_before"),
    ("normal_after", "airflow_modified"),
])
def test_next_phase_requires_its_own_release_after_preceding_zero(phase, prior_phase):
    assert validate(release(phase), previous(prior_phase)) is None


@pytest.mark.parametrize("field,value", [
    ("source", "inferred_from_timeout"),
    ("released", False),
    ("authorized_phases", ["normal_before", "airflow_modified"]),
    ("authorized_phases", ["airflow_modified"]),
    ("protocol_id", "another-study"),
    ("mounting_id", "older-mounting"),
    ("boot_id", "previous-boot"),
    ("ready", False),
    ("external_supply_connected", False),
    ("mechanical_standstill_confirmed", False),
    ("mounting_unchanged", False),
    ("accepted_monotonic_ns", True),
    ("accepted_monotonic_ns", 50.5),
    ("accepted_monotonic_ns", 9 * SECOND),
    ("accepted_monotonic_ns", 52 * SECOND),
    ("phase", "unplanned-fourth-run"),
])
def test_invalid_or_incomplete_release_cannot_start(field, value):
    candidate = release()
    candidate[field] = value
    with pytest.raises(ValueError):
        validate(candidate)


@pytest.mark.parametrize("field", [
    "ready", "external_supply_connected",
    "mechanical_standstill_confirmed", "mounting_unchanged", "released",
])
def test_missing_confirmation_is_not_permission(field):
    candidate = release()
    del candidate[field]
    with pytest.raises(ValueError):
        validate(candidate)


def test_protocol_from_previous_boot_is_not_reusable():
    plan = protocol()
    plan["boot_id"] = "previous-boot"
    with pytest.raises(ValueError):
        validate(plan=plan)


def test_first_release_does_not_authorize_later_phase():
    with pytest.raises(ValueError):
        validate(release("airflow_modified"), None)


def test_predecessor_is_not_accepted_for_first_run():
    with pytest.raises(ValueError):
        validate(release(), previous())


@pytest.mark.parametrize("field,value", [
    ("phase", "airflow_modified"),
    ("status", "error"),
    ("status", "shutdown_error"),
    ("status", "incomplete"),
    ("boot_id", "previous-boot"),
    ("protocol_id", "another-study"),
    ("zero_command_completed_monotonic_ns", 50 * SECOND),
    ("zero_command_completed_monotonic_ns", 51 * SECOND),
])
def test_predecessor_must_be_completed_same_study_and_stopped_before_release(field, value):
    prior = previous()
    prior[field] = value
    with pytest.raises(ValueError):
        validate(release("airflow_modified"), prior)


@pytest.mark.parametrize("field,value", [
    ("configured_duty_percent", 75),
    ("duty_cycle_ns", 30000),
    ("enable", 0),
    ("period_ns", 50000),
    ("polarity", "inversed"),
])
def test_saved_zero_percentage_alone_does_not_prove_valid_predecessor_control(field, value):
    prior = previous()
    prior["final_readback"]["pwm_configuration"][field] = value
    with pytest.raises(ValueError):
        validate(release("airflow_modified"), prior)


def test_predecessor_digital_pin_cannot_pass_as_hardware_pwm():
    prior = previous()
    prior["final_readback"]["pwm_mux_confirmed"] = False
    prior["final_readback"]["pin_readback"] = {"mux": "op", "function": "output"}
    with pytest.raises(ValueError):
        validate(release("airflow_modified"), prior)


class FakeClock:
    def __init__(self, seconds):
        self.ns = int(seconds * SECOND)
        self.sleeps = []

    def __call__(self):
        return self.ns

    def sleep(self, seconds):
        assert 0 < seconds <= 1
        self.sleeps.append(seconds)
        self.ns += round(seconds * SECOND)


def test_additional_off_wait_is_sixty_seconds_from_current_release():
    clock = FakeClock(50)
    target = runner.wait_off_until(50 * SECOND, clock=clock, sleep=clock.sleep)
    assert target == 110 * SECOND
    assert clock.ns == 110 * SECOND
    assert sum(clock.sleeps) == pytest.approx(60)


def test_preparation_time_counts_towards_additional_off_wait():
    clock = FakeClock(65.25)
    assert runner.wait_off_until(50 * SECOND, clock=clock, sleep=clock.sleep) == 110 * SECOND
    assert sum(clock.sleeps) == pytest.approx(44.75)


def test_delayed_preparation_does_not_reset_timer_or_cause_retry():
    clock = FakeClock(121)
    assert runner.wait_off_until(50 * SECOND, clock=clock, sleep=clock.sleep) == 110 * SECOND
    assert clock.sleeps == []


class FakeFan:
    def __init__(self, *, set_error=None, stop_error=None, verify_running_error=None):
        self.calls = []
        self.set_error = set_error
        self.stop_error = stop_error
        self.verify_running_error = verify_running_error

    def set_percent(self, percent):
        self.calls.append(("set", percent))
        assert percent == 75
        if self.set_error:
            raise self.set_error
        state = zero_readback()
        state["pwm_configuration"].update(configured_duty_percent=75, duty_cycle_ns=30000)
        return state

    def stop(self):
        self.calls.append(("stop", 0))
        if self.stop_error:
            raise self.stop_error
        return zero_readback()

    def verify(self, percent):
        self.calls.append(("verify", percent))
        if percent == 75 and self.verify_running_error:
            raise self.verify_running_error
        state = zero_readback()
        state["pwm_configuration"].update(configured_duty_percent=percent,
                                             duty_cycle_ns=int(percent * 400))
        return state

    def read_state(self):
        self.calls.append(("read_state", None))
        return {"unconfirmed_fixture_state": True}


def capture_fixture(monkeypatch, tmp_path, phase="normal_before"):
    clock = FakeClock(100)
    monkeypatch.setattr(runner.time, "monotonic_ns", clock)
    calls = []
    bus = object()
    session = {"phase": phase}
    expected_state, expected_label = runner.conditions(phase)
    metadata = {"condition_label": expected_state}
    path = tmp_path / "normal_before.csv"

    def recorder(actual_bus, duration_seconds, sample_rate_hz, **kwargs):
        assert actual_bus is bus
        assert (duration_seconds, sample_rate_hz) == (300, 200)
        assert kwargs["output_path"] == path
        assert kwargs["label"] == expected_label
        assert kwargs["state"] == expected_state
        assert kwargs["metadata"] is metadata
        calls.append(kwargs)
        frame = pd.DataFrame({"host_monotonic_ns": [100_075_000_000, 399_990_000_000]})
        frame.attrs["report"] = {"status": "completed", "summary": {"samples": 2}}
        return frame

    return bus, session, path, metadata, recorder, calls


def test_capture_is_once_normal_300s_75_percent_and_always_returns_zero(monkeypatch, tmp_path):
    bus, session, path, metadata, recorder, calls = capture_fixture(monkeypatch, tmp_path)
    fan = FakeFan()
    failure = runner.execute_capture(fan, bus, session, path, metadata, recorder=recorder)
    assert failure is None
    assert len(calls) == 1
    assert fan.calls == [("set", 75), ("verify", 75), ("stop", 0), ("verify", 0)]
    assert session["status"] == "completed"
    assert session["final_readback"]["pwm_configuration"]["configured_duty_percent"] == 0
    assert session["final_readback"]["mechanical_state"] == "not_measured"
    assert session["timing"]["first_xyz_after_command_invocation_s"] == pytest.approx(.075)
    assert metadata["pwm_command_invocation_monotonic_ns"] == 100 * SECOND
    assert not path.exists(), "A software test must not produce a supposed real capture"


@pytest.mark.parametrize("error", [OSError("sensor failed"), KeyboardInterrupt("cancelled")])
def test_record_failure_and_interrupt_preserve_error_stop_and_never_retry(monkeypatch, tmp_path, error):
    bus, session, path, metadata, _, _ = capture_fixture(monkeypatch, tmp_path)
    attempts = []

    def fail(*args, **kwargs):
        attempts.append(1)
        raise error

    fan = FakeFan()
    assert runner.execute_capture(fan, bus, session, path, metadata, recorder=fail) is error
    assert attempts == [1]
    assert fan.calls == [("set", 75), ("stop", 0), ("verify", 0)]
    assert session["status"] == "error"
    assert str(error) in session["error"]
    assert session["final_readback"]["pwm_configuration"]["configured_duty_percent"] == 0


def test_partially_failed_start_still_attempts_zero_without_recording(monkeypatch, tmp_path):
    bus, session, path, metadata, recorder, calls = capture_fixture(monkeypatch, tmp_path)
    error = OSError("PWM write failed after partial change")
    fan = FakeFan(set_error=error)
    assert runner.execute_capture(fan, bus, session, path, metadata, recorder=recorder) is error
    assert calls == []
    assert fan.calls == [("set", 75), ("stop", 0), ("verify", 0)]


def test_changed_running_pwm_rejects_capture_status_and_returns_zero(monkeypatch, tmp_path):
    bus, session, path, metadata, recorder, calls = capture_fixture(monkeypatch, tmp_path)
    error = RuntimeError("Unexpected operating point")
    fan = FakeFan(verify_running_error=error)
    assert runner.execute_capture(fan, bus, session, path, metadata, recorder=recorder) is error
    assert len(calls) == 1
    assert session["status"] == "error"
    assert fan.calls[-2:] == [("stop", 0), ("verify", 0)]


def test_shutdown_failure_reports_actual_state_instead_of_claiming_zero(monkeypatch, tmp_path):
    bus, session, path, metadata, recorder, calls = capture_fixture(monkeypatch, tmp_path)
    error = OSError("zero command could not be confirmed")
    fan = FakeFan(stop_error=error)
    assert runner.execute_capture(fan, bus, session, path, metadata, recorder=recorder) is error
    assert len(calls) == 1
    assert session["status"] == "shutdown_error"
    assert "final_readback" not in session
    assert session["actual_state_after_shutdown_error"] == {"unconfirmed_fixture_state": True}
    assert fan.calls[-2:] == [("stop", 0), ("read_state", None)]


def test_record_and_shutdown_errors_are_both_preserved(monkeypatch, tmp_path):
    bus, session, path, metadata, _, _ = capture_fixture(monkeypatch, tmp_path)
    acquisition_error = OSError("lost sensor")
    shutdown_error = OSError("could not write zero")

    def fail(*args, **kwargs):
        raise acquisition_error

    fan = FakeFan(stop_error=shutdown_error)
    assert runner.execute_capture(fan, bus, session, path, metadata, recorder=fail) is acquisition_error
    assert "lost sensor" in session["error"]
    assert "could not write zero" in session["shutdown_error"]
    assert session["status"] == "shutdown_error"
    assert fan.calls.count(("set", 75)) == 1


def test_incomplete_recorder_result_is_never_marked_completed(monkeypatch, tmp_path):
    bus, session, path, metadata, recorder, calls = capture_fixture(monkeypatch, tmp_path)

    def interrupted(*args, **kwargs):
        frame = recorder(*args, **kwargs)
        frame.attrs["report"]["status"] = "interrupted"
        return frame

    fan = FakeFan()
    runner.execute_capture(fan, bus, session, path, metadata, recorder=interrupted)
    assert session["status"] != "completed"
    assert len(calls) == 1
    assert fan.calls[-2:] == [("stop", 0), ("verify", 0)]


def gate_fixture(monkeypatch, tmp_path, phase="normal_before"):
    """Synthetic evidence only; /proc is intercepted and no device is opened."""
    implementation = tmp_path / "fixture_implementation.py"
    implementation.write_text("# fixture implementation\n")
    plan = protocol()
    plan.update(
        purpose="controlled_airflow_test", pwm_percent=75, pwm_frequency_hz=25000,
        duration_s=300, additional_off_after_release_s=60,
        implementation_sha256={str(implementation): runner.digest(implementation)},
    )
    plan_path = tmp_path / "protocol.json"
    plan_path.write_text(json.dumps(plan))
    expected = runner.digest(plan_path)
    plan_path.with_suffix(".sha256").write_text(expected)
    value = release(phase)
    value["protocol_sha256"] = expected
    release_path = tmp_path / f"{phase}_release.json"
    release_path.write_text(json.dumps(value))
    real_read_text = Path.read_text

    def read_text(path, *args, **kwargs):
        if str(path) == "/proc/sys/kernel/random/boot_id":
            return BOOT + "\n"
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr(runner.time, "monotonic_ns", FakeClock(51))
    return plan_path, release_path, implementation


def test_release_gate_is_read_only_and_accepts_only_frozen_current_release(monkeypatch, tmp_path):
    plan_path, release_path, _ = gate_fixture(monkeypatch, tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    plan, value, prior = runner.release_gate(plan_path, "normal_before", release_path)
    assert prior is None
    assert value["authorized_phases"] == ["normal_before"]
    assert plan["_sha256"] == runner.digest(plan_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize("suffix", ["_session.json", "_fan.jsonl"])
@pytest.mark.parametrize("existing_content", ["", "{}", '{"status":"error"}'])
def test_any_previous_attempt_marker_blocks_replay_even_if_empty_or_failed(monkeypatch, tmp_path, suffix, existing_content):
    plan_path, release_path, _ = gate_fixture(monkeypatch, tmp_path)
    marker = tmp_path / ("normal_before" + suffix)
    marker.write_text(existing_content)
    with pytest.raises(ValueError, match="already attempted"):
        runner.release_gate(plan_path, "normal_before", release_path)
    assert marker.read_text() == existing_content


@pytest.mark.parametrize("changed", ["protocol", "implementation", "release_hash"])
def test_changes_to_frozen_evidence_prevent_start(monkeypatch, tmp_path, changed):
    plan_path, release_path, implementation = gate_fixture(monkeypatch, tmp_path)
    if changed == "protocol":
        plan_path.write_text(plan_path.read_text() + "\n")
    elif changed == "implementation":
        implementation.write_text("# changed implementation\n")
    else:
        value = json.loads(release_path.read_text())
        value["protocol_sha256"] = "b" * 64
        release_path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="[Hh]ash|Implementation changed"):
        runner.release_gate(plan_path, "normal_before", release_path)
    assert not (tmp_path / "normal_before_session.json").exists()


def test_gate_cannot_substitute_another_release_file(monkeypatch, tmp_path):
    plan_path, release_path, _ = gate_fixture(monkeypatch, tmp_path)
    other = tmp_path / "old_release.json"
    other.write_bytes(release_path.read_bytes())
    with pytest.raises(ValueError, match="release path"):
        runner.release_gate(plan_path, "normal_before", other)


def test_second_gate_requires_immediately_previous_session_and_same_protocol_hash(monkeypatch, tmp_path):
    plan_path, release_path, _ = gate_fixture(monkeypatch, tmp_path, "airflow_modified")
    prior = previous()
    prior["protocol_sha256"] = "b" * 64
    session_path = tmp_path / "normal_before_session.json"
    session_path.write_text(json.dumps(prior))
    with pytest.raises(ValueError, match="Previous protocol mismatch"):
        runner.release_gate(plan_path, "airflow_modified", release_path)
    prior["protocol_sha256"] = runner.digest(plan_path)
    session_path.write_text(json.dumps(prior))
    _, _, accepted_prior = runner.release_gate(plan_path, "airflow_modified", release_path)
    assert accepted_prior == prior


def test_main_rejects_unreleased_start_before_any_external_command(monkeypatch, tmp_path):
    plan_path, release_path, _ = gate_fixture(monkeypatch, tmp_path)
    value = json.loads(release_path.read_text())
    value["released"] = False
    release_path.write_text(json.dumps(value))
    monkeypatch.setattr("sys.argv", [
        "runner", "--protocol", str(plan_path), "--release", str(release_path),
        "--phase", "normal_before",
    ])

    def forbidden(*args, **kwargs):
        raise AssertionError("No external command may precede release validation")

    monkeypatch.setattr(runner.subprocess, "run", forbidden)
    with pytest.raises(ValueError, match="Explicit release required"):
        runner.main()
    assert not (tmp_path / "normal_before_session.json").exists()
    assert not (tmp_path / "normal_before_fan.jsonl").exists()


@pytest.mark.parametrize("phase", ["airflow_modified", "normal_after"])
def test_each_remaining_phase_records_its_own_state_and_numeric_label_once(monkeypatch, tmp_path, phase):
    bus, session, path, metadata, recorder, calls = capture_fixture(monkeypatch, tmp_path, phase)
    fan = FakeFan()
    assert runner.execute_capture(fan, bus, session, path, metadata, recorder=recorder) is None
    assert len(calls) == 1
    assert calls[0]["state"] == ("airflow_modified" if phase == "airflow_modified" else "normal")
    assert calls[0]["label"] == (1 if phase == "airflow_modified" else 0)
    assert fan.calls == [("set", 75), ("verify", 75), ("stop", 0), ("verify", 0)]


def test_metadata_condition_mismatch_blocks_start_and_preserves_zero(monkeypatch, tmp_path):
    bus, session, path, metadata, recorder, calls = capture_fixture(monkeypatch, tmp_path)
    metadata["condition_label"] = "airflow_modified"
    fan = FakeFan()
    failure = runner.execute_capture(fan, bus, session, path, metadata, recorder=recorder)
    assert isinstance(failure, ValueError)
    assert fan.calls == [("stop", 0), ("verify", 0)]
    assert not calls


@pytest.mark.parametrize("phase,field,value", [
    ("normal_before", "plate_absent", False),
    ("normal_before", "plate_present", True),
    ("airflow_modified", "plate_present", False),
    ("airflow_modified", "plate_absent", True),
    ("airflow_modified", "plate_geometry", None),
    ("airflow_modified", "manual_change_power_disconnected", False),
    ("airflow_modified", "no_fan_sensor_movement", False),
    ("normal_after", "plate_absent", False),
    ("normal_after", "manual_change_power_disconnected", False),
    ("normal_after", "no_fan_sensor_movement", False),
])
def test_plate_and_manual_change_conditions_are_required_before_release(phase, field, value):
    candidate = release(phase)
    candidate[field] = value
    index = runner.PHASES.index(phase)
    prior = previous(runner.PHASES[index - 1]) if index else None
    with pytest.raises(ValueError):
        validate(candidate, prior)


@pytest.mark.parametrize("field,value", [
    ("width_mm", 60), ("height_mm", 100), ("distance_mm", 50),
    ("distance_mm", True), ("distance_mm", float("nan")),
    ("distance_reference", "unspecified"), ("outlet_identification", "unbekannt"),
    ("parallel_to_outlet", False), ("centered_on_outlet", False),
    ("separate_stable_holder", False), ("no_contact", False),
    ("source", "inferred_from_plan"), ("independently_measured", True),
])
def test_unknown_or_different_geometry_is_not_accepted_as_actual_confirmation(field, value):
    candidate = release("airflow_modified")
    candidate["plate_geometry"][field] = value
    with pytest.raises(ValueError):
        validate(candidate, previous())


def test_geometry_for_normal_phase_is_rejected():
    candidate = release()
    candidate["plate_geometry"] = plate_geometry()
    with pytest.raises(ValueError):
        validate(candidate)


def historical_reference(tmp_path):
    prior = previous("normal_test_03")
    prior["protocol_id"] = "separate-completed-normal-test"
    path = tmp_path / "historical_zero_session.json"
    path.write_text(json.dumps(prior))
    return path, prior, {"session": str(path), "sha256": runner.digest(path)}


def test_first_reference_uses_only_prior_zero_timing_without_phase_or_data_pooling(tmp_path):
    path, prior, ref = historical_reference(tmp_path)
    plan = protocol()
    plan["first_previous_zero_reference"] = ref
    result = runner.load_previous_zero_reference(plan, release(), BOOT)
    assert result["zero_command_completed_monotonic_ns"] == 40 * SECOND
    assert result["use"] == "off_duration_only_not_a_measurement_reference"
    assert "csv" not in result and "recording" not in result
    assert json.loads(path.read_text()) == prior


@pytest.mark.parametrize("field,value", [
    ("boot_id", "different-boot"), ("mounting_id", "different-mount"),
    ("status", "error"), ("zero_command_completed_monotonic_ns", 55 * SECOND),
    ("zero_command_completed_monotonic_ns", True),
])
def test_historical_zero_reference_must_be_comparable_and_precede_release(tmp_path, field, value):
    path, prior, ref = historical_reference(tmp_path)
    prior[field] = value
    path.write_text(json.dumps(prior))
    ref["sha256"] = runner.digest(path)
    plan = protocol()
    plan["first_previous_zero_reference"] = ref
    with pytest.raises(ValueError):
        runner.load_previous_zero_reference(plan, release(), BOOT)


def test_changed_historical_session_rejected_without_restating_zero(tmp_path):
    path, prior, ref = historical_reference(tmp_path)
    path.write_text(path.read_text() + "\n")
    plan = protocol()
    plan["first_previous_zero_reference"] = ref
    with pytest.raises(ValueError, match="hash mismatch"):
        runner.load_previous_zero_reference(plan, release(), BOOT)


def test_historical_percent_zero_alone_is_not_confirmed_hardware_pwm(tmp_path):
    path, prior, ref = historical_reference(tmp_path)
    prior["final_readback"]["pwm_mux_confirmed"] = False
    path.write_text(json.dumps(prior))
    ref["sha256"] = runner.digest(path)
    plan = protocol()
    plan["first_previous_zero_reference"] = ref
    with pytest.raises(ValueError, match="readback unconfirmed"):
        runner.load_previous_zero_reference(plan, release(), BOOT)


def test_gate_accepts_historical_off_reference_but_preserves_first_phase_identity(monkeypatch, tmp_path):
    plan_path, release_path, _ = gate_fixture(monkeypatch, tmp_path)
    _, _, ref = historical_reference(tmp_path)
    plan = json.loads(plan_path.read_text())
    plan["first_previous_zero_reference"] = ref
    plan_path.write_text(json.dumps(plan))
    sha = runner.digest(plan_path)
    plan_path.with_suffix(".sha256").write_text(sha)
    value = json.loads(release_path.read_text())
    value["protocol_sha256"] = sha
    release_path.write_text(json.dumps(value))
    actual_plan, _, prior = runner.release_gate(plan_path, "normal_before", release_path)
    assert prior is None
    assert actual_plan["_first_previous_zero_reference"]["sha256"] == ref["sha256"]


def test_gate_rejects_different_frozen_model_package_before_hardware(monkeypatch, tmp_path):
    plan_path, release_path, _ = gate_fixture(monkeypatch, tmp_path)
    plan = json.loads(plan_path.read_text())
    plan["frozen_bundle"]["sha256"] = "d" * 64
    plan_path.write_text(json.dumps(plan))
    sha = runner.digest(plan_path)
    plan_path.with_suffix(".sha256").write_text(sha)
    value = json.loads(release_path.read_text())
    value["protocol_sha256"] = sha
    release_path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Wrong frozen pilot package"):
        runner.release_gate(plan_path, "normal_before", release_path)
