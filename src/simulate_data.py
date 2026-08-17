from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# Damit bei jedem Lauf dieselben Zufallsdaten entstehen
RANDOM_SEED = 42

# 500 Messwerte pro Sekunde
SAMPLE_RATE_HZ = 500

# Ein Zyklus enthält je einmal die drei Anomalietypen und wird mehrfach
# mit frischem Rauschen wiederholt. Ein einzelner Zyklus (20 s) lieferte
# nur 20 Zeitfenster insgesamt - zu wenig für ein robustes Training und
# aussagekräftige Testmetriken der Baseline-Modelle.
CYCLE_DURATION_SECONDS = 20
NUMBER_OF_CYCLES = 25
DURATION_SECONDS = CYCLE_DURATION_SECONDS * NUMBER_OF_CYCLES

# Für die Signalgrafik wird nur ein Ausschnitt gezeigt, da ein Zyklus
# bereits alle drei Anomalietypen einmal enthält und die Grafik sonst
# bei vielen Zyklen unleserlich würde.
PLOT_DURATION_SECONDS = CYCLE_DURATION_SECONDS


def generate_cycle(
    rng: np.random.Generator,
    cycle_start_s: float,
) -> pd.DataFrame:
    """Erzeugt einen Zyklus mit denselben drei Anomalietypen wie im Original."""

    time_s = cycle_start_s + np.arange(
        0,
        CYCLE_DURATION_SECONDS,
        1 / SAMPLE_RATE_HZ,
    )
    local_time_s = time_s - cycle_start_s

    # Normalzustand:
    # gleichmäßige Schwingung mit 30 Hz und geringem Rauschen
    signal = np.sin(2 * np.pi * 30 * time_s)
    signal += rng.normal(0, 0.1, size=len(time_s))

    # Zunächst sind alle Messwerte normal
    label = np.zeros(len(time_s), dtype=int)
    anomaly_type = np.full(len(time_s), "normal", dtype=object)

    # Anomalie 1: erhöhte Amplitude zwischen Sekunde 5 und 7
    amplitude_mask = (local_time_s >= 5) & (local_time_s < 7)

    signal[amplitude_mask] = (
        2.5 * np.sin(2 * np.pi * 30 * time_s[amplitude_mask])
        + rng.normal(0, 0.1, size=amplitude_mask.sum())
    )

    label[amplitude_mask] = 1
    anomaly_type[amplitude_mask] = "increased_amplitude"

    # Anomalie 2: veränderte Frequenz zwischen Sekunde 10 und 12
    frequency_mask = (local_time_s >= 10) & (local_time_s < 12)

    signal[frequency_mask] = (
        np.sin(2 * np.pi * 60 * time_s[frequency_mask])
        + rng.normal(0, 0.1, size=frequency_mask.sum())
    )

    label[frequency_mask] = 1
    anomaly_type[frequency_mask] = "changed_frequency"

    # Anomalie 3: Drift zwischen Sekunde 15 und 17
    drift_mask = (local_time_s >= 15) & (local_time_s < 17)

    signal[drift_mask] += np.linspace(
        0,
        2,
        drift_mask.sum(),
    )

    label[drift_mask] = 1
    anomaly_type[drift_mask] = "drift"

    return pd.DataFrame(
        {
            "timestamp_s": time_s,
            "signal": signal,
            "label": label,
            "anomaly_type": anomaly_type,
            "source": "simulated",
        }
    )


def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED)

    # Zyklus mehrfach mit frischem Rauschen wiederholen, damit die
    # Fenster in Training/Validierung/Test nicht identisch sind.
    cycles = [
        generate_cycle(
            rng=rng,
            cycle_start_s=cycle_index * CYCLE_DURATION_SECONDS,
        )
        for cycle_index in range(NUMBER_OF_CYCLES)
    ]

    dataframe = pd.concat(cycles, ignore_index=True)

    # Zielordner erzeugen, falls sie noch nicht existieren
    data_directory = Path("data/simulated")
    figure_directory = Path("figures")

    data_directory.mkdir(parents=True, exist_ok=True)
    figure_directory.mkdir(parents=True, exist_ok=True)

    # CSV-Datei speichern
    csv_path = data_directory / "simulated_vibration.csv"
    dataframe.to_csv(csv_path, index=False)

    # Diagramm erstellen (nur ein Ausschnitt, da dieser bereits alle
    # drei Anomalietypen einmal enthält und so lesbar bleibt)
    plot_data = dataframe[
        dataframe["timestamp_s"] < PLOT_DURATION_SECONDS
    ]

    plt.figure(figsize=(12, 5))
    plt.gcf().canvas.manager.set_window_title(
        "Masterarbeit FB 2 - UAS Frankfurt"
    )
    plt.plot(
        plot_data["timestamp_s"],
        plot_data["signal"],
        linewidth=0.8,
        label="Vibrationssignal",
    )

    anomaly_rows = plot_data["label"] == 1

    plt.scatter(
        plot_data.loc[anomaly_rows, "timestamp_s"],
        plot_data.loc[anomaly_rows, "signal"],
        s=4,
        label="Anomalie",
    )

    plt.xlabel("Zeit in Sekunden")
    plt.ylabel("Simulierte Beschleunigung")
    plt.suptitle(
        "Masterarbeit FB 2\nUAS Frankfurt",
        y=1.02,
        fontsize=10,
    )
    plt.title(
        f"Figure 1: Simuliertes Vibrationssignal "
        f"(Ausschnitt: erste {PLOT_DURATION_SECONDS} s)"
    )
    plt.legend()
    plt.tight_layout()

    figure_path = figure_directory / "simulated_vibration.png"
    plt.savefig(figure_path, dpi=200)
    plt.close()

    print("Simulation erfolgreich abgeschlossen.")
    print(f"CSV-Datei: {csv_path}")
    print(f"Diagramm: {figure_path}")
    print(f"Anzahl Zyklen: {NUMBER_OF_CYCLES}")
    print(f"Anzahl Messwerte: {len(dataframe)}")
    print(f"Anteil Anomalien: {dataframe['label'].mean():.2%}")


if __name__ == "__main__":
    main()
