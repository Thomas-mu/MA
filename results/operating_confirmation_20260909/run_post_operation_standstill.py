"""One announced 30-s S1 pilot, only after a fresh visual standstill confirmation.

No PWM writes. Stop all analysis/rendering jobs before invocation. The confirmation
file must quote an actually received user answer after the latest shutdown.
This script has been prepared, not run; it is not a standstill measurement.
"""
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from adxl345 import connect
from collect_real_data import record
from fan_pwm import FanPWM


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirmation", type=Path, required=True)
    args = parser.parse_args()
    confirmation = json.loads(args.confirmation.read_text())
    if (confirmation.get("fan_observed_fully_stopped") is not True
            or confirmation.get("mounting_unchanged") is not True
            or not confirmation.get("operator_answer")
            or not confirmation.get("received_utc")):
        raise ValueError("A fresh, positive user observation and unchanged mount are required.")
    received = datetime.fromisoformat(confirmation["received_utc"])
    latest_stop = datetime.fromisoformat("2026-09-09T20:32:40.281593+00:00")
    if received <= latest_stop:
        raise ValueError("Confirmation predates the latest shutdown.")
    for executable in ("soffice.bin", "libreoffice"):
        check = subprocess.run(["pgrep", "-x", executable], capture_output=True, text=True, timeout=5)
        if check.returncode != 1:
            raise RuntimeError("Document renderer active or process check failed.")
    holders = subprocess.run(["fuser", "/dev/i2c-1", "/dev/gpiochip0", "/dev/gpiomem0"],
                             capture_output=True, text=True, timeout=5)
    if holders.returncode != 1 or holders.stdout.strip() or holders.stderr.strip():
        raise RuntimeError("Device holder or unclear device preflight.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = ROOT / f"data/controlled_20260909/standstill_post_operation_{stamp}.csv"
    out = ROOT / "results/operating_confirmation_20260909"
    journal = out / f"standstill_post_operation_{stamp}_fan.jsonl"
    session = out / f"standstill_post_operation_{stamp}_session.json"
    report = {"phase": "post_operation_controlled_standstill_pilot",
              "requested_utc": datetime.now(timezone.utc).isoformat(),
              "csv": str(path.relative_to(ROOT)), "fan_journal": str(journal.relative_to(ROOT)),
              "operator_confirmation": confirmation, "status": "preflight", "pwm_write_requested": False}

    def interrupt(*_):
        raise KeyboardInterrupt("Recording interrupted")

    signal.signal(signal.SIGTERM, interrupt)
    try:
        with FanPWM(journal_path=journal) as fan:
            report["fan_before_capture"] = fan.verify(0)
            with connect(odr_hz=200, range_g=2, fifo=True) as bus:
                metadata = {
                    "purpose": "pilot",
                    "mounting": "ADXL345 with intended I2C wiring attached to a corner of ARCTIC P12 Pro PST frame; fan control GPIO18",
                    "mounting_id": "fan_frame_corner_adxl345_gpio18_v1",
                    "hardware_confirmation_source": "results/hardware_confirmation_20260909/user_confirmation_and_backup.json",
                    "fan_pwm_setpoint_percent": 0.0,
                    "fan_pwm_source": "agent_hardware_pwm_held_at_verified_zero_percent_no_write_during_session",
                    "fan_control_journal": report["fan_journal"],
                    "rpm_measured": None, "rpm_method": None, "rpm_source": "not_measured",
                    "physical_state_source": "new_operator_visual_standstill_confirmation_after_operating_repeat_shutdown",
                    "operator_confirmation": confirmation, "detection_controls_fan": False,
                    "reference_role": "post_operation_background_repeat_not_normal_training",
                }
                print(json.dumps({"event": "capture_start", "utc": datetime.now(timezone.utc).isoformat(),
                                  "seconds": 30, "pwm_percent": 0, "csv": report["csv"]}), flush=True)
                data = record(bus, 30, 200, output_path=path, label=-1,
                              state="controlled_standstill_post_operation", metadata=metadata)
                report["capture_report"] = data.attrs["report"]
            report["fan_after_capture"] = fan.verify(0)
            report["status"] = report["capture_report"]["status"]
    except BaseException as exc:
        report.update(status="error", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        with session.open("x") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
    print(json.dumps({"session": str(session.relative_to(ROOT)), "status": report["status"],
                      "summary": report["capture_report"]["summary"]}), flush=True)


if __name__ == "__main__":
    main()
