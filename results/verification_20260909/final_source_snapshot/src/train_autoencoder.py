"""Train a compact TensorFlow autoencoder on normal ADXL345 windows."""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

# These flags must be set before TensorFlow is imported.
os.environ.setdefault("TF_DETERMINISTIC_OPS", "1")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import pandas as pd
import tensorflow as tf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = PROJECT_ROOT / "data" / "comparison"
MODEL_DIRECTORY = PROJECT_ROOT / "models" / "tensorflow"
RESULT_DIRECTORY = PROJECT_ROOT / "results"

X_TRAIN_PATH = DATA_DIRECTORY / "X_train.npy"
X_VALIDATION_PATH = DATA_DIRECTORY / "X_val.npy"
X_TEST_PATH = DATA_DIRECTORY / "X_test.npy"
Y_TRAIN_PATH = DATA_DIRECTORY / "y_train.npy"
Y_VALIDATION_PATH = DATA_DIRECTORY / "y_val.npy"
Y_TEST_PATH = DATA_DIRECTORY / "y_test.npy"

MODEL_PATH = MODEL_DIRECTORY / "autoencoder.keras"
HISTORY_PATH = RESULT_DIRECTORY / "tensorflow_training_history.csv"
ERRORS_PATH = RESULT_DIRECTORY / "tensorflow_reconstruction_errors.csv"
SUMMARY_PATH = RESULT_DIRECTORY / "tensorflow_training_summary.json"
MODEL_SUMMARY_PATH = RESULT_DIRECTORY / "tensorflow_model_summary.txt"

RANDOM_SEED = 42
EXPECTED_INPUT_SHAPE = (128, 3)
MAX_EPOCHS = 100
BATCH_SIZE = 32
LEARNING_RATE = 1e-3
EARLY_STOPPING_PATIENCE = 10
EARLY_STOPPING_MIN_DELTA = 1e-6


def relative_path(path: Path) -> str:
    """Return a stable repository-relative path for result files."""

    return str(path.relative_to(PROJECT_ROOT))


def configure_reproducibility() -> None:
    """Seed Python, NumPy and TensorFlow and request deterministic ops."""

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    tf.keras.utils.set_random_seed(RANDOM_SEED)
    try:
        tf.config.experimental.enable_op_determinism()
    except AttributeError:
        # Kept for compatibility with TensorFlow versions that only honour
        # TF_DETERMINISTIC_OPS.
        pass


def load_array(path: Path) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(
            f"Fehlende Eingabedatei: {relative_path(path)}. "
            "Zuerst ausführen: python src/prepare_comparison_data.py"
        )
    return np.load(path, allow_pickle=False)


def load_and_validate_data() -> tuple[
    dict[str, np.ndarray], dict[str, np.ndarray]
]:
    """Load prepared tensors and enforce training-data invariants."""

    features = {
        "train": load_array(X_TRAIN_PATH),
        "validation": load_array(X_VALIDATION_PATH),
        "test": load_array(X_TEST_PATH),
    }
    labels = {
        "train": load_array(Y_TRAIN_PATH),
        "validation": load_array(Y_VALIDATION_PATH),
        "test": load_array(Y_TEST_PATH),
    }

    for split, split_features in features.items():
        if split_features.ndim != 3:
            raise ValueError(
                f"{split}: drei Tensor-Dimensionen erwartet, "
                f"erhalten: {split_features.shape}"
            )
        if tuple(split_features.shape[1:]) != EXPECTED_INPUT_SHAPE:
            raise ValueError(
                f"{split}: erwartete Fensterform {EXPECTED_INPUT_SHAPE}, "
                f"erhalten: {split_features.shape[1:]}"
            )
        if len(split_features) != len(labels[split]):
            raise ValueError(
                f"{split}: Anzahl Fenster und Labels stimmt nicht überein."
            )
        if not np.isfinite(split_features).all():
            raise ValueError(f"{split}: nicht-endliche Tensorwerte gefunden.")

    if np.any(labels["train"] != 0):
        raise ValueError("Autoencoder-Training darf nur Normalfenster enthalten.")
    if np.any(labels["validation"] != 0):
        raise ValueError("Validierung darf nur Normalfenster enthalten.")

    return features, labels


def build_autoencoder() -> tf.keras.Model:
    """Build a small temporal convolutional autoencoder for Raspberry Pi 5."""

    inputs = tf.keras.Input(shape=EXPECTED_INPUT_SHAPE, name="xyz_window")

    encoded = tf.keras.layers.Conv1D(
        filters=8,
        kernel_size=5,
        padding="same",
        activation="relu",
        name="encoder_conv_1",
    )(inputs)
    encoded = tf.keras.layers.MaxPooling1D(
        pool_size=2, padding="same", name="encoder_pool_1"
    )(encoded)
    encoded = tf.keras.layers.Conv1D(
        filters=4,
        kernel_size=3,
        padding="same",
        activation="relu",
        name="encoder_conv_2",
    )(encoded)
    encoded = tf.keras.layers.MaxPooling1D(
        pool_size=2, padding="same", name="bottleneck"
    )(encoded)

    decoded = tf.keras.layers.Conv1D(
        filters=4,
        kernel_size=3,
        padding="same",
        activation="relu",
        name="decoder_conv_1",
    )(encoded)
    decoded = tf.keras.layers.UpSampling1D(
        size=2, name="decoder_upsample_1"
    )(decoded)
    decoded = tf.keras.layers.Conv1D(
        filters=8,
        kernel_size=3,
        padding="same",
        activation="relu",
        name="decoder_conv_2",
    )(decoded)
    decoded = tf.keras.layers.UpSampling1D(
        size=2, name="decoder_upsample_2"
    )(decoded)
    outputs = tf.keras.layers.Conv1D(
        filters=3,
        kernel_size=5,
        padding="same",
        activation="linear",
        name="reconstruction",
    )(decoded)

    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="xyz_autoencoder")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss="mse",
    )
    return model


def reconstruction_errors(
    model: tf.keras.Model,
    features: np.ndarray,
) -> np.ndarray:
    """Return one mean squared reconstruction error per window."""

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


def load_metadata(split: str) -> pd.DataFrame:
    short_name = "val" if split == "validation" else split
    path = DATA_DIRECTORY / f"{short_name}_metadata.csv"
    if not path.exists():
        raise FileNotFoundError(f"Metadaten fehlen: {relative_path(path)}")
    return pd.read_csv(path)


def save_reconstruction_errors(
    model: tf.keras.Model,
    features: dict[str, np.ndarray],
) -> dict[str, dict[str, float | int]]:
    """Calculate errors for all splits without selecting a threshold."""

    error_frames: list[pd.DataFrame] = []
    error_summary: dict[str, dict[str, float | int]] = {}

    for split, split_features in features.items():
        errors = reconstruction_errors(model, split_features)
        split_metadata = load_metadata(split)

        if len(split_metadata) != len(errors):
            raise ValueError(
                f"{split}: Metadaten und Rekonstruktionsfehler unterscheiden "
                "sich in der Länge."
            )

        result = split_metadata.copy()
        result["reconstruction_error_mse"] = errors
        error_frames.append(result)
        error_summary[split] = {
            "window_count": int(len(errors)),
            "mean_mse": float(np.mean(errors)),
            "standard_deviation_mse": float(np.std(errors, ddof=0)),
            "minimum_mse": float(np.min(errors)),
            "maximum_mse": float(np.max(errors)),
        }

    pd.concat(error_frames, ignore_index=True).to_csv(
        ERRORS_PATH, index=False
    )
    return error_summary


def main() -> None:
    configure_reproducibility()
    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    features, labels = load_and_validate_data()
    model = build_autoencoder()

    model_summary_lines: list[str] = []
    model.summary(print_fn=model_summary_lines.append)
    model_summary_text = "\n".join(model_summary_lines)
    MODEL_SUMMARY_PATH.write_text(model_summary_text + "\n", encoding="utf-8")
    print(model_summary_text)

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
        features["train"],
        features["train"],
        validation_data=(features["validation"], features["validation"]),
        epochs=MAX_EPOCHS,
        batch_size=BATCH_SIZE,
        shuffle=True,
        callbacks=callbacks,
        verbose=2,
    )

    # ModelCheckpoint contains the epoch with the lowest validation loss.
    # Reload it before calculating reconstruction errors for every split.
    best_model = tf.keras.models.load_model(MODEL_PATH)

    history_frame = pd.DataFrame(history.history)
    history_frame.insert(0, "epoch", np.arange(1, len(history_frame) + 1))
    history_frame.to_csv(HISTORY_PATH, index=False)

    error_summary = save_reconstruction_errors(best_model, features)

    best_epoch_index = int(np.argmin(history.history["val_loss"]))
    training_summary = {
        "random_seed": RANDOM_SEED,
        "tensorflow_version": tf.__version__,
        "input_shape": list(EXPECTED_INPUT_SHAPE),
        "trainable_parameters": int(
            np.sum([np.prod(weight.shape) for weight in best_model.trainable_weights])
        ),
        "training": {
            "training_windows": int(len(features["train"])),
            "validation_windows": int(len(features["validation"])),
            "test_windows_not_used_for_fitting": int(len(features["test"])),
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
            "note": (
                "No threshold was selected or optimized in Phase 2. Test "
                "labels were not used for training or threshold selection."
            ),
        },
        "reconstruction_error": {
            "definition": "Mean squared error over all 128 x 3 values per window",
            "splits": error_summary,
        },
        "artifacts": {
            "model": relative_path(MODEL_PATH),
            "history": relative_path(HISTORY_PATH),
            "reconstruction_errors": relative_path(ERRORS_PATH),
            "model_summary": relative_path(MODEL_SUMMARY_PATH),
        },
        "label_distributions": {
            split: {
                "normal": int(np.count_nonzero(split_labels == 0)),
                "anomaly": int(np.count_nonzero(split_labels == 1)),
            }
            for split, split_labels in labels.items()
        },
    }

    with SUMMARY_PATH.open("w", encoding="utf-8") as file:
        json.dump(training_summary, file, indent=2, ensure_ascii=False)

    print("\nAutoencoder-Training abgeschlossen.")
    print(f"Trainierte Epochen: {len(history.history['loss'])}")
    print(f"Beste Epoche: {best_epoch_index + 1}")
    print(f"Finaler Training Loss: {history.history['loss'][-1]:.8f}")
    print(f"Finaler Validation Loss: {history.history['val_loss'][-1]:.8f}")
    print(f"Bester Validation Loss: {history.history['val_loss'][best_epoch_index]:.8f}")
    print(f"Gespeichertes Modell: {relative_path(MODEL_PATH)}")
    print("Kein Threshold wurde ausgewählt oder anhand von Testlabels optimiert.")


if __name__ == "__main__":
    main()
