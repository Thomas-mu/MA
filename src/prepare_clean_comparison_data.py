"""Prepare the controlled 2026-08-23 ADXL345 comparison dataset."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIRECTORY = PROJECT_ROOT / "data" / "real"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "clean_comparison"
MODEL_DIRECTORY = PROJECT_ROOT / "models" / "clean_comparison"
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

SPLIT_FILES = {
    "train": [
        "normal_20260823_112402.csv",
        "normal_20260823_112518.csv",
    ],
    "validation": [
        "normal_20260823_112734.csv",
    ],
    "test": [
        "normal_20260823_112843.csv",
        "anomaly_20260823_113819.csv",
        "anomaly_20260823_114124.csv",
    ],
}

EXCLUDED_FILES = [
    {
        "path": "data/real/excluded/anomaly_20260823_113338.csv",
        "reason": (
            "Explicitly excluded: recorded with anomaly label although no "
            "disturbance was produced."
        ),
    },
    {
        "path": "data/real/anomaly_20260823_113459.csv",
        "reason": (
            "Not part of the tapping_shaking experiment because metadata "
            "identifies anomaly_type as unbalance."
        ),
    },
]


def relative_path(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def label_distribution(labels: np.ndarray) -> dict[str, int]:
    labels = np.asarray(labels)
    return {
        "normal": int(np.count_nonzero(labels == 0)),
        "anomaly": int(np.count_nonzero(labels == 1)),
        "total": int(labels.size),
    }


def validate_split_definition() -> None:
    assigned = [
        filename
        for split_files in SPLIT_FILES.values()
        for filename in split_files
    ]
    if len(assigned) != len(set(assigned)):
        raise ValueError("Eine Datei wurde mehreren Clean-Splits zugeordnet.")

    missing = [
        filename
        for filename in assigned
        if not (RAW_DATA_DIRECTORY / filename).exists()
    ]
    if missing:
        raise FileNotFoundError(
            "Fehlende kontrollierte Aufnahmen: " + ", ".join(missing)
        )

    if any("20260823" not in filename for filename in assigned):
        raise ValueError("Clean-Split darf nur Aufnahmen vom 20260823 nutzen.")

    train_and_validation = (
        SPLIT_FILES["train"] + SPLIT_FILES["validation"]
    )
    if any(not filename.startswith("normal_") for filename in train_and_validation):
        raise ValueError("Training und Validation dürfen nur Normaldateien nutzen.")

    test_anomaly_files = [
        filename
        for filename in SPLIT_FILES["test"]
        if filename.startswith("anomaly_")
    ]
    if not test_anomaly_files:
        raise ValueError("Mindestens eine Clean-Anomaliedatei wird benötigt.")


def load_recording(filename: str) -> pd.DataFrame:
    path = RAW_DATA_DIRECTORY / filename
    dataframe = pd.read_csv(path)
    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in dataframe.columns
    ]
    if missing_columns:
        raise ValueError(f"{filename}: fehlende Spalten {missing_columns}")
    if dataframe.empty:
        raise ValueError(f"{filename}: keine Messpunkte vorhanden.")
    if dataframe[REQUIRED_COLUMNS].isna().any().any():
        raise ValueError(f"{filename}: fehlende Werte gefunden.")
    if not dataframe["timestamp_s"].is_monotonic_increasing:
        raise ValueError(f"{filename}: Zeitstempel nicht monoton steigend.")

    unique_labels = set(dataframe["label"].astype(int).unique())
    if not unique_labels.issubset({0, 1}):
        raise ValueError(f"{filename}: ungültige Labels {unique_labels}")

    if filename.startswith("normal_") and unique_labels != {0}:
        raise ValueError(f"{filename}: Normalaufnahme enthält Anomalielabels.")
    if filename.startswith("anomaly_"):
        anomaly_types = set(dataframe["anomaly_type"].astype(str).unique())
        if anomaly_types != {"tapping_shaking"}:
            raise ValueError(
                f"{filename}: erwartet tapping_shaking, erhalten {anomaly_types}"
            )
    return dataframe


def session_statistics(
    dataframe: pd.DataFrame,
    filename: str,
    split: str,
) -> dict[str, float | int | str]:
    axes = dataframe[AXIS_COLUMNS].to_numpy(dtype=np.float64)
    magnitude = np.sqrt(np.sum(np.square(axes), axis=1))
    timestamps = dataframe["timestamp_s"].to_numpy(dtype=np.float64)
    duration_s = float(timestamps[-1] - timestamps[0])
    estimated_rate = (
        float((len(timestamps) - 1) / duration_s)
        if len(timestamps) > 1 and duration_s > 0
        else 0.0
    )
    labels = sorted(int(value) for value in dataframe["label"].unique())
    anomaly_types = sorted(
        str(value) for value in dataframe["anomaly_type"].unique()
    )
    return {
        "source_file": filename,
        "split": split,
        "sample_count": int(len(dataframe)),
        "duration_s": duration_s,
        "estimated_sample_rate_hz": estimated_rate,
        "labels": "|".join(str(value) for value in labels),
        "anomaly_types": "|".join(anomaly_types),
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
    filename: str,
    split: str,
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame, dict[str, object]]:
    """Window one file in original order without crossing its boundary.

    A window is anomalous if at least one contained sample has label 1.
    ``anomaly_fraction`` stores the fraction of anomalous point labels.
    """

    axes = dataframe[AXIS_COLUMNS].to_numpy(dtype=np.float32)
    point_labels = dataframe["label"].to_numpy(dtype=np.int8)
    timestamps = dataframe["timestamp_s"].to_numpy(dtype=np.float64)
    starts = list(range(0, len(dataframe) - WINDOW_SIZE + 1, STEP_SIZE))
    windows: list[np.ndarray] = []
    labels: list[int] = []
    metadata_rows: list[dict[str, float | int | str]] = []

    for window_index, start in enumerate(starts):
        end = start + WINDOW_SIZE
        sample_labels = point_labels[start:end]
        anomaly_fraction = float(np.mean(sample_labels == 1))
        window_label = int(np.any(sample_labels == 1))
        windows.append(axes[start:end])
        labels.append(window_label)
        metadata_rows.append(
            {
                "split": split,
                "source_file": filename,
                "window_index": window_index,
                "start_sample": start,
                "end_sample_exclusive": end,
                "window_start_s": float(timestamps[start]),
                "window_end_s": float(timestamps[end - 1]),
                "label": window_label,
                "anomaly_fraction": anomaly_fraction,
            }
        )

    window_array = np.stack(windows).astype(np.float32, copy=False)
    label_array = np.asarray(labels, dtype=np.int8)
    final_end = starts[-1] + WINDOW_SIZE if starts else 0
    report: dict[str, object] = {
        "source_file": filename,
        "sample_count": int(len(dataframe)),
        "created_windows": int(len(window_array)),
        "trailing_samples_dropped": int(len(dataframe) - final_end),
        "point_label_distribution": label_distribution(point_labels),
        "window_label_distribution": label_distribution(label_array),
        "anomaly_types": sorted(
            str(value) for value in dataframe["anomaly_type"].unique()
        ),
    }
    return window_array, label_array, pd.DataFrame(metadata_rows), report


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
    windows: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    metadata: list[pd.DataFrame] = []
    reports: list[dict[str, object]] = []
    statistics: list[dict[str, float | int | str]] = []

    for filename in filenames:
        dataframe = load_recording(filename)
        file_windows, file_labels, file_metadata, report = window_recording(
            dataframe, filename, split
        )
        windows.append(file_windows)
        labels.append(file_labels)
        metadata.append(file_metadata)
        reports.append(report)
        statistics.append(session_statistics(dataframe, filename, split))

    all_metadata = pd.concat(metadata, ignore_index=True)
    all_metadata.insert(1, "split_index", range(len(all_metadata)))
    return (
        np.concatenate(windows, axis=0),
        np.concatenate(labels, axis=0),
        all_metadata,
        reports,
        statistics,
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
    file_reports: dict[str, list[dict[str, object]]] = {}
    statistics_rows: list[dict[str, float | int | str]] = []

    for split, filenames in SPLIT_FILES.items():
        (
            raw_windows[split],
            labels[split],
            metadata[split],
            file_reports[split],
            statistics,
        ) = prepare_split(split, filenames)
        statistics_rows.extend(statistics)

    if np.any(labels["train"] != 0) or np.any(labels["validation"] != 0):
        raise ValueError("Clean-Training und -Validation müssen rein normal sein.")

    scaler = StandardScaler()
    scaler.fit(raw_windows["train"].reshape(-1, len(AXIS_COLUMNS)))
    scaler_path = MODEL_DIRECTORY / "scaler.joblib"
    joblib.dump(scaler, scaler_path)

    scaled_windows: dict[str, np.ndarray] = {}
    for split in SPLIT_FILES:
        shape = raw_windows[split].shape
        scaled_windows[split] = scaler.transform(
            raw_windows[split].reshape(-1, len(AXIS_COLUMNS))
        ).reshape(shape).astype(np.float32)
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
            OUTPUT_DIRECTORY / f"{short_name}_metadata.csv", index=False
        )

    statistics_path = RESULT_DIRECTORY / "clean_session_statistics.csv"
    pd.DataFrame(statistics_rows).to_csv(statistics_path, index=False)

    split_manifest: dict[str, object] = {}
    for split, filenames in SPLIT_FILES.items():
        split_manifest[split] = {
            "files": filenames,
            "sample_count": int(
                sum(report["sample_count"] for report in file_reports[split])
            ),
            "window_count": int(len(labels[split])),
            "label_distribution": label_distribution(labels[split]),
            "array_shape": list(scaled_windows[split].shape),
            "file_details": file_reports[split],
        }

    normal_means = np.asarray(
        [
            [row["x_mean_g"], row["y_mean_g"], row["z_mean_g"]]
            for row in statistics_rows
            if row["anomaly_sample_count"] == 0
        ],
        dtype=np.float64,
    )
    maximum_mean_distance = max(
        float(np.linalg.norm(first - second))
        for first in normal_means
        for second in normal_means
    )

    manifest = {
        "description": (
            "Controlled comparison using only 2026-08-23 recordings with "
            "unchanged ADXL345 mounting."
        ),
        "selection_rule": (
            "Only explicitly assigned 20260823 normal recordings and "
            "tapping_shaking anomaly recordings are used."
        ),
        "excluded_files": EXCLUDED_FILES,
        "random_seed": RANDOM_SEED,
        "randomization_used": False,
        "sampling_rate_hz": SAMPLE_RATE_HZ,
        "window_size": WINDOW_SIZE,
        "step_size": STEP_SIZE,
        "window_overlap_samples": 0,
        "axis_columns": AXIS_COLUMNS,
        "tensor_layout": "(window, time_sample, axis)",
        "window_label_rule": (
            "ANOMALY (1) if at least one point label is 1; otherwise NORMAL (0)."
        ),
        "anomaly_fraction_definition": (
            "Number of point labels equal to 1 divided by window_size."
        ),
        "incomplete_window_rule": "Trailing incomplete windows are dropped.",
        "normal_session_orientation": {
            "maximum_pairwise_xyz_mean_distance_g": maximum_mean_distance,
            "x_mean_range_g": float(np.ptp(normal_means[:, 0])),
            "y_mean_range_g": float(np.ptp(normal_means[:, 1])),
            "z_mean_range_g": float(np.ptp(normal_means[:, 2])),
        },
        "scaling": {
            "method": "StandardScaler per XYZ axis",
            "fit_data": "Normal training samples only",
            "scaler_path": relative_path(scaler_path),
            "mean": [float(value) for value in scaler.mean_],
            "scale": [float(value) for value in scaler.scale_],
        },
        "output_directory": relative_path(OUTPUT_DIRECTORY),
        "splits": split_manifest,
    }
    manifest_path = RESULT_DIRECTORY / "clean_comparison_split_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, ensure_ascii=False)

    print("Kontrollierte Vergleichsdaten erfolgreich vorbereitet.")
    for split in SPLIT_FILES:
        print(
            f"{split:>10}: X={scaled_windows[split].shape}, "
            f"Labels={label_distribution(labels[split])}"
        )
    print(
        "Maximale Distanz der Normal-Sitzungsmittel: "
        f"{maximum_mean_distance:.9f} g"
    )
    print(f"Scaler: {relative_path(scaler_path)}")
    print(f"Manifest: {relative_path(manifest_path)}")


if __name__ == "__main__":
    main()
