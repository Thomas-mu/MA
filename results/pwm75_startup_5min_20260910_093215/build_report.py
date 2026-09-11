"""Write a separate, evidence-linked report for the single startup recording."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
OUT = BASE / 'analysis'
r = json.loads((OUT / 'report.json').read_text())
s = json.loads((BASE / 'session.json').read_text())
q, timing = r['quality'], r['timing']


def fmt(x, digits=3):
    return f'{x:.{digits}f}'.replace('.', ',')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


minute_rows = []
for minute in r['minutes']:
    stats = minute['five_second_vector_ac_rms_g']
    minute_rows.append(f"| {minute['start_since_first_xyz_s']}–{minute['end_since_first_xyz_s']} "
                       f"| {fmt(1000 * stats['mean'])} | {fmt(1000 * stats['min'])}–{fmt(1000 * stats['max'])} "
                       f"| {fmt(stats['descriptive_cv_percent'])} | {fmt(minute['linear_slope_g_per_minute'] * 1000)} |")
late = r['time_intervals']['180_300']['five_second_vector_ac_rms_g']
middle = r['time_intervals']['120_180']['five_second_vector_ac_rms_g']
increase_percent = 100 * (late['mean'] / middle['mean'] - 1)
running_path = BASE / 'running_observation.json'
stop_path = BASE / 'final_standstill_confirmation.json'
observation = json.loads(running_path.read_text()) if running_path.exists() else None
stop = json.loads(stop_path.read_text()) if stop_path.exists() else None
running_note = ('Die Nutzerbeobachtung ist separat in `../running_observation.json` dokumentiert. '
                'Sie wird nicht rückwirkend in die Rohmetadaten geschrieben.' if observation else
                'Die nach der Aufnahme angefragte Nutzerbeobachtung zum Anlaufen, weiteren Lauf und '
                'möglichen Berührungen liegt zum Erstellen dieses Berichts noch nicht vor. '
                'Die Aufnahme beschreibt deshalb zunächst den beabsichtigten Normalbetrieb bei '
                'dokumentierter Stellvorgabe; störungsfreie äußere Bedingungen werden nicht automatisch bestätigt.')
stop_note = ('Vollständiger mechanischer Stillstand nach dieser Abschaltung ist durch die separate '
             'Nutzerangabe in `../final_standstill_confirmation.json` bestätigt.'
             if stop and stop.get('fan_observed_fully_stopped') is True else
             'Vollständiger mechanischer Stillstand nach dieser Abschaltung ist zum Erstellen dieses '
             'Berichts noch nicht durch eine neue Sichtangabe bestätigt; 0 % ist die rückgelesene Stellvorgabe.')

body = f"""# Fünfminütiger Einlaufversuch bei 75 % PWM

Messdatum: 10.09.2026. Es wurde **ein Start mit einer durchgehenden 300-s-Aufnahme**
ausgeführt. Nach bestätigtem vollständigem Stillstand wurde 75 % PWM bei 25 kHz
eingestellt und ohne absichtliche Wartezeit aufgezeichnet. Es gab keine
Antwortfrist, keinen zusätzlichen Start und keinen Abbruch.

## Ergebnis

Das Vibrationsniveau verändert sich während dieser Einzelaufnahme. Im ersten
5-s-Abschnitt beträgt das Vektor-AC-RMS 15,068 mg, im zweiten 30,560 mg. Danach
liegen die Werte zunächst überwiegend um 29 mg, mit einzelnen höheren Werten.
Zwischen 120 und 180 s ist die Schwankung vergleichsweise klein. In den letzten
zwei Minuten beträgt der Mittelwert der 5-s-RMS-Werte jedoch
{fmt(late['mean'] * 1000)} mg statt {fmt(middle['mean'] * 1000)} mg in Minute 3;
das sind {fmt(increase_percent)} % mehr. Zudem treten erneut deutliche
Ausschläge auf, bis 34,246 mg im Abschnitt 195–200 s.

**Ein dauerhaft konstantes Vibrationsniveau ab 60 s ist damit nicht belegt.**
Die Mittelwerte von Minute 4 und 5 liegen zwar nahe beieinander, die einzelnen
Abschnitte schwanken weiterhin. Aus diesem Verlauf lässt sich weder eine
allgemeingültige Einlaufzeit noch Reproduzierbarkeit über verschiedene Starts
ableiten. Es wurde keine nachträgliche Bestehensschwelle gewählt.

![Vektor-AC-RMS und Achsen-AC-RMS in aufeinanderfolgenden 5-s-Abschnitten](startup_rms.png)

Die orange Linie zeigt je Minute das arithmetische Mittel der zwölf
5-s-Vektor-AC-RMS-Werte. Sie ist kein separat nach einmaliger
60-s-Mittelwertentfernung berechnetes RMS. Die unteren Kurven zeigen die
Achsenbeiträge. Die Verbindungslinien dienen der Lesbarkeit; ausgewertet
werden die markierten, nicht überlappenden Zeitabschnitte.

## Messkette und unveränderte Bedingungen

| Größe | Einstellung bzw. Nachweis |
| --- | --- |
| Prüflüfter | ARCTIC P12 Pro PST mit externer 12-V-Versorgung |
| Sensor | ADXL345 an einer Ecke des Lüfterrahmens; bestehende I²C-Beschaltung |
| Montage | Kennung `fan_frame_corner_adxl345_gpio18_v1`; unverändert lassen war vor dem Start vereinbart |
| Steuerpin | BCM GPIO18, physischer Headerpin 12, `a3` / `PWM0_CHAN2` |
| PWM | vorhandenes RP1 `pwmchip0/pwm2`, 25 kHz, normale Polarität, aktiviert |
| Betrieb | 75 %: 30.000 ns Tastzeit bei 40.000 ns Periode |
| Ende | 0 %: 0 ns Tastzeit bei unveränderter Periode |
| Sensorkonfiguration | nominell 200 Hz ODR, ±2 g, Full Resolution, FIFO Stream |
| Register | BW_RATE 0x0b, DATA_FORMAT 0x08, FIFO_CTL 0x90, INT_ENABLE 0x00, POWER_CTL 0x08 |
| I²C | Bus 1, konfigurierte Busfrequenz 100 kHz |
| Umrechnung | bestehende 0,0039 g/LSB; keine neue absolute Kalibrierung |
| Drehzahl | nicht gemessen; keine RPM-Ableitung aus PWM oder Signalspitzen |

Vor dem Start wurden keine konkurrierenden Gerätenutzer gefunden. Die
gemeinsamen PWM- und Sensorsperren waren während des Versuchs gehalten.
Die Erfassung verwendet die vorhandenen Funktionen `connect` und `record`;
die produktiven Quelldateien wurden nicht geändert. Der Sensor und die
Ausgabepfade wurden vor dem Stellbefehl vorbereitet. Der Recorder setzt
den FIFO beim Beginn der Messung zurück. Eine Erkennung änderte die PWM nicht.

Der vollständige Stillstand vor dem Start ist als Nutzerbeobachtung in
`../prestart_standstill_confirmation.json` dokumentiert. {running_note}
Das Rohdatenlabel bleibt −1 mit Hinweis auf die bei Aufnahmebeginn noch
ausstehende Laufbeobachtung. Es werden daraus keine Trainingsdaten oder
automatisch bestätigten Zustandslabels erzeugt.

## Zeitbezug und tatsächlicher Aufnahmebeginn

| Ereignis | UTC am 10.09.2026 |
| --- | --- |
| Aufruf des 75-%-Stellbefehls | {s['command_invocation_utc']} |
| Journal vor Schreiben von 30.000 ns | {timing['duty_write_intent_utc']} |
| Journal der Rücklesung von 30.000 ns | {timing['duty_write_readback_utc']} |
| Abschluss des Steuerbefehls einschließlich Rücklesung | {s['command_completed_utc']} |
| Aufnahme-Metadatum „started_at“ | {s['recording']['started_at_utc']} |
| Ende der Aufnahme laut Metadatum | {s['recording']['finished_at_utc']} |
| Abschluss der Rückstellung auf 0 % | {s['zero_command_completed_utc']} |

Zur lokalen Sommerzeit CEST sind jeweils zwei Stunden zu addieren. Die
Berechnung kurzer Zeitabstände verwendet ausschließlich monotone Nanosekunden.
Der erste gelesene XYZ-Punkt liegt **{fmt(timing['first_xyz_after_command_completion_s'] * 1000)} ms
nach Abschluss** und **{fmt(timing['first_xyz_after_command_invocation_s'] * 1000)} ms
nach Aufruf** des PWM-Stellbefehls. Gegenüber dem Journal vor dem eigentlichen
Tastzeitschreiben beträgt der Abstand {fmt(timing['first_xyz_after_duty_write_intent_s'] * 1000)} ms,
gegenüber dessen Rücklesejournal {fmt(timing['first_xyz_after_duty_write_readback_s'] * 1000)} ms.

Diese Schreibjournale begrenzen einen softwareseitigen Vorgang. Weder der
elektrische Signalwechsel am Lüfter noch der tatsächliche Rotoranlauf wurden
zeitlich gemessen. `started_at` bezeichnet zudem einen Schritt der
Recorderinitialisierung und nicht den ersten Sensorwert. Der kurze Abschnitt
zwischen Stellbefehl und erstem gelesenen Messpunkt ist nicht aufgezeichnet.

Die angeforderte Erfassungsdauer ist 300 s. Zwischen erstem und letztem
XYZ-Punkt liegen {fmt(q['first_to_last_xyz_s'], 6)} s; der letzte Messpunkt
liegt {fmt(timing['last_xyz_after_command_completion_s'], 6)} s nach
Befehlsabschluss. Ein geringer Unterschied zu 300 s entsteht durch
Initialisierung, diskrete Messpunkte und das zeitgesteuerte Ende der Leseschleife.

## Datenqualität

| Kennzahl | Ergebnis |
| --- | ---: |
| Vollständige XYZ-Messpunkte | {q['xyz_points']} |
| Einzelne Achsenwerte | {q['individual_axis_values']} |
| Nominelle Sensor-ODR | {q['nominal_odr_hz']} Hz |
| Beobachteter Hostdurchsatz | {fmt(q['observed_host_rate_xyz_per_s'], 6)} XYZ/s |
| Abweichung vom nominellen Wert | +{fmt(q['rate_difference_percent'])} % |
| Nicht monotone Zeitabstände | {q['nonmonotonic_host_intervals']} |
| Lücken-/Überlauf-/Sättigungsflags | 0 / 0 / 0 |
| Hostabstände über zwei nominelle Perioden (10 ms) | {q['host_intervals_over_two_nominal_periods']} |
| Größter Hostabstand | {fmt(q['host_interval_max_ms'], 6)} ms |
| Maximale beobachtete FIFO-Belegung | {q['fifo_depth_max']} |
| Größter absoluter Achsenwert | {fmt(q['maximum_absolute_axis_g'], 4)} g |
| Qualitätsmarkierte 5-s-Abschnitte | {len(q['flagged_five_second_blocks'])} |
| Punkte außerhalb der 60 ausgewerteten Abschnitte | {q['points_outside_sixty_sections']} |

Die Indizes beginnen bei null und sind lückenlos; alle XYZ-Werte sind endlich.
CSV-/Metadatenhash, Messpunktzahl, Flaganzahlen, Zeitdarstellungen und nominale
Sensorzeitachse wurden auf Konsistenz geprüft. Es wurden keine gesetzten
Lücken-, Überlauf- oder Sättigungsflags gefunden.

Die drei größeren Hostabstände liegen bei ungefähr 137,408 s, 137,453 s und
137,500 s nach dem ersten Messpunkt und betragen 10,795 ms, 12,558 ms und
11,676 ms. Der FIFO meldete dabei zwei Einträge und keine Überlaufflags.
Der Befund wird ausdrücklich als Unregelmäßigkeit der Host-Lesezeiten
festgehalten. Aus fehlenden Flags folgt kein exakter Nachweis von null
verlorenen internen Sensorwandlungen; deren Anzahl bleibt unbekannt.

Der Durchsatz ist `(N−1)/(t_letzter−t_erster)` aus Hostzeitstempeln.
Ein XYZ-Tupel ist ein Messpunkt mit drei Achsenwerten, keine dreifache zeitliche
Abtastung. Bei exakt 200 Hz wären in 300 s ungefähr 60.000 XYZ-Punkte zu
erwarten; hier wurden 62.063 erfasst. Die nominelle ODR und der beobachtete
Durchsatz werden nicht gleichgesetzt. Die Ursache der Abweichung wird durch
diese Einzelaufnahme nicht abschließend geklärt.

Hostzeitstempel sind keine Zeitstempel der internen Wandlung.
`sample_index / 200` bleibt eine nominale Schätzung. Eine elektrische
Signalprüfung, Aliasfreiheit oder absolute Sensorkalibrierung wurde nicht
nachgewiesen. Die Daten sind für die hier dargestellte deskriptive
Verlaufsprüfung auswertbar; ein Nachweis erfolgreicher Anomalieerkennung
ergibt sich daraus nicht.

## Berechnung der 5-s-Werte

Die 60 Fenster `[0,5), …, [295,300)` beziehen sich auf den ersten tatsächlichen
XYZ-Hostzeitstempel. In der Grafik ist zusätzlich der gemessene Versatz zum
PWM-Befehlsabschluss berücksichtigt: Das erste Fenster entspricht etwa
0,029522–5,029522 s nach Befehlsabschluss. Alle Abschnitte haben dieselbe
festgelegte Länge von fünf Sekunden; es wird nicht nachträglich umgetaktet
oder interpoliert.

In jedem Abschnitt werden X-, Y- und Z-Mittelwert neu berechnet und entfernt:

`x_AC = x−mean(x)`, entsprechend für Y und Z.

`Vektor-AC-RMS = sqrt(mean(x_AC²+y_AC²+z_AC²))`.

Die Achsen-AC-RMS-Werte entsprechen den Populationsstandardabweichungen
(`ddof=0`). Die Vektorgröße wird nicht durch √3 dividiert und ist nicht das
AC-RMS eines zuvor berechneten Vektorbetrags. Es wurden keine Punkte anhand
ihres Ausschlags entfernt. Qualitätsflags werden zusätzlich pro Abschnitt
geführt. Alle Achsenmittelwerte, Streuungen und RMS-Werte stehen in der
separaten CSV-Datei.

## Verlauf und Stabilisierung

Die folgenden Bereiche sind relativ zum ersten XYZ-Punkt angegeben; für
Zeiten seit Befehlsabschluss sind jeweils rund 0,029522 s zu addieren.
CV bedeutet deskriptive Populationsstandardabweichung der zwölf RMS-Werte
geteilt durch deren Mittelwert. Die lineare Steigung ist eine einfache
Geradenanpassung an diese zwölf Abschnittswerte, kein Signifikanztest.

| Zeitraum s | Mittel der 5-s-RMS mg | Minimum–Maximum mg | CV % | Lineare Steigung mg/min |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(minute_rows)}

Der erste niedrige Abschnitt und der anschließende Anstieg sind mit dem
beabsichtigten Anlauf vereinbar. Daraus lässt sich keine Rotorhochlaufzeit
bestimmen; die erste Sekunde ist im 5-s-RMS zeitlich zusammengefasst und die
Drehzahl ungemessen.

Die geringere Streuung zwischen 120 und 180 s hält über den gesamten restlichen
Verlauf nicht an. Der Abschnitt 195–200 s erreicht 34,246 mg; spätere
Abschnitte erreichen erneut Werte über 31 mg. In den letzten 120 s beträgt
der Mittelwert 30,571 mg, der Bereich 29,043–34,246 mg und der CV 3,751 %.
Die lineare Steigung dieses letzten Bereichs ist mit rund −0,098 mg/min
klein, belegt bei den weiterhin auftretenden Schwankungen aber keine
allgemein gültige Stationarität.

Minute 4 und 5 besitzen ähnliche Mittelwerte (30,622 und 30,521 mg).
Damit ist am Ende ein annähernd gleiches mittleres Niveau über zwei Minuten
zu beobachten, während die Einzelabschnitte variieren. Es wäre nicht
begründet, allein den ruhigen Bereich der dritten Minute auszuwählen und
alle späteren Veränderungen als nicht relevant zu behandeln.

Eine physische Ursache der späteren Niveauänderung wurde nicht bestimmt.
Erwärmung, Drehzahlveränderungen und äußere Anregungen bleiben mögliche
Erklärungen, keine nachgewiesenen Ursachen. Die 60 Abschnitte stammen aus
einem einzigen Lauf und sind keine 60 unabhängigen Wiederholungen.

## Schlussfolgerung und nächster Schritt

Aus dieser Aufnahme sollte keine neue feste Einlaufzeit als validiert
übernommen werden. Als nächster Schritt bieten sich weitere lange
Normalbetriebsläufe mit gleicher Auszeit, gleicher Montage und dokumentierter
Vorgeschichte an. Vorab sollte festgelegt werden, welche Änderung der
Abschnittsmittelwerte und welche Streuung für den vorgesehenen Vergleich
vertretbar sind. Anschließend lässt sich prüfen, ob ein über mehrere Starts
hinweg geeigneter Aufnahmezeitpunkt existiert. Diese Folgeversuche wurden
hier nicht begonnen.

Keine Modelle wurden trainiert und keine Anomalien erzeugt. Der Anlaufbereich
wird nicht automatisch als stationäre Normalreferenz verwendet. Für spätere
Normal-/Anomalievergleiche ist dieselbe PWM einzuhalten; ein zweiter normaler
Betriebspunkt wird mit unveränderten Modellen, Skalierungen und Schwellen geprüft.

## Endzustand und Dateien

Die letzte Stellvorgabe beträgt **0 % PWM bei 25 kHz**. Sie wurde nach dem
Aufnahmeende angefordert und nach zehn Sekunden Auslaufzeit erneut rückgelesen.
{stop_note} Es ist kein weiterer Start vorgesehen.

| Artefakt | Datei |
| --- | --- |
| Grafik PNG | [startup_rms.png](startup_rms.png) |
| Grafik PDF | [startup_rms.pdf](startup_rms.pdf) |
| Alle 60 Abschnitte einschließlich Achsenmittelwerten und Flags | [five_second_rms.csv](five_second_rms.csv) |
| Minutenzusammenfassung | [minute_summary.csv](minute_summary.csv) |
| Numerische Auswertung und Hashes | [report.json](report.json) |
| Aufnahme-/Steuersitzung | [session.json](../session.json) |
| PWM-Befehle und Rücklesungen | [fan.jsonl](../fan.jsonl) |
| Ausgangsstand und vorab festgelegtes Vorgehen | [baseline_and_protocol.json](../baseline_and_protocol.json) |

Die Rohaufnahme liegt unter `{s['csv']}` mit gleichnamiger JSON-Metadatendatei.
Alle Dateien wurden separat gespeichert. Worddatei, historische Protokolle,
bestehende Modelle und produktiver Quellcode werden nicht verändert. Die
abschließende Erhaltungsprüfung wird in `../final_verification.json` dokumentiert.
"""
with (OUT / 'report.md').open('x', encoding='utf-8') as handle:
    handle.write(body)
decision = {'created_utc': datetime.now(timezone.utc).isoformat(),
            'single_recording_only': True, 'additional_starts': 0,
            'status': 'initial_rise_and_later_level_variation_no_validated_settling_time',
            'late_vs_minute3_mean_change_percent': increase_percent,
            'general_reproducibility_proven': False, 'stable_after60s_proven': False,
            'automatic_new_settling_time_selected': False,
            'models_trained': False, 'word_changed': False,
            'final_pwm_percent': 0, 'final_standstill_visually_confirmed': bool(stop and stop.get('fan_observed_fully_stopped')),
            'running_observation_available': observation is not None,
            'analysis_sha256': sha(OUT / 'report.json'), 'written_report_sha256': sha(OUT / 'report.md')}
with (OUT / 'decision.json').open('x', encoding='utf-8') as handle:
    json.dump(decision, handle, ensure_ascii=False, indent=2, allow_nan=False)
    handle.write('\n')
print(json.dumps({'report': str(OUT / 'report.md'), 'status': decision['status']}))
