#!/usr/bin/env python3
"""Create setup-specific normal-state calibration profiles.

The pipeline records only normal ADXL345 sessions, splits strictly by source
file, fits a StandardScaler on training sessions only, trains the established
small convolutional autoencoder, derives a validation-only P99 threshold and
converts the best Keras model to unquantized Float32 TensorFlow Lite.

Existing profiles are never overwritten.  ``--new-version`` allocates a new
``<name>_vNNN`` directory.  Training artifacts are built in a temporary
staging directory and committed only after the TFLite consistency test passes.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_DETERMINISTIC_OPS", "1")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/masterarbeit_matplotlib")

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_PROFILES_DIRECTORY = PROJECT_ROOT / "profiles"
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

WINDOW_SIZE = 128
STEP_SIZE = 128
AXIS_COLUMNS = ["x_g", "y_g", "z_g"]
EXPECTED_WINDOW_SHAPE = (WINDOW_SIZE, len(AXIS_COLUMNS))
DEFAULT_RECORDINGS = 4
DEFAULT_VALIDATION_RECORDINGS = 1
DEFAULT_SECONDS = 60.0
DEFAULT_SAMPLING_RATE_HZ = 500
RANDOM_SEED = 42
MAX_EPOCHS = 100
BATCH_SIZE = 32
EARLY_STOPPING_PATIENCE = 10
EARLY_STOPPING_MIN_DELTA = 1e-6
THRESHOLD_PERCENTILE = 99
TFLITE_MAX_RECONSTRUCTION_DIFFERENCE = 1e-3
TFLITE_MAX_MSE_DIFFERENCE = 1e-4
PROFILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class ProfilePaths:
    root: Path
    data: Path
    raw: Path
    processed: Path
    models: Path
    results: Path
    metadata: Path

    @classmethod
    def create(cls, profiles_root: Path, profile_name: str) -> "ProfilePaths":
        root = profiles_root / profile_name
        return cls(
            root=root,
            data=root / "data",
            raw=root / "data" / "raw",
            processed=root / "data" / "processed",
            models=root / "models",
            results=root / "results",
            metadata=root / "profile.json",
        )


def timestamp_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def stable_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def validate_profile_name(profile_name: str) -> None:
    if not PROFILE_NAME_PATTERN.fullmatch(profile_name):
        raise ValueError(
            "Profilname muss mit einem alphanumerischen Zeichen beginnen und "
            "darf höchstens 64 Zeichen aus Buchstaben, Ziffern, '_' und '-' enthalten."
        )


def allocate_profile_name(
    profiles_root: Path, base_name: str, new_version: bool
) -> tuple[str, int]:
    validate_profile_name(base_name)
    base_path = profiles_root / base_name
    if not base_path.exists():
        return base_name, 0
    if not new_version:
        raise FileExistsError(
            f"Profil existiert bereits und wird nicht überschrieben: {base_path}. "
            "Für eine neue Kalibrierung --new-version verwenden."
        )
    for version in range(1, 10_000):
        candidate = f"{base_name}_v{version:03d}"
        if not (profiles_root / candidate).exists():
            return candidate, version
    raise RuntimeError(f"Keine freie Version für Profil {base_name!r} gefunden.")


def write_json_atomic(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    with temporary_path.open("w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary_path, path)


def read_profile(paths: ProfilePaths) -> dict[str, Any]:
    if not paths.metadata.is_file():
        raise FileNotFoundError(f"Profilmetadaten fehlen: {paths.metadata}")
    with paths.metadata.open(encoding="utf-8") as handle:
        return json.load(handle)


def collect_system_information() -> dict[str, Any]:
    from convert_model import collect_system_information as collect_phase4_system

    information = collect_phase4_system()
    information["platform_string"] = platform.platform()
    information["package_versions"] = {
        name: package_version(name)
        for name in (
            "tensorflow",
            "keras",
            "numpy",
            "pandas",
            "scikit-learn",
            "joblib",
            "psutil",
            "smbus2",
        )
    }
    return information


def calibration_configuration(arguments: argparse.Namespace) -> dict[str, Any]:
    training_count = arguments.recordings - arguments.validation_recordings
    return {
        "normal_recordings": arguments.recordings,
        "training_recordings": training_count,
        "validation_recordings": arguments.validation_recordings,
        "seconds_per_recording": arguments.seconds,
        "sampling_rate_hz": arguments.sampling_rate,
        "window_size": WINDOW_SIZE,
        "step_size": STEP_SIZE,
        "window_overlap_samples": 0,
        "axis_columns": AXIS_COLUMNS,
        "random_seed": RANDOM_SEED,
        "batch_size": BATCH_SIZE,
        "maximum_epochs": MAX_EPOCHS,
        "early_stopping_patience": EARLY_STOPPING_PATIENCE,
        "early_stopping_min_delta": EARLY_STOPPING_MIN_DELTA,
        "threshold_percentile": THRESHOLD_PERCENTILE,
        "normal_data_only": True,
    }


def initialize_profile(
    profiles_root: Path,
    base_name: str,
    new_version: bool,
    configuration: dict[str, Any],
    description: str | None,
) -> tuple[ProfilePaths, dict[str, Any]]:
    resolved_name, version = allocate_profile_name(
        profiles_root, base_name, new_version
    )
    paths = ProfilePaths.create(profiles_root, resolved_name)
    paths.root.mkdir(parents=True, exist_ok=False)
    for directory in (
        paths.raw,
        paths.processed,
        paths.models,
        paths.results,
    ):
        directory.mkdir(parents=True, exist_ok=False)

    created_at = timestamp_now()
    profile: dict[str, Any] = {
        "profile_name": resolved_name,
        "base_profile_name": base_name,
        "profile_version": version,
        "status": "initialized",
        "created_at": created_at,
        "updated_at": created_at,
        "description": description,
        "sampling_rate_hz": configuration["sampling_rate_hz"],
        "window_size": configuration["window_size"],
        "step_size": configuration["step_size"],
        "axes": list(configuration["axis_columns"]),
        "normal_recordings": configuration["normal_recordings"],
        "training_recordings": configuration["training_recordings"],
        "validation_recordings": configuration["validation_recordings"],
        "methodology": (
            "Setup-specific normal-state calibration. Only normal training files "
            "fit the scaler and autoencoder; the threshold is the 99th percentile "
            "of reconstruction MSE from separate normal validation files."
        ),
        "system": collect_system_information(),
        "sensor": {
            "model": "ADXL345",
            "axes": AXIS_COLUMNS,
            "access_module": "src/adxl345.py",
            "connect_function": "connect",
            "read_function": "read_acceleration_g",
            "software_sampling_rate_hz": configuration["sampling_rate_hz"],
            "internal_odr_note": (
                "The reused ADXL345 access does not explicitly configure the "
                "sensor BW_RATE/ODR register; measured CSV timestamps document "
                "the software polling rate."
            ),
        },
        "configuration": configuration,
        "data": {
            "normal_only": True,
            "raw_directory": stable_path(paths.raw),
            "recordings": [],
            "split_rule": (
                "Files in acquisition order: first files TRAIN, final configured "
                "file(s) VALIDATION; no source file occurs in both splits."
            ),
        },
        "artifacts": {},
        "warnings": [],
    }
    write_json_atomic(paths.metadata, profile)
    return paths, profile


def update_profile_status(
    paths: ProfilePaths,
    profile: dict[str, Any],
    status: str,
    *,
    error: Exception | None = None,
) -> None:
    profile["status"] = status
    profile["updated_at"] = timestamp_now()
    if error is None:
        profile.pop("last_error", None)
    else:
        profile["last_error"] = {
            "type": type(error).__name__,
            "message": str(error),
            "occurred_at": timestamp_now(),
        }
    write_json_atomic(paths.metadata, profile)


def load_record_function() -> Any:
    # Sensor path setup is delegated to the already validated live helper.
    from live_tflite_monitor import load_sensor_access

    connect_sensor, _ = load_sensor_access()
    from collect_real_data import record

    return connect_sensor, record


def measured_sampling_rate(dataframe: pd.DataFrame) -> float:
    timestamps = dataframe["timestamp_s"].to_numpy(dtype=np.float64)
    if len(timestamps) < 2:
        return 0.0
    duration = float(timestamps[-1] - timestamps[0])
    return float((len(timestamps) - 1) / duration) if duration > 0 else 0.0


def record_normal_sessions(
    paths: ProfilePaths, profile: dict[str, Any]
) -> None:
    configuration = profile["configuration"]
    recording_count = int(configuration["normal_recordings"])
    validation_count = int(configuration["validation_recordings"])
    train_count = recording_count - validation_count
    connect_sensor, record = load_record_function()

    print(f"Profil: {profile['profile_name']}")
    print("ADXL345-Erreichbarkeit wird geprüft ...", flush=True)
    bus = connect_sensor()
    try:
        print("ADXL345 erreichbar.")
        print("\nKalibrierung startet.\n")
        print("Bitte:")
        print("- Sensor nicht mehr bewegen")
        print("- Lüfter normal laufen lassen")
        print("- keine Störung erzeugen\n")

        update_profile_status(paths, profile, "recording")
        for index in range(1, recording_count + 1):
            filename = f"normal_{index:03d}.csv"
            output_path = paths.raw / filename
            if output_path.exists():
                raise FileExistsError(
                    f"Rohaufnahme wird nicht überschrieben: {output_path}"
                )
            print(f"Aufnahme {index}/{recording_count} startet in:", flush=True)
            for remaining in (3, 2, 1):
                print(f"  {remaining} ...", flush=True)
                time.sleep(1)
            print(
                f"LOS! Normalaufnahme läuft für "
                f"{configuration['seconds_per_recording']:.1f} s ...",
                flush=True,
            )
            dataframe = record(
                bus=bus,
                duration_seconds=float(configuration["seconds_per_recording"]),
                sample_rate_hz=int(configuration["sampling_rate_hz"]),
            )
            if len(dataframe) < WINDOW_SIZE:
                raise RuntimeError(
                    f"{filename}: nur {len(dataframe)} Samples; mindestens "
                    f"{WINDOW_SIZE} sind erforderlich."
                )
            dataframe["label"] = np.int8(0)
            dataframe["anomaly_type"] = "normal"
            dataframe["source"] = "profile_calibration"
            dataframe["profile_name"] = profile["profile_name"]
            dataframe["recording_index"] = index
            with output_path.open("x", encoding="utf-8", newline="") as handle:
                dataframe.to_csv(handle, index=False)

            split = "train" if index <= train_count else "validation"
            record_metadata = {
                "recording_index": index,
                "recorded_at": timestamp_now(),
                "filename": filename,
                "path": stable_path(output_path),
                "split": split,
                "sample_count": int(len(dataframe)),
                "configured_duration_seconds": float(
                    configuration["seconds_per_recording"]
                ),
                "configured_sampling_rate_hz": int(
                    configuration["sampling_rate_hz"]
                ),
                "measured_sampling_rate_hz": measured_sampling_rate(dataframe),
                "sha256": sha256_file(output_path),
            }
            profile["data"]["recordings"].append(record_metadata)
            profile["updated_at"] = timestamp_now()
            write_json_atomic(paths.metadata, profile)
            print(
                f"Aufnahme abgeschlossen: {filename}, {len(dataframe)} Samples, "
                f"{record_metadata['measured_sampling_rate_hz']:.1f} Hz\n"
            )
    finally:
        bus.close()

    update_profile_status(paths, profile, "recorded")


def validate_recorded_profile(
    paths: ProfilePaths, profile: dict[str, Any]
) -> list[dict[str, Any]]:
    configuration = profile["configuration"]
    recordings = list(profile.get("data", {}).get("recordings", []))
    expected_count = int(configuration["normal_recordings"])
    if len(recordings) != expected_count:
        raise ValueError(
            f"Profil enthält {len(recordings)} statt {expected_count} Aufnahmen."
        )
    expected_filenames = [
        f"normal_{index:03d}.csv" for index in range(1, expected_count + 1)
    ]
    actual_filenames = [str(row.get("filename", "")) for row in recordings]
    if actual_filenames != expected_filenames:
        raise ValueError(
            "Aufnahmedateien oder deren Reihenfolge wurden verändert; erwartet: "
            + ", ".join(expected_filenames)
        )
    if any(Path(filename).name != filename for filename in actual_filenames):
        raise ValueError("Aufnahmedateinamen dürfen keine Pfadbestandteile enthalten.")
    expected_indices = list(range(1, expected_count + 1))
    actual_indices = [int(row.get("recording_index", -1)) for row in recordings]
    if actual_indices != expected_indices:
        raise ValueError("Aufnahmeindizes oder deren Reihenfolge sind inkonsistent.")
    training_count = int(configuration["training_recordings"])
    for index, row in enumerate(recordings, start=1):
        expected_split = "train" if index <= training_count else "validation"
        if row.get("split") != expected_split:
            raise ValueError(
                f"{row['filename']}: Split wurde verändert; "
                f"erwartet {expected_split}."
            )
    train_files = [row for row in recordings if row.get("split") == "train"]
    validation_files = [
        row for row in recordings if row.get("split") == "validation"
    ]
    if len(train_files) != int(configuration["training_recordings"]):
        raise ValueError("Anzahl Trainingsaufnahmen stimmt nicht mit dem Profil überein.")
    if len(validation_files) != int(configuration["validation_recordings"]):
        raise ValueError(
            "Anzahl Validierungsaufnahmen stimmt nicht mit dem Profil überein."
        )
    if {row["filename"] for row in train_files} & {
        row["filename"] for row in validation_files
    }:
        raise ValueError("Eine Datei ist zugleich Training und Validation.")

    for row in recordings:
        path = paths.raw / row["filename"]
        if not path.is_file():
            raise FileNotFoundError(f"Rohaufnahme fehlt: {path}")
        with path.open(encoding="utf-8", newline="") as handle:
            actual_sample_count = max(sum(1 for _ in handle) - 1, 0)
        if actual_sample_count != int(row.get("sample_count", -1)):
            raise ValueError(
                f"{path}: gespeicherte Samplezahl stimmt nicht mit der CSV überein."
            )
        actual_hash = sha256_file(path)
        if actual_hash != row["sha256"]:
            raise ValueError(
                f"Rohaufnahme wurde seit der Erfassung verändert: {path}"
            )
    return recordings


def prepare_profile_data(
    paths: ProfilePaths, profile: dict[str, Any]
) -> dict[str, Any]:
    from prepare_clean_comparison_data import session_statistics, window_recording

    recordings = validate_recorded_profile(paths, profile)
    raw_windows: dict[str, list[np.ndarray]] = {"train": [], "validation": []}
    metadata_frames: dict[str, list[pd.DataFrame]] = {
        "train": [],
        "validation": [],
    }
    labels: dict[str, list[np.ndarray]] = {"train": [], "validation": []}
    reports: list[dict[str, Any]] = []
    statistics_rows: list[dict[str, Any]] = []

    for recording in recordings:
        split = str(recording["split"])
        filename = str(recording["filename"])
        dataframe = pd.read_csv(paths.raw / filename)
        required = {"timestamp_s", *AXIS_COLUMNS, "label", "anomaly_type"}
        missing = sorted(required - set(dataframe.columns))
        if missing:
            raise ValueError(f"{filename}: fehlende Spalten {missing}")
        if dataframe.empty or dataframe[list(required)].isna().any().any():
            raise ValueError(f"{filename}: leere oder unvollständige Normalaufnahme.")
        timestamps = dataframe["timestamp_s"].to_numpy(dtype=np.float64)
        axes = dataframe[AXIS_COLUMNS].to_numpy(dtype=np.float64)
        if not np.all(np.isfinite(timestamps)) or not np.all(np.isfinite(axes)):
            raise ValueError(f"{filename}: nicht-endliche Messwerte gefunden.")
        if not dataframe["timestamp_s"].is_monotonic_increasing:
            raise ValueError(f"{filename}: Zeitstempel sind nicht monoton steigend.")
        if np.any(dataframe["label"].to_numpy(dtype=np.int8) != 0):
            raise ValueError(f"{filename}: Kalibrierung darf nur Normaldaten nutzen.")
        if set(dataframe["anomaly_type"].astype(str).unique()) != {"normal"}:
            raise ValueError(f"{filename}: anomaly_type muss ausschließlich normal sein.")

        windows, file_labels, metadata, report = window_recording(
            dataframe, filename, split
        )
        if len(windows) == 0 or np.any(file_labels != 0):
            raise ValueError(f"{filename}: keine gültigen reinen Normalfenster.")
        raw_windows[split].append(windows)
        labels[split].append(file_labels)
        metadata_frames[split].append(metadata)
        report["split"] = split
        report["path"] = stable_path(paths.raw / filename)
        report["sha256"] = recording["sha256"]
        reports.append(report)
        statistics = session_statistics(dataframe, filename, split)
        statistics["path"] = stable_path(paths.raw / filename)
        statistics["sha256"] = recording["sha256"]
        statistics_rows.append(statistics)

    combined_raw = {
        split: np.concatenate(raw_windows[split], axis=0).astype(
            np.float32, copy=False
        )
        for split in ("train", "validation")
    }
    combined_labels = {
        split: np.concatenate(labels[split]).astype(np.int8, copy=False)
        for split in ("train", "validation")
    }
    combined_metadata: dict[str, pd.DataFrame] = {}
    for split in ("train", "validation"):
        frame = pd.concat(metadata_frames[split], ignore_index=True)
        frame.insert(1, "split_index", range(len(frame)))
        combined_metadata[split] = frame

    scaler = StandardScaler()
    scaler.fit(combined_raw["train"].reshape(-1, len(AXIS_COLUMNS)))
    scaled_windows = {
        split: scaler.transform(
            combined_raw[split].reshape(-1, len(AXIS_COLUMNS))
        )
        .reshape(combined_raw[split].shape)
        .astype(np.float32)
        for split in ("train", "validation")
    }
    for split in ("train", "validation"):
        if not np.all(np.isfinite(scaled_windows[split])):
            raise ValueError(f"{split}: Skalierung erzeugte nicht-endliche Werte.")

    manifest = {
        "profile_name": profile["profile_name"],
        "normal_data_only": True,
        "split_level": "source_file",
        "train_files": [
            row["filename"] for row in recordings if row["split"] == "train"
        ],
        "validation_files": [
            row["filename"]
            for row in recordings
            if row["split"] == "validation"
        ],
        "window_size": WINDOW_SIZE,
        "step_size": STEP_SIZE,
        "window_overlap_samples": 0,
        "axis_columns": AXIS_COLUMNS,
        "incomplete_window_rule": "Trailing incomplete samples per file are dropped.",
        "files": reports,
        "training_window_count": int(len(scaled_windows["train"])),
        "validation_window_count": int(len(scaled_windows["validation"])),
        "scaler": {
            "type": "sklearn.preprocessing.StandardScaler",
            "fit_data": "Normal training samples only",
            "mean": [float(value) for value in scaler.mean_],
            "scale": [float(value) for value in scaler.scale_],
            "n_samples_seen": float(scaler.n_samples_seen_),
        },
    }
    return {
        "features": scaled_windows,
        "labels": combined_labels,
        "metadata": combined_metadata,
        "scaler": scaler,
        "manifest": manifest,
        "session_statistics": pd.DataFrame(statistics_rows),
    }


def validation_statistics(errors: np.ndarray) -> dict[str, float | int]:
    from evaluate_clean_autoencoder import validation_statistics as clean_statistics

    statistics = clean_statistics(errors)
    statistics["minimum_mse"] = float(np.min(errors))
    return statistics


def tflite_consistency_test(
    keras_model: Any,
    tflite_path: Path,
    validation_features: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    from convert_model import create_interpreter, invoke_tflite

    keras_reconstructions = np.asarray(
        keras_model.predict(
            validation_features, batch_size=BATCH_SIZE, verbose=0
        ),
        dtype=np.float32,
    )
    interpreter, interface = create_interpreter(tflite_path)
    tflite_reconstructions = np.empty_like(keras_reconstructions)
    for index, window in enumerate(validation_features):
        tflite_reconstructions[index] = invoke_tflite(
            interpreter, interface, window
        )

    reconstruction_difference = np.abs(
        keras_reconstructions.astype(np.float64)
        - tflite_reconstructions.astype(np.float64)
    )
    keras_errors = np.mean(
        np.square(validation_features - keras_reconstructions),
        axis=(1, 2),
        dtype=np.float64,
    )
    tflite_errors = np.mean(
        np.square(validation_features - tflite_reconstructions),
        axis=(1, 2),
        dtype=np.float64,
    )
    mse_difference = np.abs(keras_errors - tflite_errors)
    disagreements = int(
        np.count_nonzero((keras_errors > threshold) != (tflite_errors > threshold))
    )
    maximum_reconstruction_difference = float(np.max(reconstruction_difference))
    maximum_mse_difference = float(np.max(mse_difference))
    plausible = (
        np.all(np.isfinite(tflite_reconstructions))
        and maximum_reconstruction_difference
        <= TFLITE_MAX_RECONSTRUCTION_DIFFERENCE
        and maximum_mse_difference <= TFLITE_MAX_MSE_DIFFERENCE
        and disagreements == 0
    )
    return {
        "plausible": bool(plausible),
        "validation_windows": int(len(validation_features)),
        "compared_reconstruction_values": int(reconstruction_difference.size),
        "maximum_absolute_reconstruction_difference": maximum_reconstruction_difference,
        "mean_absolute_reconstruction_difference": float(
            np.mean(reconstruction_difference)
        ),
        "maximum_absolute_mse_difference": maximum_mse_difference,
        "mean_absolute_mse_difference": float(np.mean(mse_difference)),
        "threshold_decision_disagreements": disagreements,
        "acceptance_limits": {
            "maximum_absolute_reconstruction_difference": (
                TFLITE_MAX_RECONSTRUCTION_DIFFERENCE
            ),
            "maximum_absolute_mse_difference": TFLITE_MAX_MSE_DIFFERENCE,
            "maximum_threshold_decision_disagreements": 0,
        },
        "interface": interface,
    }


def write_training_stage(
    stage: Path,
    prepared: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    import tensorflow as tf
    from convert_model import convert_to_float32_tflite
    from train_clean_autoencoder import (
        build_autoencoder,
        configure_reproducibility,
        reconstruction_errors,
    )

    configure_reproducibility()
    stage_processed = stage / "data" / "processed"
    stage_models = stage / "models"
    stage_results = stage / "results"
    for directory in (stage_processed, stage_models, stage_results):
        directory.mkdir(parents=True, exist_ok=False)

    features = prepared["features"]
    labels = prepared["labels"]
    metadata = prepared["metadata"]
    x_train = features["train"]
    x_validation = features["validation"]
    if np.any(labels["train"] != 0) or np.any(labels["validation"] != 0):
        raise ValueError("Training und Validation müssen ausschließlich normal sein.")
    if tuple(x_train.shape[1:]) != EXPECTED_WINDOW_SHAPE:
        raise ValueError(f"Ungültige Trainingsform: {x_train.shape}")
    if tuple(x_validation.shape[1:]) != EXPECTED_WINDOW_SHAPE:
        raise ValueError(f"Ungültige Validierungsform: {x_validation.shape}")

    model_path = stage_models / "autoencoder.keras"
    model = build_autoencoder()
    summary_lines: list[str] = []
    model.summary(print_fn=summary_lines.append)
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            filepath=model_path,
            monitor="val_loss",
            mode="min",
            save_best_only=True,
            verbose=1,
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            mode="min",
            patience=EARLY_STOPPING_PATIENCE,
            min_delta=EARLY_STOPPING_MIN_DELTA,
            restore_best_weights=True,
            verbose=1,
        ),
    ]
    history = model.fit(
        x_train,
        x_train,
        validation_data=(x_validation, x_validation),
        epochs=MAX_EPOCHS,
        batch_size=BATCH_SIZE,
        shuffle=True,
        callbacks=callbacks,
        verbose=2,
    )
    best_model = tf.keras.models.load_model(model_path, compile=False)

    print("Reconstruction Errors werden berechnet ...")
    train_errors = reconstruction_errors(best_model, x_train)
    validation_errors = reconstruction_errors(best_model, x_validation)
    threshold_statistics = validation_statistics(validation_errors)
    threshold = float(threshold_statistics["percentile_99_mse"])
    validation_above_count = int(np.count_nonzero(validation_errors > threshold))
    validation_above_fraction = float(validation_above_count / len(validation_errors))
    quality_warning = validation_above_fraction > 0.02
    validation_size_warning = len(validation_errors) < 100

    print("Validation-P99-Threshold wird bestimmt ...")
    print("Float32-TFLite-Modell wird erzeugt ...")
    tflite_bytes, conversion = convert_to_float32_tflite(best_model)
    tflite_path = stage_models / "autoencoder_float32.tflite"
    tflite_path.write_bytes(tflite_bytes)
    print("Numerischer Keras-vs.-TFLite-Konsistenztest ...")
    consistency = tflite_consistency_test(
        best_model, tflite_path, x_validation, threshold
    )
    consistency["conversion"] = conversion
    if not consistency["plausible"]:
        raise RuntimeError(
            "TFLite-Konsistenzprüfung fehlgeschlagen; Profil wird nicht freigegeben: "
            f"{consistency}"
        )

    joblib.dump(prepared["scaler"], stage_models / "scaler.joblib")
    np.save(stage_processed / "X_train.npy", x_train, allow_pickle=False)
    np.save(stage_processed / "X_val.npy", x_validation, allow_pickle=False)
    np.save(
        stage_processed / "y_train.npy", labels["train"], allow_pickle=False
    )
    np.save(
        stage_processed / "y_val.npy", labels["validation"], allow_pickle=False
    )
    metadata["train"].to_csv(
        stage_processed / "train_metadata.csv", index=False
    )
    metadata["validation"].to_csv(
        stage_processed / "val_metadata.csv", index=False
    )
    write_json_atomic(
        stage_processed / "split_manifest.json", prepared["manifest"]
    )
    prepared["session_statistics"].to_csv(
        stage_results / "session_statistics.csv", index=False
    )

    history_frame = pd.DataFrame(history.history)
    history_frame.insert(0, "epoch", np.arange(1, len(history_frame) + 1))
    history_frame.to_csv(stage_results / "training_history.csv", index=False)
    (stage_results / "model_summary.txt").write_text(
        "\n".join(summary_lines) + "\n", encoding="utf-8"
    )
    validation_result = metadata["validation"].copy()
    validation_result["reconstruction_error_mse"] = validation_errors
    validation_result["threshold"] = threshold
    validation_result["predicted_label"] = (
        validation_errors > threshold
    ).astype(np.int8)
    validation_result.to_csv(
        stage_results / "validation_reconstruction_errors.csv", index=False
    )

    threshold_document = {
        "profile_name": profile["profile_name"],
        "normal_validation_only": True,
        "test_or_anomaly_data_used": False,
        "method": "99th percentile of normal validation reconstruction MSE",
        "percentile": THRESHOLD_PERCENTILE,
        "decision_rule": {
            "normal": "reconstruction_error <= selected_threshold",
            "anomaly": "reconstruction_error > selected_threshold",
        },
        "validation_statistics": threshold_statistics,
        "validation_windows_above_threshold": validation_above_count,
        "validation_fraction_above_threshold": validation_above_fraction,
        "selected_threshold": threshold,
        "threshold": threshold,
    }
    write_json_atomic(stage_models / "threshold.json", threshold_document)
    write_json_atomic(stage_results / "tflite_consistency.json", consistency)

    best_epoch_index = int(np.argmin(history.history["val_loss"]))
    training_summary = {
        "profile_name": profile["profile_name"],
        "random_seeds": {
            "python": RANDOM_SEED,
            "numpy": RANDOM_SEED,
            "tensorflow": RANDOM_SEED,
        },
        "normal_data_only": True,
        "training_files": prepared["manifest"]["train_files"],
        "validation_files": prepared["manifest"]["validation_files"],
        "training_windows": int(len(x_train)),
        "validation_windows": int(len(x_validation)),
        "batch_size": BATCH_SIZE,
        "maximum_epochs": MAX_EPOCHS,
        "epochs_trained": int(len(history.history["loss"])),
        "best_epoch": best_epoch_index + 1,
        "early_stopping_patience": EARLY_STOPPING_PATIENCE,
        "final_train_loss": float(history.history["loss"][-1]),
        "final_validation_loss": float(history.history["val_loss"][-1]),
        "best_train_loss": float(history.history["loss"][best_epoch_index]),
        "best_validation_loss": float(
            history.history["val_loss"][best_epoch_index]
        ),
        "train_reconstruction_mse": {
            "mean": float(np.mean(train_errors)),
            "std": float(np.std(train_errors)),
            "minimum": float(np.min(train_errors)),
            "maximum": float(np.max(train_errors)),
        },
        "validation_reconstruction_mse": threshold_statistics,
        "validation_fraction_above_threshold": validation_above_fraction,
        "validation_quality_warning": quality_warning,
        "validation_size_warning": validation_size_warning,
        "threshold": threshold,
        "threshold_method": threshold_document["method"],
        "tensorflow_version": tf.__version__,
        "trainable_parameters": int(best_model.count_params()),
        "architecture": [
            {
                "class_name": layer.__class__.__name__,
                "name": layer.name,
                "config": {
                    key: value
                    for key, value in layer.get_config().items()
                    if key
                    in {
                        "filters",
                        "kernel_size",
                        "pool_size",
                        "size",
                        "padding",
                        "activation",
                    }
                },
            }
            for layer in best_model.layers
        ],
    }
    write_json_atomic(stage_results / "training_summary.json", training_summary)

    return {
        "threshold": threshold,
        "threshold_document": threshold_document,
        "training_summary": training_summary,
        "consistency": consistency,
        "quality_warning": quality_warning,
        "validation_size_warning": validation_size_warning,
        "scaler_mean": [float(value) for value in prepared["scaler"].mean_],
        "scaler_scale": [float(value) for value in prepared["scaler"].scale_],
    }


def commit_stage(stage: Path, profile_root: Path) -> list[Path]:
    staged_files = sorted(path for path in stage.rglob("*") if path.is_file())
    destinations = [profile_root / path.relative_to(stage) for path in staged_files]
    collisions = [path for path in destinations if path.exists()]
    if collisions:
        raise FileExistsError(
            "Trainingsartefakte existieren bereits und werden nicht überschrieben: "
            + ", ".join(str(path) for path in collisions)
        )
    for source, destination in zip(staged_files, destinations):
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
    return destinations


def finalize_profile_metadata(
    paths: ProfilePaths,
    profile: dict[str, Any],
    outcome: dict[str, Any],
) -> None:
    summary = outcome["training_summary"]
    manifest_path = paths.processed / "split_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scaler_path = paths.models / "scaler.joblib"
    keras_path = paths.models / "autoencoder.keras"
    tflite_path = paths.models / "autoencoder_float32.tflite"
    threshold_path = paths.models / "threshold.json"

    profile["data"].update(
        {
            "training_files": manifest["train_files"],
            "validation_files": manifest["validation_files"],
            "training_windows": manifest["training_window_count"],
            "validation_windows": manifest["validation_window_count"],
            "split_manifest_path": stable_path(manifest_path),
        }
    )
    profile["training_windows"] = manifest["training_window_count"]
    profile["validation_windows"] = manifest["validation_window_count"]
    profile["scaler"] = {
        "path": stable_path(scaler_path),
        "sha256": sha256_file(scaler_path),
        "type": "sklearn.preprocessing.StandardScaler",
        "fit_data": "Normal training samples only",
        "mean": outcome["scaler_mean"],
        "scale": outcome["scaler_scale"],
    }
    profile["autoencoder"] = {
        "keras_model_path": stable_path(keras_path),
        "keras_model_sha256": sha256_file(keras_path),
        "tflite_model_path": stable_path(tflite_path),
        "tflite_model_sha256": sha256_file(tflite_path),
        "input_shape": list(EXPECTED_WINDOW_SHAPE),
        "architecture": summary["architecture"],
        "trainable_parameters": summary["trainable_parameters"],
        "tensorflow_version": summary["tensorflow_version"],
        "tflite_numeric_format": "Float32",
        "quantized": False,
    }
    profile["training"] = {
        key: summary[key]
        for key in (
            "random_seeds",
            "batch_size",
            "maximum_epochs",
            "epochs_trained",
            "best_epoch",
            "early_stopping_patience",
            "final_train_loss",
            "final_validation_loss",
            "best_train_loss",
            "best_validation_loss",
        )
    }
    profile["threshold"] = {
        "path": stable_path(threshold_path),
        "sha256": sha256_file(threshold_path),
        "selected_threshold": outcome["threshold"],
        "method": outcome["threshold_document"]["method"],
        "normal_validation_only": True,
        "validation_statistics": outcome["threshold_document"][
            "validation_statistics"
        ],
        "validation_fraction_above_threshold": outcome["threshold_document"][
            "validation_fraction_above_threshold"
        ],
    }
    profile["tflite_consistency"] = outcome["consistency"]
    profile["artifacts"] = {
        "scaler": stable_path(scaler_path),
        "keras_model": stable_path(keras_path),
        "tflite_model": stable_path(tflite_path),
        "threshold": stable_path(threshold_path),
        "training_history": stable_path(paths.results / "training_history.csv"),
        "training_summary": stable_path(paths.results / "training_summary.json"),
        "model_summary": stable_path(paths.results / "model_summary.txt"),
        "validation_errors": stable_path(
            paths.results / "validation_reconstruction_errors.csv"
        ),
        "tflite_consistency": stable_path(
            paths.results / "tflite_consistency.json"
        ),
        "session_statistics": stable_path(
            paths.results / "session_statistics.csv"
        ),
    }
    if outcome["quality_warning"]:
        profile["warnings"].append(
            "Ungewöhnlich hoher Anteil normaler Validierungsfenster über P99."
        )
    if outcome["validation_size_warning"]:
        profile["warnings"].append(
            "Weniger als 100 Validierungsfenster; P99 ist statistisch nur schwach abgestützt."
        )
    update_profile_status(paths, profile, "ready")


def train_profile(paths: ProfilePaths, profile: dict[str, Any]) -> None:
    if profile.get("status") not in {"recorded", "training_failed"}:
        raise ValueError(
            f"Profilstatus {profile.get('status')!r} erlaubt kein Training."
        )
    final_artifact_names = [
        paths.models / "scaler.joblib",
        paths.models / "autoencoder.keras",
        paths.models / "autoencoder_float32.tflite",
        paths.models / "threshold.json",
    ]
    if any(path.exists() for path in final_artifact_names):
        raise FileExistsError(
            "Mindestens ein finales Modellartefakt existiert bereits; "
            "Train-only überschreibt es nicht."
        )

    update_profile_status(paths, profile, "training")
    try:
        print("Datenaufbereitung ...")
        prepared = prepare_profile_data(paths, profile)
        print("Scaler wird ausschließlich auf Trainingsdateien erstellt ...")
        print("Autoencoder wird trainiert ...")
        with tempfile.TemporaryDirectory(
            prefix=".training_stage_", dir=paths.root
        ) as temporary_name:
            stage = Path(temporary_name)
            outcome = write_training_stage(stage, prepared, profile)
            committed = commit_stage(stage, paths.root)
        finalize_profile_metadata(paths, profile, outcome)
    except Exception as error:
        update_profile_status(
            paths, profile, "training_failed", error=error
        )
        raise

    print("\nKalibrierung erfolgreich.")
    print(f"Profil: {profile['profile_name']}")
    print(f"Threshold: {outcome['threshold']:.10f}")
    validation = outcome["threshold_document"]["validation_statistics"]
    print(f"Validation-MSE Mittelwert: {validation['mean_mse']:.10f}")
    print(f"Validation-MSE P95: {validation['percentile_95_mse']:.10f}")
    print(f"Validation-MSE P99: {validation['percentile_99_mse']:.10f}")
    print(
        "Validation-Fenster über Threshold: "
        f"{outcome['threshold_document']['validation_windows_above_threshold']} "
        f"({outcome['threshold_document']['validation_fraction_above_threshold']:.2%})"
    )
    if outcome["quality_warning"]:
        print("WARNUNG: ungewöhnlich viele normale Validation-Fenster liegen darüber.")
    if outcome["validation_size_warning"]:
        print("WARNUNG: weniger als 100 Validation-Fenster für die P99-Schätzung.")
    print(f"TFLite-Modell: {stable_path(paths.models / 'autoencoder_float32.tflite')}")
    print("Start Live Monitoring mit:")
    print(
        f".venv_tf/bin/python src/live_tflite_monitor.py "
        f"--profile {profile['profile_name']}"
    )
    print(f"Erzeugte Trainingsartefakte: {len(committed)}")


def print_dry_run(
    arguments: argparse.Namespace, profiles_root: Path
) -> None:
    if arguments.train_only:
        validate_profile_name(arguments.profile)
        paths = ProfilePaths.create(profiles_root, arguments.profile)
        if not paths.root.is_dir():
            raise FileNotFoundError(
                f"Train-only benötigt ein vorhandenes Profil: {paths.root}"
            )
        action = "Vorhandene Normalaufnahmen aufbereiten und trainieren"
        resolved_name = arguments.profile
        profile = read_profile(paths)
        if profile.get("profile_name") != arguments.profile:
            raise ValueError(
                "Profilname in profile.json stimmt nicht mit --profile überein."
            )
        configuration = profile["configuration"]
    else:
        resolved_name, _ = allocate_profile_name(
            profiles_root, arguments.profile, arguments.new_version
        )
        paths = ProfilePaths.create(profiles_root, resolved_name)
        action = (
            "Profil anlegen und Normaldaten aufnehmen"
            if arguments.record_only
            else "Profil anlegen, Normaldaten aufnehmen und vollständig trainieren"
        )
        configuration = calibration_configuration(arguments)
    print("Dry-Run – keine Verzeichnisse, Sensorzugriffe oder Trainingsläufe.")
    print(f"Aktion: {action}")
    print(f"Profil: {resolved_name}")
    print(f"Profilpfad: {paths.root}")
    print(json.dumps(configuration, indent=2, ensure_ascii=False))
    print("Geplante Struktur:")
    for path in (
        paths.raw,
        paths.processed,
        paths.models,
        paths.results,
        paths.metadata,
    ):
        print(f"  {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Setup-spezifische Normalzustandskalibrierung: Aufnahme, "
            "dateibasierter Split, Scaler, Autoencoder, Validation-P99 und TFLite."
        )
    )
    parser.add_argument("--profile", required=True, help="Profilname, z.B. uni")
    parser.add_argument(
        "--recordings",
        type=int,
        default=DEFAULT_RECORDINGS,
        help=f"Anzahl separater Normalaufnahmen (Standard: {DEFAULT_RECORDINGS})",
    )
    parser.add_argument(
        "--validation-recordings",
        type=int,
        default=DEFAULT_VALIDATION_RECORDINGS,
        help=(
            "Anzahl der letzten Dateien für Validation "
            f"(Standard: {DEFAULT_VALIDATION_RECORDINGS})"
        ),
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=DEFAULT_SECONDS,
        help=f"Dauer je Aufnahme (Standard: {DEFAULT_SECONDS:g} s)",
    )
    parser.add_argument(
        "--sampling-rate",
        type=int,
        default=DEFAULT_SAMPLING_RATE_HZ,
        help=f"Software-Samplingrate (Standard: {DEFAULT_SAMPLING_RATE_HZ} Hz)",
    )
    parser.add_argument(
        "--description",
        default=None,
        help="Optionale Beschreibung von Montage und mechanischem Aufbau.",
    )
    parser.add_argument(
        "--new-version",
        action="store_true",
        help="Bei vorhandenem Profil automatisch <name>_vNNN anlegen.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--record-only",
        action="store_true",
        help="Nur Profil und Normalaufnahmen erzeugen; später --train-only nutzen.",
    )
    mode.add_argument(
        "--train-only",
        action="store_true",
        help="Vorhandenes aufgenommenes Profil ohne neue Sensoraufnahme trainieren.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pfade und Ablauf prüfen, ohne Dateien, Sensorzugriff oder Training.",
    )
    parser.add_argument(
        "--profiles-root",
        type=Path,
        default=DEFAULT_PROFILES_DIRECTORY,
        help=argparse.SUPPRESS,
    )
    arguments = parser.parse_args()

    if arguments.recordings < 2:
        parser.error("--recordings muss mindestens 2 sein.")
    if not 1 <= arguments.validation_recordings < arguments.recordings:
        parser.error(
            "--validation-recordings muss mindestens 1 und kleiner als "
            "--recordings sein."
        )
    if arguments.seconds <= 0:
        parser.error("--seconds muss positiv sein.")
    if arguments.sampling_rate <= 0:
        parser.error("--sampling-rate muss positiv sein.")
    if arguments.train_only and arguments.new_version:
        parser.error("--new-version ist mit --train-only nicht zulässig.")
    try:
        validate_profile_name(arguments.profile)
    except ValueError as error:
        parser.error(str(error))
    return arguments


def main() -> None:
    arguments = parse_args()
    profiles_root = arguments.profiles_root.resolve()
    if arguments.dry_run:
        print_dry_run(arguments, profiles_root)
        return

    if arguments.train_only:
        paths = ProfilePaths.create(profiles_root, arguments.profile)
        profile = read_profile(paths)
        if profile.get("profile_name") != arguments.profile:
            raise ValueError(
                "Profilname in profile.json stimmt nicht mit --profile überein."
            )
        train_profile(paths, profile)
        return

    configuration = calibration_configuration(arguments)
    paths, profile = initialize_profile(
        profiles_root=profiles_root,
        base_name=arguments.profile,
        new_version=arguments.new_version,
        configuration=configuration,
        description=arguments.description,
    )
    try:
        record_normal_sessions(paths, profile)
    except Exception as error:
        update_profile_status(paths, profile, "recording_failed", error=error)
        raise
    if arguments.record_only:
        print("Normalaufnahmen abgeschlossen; Training wurde nicht gestartet.")
        print(
            ".venv_tf/bin/python src/calibrate_and_train.py "
            f"--profile {profile['profile_name']} --train-only"
        )
        return
    train_profile(paths, profile)


if __name__ == "__main__":
    main()
