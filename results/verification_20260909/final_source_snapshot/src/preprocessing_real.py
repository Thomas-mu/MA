from pathlib import Path

import pandas as pd

from preprocessing import create_windows, split_data


INPUT_DIRECTORY = Path("data/real")
OUTPUT_DIRECTORY = Path("data/processed_real")


def process_recording(csv_path: Path, time_offset_s: float) -> pd.DataFrame:
    """Fenstert eine einzelne Aufnahme und verschiebt ihre Zeitachse.

    Jede Aufnahme beginnt bei timestamp_s = 0. Damit Fenster aus
    verschiedenen Aufnahmen beim Zusammenführen nicht dieselben
    Zeitstempel tragen, wird pro Aufnahme ein Offset addiert.
    """

    raw_dataframe = pd.read_csv(csv_path)

    feature_dataframe = create_windows(raw_dataframe)

    feature_dataframe["window_start_s"] += time_offset_s
    feature_dataframe["window_end_s"] += time_offset_s
    feature_dataframe["source_file"] = csv_path.name

    return feature_dataframe


def main() -> None:
    csv_paths = sorted(INPUT_DIRECTORY.glob("*.csv"))

    if not csv_paths:
        raise FileNotFoundError(
            f"Keine CSV-Dateien in {INPUT_DIRECTORY} gefunden.\n"
            "Führe zuerst aus: python src/collect_real_data.py"
        )

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    windowed_recordings: list[pd.DataFrame] = []
    time_offset_s = 0.0

    for csv_path in csv_paths:
        recording_windows = process_recording(csv_path, time_offset_s)
        windowed_recordings.append(recording_windows)

        time_offset_s = recording_windows["window_end_s"].max() + 1.0

    feature_dataframe = pd.concat(
        windowed_recordings,
        ignore_index=True,
    )
    feature_dataframe["window_id"] = range(len(feature_dataframe))

    training_data, validation_data, test_data = split_data(
        feature_dataframe
    )

    all_features_path = OUTPUT_DIRECTORY / "window_features_all.csv"
    training_path = OUTPUT_DIRECTORY / "train_normal.csv"
    validation_path = OUTPUT_DIRECTORY / "validation_normal.csv"
    test_path = OUTPUT_DIRECTORY / "test.csv"

    feature_dataframe.to_csv(all_features_path, index=False)
    training_data.to_csv(training_path, index=False)
    validation_data.to_csv(validation_path, index=False)
    test_data.to_csv(test_path, index=False)

    print("Vorverarbeitung der echten Daten abgeschlossen.")
    print()
    print(f"Verarbeitete Aufnahmen: {len(csv_paths)}")
    for csv_path in csv_paths:
        print(f"  - {csv_path}")
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
        f"Validierung, nur normal: {len(validation_data)} Fenster"
    )
    print(f"Test, normal und anomal: {len(test_data)} Fenster")
    print()
    print("Erzeugte Dateien:")
    print(f"- {all_features_path}")
    print(f"- {training_path}")
    print(f"- {validation_path}")
    print(f"- {test_path}")


if __name__ == "__main__":
    main()
