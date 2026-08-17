import argparse
import json
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


DATA_DIRECTORY = Path("data/processed")
REAL_DATA_DIRECTORY = Path("data/processed_real")
MODEL_DIRECTORY = Path("models")
RESULT_DIRECTORY = Path("results")
FIGURE_DIRECTORY = Path("figures")

TRAIN_FILE = DATA_DIRECTORY / "train_normal.csv"
VALIDATION_FILE = DATA_DIRECTORY / "validation_normal.csv"
TEST_FILE = DATA_DIRECTORY / "test.csv"


def resolve_data_directory(explicit_path: str | None = None) -> Path:
    """Wählt den Datensatzordner robust aus.

    Beim Retraining mit neuen Messdaten hat der echte Datensatz aus
    data/processed_real Vorrang, weil er die aktuelle Hardware- und
    Lüfterumgebung abbildet. Der Standardpfad dient nur als Fallback.
    """

    if explicit_path:
        candidate = Path(explicit_path)
        if candidate.exists():
            return candidate

    if REAL_DATA_DIRECTORY.exists():
        return REAL_DATA_DIRECTORY

    if DATA_DIRECTORY.exists():
        return DATA_DIRECTORY

    return DATA_DIRECTORY

RANDOM_SEED = 42

FEATURE_COLUMNS = [
    "mean",
    "standard_deviation",
    "rms",
    "minimum",
    "maximum",
    "peak_to_peak",
    "median",
    "kurtosis",
    "dominant_frequency_hz",
    "spectral_energy",
]


def check_input_files() -> None:
    """Prüft, ob alle benötigten Dateien vorhanden sind."""

    required_files = [
        TRAIN_FILE,
        VALIDATION_FILE,
        TEST_FILE,
    ]

    missing_files = [
        str(file_path)
        for file_path in required_files
        if not file_path.exists()
    ]

    if missing_files:
        raise FileNotFoundError(
            "Folgende Dateien fehlen:\n"
            + "\n".join(missing_files)
            + "\n\nFühre zuerst aus:\n"
            + "python src/preprocessing.py"
        )


def check_feature_columns(dataframe: pd.DataFrame) -> None:
    """Prüft, ob alle erforderlichen Merkmale vorhanden sind."""

    missing_columns = [
        column
        for column in FEATURE_COLUMNS
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            "Folgende Merkmale fehlen: "
            + ", ".join(missing_columns)
        )


def calculate_metrics(
    labels: np.ndarray,
    predictions: np.ndarray,
) -> dict[str, float | int]:
    """Berechnet die wichtigsten Klassifikationsmetriken."""

    matrix = confusion_matrix(
        labels,
        predictions,
        labels=[0, 1],
    )

    true_negative, false_positive, false_negative, true_positive = (
        matrix.ravel()
    )

    false_positive_rate = (
        false_positive / (false_positive + true_negative)
        if (false_positive + true_negative) > 0
        else 0.0
    )

    false_negative_rate = (
        false_negative / (false_negative + true_positive)
        if (false_negative + true_positive) > 0
        else 0.0
    )

    return {
        "accuracy": float(
            accuracy_score(labels, predictions)
        ),
        "precision": float(
            precision_score(
                labels,
                predictions,
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                labels,
                predictions,
                zero_division=0,
            )
        ),
        "f1_score": float(
            f1_score(
                labels,
                predictions,
                zero_division=0,
            )
        ),
        "true_negative": int(true_negative),
        "false_positive": int(false_positive),
        "false_negative": int(false_negative),
        "true_positive": int(true_positive),
        "false_positive_rate": float(false_positive_rate),
        "false_negative_rate": float(false_negative_rate),
    }


def save_confusion_matrix(
    labels: np.ndarray,
    predictions: np.ndarray,
    model_name: str,
    output_path: Path,
) -> None:
    """Erstellt und speichert eine Confusion Matrix."""

    display = ConfusionMatrixDisplay.from_predictions(
        labels,
        predictions,
        labels=[0, 1],
        display_labels=["Normal", "Anomalie"],
    )

    display.ax_.set_title(
        f"Confusion Matrix: {model_name}"
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def run_rms_threshold(
    validation_data: pd.DataFrame,
    test_data: pd.DataFrame,
) -> tuple[float, np.ndarray, np.ndarray]:
    """
    Bestimmt den RMS-Schwellenwert anhand normaler
    Validierungsdaten.
    """

    validation_rms = validation_data["rms"].to_numpy(
        dtype=np.float64
    )

    # 99. Perzentil der normalen Validierungsdaten
    threshold = float(
        np.quantile(validation_rms, 0.99)
    )

    test_rms = test_data["rms"].to_numpy(
        dtype=np.float64
    )

    predictions = (
        test_rms > threshold
    ).astype(np.int8)

    # Je höher der Score, desto auffälliger das Fenster.
    anomaly_scores = test_rms - threshold

    return threshold, predictions, anomaly_scores


def train_isolation_forest(
    training_data: pd.DataFrame,
    test_data: pd.DataFrame,
) -> tuple[Pipeline, np.ndarray, np.ndarray]:
    """Trainiert einen Isolation Forest nur mit Normaldaten."""

    x_train = training_data[
        FEATURE_COLUMNS
    ].to_numpy(dtype=np.float64)

    x_test = test_data[
        FEATURE_COLUMNS
    ].to_numpy(dtype=np.float64)

    pipeline = Pipeline(
        steps=[
            (
                "scaler",
                StandardScaler(),
            ),
            (
                "model",
                IsolationForest(
                    n_estimators=200,
                    contamination="auto",
                    random_state=RANDOM_SEED,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    pipeline.fit(x_train)

    raw_predictions = pipeline.predict(x_test)

    # Isolation Forest:
    #  1 = normal
    # -1 = Anomalie
    predictions = (
        raw_predictions == -1
    ).astype(np.int8)

    # decision_function:
    # größere Werte = normaler
    # Deshalb wird das Vorzeichen umgekehrt.
    anomaly_scores = -pipeline.decision_function(
        x_test
    )

    return pipeline, predictions, anomaly_scores


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Trainiert die Baseline-Modelle für Anomalie-Erkennung. "
            "Wenn data/processed fehlt, wird automatisch "
            "data/processed_real verwendet."
        )
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help=(
            "Pfad zum Datensatzordner. Standard: data/processed, "
            "Fallback: data/processed_real"
        ),
    )
    args = parser.parse_args()

    data_directory = resolve_data_directory(args.data_dir)

    global TRAIN_FILE, VALIDATION_FILE, TEST_FILE
    TRAIN_FILE = data_directory / "train_normal.csv"
    VALIDATION_FILE = data_directory / "validation_normal.csv"
    TEST_FILE = data_directory / "test.csv"

    check_input_files()

    MODEL_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )
    RESULT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )
    FIGURE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(f"Verwende Datensatzordner: {data_directory}")

    training_data = pd.read_csv(TRAIN_FILE)
    validation_data = pd.read_csv(VALIDATION_FILE)
    test_data = pd.read_csv(TEST_FILE)

    for dataframe in [
        training_data,
        validation_data,
        test_data,
    ]:
        check_feature_columns(dataframe)

    labels = test_data["label"].to_numpy(
        dtype=np.int8
    )

    # -------------------------------------------------
    # Baseline 1: RMS-Schwellenwert
    # -------------------------------------------------

    (
        rms_threshold,
        rms_predictions,
        rms_scores,
    ) = run_rms_threshold(
        validation_data=validation_data,
        test_data=test_data,
    )

    rms_metrics = calculate_metrics(
        labels=labels,
        predictions=rms_predictions,
    )

    with open(
        MODEL_DIRECTORY / "rms_threshold.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            {
                "feature": "rms",
                "threshold": rms_threshold,
                "threshold_method": (
                    "99th percentile of normal validation data"
                ),
            },
            file,
            indent=2,
        )

    save_confusion_matrix(
        labels=labels,
        predictions=rms_predictions,
        model_name="RMS-Schwellenwert",
        output_path=(
            FIGURE_DIRECTORY
            / "confusion_matrix_rms_threshold.png"
        ),
    )

    # -------------------------------------------------
    # Baseline 2: Isolation Forest
    # -------------------------------------------------

    (
        isolation_model,
        isolation_predictions,
        isolation_scores,
    ) = train_isolation_forest(
        training_data=training_data,
        test_data=test_data,
    )

    isolation_metrics = calculate_metrics(
        labels=labels,
        predictions=isolation_predictions,
    )

    joblib.dump(
        isolation_model,
        MODEL_DIRECTORY / "isolation_forest.joblib",
    )

    save_confusion_matrix(
        labels=labels,
        predictions=isolation_predictions,
        model_name="Isolation Forest",
        output_path=(
            FIGURE_DIRECTORY
            / "confusion_matrix_isolation_forest.png"
        ),
    )

    # -------------------------------------------------
    # Vorhersagen speichern
    # -------------------------------------------------

    prediction_results = test_data[
        [
            "window_id",
            "window_start_s",
            "window_end_s",
            "label",
            "anomaly_type",
        ]
    ].copy()

    prediction_results["rms_value"] = test_data["rms"]
    prediction_results["rms_threshold"] = rms_threshold
    prediction_results["rms_anomaly_score"] = rms_scores
    prediction_results["rms_prediction"] = rms_predictions

    prediction_results[
        "isolation_forest_anomaly_score"
    ] = isolation_scores

    prediction_results[
        "isolation_forest_prediction"
    ] = isolation_predictions

    prediction_results.to_csv(
        RESULT_DIRECTORY / "baseline_predictions.csv",
        index=False,
    )

    # -------------------------------------------------
    # Metriken speichern
    # -------------------------------------------------

    all_metrics = {
        "dataset": {
            "training_windows": len(training_data),
            "validation_windows": len(validation_data),
            "test_windows": len(test_data),
            "normal_test_windows": int(
                (test_data["label"] == 0).sum()
            ),
            "anomaly_test_windows": int(
                (test_data["label"] == 1).sum()
            ),
        },
        "rms_threshold": {
            "threshold": rms_threshold,
            **rms_metrics,
        },
        "isolation_forest": isolation_metrics,
    }

    with open(
        RESULT_DIRECTORY / "baseline_metrics.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            all_metrics,
            file,
            indent=2,
        )

    # -------------------------------------------------
    # Ergebnisse im Terminal ausgeben
    # -------------------------------------------------

    print("Baseline-Training erfolgreich abgeschlossen.")
    print()

    print("Datensätze:")
    print(f"- Training: {len(training_data)} Fenster")
    print(
        f"- Validierung: {len(validation_data)} Fenster"
    )
    print(f"- Test: {len(test_data)} Fenster")
    print()

    print("RMS-Schwellenwert:")
    print(f"- Schwellenwert: {rms_threshold:.6f}")
    print(
        f"- Accuracy: {rms_metrics['accuracy']:.4f}"
    )
    print(
        f"- Precision: {rms_metrics['precision']:.4f}"
    )
    print(
        f"- Recall: {rms_metrics['recall']:.4f}"
    )
    print(
        f"- F1-Score: {rms_metrics['f1_score']:.4f}"
    )
    print()

    print("Isolation Forest:")
    print(
        "- Accuracy: "
        f"{isolation_metrics['accuracy']:.4f}"
    )
    print(
        "- Precision: "
        f"{isolation_metrics['precision']:.4f}"
    )
    print(
        "- Recall: "
        f"{isolation_metrics['recall']:.4f}"
    )
    print(
        "- F1-Score: "
        f"{isolation_metrics['f1_score']:.4f}"
    )
    print()

    print("Erzeugte Dateien:")
    print("- models/rms_threshold.json")
    print("- models/isolation_forest.joblib")
    print("- results/baseline_predictions.csv")
    print("- results/baseline_metrics.json")
    print(
        "- figures/confusion_matrix_rms_threshold.png"
    )
    print(
        "- figures/confusion_matrix_isolation_forest.png"
    )


if __name__ == "__main__":
    main()
