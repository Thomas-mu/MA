import math
import sys
import time
from collections import deque

import matplotlib

matplotlib.use("TkAgg")

import matplotlib.animation as animation
import matplotlib.pyplot as plt

try:
    import RPi.GPIO as GPIO
except ImportError:  # pragma: no cover - nur für Desktop/Testumgebungen
    GPIO = None

from adxl345 import connect, read_acceleration_g


SAMPLE_RATE_HZ = 500
ROLLING_WINDOW_SECONDS = 5
MAX_SAMPLES = ROLLING_WINDOW_SECONDS * SAMPLE_RATE_HZ

FRAME_INTERVAL_MS = 30

# Ruhewert eines liegenden Sensors liegt nahe 1g. Deutliche
# Abweichungen davon werden farblich als Anomalie hervorgehoben.
ANOMALY_THRESHOLD_G = 1.15
FAN_STOP_THRESHOLD_G = 2.0
FAN_RESTART_THRESHOLD_G = 1.0
FAN_RESTART_DELAY_S = 5.0
FAN_PIN = 18
FAN_ALLOW_RESTART_AFTER_ERROR = False


class FanController:
    """Steuert den Lüfter basierend auf der aktuellen Sensoramplitude."""

    def __init__(self, pin: int, default_on: bool = True) -> None:
        self.pin = pin
        self.default_on = default_on
        self.enabled = GPIO is not None
        self.is_running = default_on
        self.fan_off_since: float | None = None
        self.restart_allowed = FAN_ALLOW_RESTART_AFTER_ERROR
        self.restart_decision_prompted = False

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
        if self.restart_decision_prompted:
            return

        self.restart_decision_prompted = True

        if not sys.stdin.isatty():
            print(
                "Interaktive Bestätigung nicht verfügbar; "
                "Lüfter bleibt aus, bis der Fehler manuell bestätigt wurde."
            )
            return

        try:
            answer = input(
                "Fehler erkannt. Ist der Fehler behoben und soll der "
                "Lüfter wieder starten? [J/n]: "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"

        if answer in {"j", "ja", "y", "yes", "1", "true"}:
            self.set_state(True)
            self.fan_off_since = None
            print("Fehler bestätigt: Lüfter wieder AN")
            self.restart_allowed = True
        else:
            self.set_state(False)
            print("Fehler noch nicht bestätigt: Lüfter bleibt AUS")
            self.restart_allowed = False

    def set_state(self, state: bool) -> None:
        if not self.enabled:
            return

        try:
            self.is_running = state
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

        if magnitude_g >= FAN_STOP_THRESHOLD_G:
            if self.is_running:
                self.set_state(False)
                self.fan_off_since = time.monotonic()
                print(
                    f"ANOMALIE erkannt: {magnitude_g:.3f} g -> Lüfter AUS"
                )
                self.prompt_restart_decision()
            return False

        # Automatischer Neustart ist hier deaktiviert. Der Nutzer muss
        # die Fehlersituation manuell bestätigen, damit der Lüfter wieder
        # auf HIGH / 1 gesetzt wird.
        return self.is_running

    def close(self) -> None:
        if not self.enabled:
            return

        try:
            self.set_state(False)
            GPIO.cleanup(self.pin)
        except RuntimeError as exc:
            print(f"GPIO-Reset fehlgeschlagen: {exc}")


def main() -> None:
    bus = connect()
    fan_controller = FanController(pin=FAN_PIN, default_on=True)

    timestamps: deque[float] = deque(maxlen=MAX_SAMPLES)
    magnitudes: deque[float] = deque(maxlen=MAX_SAMPLES)

    start_time = time.perf_counter()

    figure, axis = plt.subplots(figsize=(12, 5))
    if figure.canvas.manager is not None:
        figure.canvas.manager.set_window_title(
            "Masterarbeit FB 2 - UAS Frankfurt"
        )
    (line,) = axis.plot([], [], linewidth=0.8, color="tab:blue")

    axis.axhline(
        ANOMALY_THRESHOLD_G,
        color="tab:red",
        linestyle="--",
        linewidth=0.8,
        label=f"Anomalie-Schwelle ({ANOMALY_THRESHOLD_G} g)",
    )
    axis.axhline(
        FAN_STOP_THRESHOLD_G,
        color="tab:orange",
        linestyle=":",
        linewidth=0.8,
        label=f"Lüfter-Aus ({FAN_STOP_THRESHOLD_G} g)",
    )
    axis.set_xlabel("Zeit in Sekunden")
    axis.set_ylabel("Betrag der Beschleunigung in g")
    axis.set_title("ADXL345 Live-Monitor mit Lüfter-Stop")
    axis.set_ylim(0, 3)
    axis.legend(loc="upper right")
    axis.grid(alpha=0.25)

    status_text = axis.text(
        0.01,
        0.95,
        "",
        transform=axis.transAxes,
        fontsize=11,
        va="top",
        fontfamily="monospace",
    )

    def update(_frame: int):
        deadline = time.perf_counter() + FRAME_INTERVAL_MS / 1000

        while time.perf_counter() < deadline:
            x_g, y_g, z_g = read_acceleration_g(bus)
            magnitude_g = math.sqrt(x_g**2 + y_g**2 + z_g**2)

            timestamps.append(time.perf_counter() - start_time)
            magnitudes.append(magnitude_g)

        if not timestamps:
            return line, status_text

        line.set_data(timestamps, magnitudes)

        latest = magnitudes[-1]
        fan_running = fan_controller.update(latest)
        is_anomaly = latest > ANOMALY_THRESHOLD_G
        line.set_color("tab:red" if is_anomaly else "tab:blue")

        status_text.set_text(
            f"aktuell: {latest:.3f} g   "
            f"{'ANOMALIE' if is_anomaly else 'normal'}   "
            f"Lüfter: {'AN' if fan_running else 'AUS'}"
        )
        status_text.set_color("tab:red" if is_anomaly else "tab:green")

        axis.set_xlim(
            max(0, timestamps[-1] - ROLLING_WINDOW_SECONDS),
            max(ROLLING_WINDOW_SECONDS, timestamps[-1]),
        )

        return line, status_text

    anim = animation.FuncAnimation(
        figure,
        update,
        interval=FRAME_INTERVAL_MS,
        blit=False,
        cache_frame_data=False,
    )

    try:
        plt.tight_layout()
        plt.show()
    finally:
        fan_controller.close()
        bus.close()


if __name__ == "__main__":
    main()
