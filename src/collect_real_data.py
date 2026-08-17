import argparse
import math
import time
from pathlib import Path

import pandas as pd

from adxl345 import connect, read_acceleration_g


SAMPLE_RATE_HZ = 500
OUTPUT_DIRECTORY = Path("data/real")


def record(bus, duration_seconds: float, sample_rate_hz: int) -> pd.DataFrame:
    """Nimmt für duration_seconds Sekunden Beschleunigungsdaten auf."""

    period_s = 1 / sample_rate_hz
    rows: list[dict[str, float]] = []

    start_time = time.perf_counter()
    next_sample_time = start_time

    while True:
        now = time.perf_counter()
        elapsed = now - start_time

        if elapsed >= duration_seconds:
            break

        x_g, y_g, z_g = read_acceleration_g(bus)
        magnitude_g = math.sqrt(x_g**2 + y_g**2 + z_g**2)

        rows.append(
            {
                "timestamp_s": elapsed,
                "signal": magnitude_g,
                "x_g": x_g,
                "y_g": y_g,
                "z_g": z_g,
            }
        )

        next_sample_time += period_s
        sleep_time = next_sample_time - time.perf_counter()

        if sleep_time > 0:
            time.sleep(sleep_time)

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Nimmt echte Beschleunigungsdaten vom ADXL345 auf und "
            "speichert sie im selben Format wie simulate_data.py."
        )
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=60.0,
        help="Aufnahmedauer in Sekunden (Standard: 60)",
    )
    parser.add_argument(
        "--label",
        choices=["normal", "anomaly"],
        default="normal",
        help="Ob diese Aufnahme als normal oder anomal gilt",
    )
    parser.add_argument(
        "--anomaly-type",
        default="unknown",
        help="Beschreibung der Anomalie, z.B. 'tapping' oder 'shaking'",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Zielpfad der CSV-Datei (Standard: data/real/<label>_<timestamp>.csv)",
    )
    args = parser.parse_args()

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    if args.output is not None:
        output_path = args.output
    else:
        run_id = time.strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIRECTORY / f"{args.label}_{run_id}.csv"

    bus = connect()

    print("Aufnahme startet in:", flush=True)
    for remaining in (3, 2, 1):
        print(f"  {remaining} ...", flush=True)
        time.sleep(1)
    print(f"LOS! Aufnahme läuft für {args.seconds:.0f} s ...", flush=True)

    try:
        dataframe = record(
            bus=bus,
            duration_seconds=args.seconds,
            sample_rate_hz=SAMPLE_RATE_HZ,
        )
    finally:
        bus.close()

    dataframe["label"] = 1 if args.label == "anomaly" else 0
    dataframe["anomaly_type"] = (
        args.anomaly_type if args.label == "anomaly" else "normal"
    )
    dataframe["source"] = "real"

    dataframe.to_csv(output_path, index=False)

    actual_rate_hz = len(dataframe) / dataframe["timestamp_s"].iloc[-1]

    print("Aufnahme abgeschlossen.")
    print(f"Datei: {output_path}")
    print(f"Messwerte: {len(dataframe)}")
    print(f"Tatsächliche Abtastrate: {actual_rate_hz:.1f} Hz")


if __name__ == "__main__":
    main()
