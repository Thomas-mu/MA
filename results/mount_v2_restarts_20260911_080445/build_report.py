"""Format a separate report after all three recordings and their assessment."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json

BASE=Path(__file__).resolve().parent
OUT=BASE/'analysis'


def fmt(value,digits=3):return f'{value:.{digits}f}'.replace('.',',')


def main():
    r=json.loads((OUT/'report.json').read_text())
    assessment=json.loads((OUT/'assessment.json').read_text())
    assert len(r['records'])==3
    lines=['# Drei unabhängige Normalstarts mit neuer Montage','',assessment['conclusion'],'',
           '## Festgelegter Ablauf und Randbedingungen','',
           'Unveränderte Montage: ADXL345 mit zwei Schrauben am äußeren, feststehenden Lüfterrahmen, Platine schräg. Aufbaukennung: `'+r['mounting_id']+'`. Die vorhandene vollständige Sicherheitsbestätigung gilt für diesen unveränderten Aufbau. Externe 12-V-Versorgung angeschlossen. Alle drei Starts erfolgten nach einer eigenen Sichtbestätigung des vollständigen Stillstands und einer angeforderten Auszeit von 60 s ab protokollierter Annahme dieser Bestätigung. Danach 75 % bei 25 kHz und jeweils 300 s Aufnahme ohne absichtliche Einlaufpause. Nach jedem Lauf Rückstellung auf 0 %, Rücklesung und zehn Sekunden Auslaufzeit. Keine Antwortfristen oder automatischen Ersatzstarts.','',
           'ADXL345: nominell 200 Hz, ±2 g, Full Resolution, FIFO Stream, I²C-Konfiguration 100 kHz. Die Registerkonfiguration wurde je Lauf gespeichert und auf Gleichheit geprüft. Steuerung: BCM-GPIO18, physischer Pin 12, Hardware-PWM PWM0_CHAN2/a3, Periode 40.000 ns, Tastdauer 30.000 ns bei 75 %. Sensor und Steuerung wurden exklusiv verwendet. Eine Stellvorgabe und ihre Rücklesung sind keine Drehzahlmessung.','',
           'Primärer, vorab festgelegter Prüfbereich: 180–300 s seit dem ersten tatsächlichen XYZ-Punkt. Darin je 24 nicht überlappende 5-s-Abschnitte. Zusätzlich wird der gesamte 300-s-Verlauf dargestellt. In jedem Abschnitt werden alle drei Achsenmittelwerte separat entfernt: Vektor-AC-RMS=sqrt(mean(sum((XYZ−Abschnitts-Achsenmittelwerte)²))). 180 s ist eine zu prüfende Einlaufzeit. 1 mg bezeichnet 0,001 g Beschleunigung.','',
           '## Zeitpunkte und Auszeiten','',
           '| Lauf | PWM-Befehl, MESZ | Auszeit ab Bestätigung bis Befehlsaufruf [s] | Gesamte Auszeit seit vorherigem 0-%-Befehlsabschluss [s] | Erster XYZ-Punkt nach Befehlsabschluss [ms] |',
           '|---|---|---:|---:|---:|']
    for x in r['records']:
        local=datetime.fromisoformat(x['command_invocation_utc']).astimezone(ZoneInfo('Europe/Berlin')).strftime('%H:%M:%S.%f')[:-3]
        lines.append(f'| {x["name"]} | {local} | {fmt(x["controlled_off_to_command_s"])} | {fmt(x["total_off_since_previous_zero_s"])} | {fmt(1000*x["timing"]["first_xyz_after_command_completion_s"])} |')
    lines+=['','Die feste Auszeit nach Bestätigung und die gesamte Auszeit sind unterschiedliche Größen. Die variable Wartezeit auf die Sichtprüfung ist vollständig enthalten. Gleiche thermische Ausgangsbedingungen oder gleiche Rotortemperaturen sind damit nicht nachgewiesen. Zeitversätze werden aus monotonen Hostzeitstempeln berechnet; elektrische Signalflanken und Rotorstart wurden nicht gemessen.','',
            '## Datenqualität und Zeitbasis','',
            '| Lauf | XYZ-Punkte | Einzelne Achsenwerte | Beobachtet [XYZ/s] | Spanne erster–letzter XYZ-Punkt [s] | Host-Abstand P99 / Maximum [ms] | Gap / Overrun / Sättigung |',
            '|---|---:|---:|---:|---:|---:|---|']
    for x in r['records']:
        q=x['quality']
        flags=' / '.join(str(q[k+'_flagged_points']) for k in ('gap','overrun','saturated'))
        lines.append(f'| {x["name"]} | {q["xyz_points"]} | {q["individual_axis_values"]} | {fmt(q["observed_rate_xyz_per_s"],5)} | {fmt(q["first_to_last_xyz_s"],6)} | {fmt(q["host_interval_p99_ms"])} / {fmt(q["host_interval_max_ms"])} | {flags} |')
    lines+=['','Der Durchsatz ist (N−1)/(letzter−erster Hostzeitpunkt). Eine Zeile enthält ein vollständiges XYZ-Tupel, also drei einzelne Achsenwerte. Die nominelle ODR bleibt 200 Hz; `sensor_time_estimate_s = sample_index/200` ist keine unabhängige Messuhr. Die Ursache einer Abweichung des beobachteten Durchsatzes von der nominellen Einstellung kann aus den Hostzeitstempeln allein nicht abschließend bestimmt werden.','',
            'Die Auswertung prüft CSV-Hashes, Zählwerte, endliche XYZ-Werte, streng monotone Zeitstempel, fortlaufende Softwareindizes, Zeitspalten und Qualitätsflags. Daten werden weder interpoliert noch stillschweigend ausgeschlossen. Ungesetzte Flags und fortlaufende Indizes beweisen keine exakt verlustfreie interne Sensorabtastung. Host-Leseabstände und Dauer des erfolgreichen Registerlesevorgangs sind getrennte Größen; vollständige Quantile und auffällige Intervalle stehen in `report.json`.','',
            '## Schwankungen im Prüfbereich 180–300 s','',
            '| Lauf | Mittel der 24 Abschnittswerte [mg] | Streuung innerhalb des Laufs [mg] | CV [%] | Minimum–Maximum [mg] | Änderung Minute 5 gegenüber Minute 4 [%] |',
            '|---|---:|---:|---:|---:|---:|']
    for x in r['records']:
        p=x['primary_180_300']
        lines.append(f'| {x["name"]} | {fmt(p["mean"]*1000)} | {fmt(p["population_std"]*1000)} | {fmt(p["descriptive_cv_percent"])} | {fmt(p["minimum"]*1000)}–{fmt(p["maximum"]*1000)} | {fmt(x["primary_late_vs_early_percent"])} |')
    b=r['between']
    lines+=['',f'Die drei Laufmittel reichen von {fmt(b["minimum"]*1000)} bis {fmt(b["maximum"]*1000)} mg. Ihre Spannweite beträgt {fmt(b["range"]*1000)} mg beziehungsweise {fmt(b["range_percent_of_grand_mean"])} % des gemeinsamen Mittels. Die Stichprobenstandardabweichung der drei Laufmittel beträgt {fmt(b["sample_std_of_three_run_means_g"]*1000)} mg (ddof=1). Die Streuungen innerhalb eines Laufs verwenden hingegen ddof=0.','',
            'Die 24 benachbarten Abschnitte eines Laufs sind keine 24 unabhängigen Starts. Der Vergleich beruht auf drei Neustarts und erlaubt eine deskriptive Pilotbewertung. Es wurden weder nachträgliche Bestehensschwellen noch Signifikanztests verwendet.','',
            '![Vergleich der drei Starts](restart_comparison.png)','','## Bewertung und nächster Schritt','',
            assessment['interpretation'],'',assessment['next_step'],'',
            '## Ablage und Grenzen','',
            'Die drei Rohaufnahmen mit individuellen JSON-Metadaten liegen im neuen Datenverzeichnis `../../../data/mount_v2_restarts_20260911_080445/`. `report.json`, `five_second_sections.csv` und `primary_summary.csv` enthalten die Ergebnisse; die Grafik liegt als PNG und PDF vor. Beobachtungen werden getrennt von PWM-Rücklesungen dokumentiert. Frühere Messwerte wurden nicht in die drei Wiederholungen aufgenommen.','',
            'Keine Modelle trainiert, keine Anomalien erzeugt und keine Worddatei oder bestehende Messdatei bearbeitet. Die abschließende Steuerungs- und Dateierhaltungsprüfung steht separat in `../final_verification.json`. Eine erfolgreiche Anomalieerkennung ist durch diesen Normalversuch nicht nachgewiesen.']
    with (OUT/'report.md').open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')


if __name__=='__main__':main()
