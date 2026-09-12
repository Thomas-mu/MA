#!/usr/bin/env python3
"""Write human report from completed, immutable evaluation artifacts only."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,hashlib
import numpy as np
BASE=Path(__file__).resolve().parent
OUT=BASE/'comparison_50_vs_75'
def read(p):return json.loads(Path(p).read_text())
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fmt(x,n=3):return 'unbekannt/nicht definiert' if x is None else f'{x:.{n}f}'
def local(s):return datetime.fromisoformat(s).astimezone(ZoneInfo('Europe/Berlin')).strftime('%H:%M:%S.%f')[:-3]

def main():
    p=read(BASE/'protocol.json');comparison=read(OUT/'comparison.json');runs=read(OUT/'acquisition_quality.json')
    lines=['# Unabhängige Normalitätsprüfung bei 50 % PWM – Aufbau v4','',
    'Drei separat gespeicherte normale Betriebsläufe ohne Platte wurden bei 50 % PWM und 25 kHz ausgeführt. Der Nutzer bestätigte vor der Folge die entfernte Platte, unveränderten Aufbau v4, mechanischen Stillstand und angeschlossene Versorgung. Die zuvor ausdrücklich erlaubte automatische Steuerung wurde für die drei geplanten Starts verwendet. Zwischen den Läufen wurden 0 % eingestellt und zurückgelesen; ein neuer mechanischer Stillstand wurde dabei nicht beobachtet. Deshalb handelt es sich um drei getrennte Stellstarts mit dokumentierter Auszeit, nicht um drei jeweils durch Sichtprüfung bestätigte mechanische Neustarts.','',
    'Das eingefrorene Modellpaket, Scaler, Schwellen, Vorverarbeitung und Abschnitt [180,300) s blieben unverändert. Rohdaten enthalten den gesamten Anlauf. Pro Methode wurden dieselben 128er-XYZ-Fenster mit Schrittweite 128 ohne Überlappung verwendet; keine Fenster über Aufnahmegrenzen. Die Mittelwertentfernung erfolgt achsenweise in Float64, danach Float32 und gespeicherte Skalierung.','',
    '## Durchführung und Zeitbasis','',
    '| Lauf | Stellbefehl (CEST) | Erstes XYZ (CEST) | Versatz (ms) | XYZ-Punkte | Host-Spanne (s) | Beobachtete XYZ/s |',
    '|---|---|---|---:|---:|---:|---:|']
    for r in runs:
        q=r['quality'];lines.append(f"| {r['phase']} | {local(r['command_utc'])} | {local(r['first_xyz_utc_estimate'])} | {r['first_xyz_delay_s']*1000:.3f} | {q['xyz_points']} | {q['first_to_last_host_span_s']:.6f} | {q['observed_xyz_per_second']:.6f} |")
    lines += ['',
    'Der erste UTC-Zeitpunkt eines XYZ-Werts wird aus Stellbefehl-UTC und monotonem Versatz zugeordnet. Host-Leseabschluss ist nicht Sensor-Konversionszeit. Nominell eingestellt sind weiterhin **200 Hz**, ±2 g, Full Resolution, 0,0039 g/LSB, FIFO-Stream und I²C-Konfiguration 100 kHz. Sensorregister: BW_RATE 0x0b, DATA_FORMAT 0x08, INT_ENABLE 0x00, FIFO_CTL 0x90, POWER_CTL 0x08. Die Steuerung verwendet BCM GPIO18 (physischer Pin 12), a3/PWM0_CHAN2, Periode 40000 ns und bei 50 % eine Tastzeit von 20000 ns. Drehzahl und elektrischer Signalverlauf wurden nicht unabhängig gemessen.','',
    '| Lauf | Zusätzliche Auszeit ab Freigabe/Fortsetzung (s) | Gesamtzeit seit vorheriger Nullstellung (s) | Abschließender 0-%-Befehl (CEST) |',
    '|---|---:|---:|---|']
    for r in runs:lines.append(f"| {r['phase']} | {fmt(r['additional_off_from_release_s'],6)} | {fmt(r['total_off_since_previous_zero_s'],6)} | {local(r['zero_command_completed_utc'])} |")
    lines += ['',
    'Die erste gesamte vorangegangene Auszeit ist unbekannt. Die folgenden Gesamtzeiten werden ab Abschluss des vorherigen Software-Nullstellbefehls gerechnet, nicht ab einem gemessenen mechanischen Stopp. Die 60 s sind eine zusätzliche Software-Auszeit; identische gesamte Auszeiten oder Kühlbedingungen werden nicht behauptet. Es gab keine automatischen Ersatzstarts.','',
    '## Datenqualität','',
    '| Lauf | Host-P99 / Maximum (ms) | Abstände >10 / >160 ms | FIFO-Maximum | Gap / Overrun / Sättigung | Gültige / ungültige Modellfenster | Rest-XYZ in [180,300) |',
    '|---|---|---|---:|---|---|---:|']
    for r in runs:
        q=r['quality'];sel=q['selected_interval']
        lines.append(f"| {r['phase']} | {q['host_interval_p99_ms']:.3f} / {q['host_interval_max_ms']:.3f} | {q['host_intervals_over_10ms']} / {q['host_intervals_over_160ms']} | {q['fifo_depth_max']} | {q['gap_flagged_xyz']} / {q['overrun_flagged_xyz']} / {q['saturated_flagged_xyz']} | {sel['quality_valid_windows']} / {sel['quality_invalid_windows']} | {sel['trailing_xyz_not_windowed']} |")
    lines += ['',
    'Die Prüfung umfasst monotone Zeitstempel, fortlaufende Indizes, konsistente relative und nominelle Zeitbasis, nichtendliche XYZ-Werte, FIFO-Vollstand, Rohwert-Sättigungsgrenzen und die gespeicherten Qualitätsflags. Ein Host-Abstand über 10 ms allein belegt keinen verlorenen Sensorwert. Die genaue Zahl physisch verlorener Samples bleibt **unbekannt**, auch bei fehlenden Verlustflags. Ein XYZ-Messpunkt enthält drei Achsenwerte; Achsenwerte werden nicht als drei zeitliche Messpunkte gezählt. Ungültige Modellfenster werden nicht als NORMAL und nicht im Fehlalarmnenner gezählt.','',
    '## Eingefrorener Modellvergleich','',
    '| Betriebspunkt / Lauf | Methode | Gültig | Ungültig | Fehlalarme | Fehlalarmrate |',
    '|---|---|---:|---:|---:|---:|']
    import csv
    table=list(csv.DictReader((OUT/'false_alarm_comparison.csv').open()))
    for r in table:
        rate=r['false_alarm_rate_among_valid_normal_windows']
        rate='nicht definiert' if not rate else f'{100*float(rate):.2f} %'
        lines.append(f"| {r['pwm_percent']} % / {r['run']} | {r['method']} | {r['valid_windows']} | {r['invalid_windows']} | {r['false_alarms']} | {rate} |")
    lines += ['',
    '![Fehlalarmraten vollständiger Läufe](comparison_50_vs_75/false_alarm_comparison.png)','',
    '![128er-Scores der drei 50-%-Läufe](comparison_50_only/scores.png)','',
    'Die Referenzgruppe umfasst alle sechs im Protokoll festgelegten früheren unabhängigen normalen v4-Testaufnahmen bei 75 %. Trainings- und Validierungsfenster sowie Plattenaufnahmen bleiben außerhalb dieser Vergleichsnenner. Die genaue Zuordnung mit CSV-, Session- und Ergebnis-Hashes steht in `comparison_50_vs_75/baseline_provenance.json`. Der Vergleich ist nicht zeitgleich und isoliert daher keinen kausalen PWM-Effekt von zeitlicher Drift oder anderen nicht erfassten Einflüssen.','',
    'Die gepoolten Raten sind deskriptive Fensteranteile. Die unabhängige Auswertungseinheit bleibt die vollständige Aufnahme. Benachbarte Fenster sind keine unabhängigen Versuchsreplikate; es werden keine naiven fensterbasierten Signifikanztests oder Konfidenzintervalle verwendet. Aus ausschließlich normalen Testdaten folgen weder Anomalie-Recall noch F1 oder allgemeine Erkennungsleistung.','',
    '## Ergänzende Vibrationsdiagnostik','',
    '| Lauf | Mittel 180–300 s (mg) | SD der 5-s-Blöcke (mg) | Bereich (mg) | Deskriptiver linearer Trend (mg/min) | Zweite minus erste Hälfte (mg) |',
    '|---|---:|---:|---|---:|---:|']
    for r in runs:
        d=r['rms_5s_late'];lines.append(f"| {r['phase']} | {fmt(d['mean_mg'])} | {fmt(d['std_sample_mg'])} | {fmt(d['min_mg'])}–{fmt(d['max_mg'])} | {fmt(d['linear_slope_mg_per_min'])} | {fmt(d['second_minus_first_half_mg'])} |")
    lines += ['',
    '![Vibrationsverlauf in 5-s-Abschnitten](comparison_50_vs_75/rms_5s.png)','',
    'Der physische Vektor-AC-RMS wird für jeden 5-s-Abschnitt nach Entfernung seiner drei Achsenmittelwerte berechnet. Diese Diagnose ist von dem standardisierten RMS-Modellscore eines 128er-Fensters zu unterscheiden. Die 180 s bleiben ein vorab festgelegter Prüfabschnitt; die Testergebnisse führen nicht zu nachträglicher Abschnittsauswahl. Unterschiede zwischen Laufmittelwerten und zeitliche Trends innerhalb eines Laufs werden getrennt ausgewiesen.','',
    '## Grenzen und nächster Nachweis','',
    'Der nächste gezielte Nachweis ist der Sensor-Livebetrieb des eingefrorenen Pakets mit der bereits geprüften Vorverarbeitung, Rohdatensicherung, begrenzter Entscheidungsqueue und Ressourcenprotokollierung. Dafür müssen die Versuchsparameter und Messgrößen vorab feststehen: komplettiertes Fenster bis Entscheidung, Scorer-/Inferenzzeiten, CPU, RSS, verworfene Fenster, Rohdaten-/Pufferverluste und ungültige Entscheidungen. Offline-Replay, Sensor-Livebetrieb ohne GUI und GUI-Zusatzlast sind getrennte Bedingungen. Ein gemeinsamer Prozess mit drei Methoden liefert keine isolierten CPU-/RAM-Kosten der Einzelmethoden.','',
    'Es erfolgt kein Nachtraining, keine neue Skalierung, keine Schwellenanpassung und kein erneuter Plattenversuch. Falls später eine Modelländerung beschlossen wird, braucht sie eine neue Version und neue unabhängige Testaufnahmen. Worddatei, Modelle, Originaldaten und historische Berichte bleiben unverändert.','',
    'Der anfängliche reine Software-Vorprüfaufruf verwendete zunächst das System-Python ohne Pandas und brach beim Import ab. Die Vorprüfung wurde anschließend in der vorhandenen Projektumgebung ausgeführt. Dieser Importfehler trat vor Sensorzugriff und Stellbefehl auf; er erzeugte keinen Lüfterstart und keine Aufnahme. Er ist in `initial_readonly_preflight.json` dokumentiert.','',
    'Der abschließende Steuerungszustand wird in `final_control_status.json` zusätzlich rein lesend geprüft. Eine bestätigte Vorgabe von 0 % ist keine Sichtbestätigung des mechanischen Stillstands.']
    with (BASE/'measurement_report.md').open('x') as f:f.write('\n'.join(lines)+'\n')
    print('measurement_report.md created')

if __name__=='__main__':main()
