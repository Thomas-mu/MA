"""Hardware-free checks: temporary sysfs fixtures and a fake pinctrl runner."""

import json
from pathlib import Path
import subprocess

import pytest

from src.fan_pwm import FanPWM, FanPWMBusy, FanPWMError


class FakePinctrl:
    def __init__(self, pwm_path):
        self.pwm_path = pwm_path
        self.mux = "a3"
        self.digital_level = "lo"
        self.commands = []
        self.ignore_restore = False
        self.fail_low = False

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        assert kwargs == {"check": False, "capture_output": True, "text": True, "timeout": 5}
        if command == ["pinctrl", "get", "18"]:
            function = "PWM0_CHAN2" if self.mux == "a3" else "output"
            level = self.digital_level if self.mux == "op" else "lo"
            return subprocess.CompletedProcess(command, 0,
                f"18: {self.mux} pd | {level} // GPIO18 = {function}\n", "")
        if command == ["pinctrl", "set", "18", "op", "dl"]:
            if self.fail_low:
                return subprocess.CompletedProcess(command, 1, "", "fixture failure")
            self.mux, self.digital_level = "op", "lo"
        elif command == ["pinctrl", "set", "18", "a3"]:
            # The previous stale duty must never appear during reconnection.
            assert (self.pwm_path / "duty_cycle").read_text() == "0"
            assert (self.pwm_path / "enable").read_text() == "1"
            if not self.ignore_restore:
                self.mux = "a3"
        else:
            raise AssertionError(f"Unexpected command: {command}")
        return subprocess.CompletedProcess(command, 0, "", "")


@pytest.fixture
def bench(tmp_path):
    device = tmp_path / "sys/devices/platform/axi/1000120000.pcie/1f00098000.pwm"
    chip = device / "pwm/pwmchip0"
    channel = chip / "pwm2"
    channel.mkdir(parents=True)
    (device / "of_node").mkdir()
    (device / "of_node/compatible").write_bytes(b"raspberrypi,rp1-pwm\0")
    (chip / "npwm").write_text("4")
    (chip / "device").symlink_to(device)
    exported = tmp_path / "sys/class/pwm/pwmchip0"
    exported.parent.mkdir(parents=True)
    exported.symlink_to(chip)
    for name, value in {"period": "40000", "duty_cycle": "0", "enable": "1", "polarity": "normal"}.items():
        (channel / name).write_text(value)
    runner = FakePinctrl(channel)
    arguments = {
        "journal_path": tmp_path / "fan.jsonl",
        "pwm_path": exported / "pwm2",
        "lock_path": tmp_path / "fan.lock",
        "runner": runner,
    }
    return arguments, channel, runner


def journal(arguments):
    return [json.loads(line) for line in arguments["journal_path"].read_text().splitlines()]


def contents(channel):
    return {path.name: path.read_text() for path in channel.iterdir()}


def writes(records):
    return [row for row in records if row["event"] in {"sysfs_write_intent", "command_intent"}
            and (row["event"] == "sysfs_write_intent" or row["command"][1] == "set")]


def test_construction_does_not_access_hardware_or_files(tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("Construction must not execute pinctrl")

    controller = FanPWM(journal_path=tmp_path / "missing/journal.jsonl",
                        pwm_path=tmp_path / "missing/pwmchip0/pwm2",
                        lock_path=tmp_path / "missing/lock", runner=forbidden)
    assert not (tmp_path / "missing").exists()
    with pytest.raises(FanPWMError, match="context manager"):
        controller.set_percent(25)


def test_context_and_readback_never_change_output(bench):
    arguments, channel, runner = bench
    (channel / "duty_cycle").write_text("10000")
    before = contents(channel)
    with FanPWM(**arguments) as fan:
        state = fan.verify(25)
        assert state["gpio_bcm"] == 18
        assert state["physical_pin"] == 12
        assert state["pwm_configuration"]["configured_frequency_hz"] == 25000
        assert state["pwm_configuration"]["configured_duty_percent"] == 25
        assert state["measured_rpm"] is None
        assert state["mechanical_state"] == "not_measured"
        assert state["electrical_waveform_measured"] is False
        assert fan.read_state()["pwm_mux_confirmed"] is True
    assert contents(channel) == before
    assert not writes(journal(arguments))
    assert all(command == ["pinctrl", "get", "18"] for command in runner.commands)


@pytest.mark.parametrize("fault", ["channel", "device", "compatible", "period", "polarity"])
def test_bad_preflight_never_partially_initializes(bench, fault):
    arguments, channel, runner = bench
    if fault == "channel":
        arguments["pwm_path"] = arguments["pwm_path"].with_name("pwm3")
    elif fault == "device":
        (channel.parent / "device").unlink()
        (channel.parent / "device").symlink_to(channel.parent)
    elif fault == "compatible":
        (channel.parents[2] / "of_node/compatible").write_bytes(b"other-device\0")
    elif fault == "period":
        (channel / "period").write_text("50000")
    else:
        (channel / "polarity").write_text("inversed")
    before = contents(channel)
    with pytest.raises(FanPWMError):
        with FanPWM(**arguments):
            raise AssertionError("Invalid preflight must not enter")
    assert contents(channel) == before
    assert runner.commands == []
    assert not writes(journal(arguments))
    assert journal(arguments)[-1]["event"] == "preflight_failed"


def test_advisory_lock_blocks_competing_controller_and_releases(bench):
    arguments, channel, runner = bench
    other_arguments = {**arguments, "journal_path": arguments["journal_path"].with_name("other.jsonl")}
    with FanPWM(**arguments):
        count = len(runner.commands)
        with pytest.raises(FanPWMBusy):
            with FanPWM(**other_arguments):
                raise AssertionError("Competing controller must not enter")
        assert len(runner.commands) == count
        assert journal(other_arguments)[-1]["event"] == "lock_busy"
    with FanPWM(**other_arguments) as other:
        other.verify(0)


def test_stale_digital_mux_is_lowered_before_restoring_pwm(bench):
    arguments, channel, runner = bench
    runner.mux, runner.digital_level = "op", "hi"
    (channel / "duty_cycle").write_text("10000")
    with FanPWM(**arguments) as fan:
        assert not fan.read_state()["pwm_mux_confirmed"]
        state = fan.set_percent(50)
        assert state["pwm_configuration"]["duty_cycle_ns"] == 20000
        fan.verify(50)
    mutations = writes(journal(arguments))
    assert [row["command"] if "command" in row else [Path(row["path"]).name, row["value"]]
            for row in mutations] == [
        ["pinctrl", "set", "18", "op", "dl"],
        ["duty_cycle", 0], ["enable", 1],
        ["pinctrl", "set", "18", "a3"], ["duty_cycle", 20000],
    ]
    assert (channel / "duty_cycle").read_text() == "20000"
    assert (channel / "enable").read_text() == "1"


def test_running_hardware_pwm_changes_directly_without_intermediate_stop(bench):
    arguments, channel, runner = bench
    (channel / "duty_cycle").write_text("10000")
    with FanPWM(**arguments) as fan:
        fan.set_percent(50)
    mutations = writes(journal(arguments))
    assert len(mutations) == 1
    assert mutations[0]["value"] == 20000
    assert (channel / "duty_cycle").read_text() == "20000"


def test_disabled_pwm_is_zeroed_before_enabling(bench):
    arguments, channel, runner = bench
    (channel / "enable").write_text("0")
    (channel / "duty_cycle").write_text("30000")
    with FanPWM(**arguments) as fan:
        fan.set_percent(25)
    assert [(Path(row["path"]).name, row["value"]) for row in writes(journal(arguments))] == [
        ("duty_cycle", 0), ("enable", 1), ("duty_cycle", 10000),
    ]


@pytest.mark.parametrize("percent", [-0.1, 100.1, float("nan"), float("inf"), -float("inf"), True, "bad"])
def test_invalid_percent_never_writes(bench, percent):
    arguments, channel, runner = bench
    before = contents(channel)
    with FanPWM(**arguments) as fan:
        with pytest.raises(ValueError, match="finite percentage"):
            fan.set_percent(percent)
    assert contents(channel) == before
    assert not writes(journal(arguments))
    assert any(row["event"] == "setting_request_rejected" for row in journal(arguments))


def test_failed_mux_readback_prevents_target_write(bench):
    arguments, channel, runner = bench
    runner.mux, runner.digital_level = "op", "hi"
    runner.ignore_restore = True
    with FanPWM(**arguments) as fan:
        with pytest.raises(FanPWMError, match="could not be restored"):
            fan.set_percent(50)
    assert (channel / "duty_cycle").read_text() == "0"
    assert not any(row.get("value") == 20000 for row in writes(journal(arguments)))
    failure = [row for row in journal(arguments) if row["event"] == "transaction_failed"][-1]
    assert failure["possible_partial_change"] is True
    assert failure["rollback_performed"] is False
    assert failure["mechanical_state"] == "not_measured"


def test_failed_low_command_prevents_all_sysfs_changes(bench):
    arguments, channel, runner = bench
    runner.mux, runner.digital_level = "op", "hi"
    runner.fail_low = True
    before = contents(channel)
    with FanPWM(**arguments) as fan:
        with pytest.raises(FanPWMError, match="pinctrl failed"):
            fan.set_percent(50)
    assert contents(channel) == before
    assert not any(row["event"] == "sysfs_write_intent" for row in journal(arguments))
    assert any(row["event"] == "command_failed" for row in journal(arguments))


def test_failed_sysfs_readback_is_reported_without_claiming_success(bench, monkeypatch):
    arguments, channel, runner = bench
    original_read = Path.read_text

    def corrupted_read(path, *args, **kwargs):
        result = original_read(path, *args, **kwargs)
        if path.name == "duty_cycle" and result == "20000":
            return "19999"
        return result

    with FanPWM(**arguments) as fan:
        monkeypatch.setattr(Path, "read_text", corrupted_read)
        with pytest.raises(FanPWMError, match="readback mismatch"):
            fan.set_percent(50)
    records = journal(arguments)
    assert any(row["event"] == "sysfs_write_failed" for row in records)
    assert any(row["event"] == "transaction_failed" for row in records)
    assert not any(row["event"] == "transaction_complete" for row in records)


@pytest.mark.parametrize("interference", ["mux", "duty", "enable"])
def test_verify_detects_external_change_without_repair(bench, interference):
    arguments, channel, runner = bench
    with FanPWM(**arguments) as fan:
        fan.verify(0)
        if interference == "mux":
            runner.mux, runner.digital_level = "op", "hi"
        elif interference == "duty":
            (channel / "duty_cycle").write_text("10000")
        else:
            (channel / "enable").write_text("0")
        before = contents(channel)
        with pytest.raises(FanPWMError, match="unconfirmed"):
            fan.verify(0)
        assert contents(channel) == before
    assert not writes(journal(arguments))
    assert any(row["event"] == "setting_verification_failed" for row in journal(arguments))


def test_stop_is_enabled_zero_without_mechanical_state_claim(bench):
    arguments, channel, runner = bench
    (channel / "duty_cycle").write_text("40000")
    with FanPWM(**arguments) as fan:
        state = fan.stop()
        assert state["pwm_configuration"]["configured_duty_percent"] == 0
        assert state["pwm_configuration"]["enable"] == 1
        assert state["mechanical_state"] == "not_measured"
    assert (channel / "enable").read_text() == "1"


def test_journal_keeps_command_intents_results_and_transaction_times(bench):
    arguments, channel, runner = bench
    with FanPWM(**arguments) as fan:
        fan.set_percent(25)
    records = journal(arguments)
    assert all(row["utc"].endswith("+00:00") for row in records)
    assert all(isinstance(row["monotonic_ns"], int) for row in records)
    assert [row["monotonic_ns"] for row in records] == sorted(row["monotonic_ns"] for row in records)
    assert all(row["gpio_bcm"] == 18 and row["physical_pin"] == 12 for row in records)
    begin = next(row for row in records if row["event"] == "transaction_begin")
    end = next(row for row in records if row["event"] == "transaction_complete")
    assert begin["transaction_id"] == end["transaction_id"]
    assert begin["requested_percent"] == end["requested_percent"] == 25
    assert end["state"]["pwm_configuration"]["configured_duty_percent"] == 25
    assert records[-1]["output_policy"] == "leave_last_setting_unchanged"


def test_journal_intent_failure_prevents_hardware_write(bench, monkeypatch):
    arguments, channel, runner = bench
    before = contents(channel)
    with FanPWM(**arguments) as fan:
        original_journal = fan._journal

        def unavailable(event, **details):
            if event == "sysfs_write_intent":
                raise OSError("journal unavailable")
            original_journal(event, **details)

        monkeypatch.setattr(fan, "_journal", unavailable)
        with pytest.raises(OSError, match="journal unavailable"):
            fan.set_percent(25)
    assert contents(channel) == before


def test_context_error_releases_lock_without_implicit_stop(bench):
    arguments, channel, runner = bench
    with pytest.raises(RuntimeError, match="recording failed"):
        with FanPWM(**arguments) as fan:
            fan.set_percent(25)
            raise RuntimeError("recording failed")
    assert (channel / "duty_cycle").read_text() == "10000"
    with FanPWM(**arguments) as fan:
        fan.verify(25)
