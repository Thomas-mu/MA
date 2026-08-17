from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kurtosis


INPUT_FILE = Path("data/simulated/simulated_vibration.csv")
OUTPUT_DIRECTORY = Path("data/processed")

SAMPLE_RATE_HZ = 500

# 500 Messwerte entsprechen bei 500 Hz genau einer Sekunde.
WINDOW_SIZE = 500

# Zunächst keine Überlappung, damit Trainings- und Testfenster
# klar voneinander getrennt bleiben.
WINDOW_STEP = 500

RANDOM_SEED = 42


def calculate_features(
    signal_window: np.ndarray,
    sample_rate_hz: int,
) -> dict[str, float]:
    """Berechnet statistische und frequenzbasierte Merkmale."""

    centered_signal = signal_window - np.mean(signal_window)

    rms = np.sqrt(np.mean(np.square(signal_window)))
    peak_to_peak = np.max(signal_window) - np.min(signal_window)

    # Frequenzanalyse
    spectrum = np.abs(np.fft.rfft(centered_signal))
    frequencies = np.fft.rfftfreq(
        len(centered_signal),
        d=1 / sample_rate_hz,
    )

    # Der Gleichanteil bei 0 Hz wird nicht als dominante Frequenz verwendet.
    if len(spectrum) > 1:
        dominant_index = np.argmax(spectrum[1:]) + 1
        dominant_frequency_hz = frequencies[dominant_index]
    else:
        dominant_frequency_hz = 0.0

    spectral_energy = np.sum(np.square(spectrum)) / len(spectrum)

    kurtosis_value = kurtosis(
        signal_window,
        fisher=True,
        bias=False,
    )

    if not np.isfinite(kurtosis_value):
        kurtosis_value = 0.0

    return {
        "mean": float(np.mean(signal_window)),
        "standard_deviation": float(np.std(signal_window)),
        "rms": float(rms),
        "minimum": float(np.min(signal_window)),
        "maximum": float(np.max(signal_window)),
        "peak_to_peak": float(peak_to_peak),
        "median": float(np.median(signal_window)),
        "kurtosis": float(kurtosis_value),
        "dominant_frequency_hz": float(dominant_frequency_hz),
        "spectral_energy": float(spectral_energy),
    }


def create_windows(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Teilt das Signal in Fenster und berechnet Merkmale."""

    required_columns = {
        "timestamp_s",
        "signal",
        "label",
        "anomaly_type",
    }

    missing_columns = required_columns.difference(dataframe.columns)

    if missing_columns:
        raise ValueError(
            f"Folgende Spalten fehlen in der Eingabedatei: "
            f"{sorted(missing_columns)}"
        )

    window_rows: list[dict[str, object]] = []

    window_id = 0

    for start_index in range(
        0,
        len(dataframe) - WINDOW_SIZE + 1,
        WINDOW_STEP,
    ):
        end_index = start_index + WINDOW_SIZE
        window = dataframe.iloc[start_index:end_index]

        signal_window = window["signal"].to_numpy(dtype=np.float64)
        label_window = window["label"].to_numpy(dtype=np.int8)

        # Ein Fenster gilt als Anomalie, sobald mindestens
        # ein Messwert als Anomalie gekennzeichnet ist.
        window_label = int(np.any(label_window == 1))

        if window_label == 1:
            anomaly_values = (
                window.loc[
                    window["label"] == 1,
                    "anomaly_type",
                ]
                .dropna()
                .unique()
            )

            anomaly_type = "|".join(
                sorted(str(value) for value in anomaly_values)
            )
        else:
            anomaly_type = "normal"

        features = calculate_features(
            signal_window=signal_window,
            sample_rate_hz=SAMPLE_RATE_HZ,
        )

        row: dict[str, object] = {
            "window_id": window_id,
            "window_start_s": float(window["timestamp_s"].iloc[0]),
            "window_end_s": float(window["timestamp_s"].iloc[-1]),
            "label": window_label,
            "anomaly_type": anomaly_type,
        }

        row.update(features)
        window_rows.append(row)

        window_id += 1

    return pd.DataFrame(window_rows)


def split_data(
    feature_dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Erstellt:
    - Training: nur Normaldaten
    - Validierung: nur Normaldaten
    - Test: Normaldaten und alle Anomalien
    """

    normal_windows = (
        feature_dataframe[feature_dataframe["label"] == 0]
        .sort_values("window_start_s")
        .reset_index(drop=True)
    )

    anomaly_windows = (
        feature_dataframe[feature_dataframe["label"] == 1]
        .sort_values("window_start_s")
        .reset_index(drop=True)
    )

    number_of_normal_windows = len(normal_windows)

    if number_of_normal_windows < 5:
        raise ValueError(
            "Es sind zu wenige normale Fenster für eine sinnvolle "
            "Aufteilung vorhanden."
        )

    train_end = int(number_of_normal_windows * 0.60)
    validation_end = int(number_of_normal_windows * 0.80)

    training_data = normal_windows.iloc[:train_end].copy()
    validation_data = normal_windows.iloc[
        train_end:validation_end
    ].copy()

    normal_test_data = normal_windows.iloc[validation_end:].copy()

    test_data = pd.concat(
        [
            normal_test_data,
            anomaly_windows,
        ],
        ignore_index=True,
    ).sort_values("window_start_s")

    test_data = test_data.reset_index(drop=True)

    return training_data, validation_data, test_data


def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Die Eingabedatei wurde nicht gefunden: {INPUT_FILE}\n"
            "Führe zuerst aus: python src/simulate_data.py"
        )

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    raw_dataframe = pd.read_csv(INPUT_FILE)

    feature_dataframe = create_windows(raw_dataframe)

    training_data, validation_data, test_data = split_data(
        feature_dataframe
    )

    all_features_path = (
        OUTPUT_DIRECTORY / "window_features_all.csv"
    )
    training_path = OUTPUT_DIRECTORY / "train_normal.csv"
    validation_path = OUTPUT_DIRECTORY / "validation_normal.csv"
    test_path = OUTPUT_DIRECTORY / "test.csv"

    feature_dataframe.to_csv(all_features_path, index=False)
    training_data.to_csv(training_path, index=False)
    validation_data.to_csv(validation_path, index=False)
    test_data.to_csv(test_path, index=False)

    print("Vorverarbeitung erfolgreich abgeschlossen.")
    print()
    print(f"Gesamte Zeitfenster: {len(feature_dataframe)}")
    print(
        "Normale Zeitfenster: "
        f"{(feature_dataframe['label'] == 0).sum()}"
    )
    print(
        "Anomaliefenster: "
        f"{(feature_dataframe['label'] == 1).sum()}"
    )
    print()
    print(f"Training, nur normal: {len(training_data)} Fenster")
    print(
        f"Validierung, nur normal: "
        f"{len(validation_data)} Fenster"
    )
    print(
        f"Test, normal und anomal: {len(test_data)} Fenster"
    )
    print()
    print("Erzeugte Dateien:")
    print(f"- {all_features_path}")
    print(f"- {training_path}")
    print(f"- {validation_path}")
    print(f"- {test_path}")


if __name__ == "__main__":
    main()
