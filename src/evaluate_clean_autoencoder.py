"""Evaluate the clean 2026-08-23 autoencoder without test tuning."""

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

from comparison_metrics import calculate_binary_metrics, calculate_session_metrics


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = PROJECT_ROOT / "data" / "clean_comparison"
MODEL_PATH = PROJECT_ROOT / "models" / "clean_comparison" / "autoencoder.keras"
RESULT_DIRECTORY = PROJECT_ROOT / "results"
FIGURE_DIRECTORY = PROJECT_ROOT / "figures"

THRESHOLD_PATH = RESULT_DIRECTORY / "clean_tensorflow_threshold.json"
METRICS_PATH = RESULT_DIRECTORY / "clean_tensorflow_test_metrics.json"
PREDICTIONS_PATH = RESULT_DIRECTORY / "clean_tensorflow_test_predictions.csv"
SESSION_METRICS_PATH = RESULT_DIRECTORY / "clean_tensorflow_metrics_by_session.csv"

ERROR_DISTRIBUTION_FIGURE = (
    FIGURE_DIRECTORY / "clean_tensorflow_reconstruction_error_distribution.png"
)
ERROR_SEQUENCE_FIGURE = (
    FIGURE_DIRECTORY / "clean_tensorflow_reconstruction_error_test_sequence.png"
)
CONFUSION_MATRIX_FIGURE = (
    FIGURE_DIRECTORY / "clean_tensorflow_confusion_matrix.png"
)

EXPECTED_WINDOW_SHAPE = (128, 3)
BATCH_SIZE = 32


def relative_path(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def load_array(filename: str) -> np.ndarray:
    path = DATA_DIRECTORY / filename
    if not path.exists():
        raise FileNotFoundError(f"Fehlende Datei: {relative_path(path)}")
    return np.load(path, allow_pickle=False)


def validate_features(features: np.ndarray, split: str) -> None:
    if features.ndim != 3 or tuple(features.shape[1:]) != EXPECTED_WINDOW_SHAPE:
        raise ValueError(
            f"{split}: erwartete Tensorform (N, 128, 3), "
            f"erhalten {features.shape}"
        )
    if not np.isfinite(features).all():
        raise ValueError(f"{split}: nicht-endliche Werte gefunden.")


def reconstruction_errors(
    model: tf.keras.Model,
    features: np.ndarray,
) -> np.ndarray:
    reconstructed = model.predict(
        features, batch_size=BATCH_SIZE, verbose=0
    )
    return np.mean(
        np.square(features - reconstructed),
        axis=(1, 2),
        dtype=np.float64,
    )


def validation_statistics(errors: np.ndarray) -> dict[str, float | int]:
    return {
        "validation_window_count": int(len(errors)),
        "mean_mse": float(np.mean(errors)),
        "standard_deviation_mse": float(np.std(errors, ddof=0)),
        "median_mse": float(np.median(errors)),
        "percentile_95_mse": float(np.percentile(errors, 95)),
        "percentile_99_mse": float(np.percentile(errors, 99)),
        "maximum_mse": float(np.max(errors)),
    }


def save_figures(
    predictions: pd.DataFrame,
    labels: np.ndarray,
    threshold: float,
) -> None:
    errors = predictions["reconstruction_error"].to_numpy(dtype=np.float64)
    normal_errors = errors[labels == 0]
    anomaly_errors = errors[labels == 1]
    positive_errors = errors[errors > 0]
    bins = np.geomspace(
        max(float(np.min(positive_errors)), np.finfo(float).eps),
        float(np.max(errors)),
        45,
    )

    figure, axis = plt.subplots(figsize=(10, 6))
    axis.hist(
        normal_errors,
        bins=bins,
        alpha=0.65,
        color="tab:blue",
        label=f"Normal (n={len(normal_errors)})",
    )
    axis.hist(
        anomaly_errors,
        bins=bins,
        alpha=0.65,
        color="tab:red",
        label=f"Anomalie (n={len(anomaly_errors)})",
    )
    axis.axvline(
        threshold,
        color="black",
        linestyle="--",
        label=f"99. Perzentil Validation: {threshold:.6f}",
    )
    axis.set_xscale("log")
    axis.set_xlabel("Rekonstruktionsfehler (MSE, logarithmische Skala)")
    axis.set_ylabel("Anzahl Testfenster")
    axis.set_title("Kontrollierter Versuch: Rekonstruktionsfehler")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(ERROR_DISTRIBUTION_FIGURE, dpi=250)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(14, 6))
    axis.plot(
        predictions["split_index"],
        errors,
        color="0.55",
        linewidth=0.8,
    )
    normal = labels == 0
    anomaly = labels == 1
    axis.scatter(
        predictions.loc[normal, "split_index"],
        errors[normal],
        s=10,
        color="tab:blue",
        label="Normal",
    )
    axis.scatter(
        predictions.loc[anomaly, "split_index"],
        errors[anomaly],
        s=10,
        color="tab:red",
        label="Anomalie",
    )
    axis.axhline(
        threshold,
        color="black",
        linestyle="--",
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
    axis.set_title("Kontrollierter Versuch: Testfenster")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(ERROR_SEQUENCE_FIGURE, dpi=250)
    plt.close(figure)

    display = ConfusionMatrixDisplay.from_predictions(
        labels,
        predictions["predicted_label"].to_numpy(dtype=np.int8),
        labels=[0, 1],
        display_labels=["Normal", "Anomalie"],
        colorbar=False,
    )
    display.ax_.set_title("Clean TensorFlow Autoencoder – Confusion Matrix")
    display.figure_.tight_layout()
    display.figure_.savefig(CONFUSION_MATRIX_FIGURE, dpi=250)
    plt.close(display.figure_)


def main() -> None:
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    FIGURE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    model = tf.keras.models.load_model(MODEL_PATH)
    if tuple(model.input_shape[1:]) != EXPECTED_WINDOW_SHAPE:
        raise ValueError(f"Unerwartete Modelleingabe: {model.input_shape}")

    # Freeze the threshold before loading any test feature or test label.
    x_validation = load_array("X_val.npy")
    y_validation = load_array("y_val.npy").astype(np.int8)
    validate_features(x_validation, "validation")
    if len(x_validation) != len(y_validation) or np.any(y_validation != 0):
        raise ValueError("Validation muss vollständig normal sein.")
    validation_errors = reconstruction_errors(model, x_validation)
    statistics = validation_statistics(validation_errors)
    threshold = statistics["percentile_99_mse"]

    threshold_report = {
        "experiment": "clean_comparison_20260823",
        "model": "TensorFlow Autoencoder",
        "model_path": relative_path(MODEL_PATH),
        "threshold_method": (
            "99th percentile of reconstruction MSE from normal validation "
            "windows only"
        ),
        "decision_rule": {
            "normal": "reconstruction_error <= threshold",
            "anomaly": "reconstruction_error > threshold",
        },
        "test_labels_used_for_threshold_selection": False,
        "validation_statistics": statistics,
        "threshold": threshold,
    }
    with THRESHOLD_PATH.open("w", encoding="utf-8") as file:
        json.dump(threshold_report, file, indent=2, ensure_ascii=False)

    x_test = load_array("X_test.npy")
    y_test = load_array("y_test.npy").astype(np.int8)
    validate_features(x_test, "test")
    metadata = pd.read_csv(DATA_DIRECTORY / "test_metadata.csv")
    if not (len(x_test) == len(y_test) == len(metadata)):
        raise ValueError("Clean-Testdaten und Metadaten sind inkonsistent.")
    if not np.array_equal(y_test, metadata["label"].to_numpy(dtype=np.int8)):
        raise ValueError("Clean-Testlabels stimmen nicht mit Metadaten überein.")

    errors = reconstruction_errors(model, x_test)
    predicted = (errors > threshold).astype(np.int8)
    metrics = calculate_binary_metrics(y_test, predicted)

    predictions = metadata.rename(columns={"label": "true_label"}).copy()
    predictions["predicted_label"] = predicted
    predictions["reconstruction_error"] = errors
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
    predictions = predictions[
        required_first
        + [column for column in predictions.columns if column not in required_first]
    ]
    predictions.to_csv(PREDICTIONS_PATH, index=False)

    normal_errors = errors[y_test == 0]
    anomaly_errors = errors[y_test == 1]
    report = {
        "experiment": "clean_comparison_20260823",
        "model": "TensorFlow Autoencoder",
        "model_path": relative_path(MODEL_PATH),
        "model_size_kb": float(MODEL_PATH.stat().st_size / 1024),
        "test_window_count": int(len(y_test)),
        "normal_test_windows": int(np.count_nonzero(y_test == 0)),
        "anomaly_test_windows": int(np.count_nonzero(y_test == 1)),
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
        json.dump(report, file, indent=2, ensure_ascii=False)

    sessions = calculate_session_metrics(
        predictions,
        score_column="reconstruction_error",
        statistic_prefix="reconstruction_error",
        model_name="TensorFlow Autoencoder",
    )
    sessions.to_csv(SESSION_METRICS_PATH, index=False)
    save_figures(predictions, y_test, threshold)

    print("Clean-TensorFlow-Evaluation abgeschlossen.")
    print(f"Threshold: {threshold:.10f}")
    print(
        f"Confusion Matrix: TN={metrics['tn']}, FP={metrics['fp']}, "
        f"FN={metrics['fn']}, TP={metrics['tp']}"
    )
    print(
        f"Accuracy={metrics['accuracy']:.6f}, "
        f"Precision={metrics['precision']:.6f}, "
        f"Recall={metrics['recall']:.6f}, F1={metrics['f1']:.6f}, "
        f"FPR={metrics['false_positive_rate']:.6f}"
    )
    print("Testlabels wurden nicht zur Threshold-Auswahl verwendet.")


if __name__ == "__main__":
    main()
