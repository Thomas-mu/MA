"""Shared binary and session metrics for the Phase-3 model comparison."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix


def _safe_ratio(
    numerator: int | float,
    denominator: int | float,
    *,
    undefined_value: float | None,
) -> float | None:
    """Divide while making undefined per-session rates explicit."""

    if denominator == 0:
        return undefined_value
    return float(numerator / denominator)


def calculate_binary_metrics(
    true_labels: np.ndarray,
    predicted_labels: np.ndarray,
) -> dict[str, float | int | None]:
    """Calculate metrics with anomaly label 1 as the positive class."""

    true_labels = np.asarray(true_labels, dtype=np.int8)
    predicted_labels = np.asarray(predicted_labels, dtype=np.int8)

    if true_labels.shape != predicted_labels.shape:
        raise ValueError("True labels and predictions must have equal shapes.")
    if not set(np.unique(true_labels)).issubset({0, 1}):
        raise ValueError("True labels must be binary values 0 and 1.")
    if not set(np.unique(predicted_labels)).issubset({0, 1}):
        raise ValueError("Predictions must be binary values 0 and 1.")

    matrix = confusion_matrix(
        true_labels,
        predicted_labels,
        labels=[0, 1],
    )
    true_negative, false_positive, false_negative, true_positive = (
        int(value) for value in matrix.ravel()
    )

    accuracy = _safe_ratio(
        true_negative + true_positive,
        len(true_labels),
        undefined_value=0.0,
    )
    precision = _safe_ratio(
        true_positive,
        true_positive + false_positive,
        undefined_value=0.0,
    )
    recall = _safe_ratio(
        true_positive,
        true_positive + false_negative,
        undefined_value=None,
    )
    specificity = _safe_ratio(
        true_negative,
        true_negative + false_positive,
        undefined_value=None,
    )
    false_positive_rate = _safe_ratio(
        false_positive,
        false_positive + true_negative,
        undefined_value=None,
    )
    false_negative_rate = _safe_ratio(
        false_negative,
        false_negative + true_positive,
        undefined_value=None,
    )

    if recall is None or precision is None or precision + recall == 0:
        f1 = 0.0 if recall is not None else None
    else:
        f1 = float(2 * precision * recall / (precision + recall))

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "sensitivity": recall,
        "f1": f1,
        "specificity": specificity,
        "false_positive_rate": false_positive_rate,
        "false_negative_rate": false_negative_rate,
        "tn": true_negative,
        "fp": false_positive,
        "fn": false_negative,
        "tp": true_positive,
    }


def calculate_session_metrics(
    prediction_frame: pd.DataFrame,
    *,
    score_column: str,
    statistic_prefix: str,
    model_name: str,
) -> pd.DataFrame:
    """Calculate classification and score statistics for every source file."""

    required_columns = {
        "source_file",
        "true_label",
        "predicted_label",
        score_column,
    }
    missing_columns = required_columns.difference(prediction_frame.columns)
    if missing_columns:
        raise ValueError(
            "Missing columns for session metrics: "
            + ", ".join(sorted(missing_columns))
        )

    rows: list[dict[str, float | int | str | None]] = []

    for source_file, session in prediction_frame.groupby(
        "source_file", sort=False
    ):
        true_labels = session["true_label"].to_numpy(dtype=np.int8)
        predictions = session["predicted_label"].to_numpy(dtype=np.int8)
        scores = session[score_column].to_numpy(dtype=np.float64)
        metrics = calculate_binary_metrics(true_labels, predictions)

        rows.append(
            {
                "model": model_name,
                "source_file": source_file,
                "window_count": int(len(session)),
                "normal_windows": int(np.count_nonzero(true_labels == 0)),
                "anomaly_windows": int(np.count_nonzero(true_labels == 1)),
                f"{statistic_prefix}_mean": float(np.mean(scores)),
                f"{statistic_prefix}_median": float(np.median(scores)),
                f"{statistic_prefix}_standard_deviation": float(
                    np.std(scores, ddof=0)
                ),
                f"{statistic_prefix}_maximum": float(np.max(scores)),
                "anomaly_window_detection_rate": metrics["recall"],
                **metrics,
            }
        )

    result = pd.DataFrame(rows)

    # Pandas represents undefined rates (e.g. recall for a normal-only file)
    # as NaN in CSV, which is scientifically clearer than reporting 0.
    result = result.replace({None: math.nan})
    return result
