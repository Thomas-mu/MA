import math
import time
from collections import deque

import matplotlib

matplotlib.use("TkAgg")

import matplotlib.animation as animation
import matplotlib.pyplot as plt

from adxl345 import connect, read_acceleration_g


SAMPLE_RATE_HZ = 500
ROLLING_WINDOW_SECONDS = 5
MAX_SAMPLES = ROLLING_WINDOW_SECONDS * SAMPLE_RATE_HZ

FRAME_INTERVAL_MS = 30

# Ruhewert eines liegenden Sensors liegt nahe 1g. Deutliche
# Abweichungen davon werden farblich als Anomalie hervorgehoben.
ANOMALY_THRESHOLD_G = 1.15


def main() -> None:
    bus = connect()

    timestamps: deque[float] = deque(maxlen=MAX_SAMPLES)
    magnitudes: deque[float] = deque(maxlen=MAX_SAMPLES)

    start_time = time.perf_counter()

    figure, axis = plt.subplots(figsize=(12, 5))
    (line,) = axis.plot([], [], linewidth=0.8, color="tab:blue")

    axis.axhline(
        ANOMALY_THRESHOLD_G,
        color="tab:red",
        linestyle="--",
        linewidth=0.8,
        label=f"Anomalie-Schwelle ({ANOMALY_THRESHOLD_G} g)",
    )
    axis.set_xlabel("Zeit in Sekunden")
    axis.set_ylabel("Betrag der Beschleunigung in g")
    axis.set_title("ADXL345 Live-Monitor")
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
        is_anomaly = latest > ANOMALY_THRESHOLD_G
        line.set_color("tab:red" if is_anomaly else "tab:blue")

        status_text.set_text(
            f"aktuell: {latest:.3f} g   "
            f"{'ANOMALIE' if is_anomaly else 'normal'}"
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
        bus.close()


if __name__ == "__main__":
    main()
