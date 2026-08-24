"""Train and evaluate Isolation Forest on the unchanged Phase-2 windows."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from comparison_metrics import (
    calculate_binary_metrics,
    calculate_session_metrics,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = PROJECT_ROOT / "data" / "comparison"
MODEL_DIRECTORY = PROJECT_ROOT / "models" / "comparison"
RESULT_DIRECTORY = PROJECT_ROOT / "results"

X_TRAIN_PATH = DATA_DIRECTORY / "X_train.npy"
Y_TRAIN_PATH = DATA_DIRECTORY / "y_train.npy"
X_VALIDATION_PATH = DATA_DIRECTORY / "X_val.npy"
Y_VALIDATION_PATH = DATA_DIRECTORY / "y_val.npy"
X_TEST_PATH = DATA_DIRECTORY / "X_test.npy"
Y_TEST_PATH = DATA_DIRECTORY / "y_test.npy"
TEST_METADATA_PATH = DATA_DIRECTORY / "test_metadata.csv"

MODEL_PATH = MODEL_DIRECTORY / "isolation_forest.joblib"
THRESHOLD_PATH = (
    RESULT_DIRECTORY / "isolation_forest_comparison_threshold.json"
)
METRICS_PATH = (
    RESULT_DIRECTORY / "isolation_forest_comparison_metrics.json"
)
PREDICTIONS_PATH = (
    RESULT_DIRECTORY / "isolation_forest_comparison_predictions.csv"
)
SESSION_METRICS_PATH = (
    RESULT_DIRECTORY / "isolation_forest_comparison_metrics_by_session.csv"
)
MODEL_COMPARISON_PATH = RESULT_DIRECTORY / "model_comparison.csv"
TENSORFLOW_METRICS_PATH = RESULT_DIRECTORY / "tensorflow_test_metrics.json"
TENSORFLOW_MODEL_PATH = (
    PROJECT_ROOT / "models" / "tensorflow" / "autoencoder.keras"
)

RANDOM_SEED = 42
THRESHOLD_PERCENTILE = 99.0
EXPECTED_WINDOW_SHAPE = (128, 3)
FLATTENED_FEATURE_COUNT = 128 * 3

MODEL_HYPERPARAMETERS = {
    "n_estimators": 200,
    "max_samples": "auto",
    "contamination": "auto",
    "max_features": 1.0,
    "bootstrap": False,
    "n_jobs": -1,
    "random_state": RANDOM_SEED,
    "verbose": 0,
    "warm_start": False,
}


def relative_path(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def load_array(path: Path) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(f"Fehlende Datei: {relative_path(path)}")
    return np.load(path, allow_pickle=False)


def flatten_windows(features: np.ndarray, split: str) -> np.ndarray:
    """Flatten (128, 3) in C order: sample order first, XYZ within sample."""

    if features.ndim != 3 or tuple(features.shape[1:]) != EXPECTED_WINDOW_SHAPE:
        raise ValueError(
            f"{split}: erwartete Tensorform (N, 128, 3), "
            f"erhalten: {features.shape}"
        )
    if not np.isfinite(features).all():
        raise ValueError(f"{split}: nicht-endliche Werte gefunden.")
    flattened = features.reshape(len(features), FLATTENED_FEATURE_COUNT)
    return flattened.astype(np.float32, copy=False)


def anomaly_scores(
    model: IsolationForest,
    flattened_features: np.ndarray,
) -> np.ndarray:
    """Return a score where larger values consistently mean more anomalous."""

    # sklearn score_samples is larger for more normal observations. Negating
    # it gives the same score direction as Autoencoder reconstruction MSE.
    return -model.score_samples(flattened_features)


def describe_validation_scores(scores: np.ndarray) -> dict[str, float | int]:
    return {
        "validation_window_count": int(len(scores)),
        "mean_anomaly_score": float(np.mean(scores)),
        "standard_deviation_anomaly_score": float(np.std(scores, ddof=0)),
        "median_anomaly_score": float(np.median(scores)),
        "percentile_95_anomaly_score": float(np.percentile(scores, 95)),
        "percentile_99_anomaly_score": float(np.percentile(scores, 99)),
        "maximum_anomaly_score": float(np.max(scores)),
    }


def create_model_comparison(
    isolation_metrics_report: dict[str, object],
) -> None:
    if not TENSORFLOW_METRICS_PATH.exists():
        raise FileNotFoundError(
            "TensorFlow-Metriken fehlen. Zuerst ausführen: "
            "python src/evaluate.py"
        )

    with TENSORFLOW_METRICS_PATH.open(encoding="utf-8") as file:
        tensorflow_report = json.load(file)

    tensorflow_metrics = tensorflow_report["metrics"]
    isolation_metrics = isolation_metrics_report["metrics"]
    metric_columns = [
        "accuracy",
        "precision",
        "recall",
        "f1",
        "specificity",
        "false_positive_rate",
        "false_negative_rate",
        "tn",
        "fp",
        "fn",
        "tp",
    ]

    comparison_rows = [
        {
            "model": "TensorFlow Autoencoder",
            **{key: tensorflow_metrics[key] for key in metric_columns},
            "model_size_kb": float(TENSORFLOW_MODEL_PATH.stat().st_size / 1024),
        },
        {
            "model": "Isolation Forest",
            **{key: isolation_metrics[key] for key in metric_columns},
            "model_size_kb": float(MODEL_PATH.stat().st_size / 1024),
        },
    ]
    pd.DataFrame(comparison_rows).to_csv(MODEL_COMPARISON_PATH, index=False)


def main() -> None:
    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    training_windows = load_array(X_TRAIN_PATH)
    training_labels = load_array(Y_TRAIN_PATH).astype(np.int8)
    flattened_training = flatten_windows(training_windows, "train")
    if len(flattened_training) != len(training_labels):
        raise ValueError("Training-Fenster und -Labels sind inkonsistent.")
    if np.any(training_labels != 0):
        raise ValueError("Isolation Forest darf nur Normalfenster trainieren.")

    model = IsolationForest(**MODEL_HYPERPARAMETERS)
    model.fit(flattened_training)
    joblib.dump(model, MODEL_PATH)

    # Threshold selection is completed using normal validation data before
    # any test feature or test label is loaded.
    validation_windows = load_array(X_VALIDATION_PATH)
    validation_labels = load_array(Y_VALIDATION_PATH).astype(np.int8)
    flattened_validation = flatten_windows(validation_windows, "validation")
    if len(flattened_validation) != len(validation_labels):
        raise ValueError("Validation-Fenster und -Labels sind inkonsistent.")
    if np.any(validation_labels != 0):
        raise ValueError(
            "Isolation-Forest-Threshold darf nur normale Validation nutzen."
        )

    validation_scores = anomaly_scores(model, flattened_validation)
    validation_statistics = describe_validation_scores(validation_scores)
    threshold = validation_statistics["percentile_99_anomaly_score"]

    threshold_report = {
        "model": "Isolation Forest",
        "model_path": relative_path(MODEL_PATH),
        "input": (
            "Already scaled Phase-2 XYZ windows flattened in C order from "
            "(128, 3) to 384 features"
        ),
        "score_definition": "anomaly_score = -IsolationForest.score_samples(X)",
        "score_direction": "Higher values are more anomalous",
        "threshold_method": (
            "99th percentile of anomaly scores from normal validation "
            "windows only"
        ),
        "decision_rule": {
            "normal": "anomaly_score <= threshold",
            "anomaly": "anomaly_score > threshold",
        },
        "test_labels_used_for_threshold_selection": False,
        "hyperparameters": MODEL_HYPERPARAMETERS,
        "validation_statistics": validation_statistics,
        "threshold": threshold,
    }
    with THRESHOLD_PATH.open("w", encoding="utf-8") as file:
        json.dump(threshold_report, file, indent=2, ensure_ascii=False)

    # Apply the frozen decision rule exactly once to the unchanged test split.
    test_windows = load_array(X_TEST_PATH)
    test_labels = load_array(Y_TEST_PATH).astype(np.int8)
    flattened_test = flatten_windows(test_windows, "test")
    test_metadata = pd.read_csv(TEST_METADATA_PATH)
    if not (
        len(flattened_test) == len(test_labels) == len(test_metadata)
    ):
        raise ValueError("Test-Fenster, Labels und Metadaten sind inkonsistent.")
    if not np.array_equal(
        test_labels, test_metadata["label"].to_numpy(dtype=np.int8)
    ):
        raise ValueError("Testlabels stimmen nicht mit den Metadaten überein.")

    test_scores = anomaly_scores(model, flattened_test)
    test_predictions = (test_scores > threshold).astype(np.int8)
    metrics = calculate_binary_metrics(test_labels, test_predictions)

    predictions = test_metadata.rename(columns={"label": "true_label"}).copy()
    predictions["predicted_label"] = test_predictions
    predictions["anomaly_score"] = test_scores
    predictions["threshold"] = threshold
    required_first = [
        "source_file",
        "window_index",
        "true_label",
        "predicted_label",
        "anomaly_score",
        "threshold",
        "anomaly_fraction",
    ]
    remaining_columns = [
        column for column in predictions.columns if column not in required_first
    ]
    predictions = predictions[required_first + remaining_columns]
    predictions.to_csv(PREDICTIONS_PATH, index=False)

    metrics_report: dict[str, object] = {
        "model": "Isolation Forest",
        "model_path": relative_path(MODEL_PATH),
        "model_size_kb": float(MODEL_PATH.stat().st_size / 1024),
        "random_state": RANDOM_SEED,
        "hyperparameters": MODEL_HYPERPARAMETERS,
        "input_window_shape": list(EXPECTED_WINDOW_SHAPE),
        "flattened_feature_count": FLATTENED_FEATURE_COUNT,
        "training_windows": int(len(flattened_training)),
        "validation_windows": int(len(flattened_validation)),
        "test_windows": int(len(flattened_test)),
        "normal_test_windows": int(np.count_nonzero(test_labels == 0)),
        "anomaly_test_windows": int(np.count_nonzero(test_labels == 1)),
        "score_definition": "anomaly_score = -IsolationForest.score_samples(X)",
        "threshold": threshold,
        "threshold_source": "Normal validation windows only",
        "test_labels_used_for_hyperparameters_or_threshold": False,
        "metrics": metrics,
        "confusion_matrix": {
            key: metrics[key] for key in ("tn", "fp", "fn", "tp")
        },
    }
    with METRICS_PATH.open("w", encoding="utf-8") as file:
        json.dump(metrics_report, file, indent=2, ensure_ascii=False)

    session_metrics = calculate_session_metrics(
        predictions,
        score_column="anomaly_score",
        statistic_prefix="anomaly_score",
        model_name="Isolation Forest",
    )
    session_metrics.to_csv(SESSION_METRICS_PATH, index=False)
    create_model_comparison(metrics_report)

    print("Vergleichs-Isolation-Forest erfolgreich trainiert und evaluiert.")
    print(f"Input: {flattened_training.shape[1]} skalierte Features je Fenster")
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
    print("Testlabels wurden nicht für Hyperparameter oder Threshold verwendet.")


if __name__ == "__main__":
    main()
