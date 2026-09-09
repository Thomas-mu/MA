import argparse
import math
import csv
import hashlib
import json
import os
import signal
import threading
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys
import time
from collections import deque

import matplotlib

matplotlib.use("TkAgg")

import matplotlib.animation as animation
import matplotlib.pyplot as plt

try:
    from rpi_hardware_pwm import HardwarePWM
except ImportError:  # pragma: no cover - nur für Desktop/Testumgebungen
    HardwarePWM = None

try:
    import RPi.GPIO as GPIO
except ImportError:  # pragma: no cover - nur für Desktop/Testumgebungen
    GPIO = None

try:
    from adxl345 import connect, read_fresh_sample, sensor_configuration, reset_fifo
    from live_pipeline import BufferedAcquisition, Sample, is_stale
except ModuleNotFoundError:
    from src.adxl345 import connect, read_fresh_sample, sensor_configuration, reset_fifo
    from src.live_pipeline import BufferedAcquisition, Sample, is_stale


SAMPLE_RATE_HZ = 200
ROLLING_WINDOW_SECONDS = 5
MAX_SAMPLES = ROLLING_WINDOW_SECONDS * SAMPLE_RATE_HZ

FRAME_INTERVAL_MS = 30

# Ruhewert eines liegenden Sensors liegt nahe 1g. Deutliche
# Abweichungen davon werden farblich als Anomalie hervorgehoben.
ANOMALY_THRESHOLD_G = 1.15
FAN_STOP_THRESHOLD_G = 1.7
FAN_RESTART_THRESHOLD_G = 1.0
FAN_RESTART_DELAY_S = 5.0
FAN_PIN = 18
FAN_PWM_CHIP = 0
FAN_PWM_CHANNEL = 2
FAN_PWM_FREQUENCY_HZ = 25000
FAN_STOP_PERCENT = 0
FAN_RUN_PERCENT = 100
FAN_DEFAULT_PWM_PERCENT = 20
FAN_ALLOW_RESTART_AFTER_ERROR = False


def fan_pwm_percent(value: str) -> float:
    """Validiert einen PWM-Duty-Cycle für die Kommandozeile."""

    percent = float(value)
    if not 0 <= percent <= 100:
        raise argparse.ArgumentTypeError(
            "--fan-pwm muss zwischen 0 und 100 Prozent liegen."
        )
    return percent


class FanController:
    """Steuert den Lüfter basierend auf der aktuellen Sensoramplitude."""

    def __init__(
        self,
        pin: int,
        default_on: bool = True,
        run_percent: float = FAN_RUN_PERCENT,
        allow_shutdown: bool = False,
    ) -> None:
        self.pin = pin
        self.default_on = default_on
        self.run_percent = run_percent
        self.allow_shutdown = allow_shutdown
        self.enabled = False
        self.is_running = default_on
        self.fan_off_since: float | None = None
        self.restart_allowed = FAN_ALLOW_RESTART_AFTER_ERROR
        self.restart_decision_prompted = False
        self.pwm = None

        # Digitales HIGH ist nur für den bisherigen 100-%-Betrieb geeignet.
        # Zwischenwerte müssen über Hardware-PWM erzeugt werden.
        if (
            self.run_percent == FAN_RUN_PERCENT
            and shutil.which("pinctrl") is not None
        ):
            self.enabled = True
            self.set_state(default_on)
            print(
                f"Lüftersteuerung via pinctrl aktiv (Pin {self.pin})."
            )
            return

        if HardwarePWM is not None:
            try:
                self.pwm = HardwarePWM(
                    pwm_channel=FAN_PWM_CHANNEL,
                    hz=FAN_PWM_FREQUENCY_HZ,
                    chip=FAN_PWM_CHIP,
                )
                self.pwm.start(
                    self.run_percent if default_on else FAN_STOP_PERCENT
                )
                self.enabled = True
                print(f"Lüftersteuerung: GPIO{self.pin}")
                print(f"PWM: {FAN_PWM_FREQUENCY_HZ / 1000:g} kHz")
                print(f"Duty Cycle: {self.run_percent:g} %")
                print(
                    f"Hardware-PWM: PWM{FAN_PWM_CHIP}_CHAN{FAN_PWM_CHANNEL}"
                )
                return
            except Exception as exc:  # pragma: no cover - hardwareabhängig
                self.pwm = None
                print(
                    "HardwarePWM konnte nicht initialisiert werden: "
                    f"{exc}."
                )

        if self.run_percent != FAN_RUN_PERCENT:
            self.is_running = False
            print(
                f"{self.run_percent:g} % können nicht als digitales GPIO-Signal "
                "ausgegeben werden. Lüfter-Steuerung deaktiviert."
            )
            return

        self.enabled = GPIO is not None
        if not self.enabled:
            print("GPIO nicht verfügbar. Lüfter-Steuerung deaktiviert.")
            return

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT)
            self.set_state(default_on)
        except RuntimeError as exc:
            self.enabled = False
            print(
                "GPIO-Initialisierung fehlgeschlagen: "
                f"{exc}. Lüfter-Steuerung deaktiviert."
            )
            return

    def prompt_restart_decision(self) -> None:
        self.restart_decision_prompted = True

        if not sys.stdin.isatty():
            self.restart_decision_prompted = False
            return

        try:
            answer = input(
                "Lüfter aus. Wieder starten? [J/n]: "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"

        if answer in {"j", "ja", "y", "yes", "1", "true"}:
            self.set_state(True)
            self.fan_off_since = None
            self.restart_allowed = True
        else:
            self.set_state(False)
            self.restart_allowed = False

        self.restart_decision_prompted = False

    def set_state(self, state: bool) -> None:
        if not self.enabled:
            return

        if self.pwm is not None:
            duty_cycle = self.run_percent if state else FAN_STOP_PERCENT
            self.pwm.change_duty_cycle(duty_cycle)
            self.is_running = state
            return

        if shutil.which("pinctrl") is not None:
            command = [
                "pinctrl",
                "set",
                str(self.pin),
                "op",
                "dh" if state else "dl",
            ]
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
                self.is_running = state
                return
            except Exception as exc:  # pragma: no cover - hardwareabhängig
                print(
                    f"pinctrl-Befehl fehlgeschlagen: {command} -> {exc}. "
                    "Fallback auf GPIO/PWM."
                )

        self.is_running = state

        try:
            GPIO.output(self.pin, GPIO.HIGH if state else GPIO.LOW)
        except RuntimeError as exc:
            self.enabled = False
            print(
                "GPIO-Ausgabe fehlgeschlagen: "
                f"{exc}. Lüfter-Steuerung deaktiviert."
            )
            self.is_running = False

    def update(self, magnitude_g: float) -> bool:
        """Gibt True zurück, wenn der Lüfter gerade aktiv ist."""

        if not self.enabled:
            return self.is_running

        if not self.allow_shutdown or not math.isfinite(magnitude_g):
            return self.is_running

        if magnitude_g >= FAN_STOP_THRESHOLD_G:
            if self.is_running:
                self.set_state(False)
                self.fan_off_since = time.monotonic()
                self.restart_decision_prompted = False
                print("Entwicklungs-Abschaltung: Lüfter bleibt aus; Neustart erfordert einen neuen expliziten Lauf.")
            return False

        # Automatischer Neustart ist hier deaktiviert. Der Nutzer muss
        # die Fehlersituation manuell bestätigen, damit der Lüfter wieder
        # auf den eingestellten Duty Cycle gesetzt wird.
        return self.is_running

    def close(self) -> None:
        if not self.enabled:
            return

        if self.pwm is not None:
            try:
                self.pwm.change_duty_cycle(FAN_STOP_PERCENT)
            finally:
                self.pwm.stop()
            self.is_running = False
            return

        try:
            self.set_state(False)
            if GPIO is not None:
                GPIO.cleanup(self.pin)
        except RuntimeError as exc:
            print(f"GPIO-Reset fehlgeschlagen: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ADXL345 Live-Monitor")
    parser.add_argument(
        "--fan-pwm",
        type=fan_pwm_percent,
        default=FAN_DEFAULT_PWM_PERCENT,
        metavar="PROZENT",
        help=(
            "PWM-Duty-Cycle des Lüfters auf GPIO18 "
            f"(Standard: {FAN_DEFAULT_PWM_PERCENT} Prozent)."
        ),
    )
    parser.add_argument("--sensor-odr", type=float, default=200)
    parser.add_argument("--sensor-range", type=int, choices=(2, 4, 8, 16), default=2)
    parser.add_argument("--no-fan-control", action="store_true", help="Nur Sensoranzeige, keine PWM/GPIO-Aktion.")
    parser.add_argument("--enable-development-shutdown", action="store_true", help="Amplitudenabhängige Abschaltung als Entwicklungsdemo aktivieren; nicht für Methodenvergleich.")
    parser.add_argument("--measured-rpm", type=float, default=None)
    parser.add_argument("--rpm-source", default=None)
    args = parser.parse_args()
    if args.measured_rpm is not None and (not math.isfinite(args.measured_rpm) or args.measured_rpm < 0 or not args.rpm_source):
        parser.error("--measured-rpm benötigt endlichen nichtnegativen Wert und --rpm-source")
    return args


def main() -> None:
    arguments = parse_args()
    project = Path(__file__).resolve().parents[1]
    directory = project / "results" / "live_runs"
    directory.mkdir(parents=True, exist_ok=True)
    stem = directory / ("amplitude_gui_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    stop = threading.Event()
    bus = connect(odr_hz=arguments.sensor_odr, range_g=arguments.sensor_range, fifo=True)
    fan_controller = None
    acquisition = None
    events = None
    manifest = {"mode": "development_amplitude_display_not_RMS_method", "configuration": vars(arguments),
                "sensor": sensor_configuration(bus), "started_utc": datetime.now().astimezone().isoformat(),
                "fan_pwm_setpoint_percent": None if arguments.no_fan_control else arguments.fan_pwm,
                "measured_rpm": arguments.measured_rpm, "rpm_source": arguments.rpm_source,
                "threshold_note": "Momentaner Beschleunigungsbetrag, kein RMS-Fensterverfahren",
                "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "final_p99_comparison_eligible": False}
    try:
        events = stem.with_suffix(".fan.jsonl").open("x", encoding="utf-8", buffering=1)
        if not arguments.no_fan_control:
            fan_controller = FanController(FAN_PIN, default_on=True, run_percent=arguments.fan_pwm,
                                           allow_shutdown=arguments.enable_development_shutdown)
            events.write(json.dumps({"event": "initial_pwm_command", "percent": arguments.fan_pwm,
                                     "enabled": fan_controller.enabled, "timestamp": datetime.now().astimezone().isoformat()}) + "\n")
        def read(stop_event: threading.Event) -> Sample | None:
            sample = read_fresh_sample(bus, stop_event=stop_event)
            if sample is None:
                return None
            return Sample(sample.xyz_g, sample.monotonic_ns, time.time_ns(), sample.gap,
                          sample.overrun, sample.saturated,
                          {"fifo_depth": sample.fifo_depth, "sample_index": sample.sample_index,
                           "sensor_time_estimate_s": sample.sensor_time_estimate_s})
        reset_fifo(bus)
        acquisition = BufferedAcquisition(read, stem.with_suffix(".raw.csv"), window_size=16, capacity=8,
                                          stop_event=stop).start()
        timestamps: deque[float] = deque(maxlen=int(5 * arguments.sensor_odr))
        magnitudes: deque[float] = deque(maxlen=int(5 * arguments.sensor_odr))
        start_ns = time.monotonic_ns()
        last_ns = None
        last_valid = False
        figure, axis = plt.subplots(figsize=(12, 5))
        figure.canvas.manager.set_window_title("Masterarbeit – Entwicklungsanzeige")
        (line,) = axis.plot([], [], linewidth=0.8)
        axis.axhline(ANOMALY_THRESHOLD_G, color="tab:red", linestyle="--", label="Entwicklungs-Amplitudenschwelle")
        if arguments.enable_development_shutdown:
            axis.axhline(FAN_STOP_THRESHOLD_G, color="tab:orange", linestyle=":", label="Entwicklungs-Abschaltung")
        axis.set(xlabel="Host-Empfangszeit in Sekunden", ylabel="Beschleunigungsbetrag in g",
                 title="ADXL345 – Amplitudenanzeige (kein RMS-Methodenvergleich)", ylim=(0, 3))
        axis.legend(loc="upper right")
        axis.grid(alpha=0.25)
        status_text = axis.text(0.01, 0.95, "STARTING", transform=axis.transAxes, va="top")
        def update(_frame: int):
            nonlocal last_ns, last_valid
            if stop.is_set():
                plt.close(figure)
                return line, status_text
            while True:
                window = acquisition.get(timeout=0)
                if window is None:
                    break
                last_ns = window.complete_ns
                last_valid = not (window.gap_count or window.overrun_count or window.saturated_count)
                for index, xyz in enumerate(window.values):
                    # Plotposition nur interpoliert zwischen Host-Empfangszeitpunkten; Roh-CSV enthält exakte Zeiten.
                    fraction = index / (len(window.values) - 1)
                    timestamps.append((window.first_sample_ns + fraction * (window.complete_ns - window.first_sample_ns) - start_ns) / 1e9)
                    magnitudes.append(math.sqrt(float(sum(value * value for value in xyz))))
            if acquisition.done.is_set() and acquisition.error is not None:
                status_text.set_text(f"ERROR: {acquisition.error}")
                status_text.set_color("tab:red")
                return line, status_text
            if not timestamps or is_stale(last_ns):
                status_text.set_text("STALE / KEINE AKTUELLEN MESSWERTE")
                status_text.set_color("tab:gray")
                return line, status_text
            latest = magnitudes[-1]
            valid = last_valid and math.isfinite(latest)
            fan_running = fan_controller.is_running if fan_controller else None
            if fan_controller and valid:
                before = fan_controller.is_running
                fan_running = fan_controller.update(latest)
                if before != fan_controller.is_running:
                    events.write(json.dumps({"event": "development_amplitude_fan_action", "running": fan_controller.is_running,
                                             "timestamp": datetime.now().astimezone().isoformat(), "magnitude_g": latest}) + "\n")
            state = "ERROR" if not valid else ("AMPLITUDE HIGH" if latest > ANOMALY_THRESHOLD_G else "AMPLITUDE LOW")
            line.set_data(timestamps, magnitudes)
            line.set_color("tab:red" if not valid or latest > ANOMALY_THRESHOLD_G else "tab:blue")
            status_text.set_text(f"{latest:.3f} g | {state} | PWM-Vorgabe {manifest['fan_pwm_setpoint_percent']} % | "
                                 f"RPM {arguments.measured_rpm if arguments.measured_rpm is not None else 'nicht gemessen'} | "
                                 f"GUI-Fenster verworfen {acquisition.stats['windows_dropped']}")
            axis.set_xlim(max(0, timestamps[-1] - 5), max(5, timestamps[-1]))
            return line, status_text
        anim = animation.FuncAnimation(figure, update, interval=FRAME_INTERVAL_MS, blit=False, cache_frame_data=False)
        previous = {signum: signal.signal(signum, lambda signum, frame: stop.set()) for signum in (signal.SIGINT, signal.SIGTERM)}
        try:
            plt.tight_layout()
            plt.show()
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
    finally:
        if acquisition is not None:
            acquisition.stop()
            manifest["acquisition"] = acquisition.snapshot()
        if fan_controller is not None:
            fan_controller.close()
            if events is not None:
                events.write(json.dumps({"event": "fan_stop_on_exit", "timestamp": datetime.now().astimezone().isoformat()}) + "\n")
        bus.close()
        if events is not None:
            events.flush()
            os.fsync(events.fileno())
            events.close()
        manifest["ended_utc"] = datetime.now().astimezone().isoformat()
        stem.with_suffix(".run.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
