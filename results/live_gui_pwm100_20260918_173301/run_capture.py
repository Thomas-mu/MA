"""Bounded real-sensor GUI run at 100% PWM; capture the actual X11 window."""
import os
from pathlib import Path
import sys
import subprocess
import time
import json
import signal
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.update(DISPLAY=":99", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                  MKL_NUM_THREADS="1", MPLCONFIGDIR="/tmp/masterarbeit_matplotlib")

def utc():
    return datetime.now(timezone.utc).isoformat()

report = {"started_utc": utc(), "purpose": "User-requested real GUI test and screenshot at 100% PWM",
          "profile": "fan_25", "mode": "development", "sensor_odr_hz": 200,
          "profile_sampling_rate_hz": 500, "allow_sampling_mismatch": True,
          "calibrated_for_pwm100": False, "sensor_data_simulated": False,
          "virtual_display": True, "duration_target_s": 70, "screenshot_target_s": 65,
          "status": "starting"}

def save():
    (OUT / "session.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))

save()
server = None
app = None
root = None
try:
    if Path("/tmp/.X11-unix/X99").exists():
        raise RuntimeError("Display :99 already in use")
    server = subprocess.Popen(["/tmp/edge-ai-screenshot-xvfb/usr/bin/Xvfb", ":99",
                               "-screen", "0", "1200x960x24", "-nolisten", "tcp"],
                              stdout=(OUT / "xvfb.log").open("w"), stderr=subprocess.STDOUT)
    for _ in range(100):
        if server.poll() is not None:
            raise RuntimeError("Virtual display failed to start")
        if Path("/tmp/.X11-unix/X99").exists():
            break
        time.sleep(0.05)
    import matplotlib
    matplotlib.use("TkAgg")
    import tkinter as tk
    from PIL import ImageGrab
    from fan_pwm import FanPWM
    from live_tflite_gui import LiveTFLiteApplication, read_profile_display_metadata
    from live_tflite_monitor import resolve_live_configuration, validate_acquisition_options

    config = resolve_live_configuration("fan_25")
    metadata = read_profile_display_metadata(config)
    options = dict(sensor_odr=200, sensor_range=2, buffer_windows=4,
                   allow_sampling_mismatch=True, fan_pwm_setpoint=100,
                   measured_rpm=None, rpm_source=None)
    validate_acquisition_options(config, **options)
    root = tk.Tk()
    banner = tk.Label(root, text="LIVE-TEST | Luefter-PWM 100 % | echte ADXL345-Sensordaten",
                      font=("Helvetica", 16, "bold"), bg="#16324f", fg="white", pady=9)
    banner.pack(fill="x")
    tk.Label(root, text="Entwicklungstest: Altprofil fan_25 (500 Hz), Sensor-ODR 200 Hz | keine 100-%-Kalibrierung",
             font=("Helvetica", 11), bg="#fff1cb", fg="#493600", pady=6).pack(fill="x")
    app = LiveTFLiteApplication(root, config, metadata, threshold_source="PROFILE / P99",
                                self_test=False, self_test_duration=None,
                                acquisition_configuration=options)
    root.geometry("1200x960+0+0")
    root.update_idletasks()
    # Confirm screenshot capability before changing the fan.
    probe = ImageGrab.grab(xdisplay=":99")
    if probe.size != (1200, 960):
        raise RuntimeError(f"Unexpected display size: {probe.size}")

    with FanPWM(journal_path=OUT / "fan.jsonl") as fan:
        before = fan.read_state()
        report["pwm_before"] = before
        previous = before["pwm_configuration"]["configured_duty_percent"]
        if before["pwm_configuration"]["enable"] != 1:
            raise RuntimeError("Expected previously enabled PWM")
        try:
            report["pwm_100_readback"] = fan.set_percent(100)
            report["pwm_100_started_utc"] = utc()
            start = time.monotonic()
            report["status"] = "running"
            save()
            print("Real sensor GUI running at verified 100% PWM; screenshot at 65 s, stop at 70 s.", flush=True)

            def capture():
                try:
                    report["pwm_at_screenshot"] = fan.verify(100)
                    report["screenshot_utc"] = utc()
                    report["screenshot_elapsed_s"] = time.monotonic() - start
                    report["display_values"] = {
                        "status": app.status_text.get(), "mse": app.mse_text.get(),
                        "threshold": app.threshold_text.get(), "window": app.window_text.get(),
                        "sampling": app.sampling_text.get(), "inference": app.inference_text.get(),
                        "decision": app.decision_text.get(), "latency": app.latency_text.get(),
                        "worker": app.worker_status_text.get()}
                    banner.config(text="LIVE-TEST | Luefter-PWM 100 % (Ruecklesung bestaetigt) | "
                                       + datetime.now().astimezone().strftime("%d.%m.%Y %H:%M:%S"))
                    root.update_idletasks()
                    ImageGrab.grab(xdisplay=":99").save(OUT / "screenshot_pwm100.png")
                    report["screenshot"] = str(OUT / "screenshot_pwm100.png")
                    save()
                    print(json.dumps(report["display_values"], ensure_ascii=False), flush=True)
                except Exception as exc:
                    report["capture_error"] = repr(exc)
                    save()
                    app.close_application()

            def shutdown(*_):
                app.close_application()

            signal.signal(signal.SIGTERM, shutdown)
            signal.signal(signal.SIGINT, shutdown)
            root.after(65000, capture)
            root.after(70000, app.close_application)
            root.mainloop()
            report["pwm100_elapsed_s"] = time.monotonic() - start
            report["log_path"] = str(app.log_path) if app.log_path else None
            report["status"] = "completed" if report.get("screenshot") and app.window_indices else "error"
        finally:
            if app.worker is not None and app.worker.is_alive():
                app.stop_event.set()
                app.worker.join(timeout=15)
            report["pwm_restored"] = fan.set_percent(previous)
            report["pwm_restored_utc"] = utc()
            print(f"Restored verified PWM {previous:g}%.", flush=True)
except BaseException as exc:
    report.update(status="error", error=f"{type(exc).__name__}: {exc}")
    raise
finally:
    if server is not None:
        server.terminate()
        server.wait(timeout=5)
    report["finished_utc"] = utc()
    save()
    print(json.dumps({k: report.get(k) for k in ("status", "screenshot", "log_path", "error")}, ensure_ascii=False), flush=True)
