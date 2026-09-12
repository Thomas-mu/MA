#!/usr/bin/env python3
"""One explicitly released controlled airflow phase; never loop or retry.

Imports and release checks do not open a sensor or change PWM. The real capture
uses the existing FIFO recorder and the existing locked hardware-PWM control.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
try:
    from .controlled_airflow_contract import PHASES, conditions, validate_release_conditions
except ImportError:
    from controlled_airflow_contract import PHASES, conditions, validate_release_conditions

FROZEN_BUNDLE_SHA256 = "cec1859bfb354bafef77a619e6d2c1ffd85b50787c87595aba9a1e20a80cdae5"


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def persist(path, data):
    temp = path.with_suffix(".json.tmp")
    with temp.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def emit(event, **fields):
    print(json.dumps({"utc": utc(), "event": event, **fields}, ensure_ascii=False), flush=True)


def confirmed_zero(state):
    cfg = state.get("pwm_configuration", {})
    return (state.get("gpio_bcm") == 18 and state.get("physical_pin") == 12
            and state.get("pwm_mux_confirmed") is True
            and cfg.get("period_ns") == 40000 and cfg.get("duty_cycle_ns") == 0
            and cfg.get("enable") == 1 and cfg.get("polarity") == "normal"
            and cfg.get("configured_duty_percent") == 0)


def validate_release(protocol, release, previous, *, boot_id, now_ns):
    phase = release.get("phase")
    check(protocol.get("planned_runs") == PHASES and phase in PHASES, "Unexpected run")
    check(protocol.get("boot_id") == boot_id == release.get("boot_id"), "Different boot")
    check(release.get("source") == "explicit_user_message" and release.get("released") is True,
          "Explicit release required")
    check(release.get("authorized_phases") == [phase], "Release applies to one run only")
    check(release.get("protocol_id") == protocol["protocol_id"], "Different protocol")
    if "_sha256" in protocol:
        check(release.get("protocol_sha256") == protocol["_sha256"], "Release protocol hash mismatch")
    check(release.get("mounting_id") == protocol["mounting_id"], "Different mounting")
    validate_release_conditions(release, phase)
    accepted = release.get("accepted_monotonic_ns")
    check(type(accepted) is int and protocol["frozen_at_monotonic_ns"] < accepted <= now_ns,
          "Release must follow protocol freeze and not lie in the future")
    index = PHASES.index(phase)
    if index == 0:
        check(previous is None, "First run must not reuse an earlier measurement phase")
    else:
        check(isinstance(previous, dict), "Previous run missing")
        check(previous.get("phase") == PHASES[index - 1] and previous.get("status") == "completed",
              "Previous run did not complete; no automatic replacement")
        check(previous.get("boot_id") == boot_id and previous.get("protocol_id") == protocol["protocol_id"]
              and previous.get("mounting_id") == protocol["mounting_id"],
              "Previous run belongs to another boot/protocol/mounting")
        check(confirmed_zero(previous.get("final_readback", {})), "Previous 0 percent setting unconfirmed")
        zero = previous.get("zero_command_completed_monotonic_ns")
        check(type(zero) is int and zero < accepted, "Release must follow previous shutdown")


def wait_off_until(release_ns, *, clock=time.monotonic_ns, sleep=time.sleep):
    target = release_ns + 60_000_000_000
    while clock() < target:
        sleep(min(1., max(0., (target - clock()) / 1e9)))
    return target


def return_to_zero(fan, session):
    emit("returning_to_zero", pwm_percent=0)
    try:
        session["zero_command_result"] = fan.stop()
        session["zero_command_completed_monotonic_ns"] = time.monotonic_ns()
        session["zero_command_completed_utc"] = utc()
        state = fan.verify(0)
        check(confirmed_zero(state), "Final hardware-PWM readback is not confirmed zero")
        session["final_readback"] = state
        session["final_mechanical_state"] = "not_observed"
        emit("zero_readback_complete", pwm_percent=0, mechanical_state="not_observed")
        return None
    except BaseException as exc:
        session["shutdown_error"] = f"{type(exc).__name__}: {exc}"
        session["status"] = "shutdown_error"
        try:
            session["actual_state_after_shutdown_error"] = fan.read_state()
        except BaseException as read_exc:
            session["actual_state_read_error"] = str(read_exc)
        emit("shutdown_error", error=session["shutdown_error"], actual=session.get("actual_state_after_shutdown_error"))
        return exc


def execute_capture(fan, bus, session, csv_path, metadata, recorder=None):
    if recorder is None:
        from collect_real_data import record
        recorder = record
    failure = None
    try:
        state, numeric_label = conditions(session["phase"])
        check(metadata.get("condition_label") == state, "Capture condition mismatch")
        session["command_invocation_utc"] = utc()
        session["command_invocation_monotonic_ns"] = time.monotonic_ns()
        session["setting_result"] = fan.set_percent(75)
        session["command_completed_monotonic_ns"] = time.monotonic_ns()
        session["command_completed_utc"] = utc()
        for key in ("command_invocation_utc", "command_invocation_monotonic_ns", "command_completed_utc", "command_completed_monotonic_ns"):
            metadata["pwm_" + key] = session[key]
        session["status"] = "recording"
        session["record_invoked_monotonic_ns"] = time.monotonic_ns()
        emit("capture_start", phase=session["phase"], pwm_percent=75, frequency_hz=25000, duration_s=300, csv=str(csv_path))
        df = recorder(bus, 300, 200, output_path=csv_path, label=numeric_label, state=state, metadata=metadata)
        session["recording"] = df.attrs["report"]
        session["after_capture_readback"] = fan.verify(75)
        check(session["recording"].get("status") == "completed", "Recording incomplete; no restart")
        if len(df):
            first, last = int(df.host_monotonic_ns.iloc[0]), int(df.host_monotonic_ns.iloc[-1])
            origin = session["command_invocation_monotonic_ns"]
            session["timing"] = {
                "first_xyz_monotonic_ns": first, "last_xyz_monotonic_ns": last,
                "first_xyz_after_command_invocation_s": (first - origin) / 1e9,
                "first_xyz_after_command_completion_s": (first - session["command_completed_monotonic_ns"]) / 1e9,
                "first_to_last_xyz_s": (last - first) / 1e9,
                "last_xyz_after_command_invocation_s": (last - origin) / 1e9,
                "first_xyz_utc_estimate": datetime.fromtimestamp(datetime.fromisoformat(session["command_invocation_utc"]).timestamp() + (first - origin) / 1e9, timezone.utc).isoformat(),
                "electrical_signal_and_rotor_start_measured": False}
        session["status"] = "completed"
    except BaseException as exc:
        failure = exc
        session.update(status="error", error=f"{type(exc).__name__}: {exc}")
        emit("capture_error", error=session["error"])
    finally:
        shutdown = return_to_zero(fan, session)
        failure = failure or shutdown
    return failure


def release_gate(protocol_path, phase, release_path):
    protocol_path, release_path = Path(protocol_path).resolve(), Path(release_path).resolve()
    base = protocol_path.parent
    expected = protocol_path.with_suffix(".sha256").read_text().strip()
    check(digest(protocol_path) == expected, "Protocol hash mismatch")
    protocol = json.loads(protocol_path.read_text())
    protocol["_sha256"] = expected
    check(protocol["purpose"] == "controlled_airflow_test" and protocol["planned_runs"] == PHASES, "Wrong protocol")
    check(protocol["pwm_percent"] == 75 and protocol["pwm_frequency_hz"] == 25000 and protocol["duration_s"] == 300,
          "Operating point/duration changed")
    check(protocol["additional_off_after_release_s"] == 60, "Off-time changed")
    check(protocol["frozen_bundle"]["sha256"] == FROZEN_BUNDLE_SHA256, "Wrong frozen pilot package")
    for path, expected_hash in protocol["implementation_sha256"].items():
        check(digest(path) == expected_hash, f"Implementation changed after freeze: {path}")
    check(phase in PHASES, "Unexpected phase")
    check(release_path == base / f"{phase}_release.json", "Unexpected release path")
    for suffix in ("_session.json", "_fan.jsonl"):
        check(not (base / (phase + suffix)).exists(), "Run already attempted; no repeat or overwrite")
    release = json.loads(release_path.read_text())
    check(release.get("phase") == phase, "Release phase mismatch")
    previous = None
    index = PHASES.index(phase)
    if index:
        previous = json.loads((base / f"{PHASES[index-1]}_session.json").read_text())
        check(previous["protocol_sha256"] == expected, "Previous protocol mismatch")
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    validate_release(protocol, release, previous, boot_id=boot_id, now_ns=time.monotonic_ns())
    if index == 0 and protocol.get("first_previous_zero_reference") is not None:
        protocol["_first_previous_zero_reference"] = load_previous_zero_reference(protocol, release, boot_id)
    return protocol, release, previous


def load_previous_zero_reference(protocol, release, boot_id):
    """Use historical command timing only; never import a prior capture as reference."""
    reference = protocol["first_previous_zero_reference"]
    path = Path(reference["session"]).resolve()
    check(digest(path) == reference["sha256"], "Historical zero session hash mismatch")
    prior = json.loads(path.read_text())
    check(prior.get("status") == "completed", "Historical session did not complete")
    check(prior.get("boot_id") == boot_id and prior.get("mounting_id") == protocol["mounting_id"],
          "Historical zero reference boot/mounting differs")
    check(confirmed_zero(prior.get("final_readback", {})), "Historical zero readback unconfirmed")
    zero = prior.get("zero_command_completed_monotonic_ns")
    check(type(zero) is int and 0 < zero < release["accepted_monotonic_ns"],
          "Historical zero must precede current release")
    return {"session": str(path), "sha256": reference["sha256"],
            "zero_command_completed_monotonic_ns": zero,
            "use": "off_duration_only_not_a_measurement_reference"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--phase", choices=PHASES, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--check-release-only", action="store_true")
    args = parser.parse_args()
    protocol, release, previous = release_gate(args.protocol, args.phase, args.release)
    if args.check_release_only:
        emit("release_valid", phase=args.phase, hardware_access=False)
        return
    # Read frozen artifacts; never train, scale-fit, score, or actuate from detection.
    import pilot_method_comparison as pilot
    bundle_path = Path(protocol["frozen_bundle"]["directory"])
    bundle = pilot.load_bundle(bundle_path)
    check(digest(bundle_path / "pilot_bundle.json") == protocol["frozen_bundle"]["sha256"], "Frozen bundle changed")
    base = args.protocol.resolve().parent
    path = base / f"{args.phase}_session.json"
    journal = base / f"{args.phase}_fan.jsonl"
    session = {"phase": args.phase, "status": "preflight", "started_utc": utc(),
        "protocol_id": protocol["protocol_id"], "protocol_sha256": protocol["_sha256"],
        "frozen_bundle_sha256": protocol["frozen_bundle"]["sha256"],
        "mounting_id": protocol["mounting_id"], "boot_id": protocol["boot_id"],
        "user_release": release, "user_release_sha256": digest(args.release),
        "condition_label": conditions(args.phase)[0], "plate_geometry": release.get("plate_geometry"),
        "fan_journal": str(journal), "csv": None, "planned_additional_off_s": 60,
        "final_mechanical_state": "not_observed", "automatic_restarts": False,
        "running_observation_requested": False, "requested_duration_s": 300}
    with path.open("x") as handle:
        json.dump(session, handle, indent=2)
    done = threading.Event()
    def heartbeat():
        while not done.wait(30):
            emit("progress", phase=args.phase, status=session["status"],
                 elapsed_since_command_s=(time.monotonic_ns()-session["command_invocation_monotonic_ns"])/1e9 if "command_invocation_monotonic_ns" in session else None)
    progress = threading.Thread(target=heartbeat, daemon=True)
    progress.start()
    def stop_signal(*_):
        raise KeyboardInterrupt("Capture interrupted; attempt zero; no restart")
    signal.signal(signal.SIGINT, stop_signal)
    signal.signal(signal.SIGTERM, stop_signal)
    failure = None
    try:
        holders = subprocess.run(["fuser", "-v", "/dev/i2c-1", "/dev/gpiochip0", "/dev/gpiomem0"], capture_output=True, text=True, timeout=5)
        check(holders.returncode == 1 and not holders.stdout and not holders.stderr, "Sensor/controller busy or unclear; no start")
        from fan_pwm import FanPWM
        from adxl345 import connect, sensor_configuration
        with FanPWM(journal_path=journal) as fan:
            try:
                session["initial_readback"] = fan.verify(0)
                check(confirmed_zero(session["initial_readback"]), "Initial zero unconfirmed")
                with connect(odr_hz=200, range_g=2, fifo=True) as bus:
                    cfg = sensor_configuration(bus)
                    check(all(cfg.get(k) == v for k, v in protocol["sensor"].items()), "Sensor configuration differs")
                    session["sensor"] = cfg
                    session["status"] = "additional_off_wait"
                    persist(path, session)
                    emit("off_wait", phase=args.phase, additional_seconds=60, pwm_percent=0,
                         remaining_s=max(0,(release["accepted_monotonic_ns"]+60_000_000_000-time.monotonic_ns())/1e9))
                    session["off_timer_target_monotonic_ns"] = wait_off_until(release["accepted_monotonic_ns"])
                    session["precommand_zero_readback"] = fan.verify(0)
                    check(confirmed_zero(session["precommand_zero_readback"]), "Precommand zero unconfirmed")
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
                    csv_path = Path(protocol["data_directory"]) / f"{args.phase}_75pwm_300s_{stamp}.csv"
                    check(not csv_path.exists() and not csv_path.with_suffix(".json").exists(), "Capture path collision")
                    session["csv"] = str(csv_path)
                    persist(path, session)
                    metadata = {"purpose": "test", "split": "independent_test", "phase": args.phase,
                        "condition_label": conditions(args.phase)[0], "protocol_id": protocol["protocol_id"],
                        "plate_geometry": release.get("plate_geometry"),
                        "protocol_sha256": protocol["_sha256"], "frozen_bundle_sha256": protocol["frozen_bundle"]["sha256"],
                        "mounting_id": protocol["mounting_id"], "mounting": protocol["mounting"],
                        "user_release": release, "fan_pwm_setpoint_percent": 75, "fan_pwm_frequency_hz": 25000,
                        "fan_control_journal": str(journal), "detection_controls_fan": False,
                        "rpm_measured": None, "rpm_method": None, "sensor_settings_changed": False,
                        "primary_comparison_interval_s": [180,300], "primary_time_origin": "pwm_command_invocation",
                        "settling_time_validated": False, "old_measurements_pooled": False,
                        "no_plate_user_confirmed": release.get("plate_absent") is True,
                        "controlled_changed_condition_not_proven_defect": args.phase == "airflow_modified",
                        "running_observation_requested": False}
                    failure = execute_capture(fan, bus, session, csv_path, metadata)
            except BaseException as exc:
                failure = failure or exc
                session.update(status="error", error=f"{type(exc).__name__}: {exc}")
                if "final_readback" not in session:
                    shutdown = return_to_zero(fan, session)
                    failure = failure or shutdown
    except BaseException as exc:
        failure = failure or exc
        session.update(status="error", preflight_or_controller_error=f"{type(exc).__name__}: {exc}")
    finally:
        done.set()
        progress.join(timeout=1)
        if "command_invocation_monotonic_ns" in session:
            command = session["command_invocation_monotonic_ns"]
            session["additional_off_from_release_actual_s"] = (command-release["accepted_monotonic_ns"])/1e9
            off_reference = previous if previous else protocol.get("_first_previous_zero_reference")
            session["total_off_since_previous_zero_s"] = (command-off_reference["zero_command_completed_monotonic_ns"])/1e9 if off_reference else None
            session["previous_zero_reference"] = ({"phase": previous["phase"], "protocol_id": previous["protocol_id"]} if previous else protocol.get("_first_previous_zero_reference"))
            session["total_off_time_note"] = "Software zero-completion to start-command interval; exact mechanical stop, supply-disconnection, and cooling intervals unknown. Total off-time is unknown if no verified reference exists."
        session["finished_utc"] = utc()
        try:
            persist(path, session)
        except BaseException as journal_error:
            failure = failure or journal_error
            emit("session_persist_failed", error=str(journal_error), session_snapshot=session)
    emit("phase_finished", phase=args.phase, status=session["status"], session=str(path),
         next_action="No further start; wait for explicit next-run release" if args.phase != PHASES[-1] else "All scheduled starts attempted; no further start")
    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
