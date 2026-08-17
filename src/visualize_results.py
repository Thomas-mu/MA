import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FIGURE_DIR = Path("figures")
FIGURE_DIR.mkdir(parents=True, exist_ok=True)

DATA_FILE = Path("data/simulated/simulated_vibration.csv")
METRICS_FILE = Path("results/baseline_metrics.json")
PREDICTIONS_FILE = Path("results/baseline_predictions.csv")

# Für die Signalgrafik wird nur ein Ausschnitt gezeigt, damit sie bei
# vielen simulierten Zyklen lesbar bleibt.
PLOT_DURATION_SECONDS = 20


def check_input_files() -> None:
    """Prüft, ob alle benötigten Dateien vorhanden sind."""

    required_files = [DATA_FILE, METRICS_FILE, PREDICTIONS_FILE]

    missing_files = [
        str(file_path)
        for file_path in required_files
        if not file_path.exists()
    ]

    if missing_files:
        raise FileNotFoundError(
            "Folgende Dateien fehlen:\n"
            + "\n".join(missing_files)
            + "\n\nFühre zuerst diese Befehle aus:\n"
            + "python src/simulate_data.py\n"
            + "python src/preprocessing.py\n"
            + "python src/train_baseline.py"
        )


def plot_signal() -> None:
    data = pd.read_csv(DATA_FILE)
    data = data[data["timestamp_s"] < PLOT_DURATION_SECONDS]

    plt.figure(figsize=(14, 5))

    plt.plot(
        data["timestamp_s"],
        data["signal"],
        linewidth=0.8,
        label="Vibrationssignal",
    )

    anomalies = data["label"] == 1

    plt.scatter(
        data.loc[anomalies, "timestamp_s"],
        data.loc[anomalies, "signal"],
        s=6,
        label="Anomalie",
    )

    plt.title(
        f"Simuliertes Vibrationssignal "
        f"(Ausschnitt: erste {PLOT_DURATION_SECONDS} s)"
    )
    plt.xlabel("Zeit in Sekunden")
    plt.ylabel("Signalwert")
    plt.legend()
    plt.grid(alpha=0.25)
    plt.tight_layout()

    plt.savefig(
        FIGURE_DIR / "01_vibrationssignal.png",
        dpi=300,
    )
    plt.close()


def plot_metrics() -> None:
    with open(METRICS_FILE, encoding="utf-8") as file:
        metrics = json.load(file)

    names = [
        "Accuracy",
        "Precision",
        "Recall",
        "F1-Score",
    ]

    rms = [
        metrics["rms_threshold"]["accuracy"],
        metrics["rms_threshold"]["precision"],
        metrics["rms_threshold"]["recall"],
        metrics["rms_threshold"]["f1_score"],
    ]

    isolation = [
        metrics["isolation_forest"]["accuracy"],
        metrics["isolation_forest"]["precision"],
        metrics["isolation_forest"]["recall"],
        metrics["isolation_forest"]["f1_score"],
    ]

    positions = np.arange(len(names))
    width = 0.36

    plt.figure(figsize=(10, 6))

    rms_bars = plt.bar(
        positions - width / 2,
        rms,
        width,
        label="RMS-Schwellenwert",
    )

    isolation_bars = plt.bar(
        positions + width / 2,
        isolation,
        width,
        label="Isolation Forest",
    )

    plt.title("Vergleich der Baseline-Modelle")
    plt.xlabel("Metrik")
    plt.ylabel("Ergebnis")
    plt.xticks(positions, names)
    plt.ylim(0, 1.1)
    plt.grid(axis="y", alpha=0.25)
    plt.legend()

    for bars in (rms_bars, isolation_bars):
        for bar in bars:
            value = bar.get_height()

            plt.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.02,
                f"{value:.2f}",
                ha="center",
            )

    plt.tight_layout()

    plt.savefig(
        FIGURE_DIR / "02_modellvergleich.png",
        dpi=300,
    )
    plt.close()


def _break_at_gaps(
    x: pd.Series,
    y: pd.Series,
    max_gap_s: float = 1.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Fügt an großen Zeitlücken NaN-Werte ein.

    Der Testdatensatz enthält nur einen Teil der Zeitfenster (normale
    Fenster nur aus dem letzten Zeitabschnitt, Anomaliefenster aus dem
    gesamten Zeitraum). Ohne diese Lücken würde eine Stufenlinie weit
    auseinanderliegende Fenster fälschlich als durchgehenden Zustand
    darstellen.
    """

    x = x.to_numpy(dtype=float)
    y = y.to_numpy(dtype=float)

    gap_indices = np.where(np.diff(x) > max_gap_s)[0]

    x_with_gaps = np.insert(x, gap_indices + 1, x[gap_indices] + 1e-9)
    y_with_gaps = np.insert(y, gap_indices + 1, np.nan)

    return x_with_gaps, y_with_gaps


def plot_predictions() -> None:
    data = pd.read_csv(PREDICTIONS_FILE)

    plt.figure(figsize=(14, 5))

    plt.step(
        *_break_at_gaps(data["window_start_s"], data["label"]),
        where="post",
        linewidth=2.5,
        label="Tatsächlicher Zustand",
    )

    plt.step(
        *_break_at_gaps(
            data["window_start_s"],
            data["rms_prediction"] + 0.05,
        ),
        where="post",
        linestyle="--",
        label="RMS-Ergebnis",
    )

    plt.step(
        *_break_at_gaps(
            data["window_start_s"],
            data["isolation_forest_prediction"] - 0.05,
        ),
        where="post",
        linestyle=":",
        label="Isolation-Forest-Ergebnis",
    )

    plt.title("Tatsächliche und erkannte Anomalien")
    plt.xlabel("Zeitfenster in Sekunden")
    plt.ylabel("Zustand")
    plt.yticks([0, 1], ["Normal", "Anomalie"])
    plt.ylim(-0.2, 1.2)
    plt.grid(alpha=0.25)
    plt.legend()
    plt.figtext(
        0.5,
        0.01,
        "Hinweis: Normale Zeitfenster stammen nur aus dem letzten "
        "Zeitabschnitt (Testdaten), Anomaliefenster aus dem gesamten "
        "Zeitraum. Lücken markieren Bereiche ohne Testdaten.",
        ha="center",
        fontsize=8,
        color="gray",
    )
    plt.tight_layout(rect=(0, 0.04, 1, 1))

    plt.savefig(
        FIGURE_DIR / "03_anomalieerkennung.png",
        dpi=300,
    )
    plt.close()


def main() -> None:
    check_input_files()

    plot_signal()
    plot_metrics()
    plot_predictions()

    print("Diagramme erfolgreich erstellt:")
    print("- figures/01_vibrationssignal.png")
    print("- figures/02_modellvergleich.png")
    print("- figures/03_anomalieerkennung.png")


if __name__ == "__main__":
    main()
