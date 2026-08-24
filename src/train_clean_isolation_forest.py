"""Train and evaluate Isolation Forest on the controlled clean split."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from comparison_metrics import calculate_binary_metrics, calculate_session_metrics


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = PROJECT_ROOT / "data" / "clean_comparison"
MODEL_DIRECTORY = PROJECT_ROOT / "models" / "clean_comparison"
RESULT_DIRECTORY = PROJECT_ROOT / "results"

MODEL_PATH = MODEL_DIRECTORY / "isolation_forest.joblib"
THRESHOLD_PATH = RESULT_DIRECTORY / "clean_isolation_forest_threshold.json"
METRICS_PATH = RESULT_DIRECTORY / "clean_isolation_forest_metrics.json"
PREDICTIONS_PATH = RESULT_DIRECTORY / "clean_isolation_forest_predictions.csv"
SESSION_METRICS_PATH = (
    RESULT_DIRECTORY / "clean_isolation_forest_metrics_by_session.csv"
)
CLEAN_COMPARISON_PATH = RESULT_DIRECTORY / "clean_model_comparison.csv"
OLD_VS_NEW_PATH = RESULT_DIRECTORY / "clean_vs_previous_comparison.csv"
CLEAN_TENSORFLOW_METRICS_PATH = (
    RESULT_DIRECTORY / "clean_tensorflow_test_metrics.json"
)
PREVIOUS_COMPARISON_PATH = RESULT_DIRECTORY / "model_comparison.csv"
CLEAN_TENSORFLOW_MODEL_PATH = MODEL_DIRECTORY / "autoencoder.keras"

EXPECTED_WINDOW_SHAPE = (128, 3)
FLATTENED_FEATURE_COUNT = 384
RANDOM_SEED = 42
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


def load_array(filename: str) -> np.ndarray:
    path = DATA_DIRECTORY / filename
    if not path.exists():
        raise FileNotFoundError(f"Fehlende Datei: {relative_path(path)}")
    return np.load(path, allow_pickle=False)


def flatten(features: np.ndarray, split: str) -> np.ndarray:
    if features.ndim != 3 or tuple(features.shape[1:]) != EXPECTED_WINDOW_SHAPE:
        raise ValueError(
            f"{split}: erwartete Tensorform (N,128,3), erhalten {features.shape}"
        )
    if not np.isfinite(features).all():
        raise ValueError(f"{split}: nicht-endliche Werte gefunden.")
    return features.reshape(len(features), FLATTENED_FEATURE_COUNT).astype(
        np.float32, copy=False
    )


def anomaly_scores(
    model: IsolationForest,
    features: np.ndarray,
) -> np.ndarray:
    return -model.score_samples(features)


def score_statistics(scores: np.ndarray) -> dict[str, float | int]:
    return {
        "validation_window_count": int(len(scores)),
        "mean_anomaly_score": float(np.mean(scores)),
        "standard_deviation_anomaly_score": float(np.std(scores, ddof=0)),
        "median_anomaly_score": float(np.median(scores)),
        "percentile_95_anomaly_score": float(np.percentile(scores, 95)),
        "percentile_99_anomaly_score": float(np.percentile(scores, 99)),
        "maximum_anomaly_score": float(np.max(scores)),
    }


def create_comparison(isolation_report: dict[str, object]) -> None:
    with CLEAN_TENSORFLOW_METRICS_PATH.open(encoding="utf-8") as file:
        tensorflow_report = json.load(file)
    tensorflow_metrics = tensorflow_report["metrics"]
    isolation_metrics = isolation_report["metrics"]
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
    rows = [
        {
            "model": "TensorFlow Autoencoder",
            **{key: tensorflow_metrics[key] for key in metric_columns},
            "model_size_kb": float(
                CLEAN_TENSORFLOW_MODEL_PATH.stat().st_size / 1024
            ),
        },
        {
            "model": "Isolation Forest",
            **{key: isolation_metrics[key] for key in metric_columns},
            "model_size_kb": float(MODEL_PATH.stat().st_size / 1024),
        },
    ]
    clean_comparison = pd.DataFrame(rows)
    clean_comparison.to_csv(CLEAN_COMPARISON_PATH, index=False)

    previous = pd.read_csv(PREVIOUS_COMPARISON_PATH)
    compared_metrics = [
        "accuracy",
        "precision",
        "recall",
        "f1",
        "specificity",
        "false_positive_rate",
        "false_negative_rate",
    ]
    comparison_rows: list[dict[str, float | str]] = []
    for model_name in clean_comparison["model"]:
        old_row = previous.loc[previous["model"] == model_name].iloc[0]
        clean_row = clean_comparison.loc[
            clean_comparison["model"] == model_name
        ].iloc[0]
        row: dict[str, float | str] = {"model": model_name}
        for metric in compared_metrics:
            old_value = float(old_row[metric])
            clean_value = float(clean_row[metric])
            row[f"previous_{metric}"] = old_value
            row[f"clean_{metric}"] = clean_value
            row[f"delta_{metric}"] = clean_value - old_value
        comparison_rows.append(row)
    pd.DataFrame(comparison_rows).to_csv(OLD_VS_NEW_PATH, index=False)


def main() -> None:
    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    x_train = flatten(load_array("X_train.npy"), "train")
    y_train = load_array("y_train.npy").astype(np.int8)
    if len(x_train) != len(y_train) or np.any(y_train != 0):
        raise ValueError("Clean-Isolation-Forest-Training muss rein normal sein.")
    model = IsolationForest(**MODEL_HYPERPARAMETERS)
    model.fit(x_train)
    joblib.dump(model, MODEL_PATH)

    # Freeze the validation threshold before loading test data.
    x_validation = flatten(load_array("X_val.npy"), "validation")
    y_validation = load_array("y_val.npy").astype(np.int8)
    if len(x_validation) != len(y_validation) or np.any(y_validation != 0):
        raise ValueError("Clean-Validation muss vollständig normal sein.")
    validation_scores = anomaly_scores(model, x_validation)
    statistics = score_statistics(validation_scores)
    threshold = statistics["percentile_99_anomaly_score"]

    threshold_report = {
        "experiment": "clean_comparison_20260823",
        "model": "Isolation Forest",
        "model_path": relative_path(MODEL_PATH),
        "input": "Scaled (128,3) windows flattened to 384 features in C order",
        "score_definition": "anomaly_score = -IsolationForest.score_samples(X)",
        "score_direction": "Higher values are more anomalous",
        "threshold_method": (
            "99th percentile of normal validation anomaly scores only"
        ),
        "decision_rule": {
            "normal": "anomaly_score <= threshold",
            "anomaly": "anomaly_score > threshold",
        },
        "test_labels_used_for_threshold_selection": False,
        "hyperparameters": MODEL_HYPERPARAMETERS,
        "validation_statistics": statistics,
        "threshold": threshold,
    }
    with THRESHOLD_PATH.open("w", encoding="utf-8") as file:
        json.dump(threshold_report, file, indent=2, ensure_ascii=False)

    x_test = flatten(load_array("X_test.npy"), "test")
    y_test = load_array("y_test.npy").astype(np.int8)
    metadata = pd.read_csv(DATA_DIRECTORY / "test_metadata.csv")
    if not (len(x_test) == len(y_test) == len(metadata)):
        raise ValueError("Clean-Testdaten und Metadaten sind inkonsistent.")
    if not np.array_equal(y_test, metadata["label"].to_numpy(dtype=np.int8)):
        raise ValueError("Clean-Testlabels stimmen nicht mit Metadaten überein.")

    scores = anomaly_scores(model, x_test)
    predicted = (scores > threshold).astype(np.int8)
    metrics = calculate_binary_metrics(y_test, predicted)

    predictions = metadata.rename(columns={"label": "true_label"}).copy()
    predictions["predicted_label"] = predicted
    predictions["anomaly_score"] = scores
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
    predictions = predictions[
        required_first
        + [column for column in predictions.columns if column not in required_first]
    ]
    predictions.to_csv(PREDICTIONS_PATH, index=False)

    report: dict[str, object] = {
        "experiment": "clean_comparison_20260823",
        "model": "Isolation Forest",
        "model_path": relative_path(MODEL_PATH),
        "model_size_kb": float(MODEL_PATH.stat().st_size / 1024),
        "hyperparameters": MODEL_HYPERPARAMETERS,
        "input_window_shape": list(EXPECTED_WINDOW_SHAPE),
        "flattened_feature_count": FLATTENED_FEATURE_COUNT,
        "training_windows": int(len(x_train)),
        "validation_windows": int(len(x_validation)),
        "test_windows": int(len(x_test)),
        "normal_test_windows": int(np.count_nonzero(y_test == 0)),
        "anomaly_test_windows": int(np.count_nonzero(y_test == 1)),
        "threshold": threshold,
        "threshold_source": "Normal validation windows only",
        "test_labels_used_for_hyperparameters_or_threshold": False,
        "metrics": metrics,
        "confusion_matrix": {
            key: metrics[key] for key in ("tn", "fp", "fn", "tp")
        },
    }
    with METRICS_PATH.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    sessions = calculate_session_metrics(
        predictions,
        score_column="anomaly_score",
        statistic_prefix="anomaly_score",
        model_name="Isolation Forest",
    )
    sessions.to_csv(SESSION_METRICS_PATH, index=False)
    create_comparison(report)

    print("Clean-Isolation-Forest abgeschlossen.")
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
    print("Testlabels wurden nicht für Fit, Hyperparameter oder Threshold genutzt.")


if __name__ == "__main__":
    main()
