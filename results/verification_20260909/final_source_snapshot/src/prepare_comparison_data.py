"""Prepare leakage-free ADXL345 windows for model comparison.

The split is defined on recording-file level before windowing. Therefore, no
window from one acquisition session can appear in more than one data split.
Raw measurement files are only read and are never modified.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIRECTORY = PROJECT_ROOT / "data" / "real"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "comparison"
MODEL_DIRECTORY = PROJECT_ROOT / "models" / "tensorflow"
RESULT_DIRECTORY = PROJECT_ROOT / "results"

WINDOW_SIZE = 128
STEP_SIZE = 128
SAMPLE_RATE_HZ = 500
RANDOM_SEED = 42

AXIS_COLUMNS = ["x_g", "y_g", "z_g"]
REQUIRED_COLUMNS = [
    "timestamp_s",
    *AXIS_COLUMNS,
    "label",
    "anomaly_type",
]

# The assignment is explicit so that later runs reproduce exactly the same
# session-level split. New recordings must be assigned deliberately instead
# of silently entering one of the splits.
SPLIT_FILES = {
    "train": [
        "normal_20260725_184948.csv",
        "normal_20260725_185107.csv",
        "normal_20260725_185257.csv",
        "normal_20260817_100340.csv",
    ],
    "validation": [
        "normal_20260817_100640.csv",
    ],
    "test": [
        "normal_20260817_111818.csv",
        "anomaly_20260725_185423.csv",
    ],
}

NORMAL_ONLY_SPLITS = {"train", "validation"}


def relative_path(path: Path) -> str:
    """Return a stable repository-relative path for reports."""

    return str(path.relative_to(PROJECT_ROOT))


def label_distribution(labels: np.ndarray) -> dict[str, int]:
    """Return a consistently shaped binary-label summary."""

    labels = np.asarray(labels)
    return {
        "normal": int(np.count_nonzero(labels == 0)),
        "anomaly": int(np.count_nonzero(labels == 1)),
        "total": int(labels.size),
    }


def validate_split_definition() -> None:
    """Ensure every current recording is assigned exactly once."""

    assigned_files = [
        filename
        for filenames in SPLIT_FILES.values()
        for filename in filenames
    ]

    if len(assigned_files) != len(set(assigned_files)):
        raise ValueError("Eine Aufnahmedatei wurde mehreren Splits zugewiesen.")

    available_files = {
        path.name for path in RAW_DATA_DIRECTORY.glob("*.csv")
    }
    assigned_file_set = set(assigned_files)

    missing_files = sorted(assigned_file_set - available_files)
    unassigned_files = sorted(available_files - assigned_file_set)

    if missing_files:
        raise FileNotFoundError(
            "Folgende im Split definierte Dateien fehlen: "
            + ", ".join(missing_files)
        )

    if unassigned_files:
        raise ValueError(
            "Neue oder nicht zugewiesene Aufnahmedateien gefunden: "
            + ", ".join(unassigned_files)
            + ". Bitte SPLIT_FILES bewusst aktualisieren."
        )


def load_recording(csv_path: Path) -> pd.DataFrame:
    """Load and validate one recording without changing its row order."""

    dataframe = pd.read_csv(csv_path)
    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"{csv_path.name}: fehlende Spalten: {missing_columns}"
        )

    if dataframe.empty:
        raise ValueError(f"{csv_path.name}: Datei enthält keine Messwerte.")

    if dataframe[REQUIRED_COLUMNS].isna().any().any():
        raise ValueError(f"{csv_path.name}: fehlende Werte gefunden.")

    if not dataframe["timestamp_s"].is_monotonic_increasing:
        raise ValueError(
            f"{csv_path.name}: Zeitstempel sind nicht monoton steigend."
        )

    unique_labels = set(dataframe["label"].astype(int).unique())
    if not unique_labels.issubset({0, 1}):
        raise ValueError(
            f"{csv_path.name}: unerwartete Labels: {sorted(unique_labels)}"
        )

    return dataframe


def create_session_statistics(
    dataframe: pd.DataFrame,
    source_file: str,
    split: str,
) -> dict[str, float | int | str]:
    """Calculate orientation and vibration statistics for one session."""

    axes = dataframe[AXIS_COLUMNS].to_numpy(dtype=np.float64)
    magnitude = np.sqrt(np.sum(np.square(axes), axis=1))
    timestamps = dataframe["timestamp_s"].to_numpy(dtype=np.float64)
    duration_s = float(timestamps[-1] - timestamps[0])
    estimated_rate_hz = (
        float((len(timestamps) - 1) / duration_s)
        if len(timestamps) > 1 and duration_s > 0
        else 0.0
    )

    return {
        "source_file": source_file,
        "split": split,
        "sample_count": int(len(dataframe)),
        "duration_s": duration_s,
        "estimated_sample_rate_hz": estimated_rate_hz,
        "normal_sample_count": int((dataframe["label"] == 0).sum()),
        "anomaly_sample_count": int((dataframe["label"] == 1).sum()),
        "x_mean_g": float(np.mean(axes[:, 0])),
        "x_std_g": float(np.std(axes[:, 0], ddof=0)),
        "y_mean_g": float(np.mean(axes[:, 1])),
        "y_std_g": float(np.std(axes[:, 1], ddof=0)),
        "z_mean_g": float(np.mean(axes[:, 2])),
        "z_std_g": float(np.std(axes[:, 2], ddof=0)),
        "magnitude_mean_g": float(np.mean(magnitude)),
        "magnitude_std_g": float(np.std(magnitude, ddof=0)),
        "magnitude_min_g": float(np.min(magnitude)),
        "magnitude_max_g": float(np.max(magnitude)),
    }


def window_recording(
    dataframe: pd.DataFrame,
    source_file: str,
    split: str,
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame, dict[str, object]]:
    """Create ordered XYZ windows that never cross a file boundary.

    A window is labelled anomalous when at least one sample in that window has
    label 1. ``anomaly_fraction`` preserves the proportion of anomalous samples
    so that this deliberately sensitive rule can be studied later.
    """

    axes = dataframe[AXIS_COLUMNS].to_numpy(dtype=np.float32)
    point_labels = dataframe["label"].to_numpy(dtype=np.int8)
    timestamps = dataframe["timestamp_s"].to_numpy(dtype=np.float64)

    starts = list(
        range(0, len(dataframe) - WINDOW_SIZE + 1, STEP_SIZE)
    )
    windows: list[np.ndarray] = []
    window_labels: list[int] = []
    metadata_rows: list[dict[str, object]] = []

    for window_index, start_index in enumerate(starts):
        end_index = start_index + WINDOW_SIZE
        labels_in_window = point_labels[start_index:end_index]
        anomaly_fraction = float(np.mean(labels_in_window == 1))
        window_label = int(np.any(labels_in_window == 1))

        windows.append(axes[start_index:end_index])
        window_labels.append(window_label)
        metadata_rows.append(
            {
                "split": split,
                "source_file": source_file,
                "window_index": window_index,
                "start_sample": start_index,
                "end_sample_exclusive": end_index,
                "window_start_s": float(timestamps[start_index]),
                "window_end_s": float(timestamps[end_index - 1]),
                "label": window_label,
                "anomaly_fraction": anomaly_fraction,
            }
        )

    if windows:
        window_array = np.stack(windows).astype(np.float32, copy=False)
    else:
        window_array = np.empty(
            (0, WINDOW_SIZE, len(AXIS_COLUMNS)), dtype=np.float32
        )

    labels_array = np.asarray(window_labels, dtype=np.int8)
    final_covered_sample = starts[-1] + WINDOW_SIZE if starts else 0

    file_report: dict[str, object] = {
        "source_file": source_file,
        "sample_count": int(len(dataframe)),
        "created_windows": int(len(window_array)),
        "trailing_samples_dropped": int(
            len(dataframe) - final_covered_sample
        ),
        "point_label_distribution": label_distribution(point_labels),
        "window_label_distribution": label_distribution(labels_array),
    }

    return (
        window_array,
        labels_array,
        pd.DataFrame(metadata_rows),
        file_report,
    )


def prepare_split(
    split: str,
    filenames: list[str],
) -> tuple[
    np.ndarray,
    np.ndarray,
    pd.DataFrame,
    list[dict[str, object]],
    list[dict[str, float | int | str]],
]:
    """Load all files assigned to one split and concatenate their windows."""

    split_windows: list[np.ndarray] = []
    split_labels: list[np.ndarray] = []
    split_metadata: list[pd.DataFrame] = []
    file_reports: list[dict[str, object]] = []
    session_statistics: list[dict[str, float | int | str]] = []

    for filename in filenames:
        csv_path = RAW_DATA_DIRECTORY / filename
        dataframe = load_recording(csv_path)

        if split in NORMAL_ONLY_SPLITS and (dataframe["label"] != 0).any():
            raise ValueError(
                f"{filename}: {split} darf nur normale Messpunkte enthalten."
            )

        windows, labels, metadata, report = window_recording(
            dataframe=dataframe,
            source_file=filename,
            split=split,
        )
        split_windows.append(windows)
        split_labels.append(labels)
        split_metadata.append(metadata)
        file_reports.append(report)
        session_statistics.append(
            create_session_statistics(dataframe, filename, split)
        )

    all_windows = np.concatenate(split_windows, axis=0)
    all_labels = np.concatenate(split_labels, axis=0)
    all_metadata = pd.concat(split_metadata, ignore_index=True)
    all_metadata.insert(1, "split_index", range(len(all_metadata)))

    return (
        all_windows,
        all_labels,
        all_metadata,
        file_reports,
        session_statistics,
    )


def main() -> None:
    np.random.seed(RANDOM_SEED)
    validate_split_definition()

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    raw_windows: dict[str, np.ndarray] = {}
    labels: dict[str, np.ndarray] = {}
    metadata: dict[str, pd.DataFrame] = {}
    split_file_reports: dict[str, list[dict[str, object]]] = {}
    all_session_statistics: list[dict[str, float | int | str]] = []

    for split, filenames in SPLIT_FILES.items():
        (
            raw_windows[split],
            labels[split],
            metadata[split],
            split_file_reports[split],
            session_statistics,
        ) = prepare_split(split, filenames)
        all_session_statistics.extend(session_statistics)

    if np.any(labels["train"] != 0):
        raise ValueError("Training enthält mindestens ein Anomaliefenster.")
    if np.any(labels["validation"] != 0):
        raise ValueError("Validierung enthält mindestens ein Anomaliefenster.")

    # Fit exactly once and exclusively on normal training samples. Reshaping
    # combines the sample dimension while retaining X/Y/Z as separate features.
    scaler = StandardScaler()
    scaler.fit(raw_windows["train"].reshape(-1, len(AXIS_COLUMNS)))
    scaler_path = MODEL_DIRECTORY / "scaler.joblib"
    joblib.dump(scaler, scaler_path)

    scaled_windows: dict[str, np.ndarray] = {}
    for split in SPLIT_FILES:
        original_shape = raw_windows[split].shape
        scaled_windows[split] = scaler.transform(
            raw_windows[split].reshape(-1, len(AXIS_COLUMNS))
        ).reshape(original_shape).astype(np.float32)

        short_name = "val" if split == "validation" else split
        np.save(
            OUTPUT_DIRECTORY / f"X_{short_name}.npy",
            scaled_windows[split],
            allow_pickle=False,
        )
        np.save(
            OUTPUT_DIRECTORY / f"y_{short_name}.npy",
            labels[split],
            allow_pickle=False,
        )
        metadata[split].to_csv(
            OUTPUT_DIRECTORY / f"{short_name}_metadata.csv",
            index=False,
        )

    statistics_path = RESULT_DIRECTORY / "sensor_session_statistics.csv"
    pd.DataFrame(all_session_statistics).to_csv(statistics_path, index=False)

    manifest_splits: dict[str, object] = {}
    for split, filenames in SPLIT_FILES.items():
        manifest_splits[split] = {
            "files": filenames,
            "sample_count": int(
                sum(
                    report["sample_count"]
                    for report in split_file_reports[split]
                )
            ),
            "window_count": int(len(labels[split])),
            "label_distribution": label_distribution(labels[split]),
            "array_shape": list(scaled_windows[split].shape),
            "file_details": split_file_reports[split],
        }

    manifest = {
        "description": (
            "Session-level split for a fair comparison of TensorFlow "
            "Autoencoder and classical anomaly detection methods."
        ),
        "random_seed": RANDOM_SEED,
        "randomization_used": False,
        "sampling_rate_hz": SAMPLE_RATE_HZ,
        "window_size": WINDOW_SIZE,
        "step_size": STEP_SIZE,
        "window_overlap_samples": max(0, WINDOW_SIZE - STEP_SIZE),
        "axis_columns": AXIS_COLUMNS,
        "tensor_layout": "(window, time_sample, axis)",
        "sample_order": "Original row order within each source file",
        "incomplete_window_rule": (
            "Trailing samples that do not fill a complete window are dropped."
        ),
        "window_label_rule": (
            "ANOMALY (1) if at least one sample in the window has label 1; "
            "otherwise NORMAL (0)."
        ),
        "anomaly_fraction_definition": (
            "Number of samples with label 1 divided by window_size."
        ),
        "scaling": {
            "method": "sklearn.preprocessing.StandardScaler per XYZ axis",
            "fit_data": "Normal training samples only",
            "scaler_path": relative_path(scaler_path),
            "mean": [float(value) for value in scaler.mean_],
            "scale": [float(value) for value in scaler.scale_],
        },
        "output_directory": relative_path(OUTPUT_DIRECTORY),
        "splits": manifest_splits,
    }

    manifest_path = RESULT_DIRECTORY / "comparison_split_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, ensure_ascii=False)

    print("Vergleichsdaten erfolgreich vorbereitet.")
    print(f"Fenstergröße: {WINDOW_SIZE}, Schrittweite: {STEP_SIZE}")
    for split in SPLIT_FILES:
        print(
            f"{split:>10}: X={scaled_windows[split].shape}, "
            f"Labels={label_distribution(labels[split])}"
        )
    print(f"Scaler: {relative_path(scaler_path)}")
    print(f"Manifest: {relative_path(manifest_path)}")
    print(f"Sitzungsstatistik: {relative_path(statistics_path)}")


if __name__ == "__main__":
    main()
