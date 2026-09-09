"""Train a separate autoencoder on the controlled 2026-08-23 split."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/masterarbeit-matplotlib-cache")
os.environ.setdefault("TF_DETERMINISTIC_OPS", "1")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import pandas as pd
import tensorflow as tf

from train_autoencoder import build_autoencoder, configure_reproducibility


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = PROJECT_ROOT / "data" / "clean_comparison"
MODEL_DIRECTORY = PROJECT_ROOT / "models" / "clean_comparison"
RESULT_DIRECTORY = PROJECT_ROOT / "results"

MODEL_PATH = MODEL_DIRECTORY / "autoencoder.keras"
HISTORY_PATH = RESULT_DIRECTORY / "clean_tensorflow_training_history.csv"
ERRORS_PATH = RESULT_DIRECTORY / "clean_tensorflow_reconstruction_errors.csv"
SUMMARY_PATH = RESULT_DIRECTORY / "clean_tensorflow_training_summary.json"
MODEL_SUMMARY_PATH = RESULT_DIRECTORY / "clean_tensorflow_model_summary.txt"

EXPECTED_WINDOW_SHAPE = (128, 3)
MAX_EPOCHS = 100
BATCH_SIZE = 32
EARLY_STOPPING_PATIENCE = 10
EARLY_STOPPING_MIN_DELTA = 1e-6
RANDOM_SEED = 42


def relative_path(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def load_array(filename: str) -> np.ndarray:
    path = DATA_DIRECTORY / filename
    if not path.exists():
        raise FileNotFoundError(f"Fehlende Datei: {relative_path(path)}")
    return np.load(path, allow_pickle=False)


def validate_split(
    features: np.ndarray,
    labels: np.ndarray,
    split: str,
    *,
    require_normal: bool,
) -> None:
    if features.ndim != 3 or tuple(features.shape[1:]) != EXPECTED_WINDOW_SHAPE:
        raise ValueError(
            f"{split}: erwartete Tensorform (N, 128, 3), "
            f"erhalten {features.shape}"
        )
    if len(features) != len(labels):
        raise ValueError(f"{split}: Fenster und Labels sind inkonsistent.")
    if not np.isfinite(features).all():
        raise ValueError(f"{split}: nicht-endliche Werte gefunden.")
    if require_normal and np.any(labels != 0):
        raise ValueError(f"{split}: darf nur normale Fenster enthalten.")


def reconstruction_errors(
    model: tf.keras.Model,
    features: np.ndarray,
) -> np.ndarray:
    reconstructions = model.predict(
        features,
        batch_size=BATCH_SIZE,
        verbose=0,
    )
    return np.mean(
        np.square(features - reconstructions),
        axis=(1, 2),
        dtype=np.float64,
    )


def save_errors(
    model: tf.keras.Model,
    split_data: dict[str, tuple[np.ndarray, np.ndarray]],
) -> dict[str, dict[str, float | int]]:
    frames: list[pd.DataFrame] = []
    summaries: dict[str, dict[str, float | int]] = {}

    for split, (features, labels) in split_data.items():
        short_name = "val" if split == "validation" else split
        metadata_path = DATA_DIRECTORY / f"{short_name}_metadata.csv"
        metadata = pd.read_csv(metadata_path)
        errors = reconstruction_errors(model, features)
        if len(metadata) != len(errors):
            raise ValueError(f"{split}: Metadatenlänge stimmt nicht.")
        if not np.array_equal(
            labels.astype(np.int8), metadata["label"].to_numpy(dtype=np.int8)
        ):
            raise ValueError(f"{split}: Metadatenlabels stimmen nicht.")

        frame = metadata.copy()
        frame["reconstruction_error_mse"] = errors
        frames.append(frame)
        summaries[split] = {
            "window_count": int(len(errors)),
            "mean_mse": float(np.mean(errors)),
            "standard_deviation_mse": float(np.std(errors, ddof=0)),
            "minimum_mse": float(np.min(errors)),
            "maximum_mse": float(np.max(errors)),
        }

    pd.concat(frames, ignore_index=True).to_csv(ERRORS_PATH, index=False)
    return summaries


def main() -> None:
    configure_reproducibility()
    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # Only training and validation data are loaded before model.fit.
    x_train = load_array("X_train.npy")
    y_train = load_array("y_train.npy").astype(np.int8)
    x_validation = load_array("X_val.npy")
    y_validation = load_array("y_val.npy").astype(np.int8)
    validate_split(x_train, y_train, "train", require_normal=True)
    validate_split(
        x_validation, y_validation, "validation", require_normal=True
    )

    model = build_autoencoder()
    summary_lines: list[str] = []
    model.summary(print_fn=summary_lines.append)
    summary_text = "\n".join(summary_lines)
    MODEL_SUMMARY_PATH.write_text(summary_text + "\n", encoding="utf-8")
    print(summary_text)

    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            filepath=MODEL_PATH,
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

    best_model = tf.keras.models.load_model(MODEL_PATH)
    history_frame = pd.DataFrame(history.history)
    history_frame.insert(0, "epoch", np.arange(1, len(history_frame) + 1))
    history_frame.to_csv(HISTORY_PATH, index=False)

    # Test data are deliberately loaded only after fitting has completed.
    x_test = load_array("X_test.npy")
    y_test = load_array("y_test.npy").astype(np.int8)
    validate_split(x_test, y_test, "test", require_normal=False)

    error_summary = save_errors(
        best_model,
        {
            "train": (x_train, y_train),
            "validation": (x_validation, y_validation),
            "test": (x_test, y_test),
        },
    )
    best_epoch_index = int(np.argmin(history.history["val_loss"]))
    parameter_count = int(best_model.count_params())

    training_summary = {
        "experiment": "clean_comparison_20260823",
        "random_seed": RANDOM_SEED,
        "tensorflow_version": tf.__version__,
        "input_shape": list(EXPECTED_WINDOW_SHAPE),
        "trainable_parameters": parameter_count,
        "training": {
            "training_windows": int(len(x_train)),
            "validation_windows": int(len(x_validation)),
            "test_windows_not_used_for_fitting": int(len(x_test)),
            "batch_size": BATCH_SIZE,
            "maximum_epochs": MAX_EPOCHS,
            "epochs_trained": int(len(history.history["loss"])),
            "early_stopping_patience": EARLY_STOPPING_PATIENCE,
            "best_epoch": best_epoch_index + 1,
            "final_training_loss": float(history.history["loss"][-1]),
            "final_validation_loss": float(history.history["val_loss"][-1]),
            "best_training_loss": float(history.history["loss"][best_epoch_index]),
            "best_validation_loss": float(
                history.history["val_loss"][best_epoch_index]
            ),
        },
        "threshold": {
            "selected": False,
            "note": "Threshold is selected later from normal validation MSE only.",
        },
        "reconstruction_error": {
            "definition": "MSE over all 128 x 3 values per window",
            "splits": error_summary,
        },
        "artifacts": {
            "model": relative_path(MODEL_PATH),
            "history": relative_path(HISTORY_PATH),
            "reconstruction_errors": relative_path(ERRORS_PATH),
            "model_summary": relative_path(MODEL_SUMMARY_PATH),
        },
    }
    with SUMMARY_PATH.open("w", encoding="utf-8") as file:
        json.dump(training_summary, file, indent=2, ensure_ascii=False)

    print("\nClean-Autoencoder-Training abgeschlossen.")
    print(f"Trainierte Epochen: {len(history.history['loss'])}")
    print(f"Beste Epoche: {best_epoch_index + 1}")
    print(f"Finaler Training Loss: {history.history['loss'][-1]:.8f}")
    print(f"Finaler Validation Loss: {history.history['val_loss'][-1]:.8f}")
    print(
        "Bester Validation Loss: "
        f"{history.history['val_loss'][best_epoch_index]:.8f}"
    )
    print(f"Modell: {relative_path(MODEL_PATH)}")
    print("Testdaten wurden erst nach model.fit geladen.")


if __name__ == "__main__":
    main()
