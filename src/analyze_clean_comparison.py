"""Document the measured differences between Phase 3 and clean experiment."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_DIRECTORY = PROJECT_ROOT / "results"
OUTPUT_PATH = RESULT_DIRECTORY / "clean_comparison_findings.json"


def load_json(filename: str) -> dict[str, object]:
    with (RESULT_DIRECTORY / filename).open(encoding="utf-8") as file:
        return json.load(file)


def maximum_pairwise_distance(values: np.ndarray) -> float:
    return max(
        float(np.linalg.norm(first - second))
        for first in values
        for second in values
    )


def score_summary(
    previous_path: str,
    clean_path: str,
    score_column: str,
) -> dict[str, object]:
    previous = pd.read_csv(RESULT_DIRECTORY / previous_path)
    clean = pd.read_csv(RESULT_DIRECTORY / clean_path)

    def experiment_summary(frame: pd.DataFrame) -> dict[str, object]:
        normal = frame.loc[frame["true_label"] == 0, score_column].to_numpy(
            dtype=np.float64
        )
        anomaly = frame.loc[frame["true_label"] == 1, score_column].to_numpy(
            dtype=np.float64
        )
        mean_gap = float(np.mean(anomaly) - np.mean(normal))
        pooled_standard_deviation = float(
            np.sqrt((np.var(normal, ddof=0) + np.var(anomaly, ddof=0)) / 2)
        )
        standardized_gap = (
            mean_gap / pooled_standard_deviation
            if pooled_standard_deviation > 0
            else None
        )
        return {
            "normal_count": int(len(normal)),
            "anomaly_count": int(len(anomaly)),
            "normal_mean": float(np.mean(normal)),
            "normal_standard_deviation": float(np.std(normal, ddof=0)),
            "anomaly_mean": float(np.mean(anomaly)),
            "anomaly_standard_deviation": float(np.std(anomaly, ddof=0)),
            "anomaly_minus_normal_mean_gap": mean_gap,
            "standardized_mean_gap": standardized_gap,
        }

    return {
        "score_column": score_column,
        "previous": experiment_summary(previous),
        "clean": experiment_summary(clean),
    }


def normal_windows_inside_anomaly_files(
    predictions_path: str,
) -> dict[str, object]:
    predictions = pd.read_csv(RESULT_DIRECTORY / predictions_path)
    anomaly_files = predictions["source_file"].str.startswith("anomaly_")
    normal_inside = predictions[anomaly_files & (predictions["true_label"] == 0)]
    return {
        "available_normal_windows": int(len(normal_inside)),
        "predicted_anomaly": int(
            np.count_nonzero(normal_inside["predicted_label"] == 1)
        ),
        "rate_predicted_anomaly": (
            float(np.mean(normal_inside["predicted_label"] == 1))
            if len(normal_inside) > 0
            else None
        ),
    }


def main() -> None:
    previous_tensorflow = load_json("tensorflow_test_metrics.json")
    clean_tensorflow = load_json("clean_tensorflow_test_metrics.json")
    previous_isolation = load_json(
        "isolation_forest_comparison_metrics.json"
    )
    clean_isolation = load_json("clean_isolation_forest_metrics.json")

    previous_stats = pd.read_csv(
        RESULT_DIRECTORY / "sensor_session_statistics.csv"
    )
    clean_stats = pd.read_csv(
        RESULT_DIRECTORY / "clean_session_statistics.csv"
    )
    axes = ["x_mean_g", "y_mean_g", "z_mean_g"]
    previous_normal_means = previous_stats.loc[
        previous_stats["anomaly_sample_count"] == 0, axes
    ].to_numpy(dtype=np.float64)
    clean_normal_means = clean_stats.loc[
        clean_stats["anomaly_sample_count"] == 0, axes
    ].to_numpy(dtype=np.float64)
    previous_orientation_distance = maximum_pairwise_distance(
        previous_normal_means
    )
    clean_orientation_distance = maximum_pairwise_distance(clean_normal_means)

    previous_test_count = int(previous_tensorflow["test_window_count"])
    clean_test_count = int(clean_tensorflow["test_window_count"])
    previous_anomaly_count = int(previous_tensorflow["anomaly_test_windows"])
    clean_anomaly_count = int(clean_tensorflow["anomaly_test_windows"])

    model_metrics: dict[str, object] = {}
    for model_name, previous_report, clean_report in (
        (
            "TensorFlow Autoencoder",
            previous_tensorflow,
            clean_tensorflow,
        ),
        (
            "Isolation Forest",
            previous_isolation,
            clean_isolation,
        ),
    ):
        previous_metrics = previous_report["metrics"]
        clean_metrics = clean_report["metrics"]
        previous_fpr = float(previous_metrics["false_positive_rate"])
        clean_fpr = float(clean_metrics["false_positive_rate"])
        model_metrics[model_name] = {
            "previous": previous_metrics,
            "clean": clean_metrics,
            "changes_clean_minus_previous": {
                "false_positive_rate": clean_fpr - previous_fpr,
                "relative_false_positive_rate_reduction": (
                    (previous_fpr - clean_fpr) / previous_fpr
                    if previous_fpr > 0
                    else None
                ),
                "precision": float(clean_metrics["precision"])
                - float(previous_metrics["precision"]),
                "recall": float(clean_metrics["recall"])
                - float(previous_metrics["recall"]),
                "f1": float(clean_metrics["f1"])
                - float(previous_metrics["f1"]),
            },
        }

    report = {
        "comparison_scope": (
            "Descriptive comparison of Phase 3 and the controlled 20260823 "
            "experiment; no new threshold or hyperparameter selection."
        ),
        "sensor_orientation": {
            "previous_maximum_pairwise_normal_session_xyz_mean_distance_g": (
                previous_orientation_distance
            ),
            "clean_maximum_pairwise_normal_session_xyz_mean_distance_g": (
                clean_orientation_distance
            ),
            "relative_reduction": (
                1 - clean_orientation_distance / previous_orientation_distance
            ),
            "assessment": (
                "The orientation/session mean shift is substantially reduced "
                "in the controlled normal recordings."
            ),
        },
        "test_class_prevalence": {
            "previous_anomaly_fraction": previous_anomaly_count
            / previous_test_count,
            "clean_anomaly_fraction": clean_anomaly_count / clean_test_count,
            "warning": (
                "Precision, F1 and accuracy are not directly comparable "
                "without considering the strongly changed class prevalence."
            ),
        },
        "model_metrics": model_metrics,
        "score_separation": {
            "TensorFlow Autoencoder": score_summary(
                "tensorflow_test_predictions.csv",
                "clean_tensorflow_test_predictions.csv",
                "reconstruction_error",
            ),
            "Isolation Forest": score_summary(
                "isolation_forest_comparison_predictions.csv",
                "clean_isolation_forest_predictions.csv",
                "anomaly_score",
            ),
        },
        "normal_windows_inside_anomaly_recordings": {
            "previous_tensorflow": normal_windows_inside_anomaly_files(
                "tensorflow_test_predictions.csv"
            ),
            "clean_tensorflow": normal_windows_inside_anomaly_files(
                "clean_tensorflow_test_predictions.csv"
            ),
            "previous_isolation_forest": normal_windows_inside_anomaly_files(
                "isolation_forest_comparison_predictions.csv"
            ),
            "clean_isolation_forest": normal_windows_inside_anomaly_files(
                "clean_isolation_forest_predictions.csv"
            ),
            "clean_limitation": (
                "The clean anomaly recordings contain no normal point or "
                "window labels, so systematic false positives within those "
                "recordings cannot be re-evaluated."
            ),
        },
        "limitations": [
            (
                "Clean test prevalence changed from 26/546 anomaly windows "
                "to 468/702, affecting precision, F1 and accuracy."
            ),
            (
                "Every sample of both clean anomaly recordings is labelled "
                "anomalous; quiet intervals, if present, cannot be assessed."
            ),
            (
                "The Autoencoder validation loss continued improving through "
                "epoch 100; architecture and epoch cap were retained for "
                "comparability rather than tuned on test data."
            ),
        ],
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    print("Alt-vs-Neu-Analyse gespeichert:", OUTPUT_PATH.relative_to(PROJECT_ROOT))
    print(
        "Orientierungsdistanz alt/clean: "
        f"{previous_orientation_distance:.9f} / "
        f"{clean_orientation_distance:.9f} g"
    )


if __name__ == "__main__":
    main()
