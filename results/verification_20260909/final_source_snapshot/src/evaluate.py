"""Evaluate the frozen TensorFlow autoencoder on the Phase-2 split."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/masterarbeit-matplotlib-cache")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import ConfusionMatrixDisplay

from comparison_metrics import (
    calculate_binary_metrics,
    calculate_session_metrics,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = PROJECT_ROOT / "data" / "comparison"
MODEL_PATH = PROJECT_ROOT / "models" / "tensorflow" / "autoencoder.keras"
RESULT_DIRECTORY = PROJECT_ROOT / "results"
FIGURE_DIRECTORY = PROJECT_ROOT / "figures"

X_VALIDATION_PATH = DATA_DIRECTORY / "X_val.npy"
Y_VALIDATION_PATH = DATA_DIRECTORY / "y_val.npy"
X_TEST_PATH = DATA_DIRECTORY / "X_test.npy"
Y_TEST_PATH = DATA_DIRECTORY / "y_test.npy"
TEST_METADATA_PATH = DATA_DIRECTORY / "test_metadata.csv"

THRESHOLD_PATH = RESULT_DIRECTORY / "tensorflow_threshold.json"
METRICS_PATH = RESULT_DIRECTORY / "tensorflow_test_metrics.json"
PREDICTIONS_PATH = RESULT_DIRECTORY / "tensorflow_test_predictions.csv"
SESSION_METRICS_PATH = (
    RESULT_DIRECTORY / "tensorflow_metrics_by_session.csv"
)

ERROR_DISTRIBUTION_FIGURE = (
    FIGURE_DIRECTORY / "tensorflow_reconstruction_error_distribution.png"
)
ERROR_SEQUENCE_FIGURE = (
    FIGURE_DIRECTORY / "tensorflow_reconstruction_error_test_sequence.png"
)
CONFUSION_MATRIX_FIGURE = (
    FIGURE_DIRECTORY / "tensorflow_confusion_matrix_comparison.png"
)

THRESHOLD_PERCENTILE = 99.0
BATCH_SIZE = 32
EXPECTED_WINDOW_SHAPE = (128, 3)


def relative_path(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def load_array(path: Path) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(f"Fehlende Datei: {relative_path(path)}")
    return np.load(path, allow_pickle=False)


def validate_features(features: np.ndarray, split: str) -> None:
    if features.ndim != 3 or tuple(features.shape[1:]) != EXPECTED_WINDOW_SHAPE:
        raise ValueError(
            f"{split}: erwartete Tensorform (N, 128, 3), "
            f"erhalten: {features.shape}"
        )
    if not np.isfinite(features).all():
        raise ValueError(f"{split}: nicht-endliche Werte gefunden.")


def calculate_reconstruction_errors(
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


def describe_validation_errors(errors: np.ndarray) -> dict[str, float | int]:
    """Describe normal validation MSE before any test data are loaded."""

    return {
        "validation_window_count": int(len(errors)),
        "mean_mse": float(np.mean(errors)),
        "standard_deviation_mse": float(np.std(errors, ddof=0)),
        "median_mse": float(np.median(errors)),
        "percentile_95_mse": float(np.percentile(errors, 95)),
        "percentile_99_mse": float(np.percentile(errors, 99)),
        "maximum_mse": float(np.max(errors)),
    }


def save_error_distribution(
    errors: np.ndarray,
    labels: np.ndarray,
    threshold: float,
) -> None:
    normal_errors = errors[labels == 0]
    anomaly_errors = errors[labels == 1]
    positive_errors = errors[errors > 0]
    lower_bound = max(float(np.min(positive_errors)), np.finfo(float).eps)
    upper_bound = float(np.max(errors))
    bins = np.geomspace(lower_bound, upper_bound, 45)

    figure, axis = plt.subplots(figsize=(10, 6))
    axis.hist(
        normal_errors,
        bins=bins,
        alpha=0.65,
        label=f"Normal (n={len(normal_errors)})",
        color="tab:blue",
    )
    axis.hist(
        anomaly_errors,
        bins=bins,
        alpha=0.65,
        label=f"Anomalie (n={len(anomaly_errors)})",
        color="tab:red",
    )
    axis.axvline(
        threshold,
        color="black",
        linestyle="--",
        linewidth=1.5,
        label=f"99. Perzentil Validation: {threshold:.6f}",
    )
    axis.set_xscale("log")
    axis.set_xlabel("Rekonstruktionsfehler (MSE, logarithmische Skala)")
    axis.set_ylabel("Anzahl Testfenster")
    axis.set_title("Verteilung der Autoencoder-Rekonstruktionsfehler")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(ERROR_DISTRIBUTION_FIGURE, dpi=250)
    plt.close(figure)


def save_error_sequence(
    predictions: pd.DataFrame,
    threshold: float,
) -> None:
    figure, axis = plt.subplots(figsize=(14, 6))
    axis.plot(
        predictions["split_index"],
        predictions["reconstruction_error"],
        color="0.55",
        linewidth=0.8,
        label="Rekonstruktionsfehler",
    )

    normal = predictions["true_label"] == 0
    anomaly = predictions["true_label"] == 1
    axis.scatter(
        predictions.loc[normal, "split_index"],
        predictions.loc[normal, "reconstruction_error"],
        s=10,
        color="tab:blue",
        label="Normal",
    )
    axis.scatter(
        predictions.loc[anomaly, "split_index"],
        predictions.loc[anomaly, "reconstruction_error"],
        s=14,
        color="tab:red",
        label="Anomalie",
    )
    axis.axhline(
        threshold,
        color="black",
        linestyle="--",
        linewidth=1.5,
        label=f"Threshold: {threshold:.6f}",
    )

    previous_file: str | None = None
    for row in predictions.itertuples(index=False):
        if previous_file is not None and row.source_file != previous_file:
            axis.axvline(row.split_index - 0.5, color="0.3", linestyle=":")
        previous_file = row.source_file

    axis.set_yscale("log")
    axis.set_xlabel("Testfenster in unveränderter Split-Reihenfolge")
    axis.set_ylabel("Rekonstruktionsfehler (MSE, logarithmische Skala)")
    axis.set_title("Autoencoder-Rekonstruktionsfehler über dem Testdatensatz")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(ERROR_SEQUENCE_FIGURE, dpi=250)
    plt.close(figure)


def save_confusion_matrix(
    labels: np.ndarray,
    predictions: np.ndarray,
) -> None:
    display = ConfusionMatrixDisplay.from_predictions(
        labels,
        predictions,
        labels=[0, 1],
        display_labels=["Normal", "Anomalie"],
        colorbar=False,
    )
    display.ax_.set_title("TensorFlow Autoencoder – Confusion Matrix")
    display.figure_.tight_layout()
    display.figure_.savefig(CONFUSION_MATRIX_FIGURE, dpi=250)
    plt.close(display.figure_)


def main() -> None:
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    FIGURE_DIRECTORY.mkdir(parents=True, exist_ok=True)

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Modell fehlt: {relative_path(MODEL_PATH)}")
    model = tf.keras.models.load_model(MODEL_PATH)
    if tuple(model.input_shape[1:]) != EXPECTED_WINDOW_SHAPE:
        raise ValueError(f"Unerwartete Modell-Eingabeform: {model.input_shape}")

    # Threshold selection is intentionally completed and persisted before
    # test features or test labels are loaded.
    validation_features = load_array(X_VALIDATION_PATH)
    validation_labels = load_array(Y_VALIDATION_PATH)
    validate_features(validation_features, "validation")
    if len(validation_features) != len(validation_labels):
        raise ValueError("Validation-Fenster und -Labels sind inkonsistent.")
    if np.any(validation_labels != 0):
        raise ValueError(
            "Der Threshold darf nur aus normalen Validation-Fenstern stammen."
        )

    validation_errors = calculate_reconstruction_errors(
        model, validation_features
    )
    validation_statistics = describe_validation_errors(validation_errors)
    threshold = validation_statistics["percentile_99_mse"]

    threshold_report = {
        "model": "TensorFlow Autoencoder",
        "model_path": relative_path(MODEL_PATH),
        "threshold_method": (
            "99th percentile of reconstruction MSE from normal validation "
            "windows only"
        ),
        "positive_class": "ANOMALY (1)",
        "decision_rule": {
            "normal": "reconstruction_error <= threshold",
            "anomaly": "reconstruction_error > threshold",
        },
        "test_labels_used_for_threshold_selection": False,
        "validation_statistics": validation_statistics,
        "threshold": threshold,
    }
    with THRESHOLD_PATH.open("w", encoding="utf-8") as file:
        json.dump(threshold_report, file, indent=2, ensure_ascii=False)

    # The frozen threshold is now applied exactly once to the test split.
    test_features = load_array(X_TEST_PATH)
    test_labels = load_array(Y_TEST_PATH).astype(np.int8)
    validate_features(test_features, "test")
    test_metadata = pd.read_csv(TEST_METADATA_PATH)
    if not (
        len(test_features) == len(test_labels) == len(test_metadata)
    ):
        raise ValueError("Test-Fenster, Labels und Metadaten sind inkonsistent.")
    if not np.array_equal(
        test_labels, test_metadata["label"].to_numpy(dtype=np.int8)
    ):
        raise ValueError("Testlabels stimmen nicht mit den Metadaten überein.")

    test_errors = calculate_reconstruction_errors(model, test_features)
    test_predictions = (test_errors > threshold).astype(np.int8)
    metrics = calculate_binary_metrics(test_labels, test_predictions)

    predictions = test_metadata.rename(columns={"label": "true_label"}).copy()
    predictions["predicted_label"] = test_predictions
    predictions["reconstruction_error"] = test_errors
    predictions["threshold"] = threshold
    required_first = [
        "source_file",
        "window_index",
        "true_label",
        "predicted_label",
        "reconstruction_error",
        "threshold",
        "anomaly_fraction",
    ]
    remaining_columns = [
        column for column in predictions.columns if column not in required_first
    ]
    predictions = predictions[required_first + remaining_columns]
    predictions.to_csv(PREDICTIONS_PATH, index=False)

    normal_errors = test_errors[test_labels == 0]
    anomaly_errors = test_errors[test_labels == 1]
    metrics_report = {
        "model": "TensorFlow Autoencoder",
        "model_path": relative_path(MODEL_PATH),
        "model_size_kb": float(MODEL_PATH.stat().st_size / 1024),
        "test_window_count": int(len(test_labels)),
        "normal_test_windows": int(np.count_nonzero(test_labels == 0)),
        "anomaly_test_windows": int(np.count_nonzero(test_labels == 1)),
        "threshold": threshold,
        "threshold_source": "Normal validation windows only",
        "test_labels_used_for_threshold_selection": False,
        "metrics": metrics,
        "confusion_matrix": {
            key: metrics[key] for key in ("tn", "fp", "fn", "tp")
        },
        "test_reconstruction_error": {
            "normal_mean_mse": float(np.mean(normal_errors)),
            "normal_median_mse": float(np.median(normal_errors)),
            "anomaly_mean_mse": float(np.mean(anomaly_errors)),
            "anomaly_median_mse": float(np.median(anomaly_errors)),
        },
    }
    with METRICS_PATH.open("w", encoding="utf-8") as file:
        json.dump(metrics_report, file, indent=2, ensure_ascii=False)

    session_metrics = calculate_session_metrics(
        predictions,
        score_column="reconstruction_error",
        statistic_prefix="reconstruction_error",
        model_name="TensorFlow Autoencoder",
    )
    session_metrics.to_csv(SESSION_METRICS_PATH, index=False)

    save_error_distribution(test_errors, test_labels, threshold)
    save_error_sequence(predictions, threshold)
    save_confusion_matrix(test_labels, test_predictions)

    print("TensorFlow-Evaluation abgeschlossen.")
    print(f"Threshold (99. Perzentil Validation): {threshold:.10f}")
    print(
        "Confusion Matrix: "
        f"TN={metrics['tn']}, FP={metrics['fp']}, "
        f"FN={metrics['fn']}, TP={metrics['tp']}"
    )
    print(
        f"Accuracy={metrics['accuracy']:.6f}, "
        f"Precision={metrics['precision']:.6f}, "
        f"Recall={metrics['recall']:.6f}, F1={metrics['f1']:.6f}"
    )
    print(f"False Positive Rate={metrics['false_positive_rate']:.6f}")
    print("Testlabels wurden nicht zur Threshold-Auswahl verwendet.")


if __name__ == "__main__":
    main()
