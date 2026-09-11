"""Offline interim comparison; preserves earlier reports and awaits normal_after."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
PHASES = ('normal_before', 'airflow_modified')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fmt(value, digits=3):
    return f'{value:.{digits}f}'.replace('.', ',')


def main():
    out = BASE / 'analysis' / 'airflow_before_comparison'
    report_path = BASE / 'airflow_interim_report.md'
    if out.exists() or report_path.exists():
        raise FileExistsError('Existing interim results must not be overwritten')
    reports = {p: json.loads((BASE / 'analysis' / p / 'summary.json').read_text()) for p in PHASES}
    sessions = {p: json.loads((BASE / f'{p}_session.json').read_text()) for p in PHASES}
    tables = {p: pd.read_csv(BASE / 'analysis' / p / 'five_second_rms.csv') for p in PHASES}
    normal, altered = (reports[p] for p in PHASES)
    assert normal['mounting_id'] == altered['mounting_id']
    assert normal['sensor'] == altered['sensor']
    assert not (BASE / 'normal_after_session.json').exists(), 'Use the complete comparison after the last phase'
    inputs = {}
    for p in PHASES:
        assert sessions[p]['status'] == 'completed'
        assert sessions[p]['final_readback']['pwm_configuration']['configured_duty_percent'] == 0
        assert reports[p]['control_transactions'] == [75.0, 0.0]
        for relative, expected in reports[p]['input_sha256'].items():
            assert digest(ROOT / relative) == expected
            inputs[relative] = expected
        for path in [BASE / 'analysis' / p / 'summary.json', BASE / 'analysis' / p / 'five_second_rms.csv']:
            inputs[str(path.relative_to(ROOT))] = digest(path)
    late = {p: tables[p].loc[tables[p].start_s >= 180, 'vector_ac_rms_mg'].to_numpy() for p in PHASES}
    assert all(len(v) == 24 for v in late.values())
    before, changed = (late[p] for p in PHASES)
    delta = float(changed.mean() - before.mean())
    comparison = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'mounting_id': normal['mounting_id'],
        'status': 'interim; normal_after not captured',
        'phase_labels': list(PHASES), 'primary_interval_s': [180, 300],
        'one_complete_recording_per_phase': True, 'windows_are_independent_replicates': False,
        'mean_difference_mg': delta,
        'mean_difference_percent_of_normal': float(100 * delta / before.mean()),
        'observed_window_ranges_overlap': bool(max(before.min(), changed.min()) <= min(before.max(), changed.max())),
        'absolute_difference_over_before_window_sd': float(abs(delta) / before.std()) if before.std() else None,
        'normal_between_start_variability_estimated': False,
        'return_to_normal_assessed': False, 'settling_time_validated': False,
        'primary': {p: reports[p]['primary_180_300'] for p in PHASES},
        'input_sha256': inputs, 'source_sha256': digest(Path(__file__)),
        'models_trained': False, 'defect_proven': False, 'anomaly_detection_evaluated': False,
    }
    out.mkdir()
    with (out / 'comparison.json').open('x') as handle:
        json.dump(comparison, handle, indent=2, ensure_ascii=False, allow_nan=False)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), layout='constrained')
    names = {'normal_before': 'Normal vor Umbau', 'airflow_modified': 'Mit Platte'}
    for phase in PHASES:
        d = tables[phase]
        x, y = d.start_s.to_numpy() + 2.5, d.vector_ac_rms_mg.to_numpy()
        axes[0].plot(x, y, 'o-', markersize=3, label=names[phase])
        axes[1].plot(x[36:], y[36:], 'o-', markersize=3, label=names[phase])
        axes[2].plot(x[36:], y[36:] - y[36:].mean(), 'o-', markersize=3, label=names[phase])
    axes[0].axvspan(180, 300, color='gray', alpha=.12)
    axes[0].set(xlim=(0, 300), ylabel='Vektor-AC-RMS [mg]', title='Vollständige Verläufe: eigene Achsenmittelwerte je 5-s-Fenster entfernt')
    axes[1].set(xlim=(180, 300), ylabel='Vektor-AC-RMS [mg]', title='180–300 s: vorläufiges Auswertefenster')
    axes[2].axhline(0, color='gray', linewidth=.7)
    axes[2].set(xlim=(180, 300), ylabel='Abweichung vom Laufmittel [mg]', title='Zeitlicher Verlauf nach Abzug des jeweiligen späten RMS-Laufmittels')
    for ax in axes:
        ax.set_xlabel('Zeit seit jeweiligem PWM-Befehlsaufruf [s]')
        ax.grid(alpha=.25)
        ax.legend()
    fig.suptitle('Aufbauversion v4: 75 % PWM, 25 kHz\nZwischenvergleich; Rückkehrreferenz steht noch aus')
    fig.savefig(out / 'comparison.png', dpi=160)
    fig.savefig(out / 'comparison.pdf')
    plt.close(fig)

    a = altered['primary_180_300']
    n = normal['primary_180_300']
    s = sessions['airflow_modified']
    q = altered['quality']
    table = []
    for p in PHASES:
        r = reports[p]; quality = r['quality']; primary = r['primary_180_300']
        table.append(f"| `{p}` | {quality['xyz_points']} | {fmt(quality['observed_xyz_s'], 4)} | {fmt(quality['host_interval_max_ms'])} | {quality['host_intervals_over_10ms']} | {quality['fifo_max']} | {quality['gap_count']} / {quality['overrun_count']} / {quality['saturated_count']} |")
    values = []
    for label, key in [('Mittlerer Fenster-AC-RMS [mg]', 'mean_mg'), ('Fensterstandardabweichung, Divisor 24 [mg]', 'std_mg_ddof0'), ('Minimum [mg]', 'min_mg'), ('Maximum [mg]', 'max_mg'), ('Lineare Steigung [mg/min]', 'linear_slope_mg_min'), ('Robuste Mediansteigung [mg/min]', 'theil_sen_slope_mg_min'), ('Angepasste Änderung über 120 s [mg]', 'fitted_120s_change_mg'), ('Angepasste Änderung relativ zum Laufmittel [%]', 'fitted_120s_change_percent'), ('Letzte 60 s minus erste 60 s [mg]', 'last60_minus_first60_mg')]:
        values.append(f'| {label} | {fmt(n[key])} | {fmt(a[key])} |')
    message = f'''# Zwischenbericht: Normalbetrieb und eingesetzte Platte

Aufbauversion **`{altered['mounting_id']}`**. `standstill`, `normal_before` und `airflow_modified` sind abgeschlossen. Die Rückkehrreferenz `normal_after` steht aus und ist noch nicht freigegeben. Frühere Aufstellungen werden nicht als direkte Normalreferenz verwendet.

## Bedingungen und Durchführung

Der Nutzer berichtete, vor dem Plattenumbau die externe 12-V-Versorgung getrennt und vollständigen Stillstand abgewartet zu haben. Nur die Platte wurde eingesetzt; Lüfter und Sensor blieben nach seiner Angabe an ihrer Position. Die anschließend wieder angeschlossene Versorgung und die Freigabe ausschließlich dieses Laufs sind in [airflow_modified_release.json](airflow_modified_release.json) dokumentiert. Der Originalwortlaut bleibt dort neben der für die bestehende Software normalisierten Freigabe erhalten.

Geplant sind eine separat befestigte Platte von 60 × 120 mm, parallel zum Luftauslass, mit 100 mm Abstand. Tatsächliche Maße, Abstand, Ausrichtung, Auslassidentifikation und Material sind weiterhin unbekannt. Die Angabe „Platte eingesetzt“ ist keine Vermessung. [Phasengeometrie](airflow_modified_geometry.json) trennt Sollwerte und Nutzerangaben. Der Luftstrom wurde nicht direkt gemessen. Die Bedingung heißt kontrollierter veränderter Betriebszustand, nicht nachgewiesener Defekt. Ein numerisches CSV-Label 1 bezeichnet allein diese Versuchsbedingung.

Der PWM-Befehlsaufruf erfolgte **{s['command_invocation_utc']}**. Alle hier genannten Zeitstempel sind UTC; Ortszeit Europe/Berlin liegt zwei Stunden später. Die zusätzliche Auszeit ab softwareseitiger Annahme der Freigabe betrug **{fmt(s['additional_off_from_release_actual_s'], 6)} s** bei geplanten 60 s. Der Abstand zum Abschluss des vorangegangenen Nullbefehls betrug **{fmt(s['total_off_since_previous_zero_s'], 6)} s**; dies ist keine unabhängig gemessene mechanische Stillstands-, Abkühl- oder Spannungsunterbrechungsdauer. Beim ersten Normallauf waren es wegen der Vorbereitung 84,097 s ab Freigabe. Gleiche gesamte Auszeiten werden nicht behauptet.

Die erste XYZ-Lesung erfolgte **{s['timing']['first_xyz_utc_estimate']}**, **{fmt(1000 * s['timing']['first_xyz_after_command_invocation_s'])} ms nach Befehlsaufruf** bzw. {fmt(1000 * s['timing']['first_xyz_after_command_completion_s'])} ms nach Befehlsabschluss. Elektrische PWM-Flanke, Rotorstart und Drehzahl wurden nicht gemessen. Es gab genau einen Start auf 75 % bei 25 kHz, 300 s Erfassung und anschließend genau einen Nullbefehl. Keine Antwortfrist, Laufbeobachtungsfrage oder automatische Wiederholung wurde verwendet.

## Datenqualität und Zeitbasis

Die rückgelesene Sensorkonfiguration entspricht der neuen Normalreferenz: ADXL345, nominell **200 Hz**, ±2 g, Full Resolution, FIFO-Stream, 0,0039 g/LSB, I²C-Bus 1 und konfigurierter Bustakt 100 kHz. Register BW_RATE=0x0B, DATA_FORMAT=0x08, INT_ENABLE=0x00, FIFO_CTL=0x90, POWER_CTL=0x08. Die Hostzeitpunkte stammen vom Abschluss der jeweiligen XYZ-Lesung. Der Durchsatz wird als `(N−1)/(t_letzter−t_erster)` berechnet, getrennt von der nominellen Sensor-ODR.

| Phase | XYZ-Punkte | Beobachtet [XYZ/s] | Hostabstand max. [ms] | Abstände >10 ms | FIFO max. | Gap / Overrun / Sättigung |
|---|---:|---:|---:|---:|---:|---|
{chr(10).join(table)}

Die neue Plattenaufnahme enthält **{q['single_axis_values']} einzelne Achsenwerte**, also drei pro XYZ-Messpunkt; erste bis letzte XYZ-Lesung umfassen {fmt(q['first_to_last_host_s'], 6)} s. Rohdatenhashes, endliche Achsenwerte, streng steigende Hostzeitstempel, Zeitspaltenkonsistenz und fortlaufende Softwareindices wurden geprüft. Die genaue Sensorverlustzahl bleibt unbekannt: fehlende Flags und fortlaufende Softwareindices beweisen nicht, dass jede physische Sensorwandlung erfasst wurde. Größere Host-Leseabstände sind nicht automatisch verlorene Messpunkte. Die Beobachtung von etwa 207 XYZ/s wird nicht in 200 Hz umetikettiert; eine unabhängige Kalibrierung der Sensorzeitbasis liegt nicht vor.

Zeitpunkte größerer Hostabstände, Achsenmittelwerte und Achsenstreuungen stehen in der [Phasenauswertung](analysis/airflow_modified/summary.json). Die bisherige Stillstandsreferenz bleibt separat im [ersten Zwischenbericht](initial_report.md) dokumentiert. In dieser Phase wurde keine weitere Stillstandsaufnahme vorgenommen.

## Vibration und zeitlicher Verlauf

In jedem nicht überlappenden 5-s-Fenster werden zunächst die drei jeweiligen Achsenmittelwerte abgezogen. Danach wird `sqrt(mean(x_ac² + y_ac² + z_ac²))` berechnet. mg bezeichnet 0,001 g Beschleunigung. Pro Betriebslauf entstehen 60 Fenster, davon 24 im Prüfabschnitt 180–300 s. Die kurze Lücke zwischen Stellbefehl und erster Lesung wird nicht aufgefüllt. Rohdaten nach 300 s bleiben erhalten und werden außerhalb der festgelegten Fenster nicht einbezogen.

| Kennwert in 180–300 s | Normal vor Umbau | Mit Platte |
|---|---:|---:|
{chr(10).join(values)}

Der Unterschied der späten RMS-Mittelwerte beträgt **{fmt(delta)} mg ({fmt(comparison['mean_difference_percent_of_normal'])} % des Normalmittelwerts)**. Die beobachteten Fensterbereiche überlappen: **{'ja' if comparison['observed_window_ranges_overlap'] else 'nein'}**. Dies beschreibt zwei konkrete Aufnahmen; die 24 benachbarten Fenster sind keine unabhängigen Versuchsreplikate. Der Unterschied zwischen Aufnahmen ist getrennt von den tabellierten zeitlichen Steigungen innerhalb jeder Aufnahme zu betrachten. 180 s bleiben ein Prüfkandidat, keine gesicherte allgemeine Einlaufzeit.

![Zwischenvergleich der vollständigen Verläufe, späten Niveaus und zeitlichen Schwankungen](analysis/airflow_before_comparison/comparison.png)

![Plattenaufnahme einschließlich Host-Leseabständen](analysis/airflow_modified/phase_overview.png)

[Fensterwerte](analysis/airflow_modified/five_second_rms.csv), [Vergleich als JSON](analysis/airflow_before_comparison/comparison.json), [Vergleichsgrafik als PDF](analysis/airflow_before_comparison/comparison.pdf). Rohdaten: [{Path(s['csv']).name}](../../{s['csv']}). Die Rohdaten- und Steuerjournalhashes stehen in der Phasenauswertung.

## Grenzen und nächster Schritt

Ohne Rückkehrreferenz ist noch ungeklärt, ob das Signal nach Entfernen der Platte zurückkehrt und wie groß die normalen Unterschiede zwischen den beiden Starts dieser Folge sind. Die Veränderung kann daher noch nicht eindeutig der Platte zugeschrieben werden. Selbst die vollständige einzelne Folge belegt weder allgemeine Reproduzierbarkeit noch einen Defekt oder erfolgreiche Anomalieerkennung. Die fehlenden Istmaße begrenzen zusätzlich die Wiederholbarkeit des Plattenzustands. Es wurden keine Modelle trainiert.

Nach der Aufnahme wurde **0 % PWM bei 25 kHz** eingestellt und mit korrekter Pin-Funktion rückgelesen; Nullbefehlsabschluss: **{s['zero_command_completed_utc']}**. Mechanischer Stillstand nach diesem Lauf wurde nicht beobachtet.

Nächster manueller Schritt: externe 12-V-Versorgung trennen, vollständigen Stillstand abwarten und nur die Platte entfernen. Lüfter und Sensor bleiben unverändert. Nach Wiederanschließen der Versorgung sendet der Nutzer selbstständig seine Freigabe für den nächsten Lauf. Bis dahin wird pausiert. Erst dann folgen 60 s zusätzliche Auszeit und einmalig 300 s `normal_after` bei 75 % und 25 kHz, anschließend 0 % mit Rücklesen. Die vollständige Rückkehrbewertung folgt nach dieser Aufnahme. Worddatei, Modelle und historische Dateien werden nicht bearbeitet.
'''
    with report_path.open('x') as handle:
        handle.write(message)
    assert all(digest(ROOT / path) == expected for path, expected in inputs.items())
    print(json.dumps({key: comparison[key] for key in ['mean_difference_mg', 'mean_difference_percent_of_normal', 'observed_window_ranges_overlap']}, indent=2))
    print(report_path)


if __name__ == '__main__':
    main()
