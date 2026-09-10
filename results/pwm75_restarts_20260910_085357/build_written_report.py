"""Write a separate report from the completed three-record restart analysis."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
OUT = BASE / 'comparison'
r = json.loads((OUT / 'report.json').read_text())
records = r['records']
aggregate = r['between_start_statistics']['vector_ac_rms_g']
timing = r['actual_settling_to_first_point_s']
stop = json.loads((BASE / 'final_standstill_confirmation.json').read_text())
assert stop['fan_observed_fully_stopped'] is True


def fmt(value, digits=3):
    return f'{value:.{digits}f}'.replace('.', ',')


def local(iso):
    return datetime.fromisoformat(iso).astimezone(ZoneInfo('Europe/Berlin')).strftime('%H:%M:%S')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


capture_rows, axis_rows, quality_rows, short_rows = [], [], [], []
for name, item in records.items():
    number = item['trial']
    stats, q, blocks = item['statistics'], item['quality_summary'], item['five_second_vector_rms_summary']
    capture_rows.append(f"| {number} | {local(item['started_utc'])}–{local(item['finished_utc'])} "
                        f"| {item['xyz_points']} | {fmt(item['first_to_last_point_s'], 4)} "
                        f"| {fmt(item['host_observed_rate_xyz_per_s'])} "
                        f"| {fmt(item['actual_first_point_after_setting_s'])} "
                        f"| {fmt(1000 * stats['vector_ac_rms_g'])} |")
    axis_rows.append(f'| {number} | ' + ' | '.join(fmt(stats[f'{stat}_{axis}_g'], 6)
                     for stat in ('mean', 'std') for axis in 'xyz') + ' |')
    quality_rows.append(f"| {number} | {q['gap_flagged_samples']} | {q['overrun_flagged_samples']} "
                        f"| {q['saturated_samples']} | {fmt(q['host_interval_max_ms'])} "
                        f"| {q['host_intervals_over_2_periods']} | {q['fifo_depth_max']} |")
    short_rows.append(f"| {number} | {fmt(blocks['min'] * 1000)}–{fmt(blocks['max'] * 1000)} "
                      f"| {fmt(blocks['range'] * 1000)} | {fmt(blocks['descriptive_cv_percent'])} |")

all_sessions = []
for path in BASE.glob('start_*.json'):
    session = json.loads(path.read_text())
    if 'setting_completed_utc' in session:
        all_sessions.append((path, session))
all_sessions.sort(key=lambda pair: pair[1]['setting_completed_utc'])
timeline_rows, chronology = [], []
previous_zero = None
for physical_number, (path, session) in enumerate(all_sessions, 1):
    since_zero = ((datetime.fromisoformat(session['setting_completed_utc']) - previous_zero).total_seconds()
                  if previous_zero else None)
    outcome = f"Aufnahme {session['trial']} vollständig" if session['status'] == 'completed' else 'Abbruch ohne Aufnahme'
    timeline_rows.append(f"| {physical_number} | {session['trial']} / {session.get('attempt', 1)} "
                         f"| {local(session['setting_completed_utc'])} "
                         f"| {local(session['zero_command_completed_utc'])} "
                         f"| {fmt(since_zero) if since_zero is not None else 'nicht bestimmt'} | {outcome} |")
    chronology.append({'physical_start': physical_number, 'session': str(path.relative_to(ROOT)),
                       'sha256': digest(path), 'trial': session['trial'], 'attempt': session.get('attempt', 1),
                       'setting_completed_utc': session['setting_completed_utc'],
                       'zero_command_completed_utc': session['zero_command_completed_utc'],
                       'seconds_since_previous_documented_zero_command': since_zero,
                       'status': session['status']})
    previous_zero = datetime.fromisoformat(session['zero_command_completed_utc'])

pair_rows = []
for pair in r['pairwise']:
    pair_rows.append(f"| {pair['a'].split('_')[-1]} – {pair['b'].split('_')[-1]} "
                     f"| {fmt(1000 * pair['absolute_difference_g'])} "
                     f"| {fmt(pair['relative_pair_difference_percent'])} "
                     f"| {'ja' if pair['five_second_ranges_overlap'] else 'nein'} |")

report = f"""# Wiederholbarkeit bei 75 % PWM über separate Lüfterstarts

Messdatum: 10.09.2026. Alle Tabellenzeiten sind Europe/Berlin, CEST (UTC+2).
Rohdaten, Metadaten und Steuerjournale enthalten UTC-Zeitpunkte bzw. monotone
Hostzeitstempel. mg bedeutet 0,001 g.

## 1. Ergebnis

**Drei getrennte 30-s-Aufnahmen nach jeweils bestätigtem mechanischem Stillstand
und erneutem Start auf 75 % PWM sind abgeschlossen.** Die Vektor-AC-RMS-Werte
betragen 28,920 mg, 31,479 mg und 29,530 mg. Ihr Mittelwert ist
{fmt(aggregate['mean'] * 1000)} mg; die Spannweite beträgt
{fmt(aggregate['range'] * 1000)} mg bzw. {fmt(aggregate['relative_range_percent'])} %
des Mittelwerts. Der deskriptive Variationskoeffizient beträgt
{fmt(aggregate['descriptive_cv_percent'])} %.

Aufnahme 2 liegt auch in ihren sechs kurzen Abschnitten oberhalb der Bereiche
von Aufnahme 1 und 3. Innerhalb eines einzelnen Laufs schwankt das Signal weniger
als zwischen diesen Starts. Die besonders geringe Differenz des früheren
75-%-Paares aus einem durchgehenden Lauf lässt sich daher nicht als allgemeine
Wiederholbarkeit über Neustarts übernehmen.

75 % PWM bleibt ein untersuchbarer Betriebspunkt. Eine hinreichend konstante
Normalreferenz für spätere Anomalieversuche ist mit diesen Daten jedoch noch
nicht nachgewiesen. Eine zulässige Streuung oder ein minimal zu erkennender
Anomalieeffekt war nicht vorab festgelegt; es wird deshalb keine nachträglich
gewählte Bestehensschwelle angewendet. Es wurden keine Modelle trainiert,
keine Schwellen angepasst und keine künstlichen Anomalien erzeugt.

## 2. Aufbau und unveränderte Messparameter

| Parameter | Belegter Stand |
| --- | --- |
| Prüflüfter | ARCTIC P12 Pro PST, externe 12-V-Versorgung |
| Sensorposition | ADXL345 an einer Ecke des Lüfterrahmens; Montage und Sensorposition laut Nutzer unverändert |
| Montagekennung | `fan_frame_corner_adxl345_gpio18_v1` |
| Steuerausgang | BCM GPIO18, physischer Headerpin 12, RP1 `pwmchip0/pwm2`, Funktion `a3` / `PWM0_CHAN2` |
| Betriebsvorgabe | 75 % bei 25 kHz: 30.000 ns Tastzeit bei 40.000 ns Periode |
| Zwischen- und Endvorgabe | 0 % bei 25 kHz: 0 ns Tastzeit; Kanal bleibt aktiviert |
| Sensor | nominelle ODR 200 Hz, ±2 g, Full Resolution, FIFO Stream |
| Register | BW_RATE 0x0b, DATA_FORMAT 0x08, FIFO_CTL 0x90, INT_ENABLE 0x00, POWER_CTL 0x08 |
| I²C | Bus 1, konfigurierte Frequenz 100 kHz |
| Skalierung | bestehende 0,0039 g/LSB; keine neue absolute Kalibrierung |
| Zeitplanung | jeweils 60-s-Timer ab abgeschlossenem PWM-Stellbefehl, danach 30-s-Aufnahme |
| Drehzahl | nicht gemessen; keine RPM-Ableitung aus PWM oder Sichtbeobachtung |

Der vorhandene Hardware-PWM-Controller prüfte Kanal, Pin-Funktion und Vorgabe.
Die PWM wurde vor und nach jeder Aufnahme rückgelesen. Sensor- und
Steuerungssperren waren während der jeweiligen Versuche gehalten; bei den
Zugriffsprüfungen wurden keine konkurrierenden Gerätenutzer gefunden. Die
Erkennung steuerte den Lüfter nicht. Eine elektrische PWM-Signalmessung erfolgte
nicht; rückgelesene Einstellungen und Nutzerbeobachtungen bleiben getrennte
Nachweisarten.

## 3. Tatsächlicher Ablauf einschließlich der Abbrüche

Für drei vollständige Aufnahmen wurden insgesamt **sechs physische Starts**
ausgeführt. Drei zusätzliche Starts für Aufnahme 2 endeten ohne Aufnahme, weil
die zunächst vom Assistenten eingeführte Laufbestätigung innerhalb der
60-s-Einlaufminute nicht rechtzeitig vorlag. Bei jedem Abbruch wurde 0 %
angefordert und rückgelesen; vor jedem weiteren Start wurde vollständiger
Stillstand erneut durch den Nutzer bestätigt. Die Abbrüche werden nicht als
Nullsignal, erfolgreiche Wiederholung oder zusätzliche Messdatei ausgegeben.

| Physischer Start | Aufnahme / Versuch | 75 % eingestellt | 0 % eingestellt | Zeit seit vorherigem 0-%-Befehl s | Ergebnis |
| --- | --- | --- | --- | ---: | --- |
{chr(10).join(timeline_rows)}

Die Einlaufzeit wurde nicht wegen einer verspäteten Chatantwort verlängert.
Nach drei Abbrüchen wurde der organisatorische Ablauf vor dem nächsten Start
angekündigt geändert: Die Aufnahme erfolgt automatisch nach dem 60-s-Timer;
der Nutzer beobachtet den Lauf und bestätigt seine Beobachtung anschließend
ohne Antwortfrist. Der Sensorcode, die Erfassungsdauer und die PWM-Parameter
blieben gleich. Die Revision liegt in
`../protocol_revision_without_chat_deadline.json`; ursprüngliches Protokoll,
Skripte, Abbruchjournale und die verspätete Laufantwort bleiben erhalten.

Für Aufnahme 1 lag die Laufbestätigung bereits vor der Aufnahme vor. Für
Aufnahme 2 und 3 bestätigte der Nutzer anschließend ausdrücklich den
gleichmäßigen Lauf **während des jeweils benannten Aufnahmezeitraums** sowie
unveränderte Montage. Diese Angaben liegen in separaten Beobachtungsdateien.
Die ursprünglichen CSV-/JSON-Dateien wurden nicht rückwirkend geändert:
Aufnahme 2 und 3 behalten das bei der Erfassung gesetzte Label −1 und den
Hinweis auf die damals noch ausstehende Laufbeobachtung. Die Auswertung ordnet
ihnen die späteren Angaben über Sitzungspfad und Prüfsummen zu.

Die zusätzlichen Starts und unterschiedlichen Auszeiten können die
Vorgeschichte des Aufbaus beeinflussen. Temperatur und tatsächliche Drehzahl
wurden nicht gemessen. Bestätigter Rotorstillstand ist deshalb kein Nachweis
identischer thermischer Bedingungen oder eines Kaltstarts.

## 4. Erfasste Dateien, Zeitsteuerung und Abtastrate

Die angeforderte Dauer beträgt jeweils 30 s. Die Zeitspanne in der Tabelle
ist der Abstand zwischen erstem und letztem XYZ-Messpunkt. Beginn–Ende bezeichnet
die UTC-Metadaten des Aufnahmeprozesses, hier in Ortszeit umgerechnet.

| Aufnahme | Beginn–Ende CEST | XYZ-Punkte N | Zeitspanne s | Beobachtet XYZ/s | Erster Punkt nach Stellbefehl s | Vektor-AC-RMS mg |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(capture_rows)}

Alle drei Starts verwendeten denselben 60-s-Timer. Durch Rücklesung, Journal-
und Recorderinitialisierung lagen die ersten gelesenen XYZ-Punkte tatsächlich
{fmt(timing['min'])} bis {fmt(timing['max'])} s nach dem Stellbefehl. Die
Spannweite dieser Zeitpunkte beträgt {fmt(timing['range'] * 1000)} ms.
Die reale Startzeit wird daher nicht als exakt identisch behauptet.

Vorab war eine technische Startverzögerung von mehr als 100 ms als
prüfbedürftig markiert worden. Aufnahme 1 überschreitet diesen Prüfwert mit
164,304 ms; Aufnahme 2 und 3 liegen bei 97,605 bzw. 75,337 ms. Das ist keine
vorab festgelegte wissenschaftliche Ausschlussgrenze. Die Aufnahme bleibt mit
dieser Kennzeichnung im Vergleich. Welchen Einfluss eine Zeitdifferenz dieser
Größe auf das Schwingungssignal hat, wurde nicht separat untersucht. Ein
60-s-Timer allein beweist keinen stationären Betrieb.

Der beobachtete Durchsatz wird als `(N−1)/(t_letzter−t_erster)` aus monotonen
Hostzeitstempeln berechnet. Er beträgt 206,896–206,941 vollständige XYZ-Punkte/s
und liegt damit etwa 3,45–3,47 % über der nominellen ODR von 200 Hz. Die
Konfiguration und der beobachtete Durchsatz werden ausdrücklich getrennt.
N zählt XYZ-Tupel, nicht einzelne Achsenwerte: 6.206 Punkte entsprechen
18.618 Achsenwerten, 6.207 Punkte 18.621 Achsenwerten. Eine 30-s-Aufnahme bei
exakt 200 Hz würde ungefähr 6.000 XYZ-Punkte enthalten. Die Erfassung endet
zeitgesteuert und erzwingt keine feste Punktzahl.

Die Hostzeitstempel beschreiben den Abschluss der Registerlesung, nicht den
internen Wandlungszeitpunkt. `sample_index / 200` ist nur eine nominale
Zeitachse. Die Ursache der Abweichung zwischen ODR-Vorgabe und beobachtetem
Durchsatz wird durch diese drei Aufnahmen nicht abschließend geklärt.

## 5. Qualitätsprüfung

| Aufnahme | Lückenflags | Überlaufflags | Sättigungsflags | Größter Hostabstand ms | Hostabstände über 10 ms | Maximale FIFO-Belegung |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(quality_rows)}

Alle Werte sind endlich, die Zeitstempel streng monoton und die gespeicherten
Messpunktindizes lückenlos. In keiner Aufnahme wurden Lücken-, Überlauf- oder
Sättigungsflags gesetzt. Aufnahme 1 enthält jedoch einen Hostabstand von
10,942 ms, also mehr als zwei nominelle Sensorperioden. Darauf folgen kürzere
Hostabstände von ungefähr 2,018 und 2,118 ms. Dieser Befund wird nicht als
unauffälliges exakt gleichmäßiges Abtasten dargestellt. Die Metadaten melden
maximal zwei FIFO-Einträge, aber keinen Überlauf.

Der größte Betrag eines Achsenwerts beträgt 1,1466 g und liegt im eingestellten
Bereich. Fehlende Flags beweisen nicht die exakte Anzahl möglicherweise
verlorener interner Wandlungen; `lost_samples_exact` bleibt unbekannt. Die
Dateien sind für diesen deskriptiven Pilotvergleich auswertbar. Ein Nachweis
von Aliasfreiheit, kalibrierter Absolutgenauigkeit oder erfolgreicher
Anomalieerkennung wird daraus nicht abgeleitet.

## 6. Achsenmittelwerte und vibrationsbezogenes RMS

Pro Datei wird zunächst jeder Achsenmittelwert entfernt:
`x_AC = x−mean(x)`, entsprechend für Y und Z. Die Achsenstreuungen sind
Populationsstandardabweichungen mit `ddof=0` und damit zugleich die jeweiligen
Achsen-AC-RMS-Werte.

`Vektor-AC-RMS = sqrt(mean(x_AC²+y_AC²+z_AC²)) = sqrt(σX²+σY²+σZ²)`.

Es wird nicht durch √3 dividiert. Diese Größe unterscheidet sich vom AC-RMS
des zuvor gebildeten Vektorbetrags. Die Mittelwertentfernung ersetzt keine
Sensorkalibrierung.

| Aufnahme | Mittel X g | Mittel Y g | Mittel Z g | σX g | σY g | σZ g |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(axis_rows)}

Die Unterschiede bleiben nach Entfernung der Achsengleichanteile bestehen.
Aufnahme 2 weist insbesondere eine höhere X-Achsenstreuung auf. Aus den
Gleichanteilsänderungen wird keine Montageänderung abgeleitet; der Nutzer
bestätigt die unveränderte Montage. Eine physische Ursache der Unterschiede
ist mit den verfügbaren Angaben nicht bestimmt.

## 7. Wiederholbarkeit zwischen Starts und innerhalb der Aufnahmen

Jede Datei wird in sechs nicht überlappende 5-s-Abschnitte zerlegt. Die Grenzen
`[0,5), …, [25,30)` beziehen sich auf die Hostzeit relativ zum ersten Messpunkt;
für jeden Abschnitt werden eigene Achsenmittelwerte entfernt. Die 18 Abschnitte
sind keine 18 unabhängigen Neustarts.

| Aufnahme | 5-s-Vektor-AC-RMS min–max mg | Spannweite mg | Deskriptiver CV % |
| --- | ---: | ---: | ---: |
{chr(10).join(short_rows)}

![Vektor-AC-RMS der drei vollständigen Aufnahmen und ihrer 5-s-Abschnitte](comparison.png)

| Paar | Absolute Differenz der Datei-RMS mg | Differenz relativ zum Paarmittel % | Überlappung der 5-s-Bereiche |
| --- | ---: | ---: | --- |
{chr(10).join(pair_rows)}

Die Bereiche von Aufnahme 1 und 3 überlappen. Aufnahme 2 liegt mit allen sechs
Abschnittswerten über beiden anderen Bereichen. Die Datei-RMS-Differenz
zwischen Aufnahme 1 und 2 beträgt 2,560 mg; ihre jeweiligen Abschnittsspannweiten
betragen 1,255 und 0,626 mg. Zwischen Aufnahme 2 und 3 beträgt die Dateidifferenz
1,949 mg, ebenfalls mehr als die Abschnittsspannweiten beider Dateien.
Dies beschreibt einen Unterschied zwischen den Laufniveaus und nicht nur einen
einzelnen kurzen Ausschlag innerhalb einer Aufnahme.

Über die drei Datei-RMS-Werte ergeben sich ein Mittelwert von 29,976 mg, eine
Populationsstandardabweichung von 1,092 mg und eine Stichprobenstandardabweichung
von 1,337 mg. Der CV von 3,641 % verwendet die Populationsstandardabweichung und
ist rein deskriptiv. Die Spannweite von 8,539 % bezieht sich auf das Mittel aller
drei Dateien; die paarweise Differenz 1–2 von 8,476 % verwendet dagegen nur das
Paarmittel. Es wurden keine p-Werte oder Konfidenzbehauptungen aus den kurzen
Abschnitten erzeugt.

Zum getrennten historischen Kontext: Das frühere 75-%-Paar hatte 29,387 und
29,362 mg und eine relative Differenz von 0,086 %. Es stammte aus einem
durchgehend gehaltenen Betriebspunkt mit anderer Zeit seit der PWM-Änderung.
Es wird nicht mit den drei neuen Starts zusammengefasst und nicht rückwirkend
als Neustartversuch umgedeutet.

## 8. Bewertung und nächster Schritt

Die drei neuen Dateien zeigen ein messbares Vibrationssignal, aber auch eine
erkennbare Variation zwischen Starts. Die vorherige vorläufige Bevorzugung von
75 % muss deshalb um diesen Befund ergänzt werden: **75 % ist ein Kandidat;
eine ausreichend reproduzierbare Normalreferenz für die geplanten
Anomalieversuche ist noch offen.** Drei Starts an einer unveränderten Montage
erlauben keine belastbare statistische Verallgemeinerung.

Als nächste Prüfung ist ein prospektiv festgelegter Normalbetriebsablauf mit
gleichen Auszeiten und dokumentierter Betriebsvorgeschichte sinnvoll. Ein
längerer zeitlich aufgelöster Normalbetrieb kann zunächst zeigen, ob sich nach
60 s ein stabiles RMS-Niveau einstellt oder ein anderer festgelegter
Aufnahmezeitpunkt erforderlich ist. Mögliche Einflüsse von Erwärmung, Drehzahl
oder Aufbauzustand sind bislang Hypothesen. Sie dürfen nicht als Ursache der
gemessenen Unterschiede behauptet werden. Eine Tachomessung wäre nur bei
separat bestätigtem Anschluss ein zusätzlicher Nachweis.

Vor dem späteren Training müssen Normaldaten mehrere tatsächliche Neustarts
abdecken. Training, Validierung und unabhängige Tests sollten nach Aufnahme
bzw. Start getrennt werden; kurze Abschnitte derselben Datei gehören nicht in
verschiedene unabhängige Datensätze. Die zulässige Normalvariation und die
angestrebte Empfindlichkeit sind vor der Anomalieevaluation festzulegen.
Normal- und Anomaliezustände werden bei gleicher PWM verglichen. Für einen
zweiten normalen Betriebspunkt bleiben Modelle, Skalierung und Schwellen
unverändert. Diese weiteren Versuche und Trainings wurden hier nicht begonnen.

## 9. Endzustand, Dateien und Erhalt bestehender Arbeit

Der letzte Stellbefehl setzte **0 % PWM bei 25 kHz** um 09:17:50 UTC / 11:17:50
CEST. Nach zehn Sekunden wurde diese Vorgabe erneut rückgelesen. Anschließend
bestätigte der Nutzer vollständigen mechanischen Stillstand. Der
Protokollierungszeitpunkt dieser Sichtangabe ist `{stop['recorded_utc']}`; er
ist keine Messung des genauen mechanischen Stoppzeitpunkts. Es ist kein
weiterer Start vorgesehen.

| Nachweis | Datei |
| --- | --- |
| Vollständige numerische Auswertung | [report.json](report.json) |
| Aufnahme- und Qualitätskennzahlen | [recording_metrics.csv](recording_metrics.csv) |
| Alle 18 Abschnitte | [five_second_metrics.csv](five_second_metrics.csv) |
| Paarweise Vergleiche | [pairwise.csv](pairwise.csv) |
| Grafik als PDF | [comparison.pdf](comparison.pdf) |
| Ergänzende Spektren ohne RPM-Zuordnung | [spectra.csv](spectra.csv) |
| Originales Protokoll | [protocol.md](../protocol.md) |
| Angekündigte Ablaufrevision | [protocol_revision_without_chat_deadline.json](../protocol_revision_without_chat_deadline.json) |
| Aufnahme 1 | [start_1.json](../start_1.json) |
| Aufnahme 2 einschließlich Versuchszähler | [start_2_attempt4.json](../start_2_attempt4.json) |
| Aufnahme 3 | [start_3.json](../start_3.json) |
| Spätere Laufbeobachtung zu Aufnahme 2 | [running_observation_start_2_attempt4.json](../running_observation_start_2_attempt4.json) |
| Spätere Laufbeobachtung zu Aufnahme 3 | [running_observation_start_3.json](../running_observation_start_3.json) |
| Abschließende Stillstandsbestätigung | [final_standstill_confirmation.json](../final_standstill_confirmation.json) |

Jede Rohdatei und jede Aufnahmemetadatei hat einen eigenen Zeitstempel und
einen eindeutigen Pfad. Die Sitzungen verweisen auf die jeweiligen
PWM-Steuerjournale; die Gesamtauswertung enthält Eingabe- und Quellcodehashes.
Ein separates Abschlussmanifest führt alle sechs Starts und die drei
vollständigen Aufnahmen zusammen. Die Worddatei, historische Messprotokolle,
bestehende Modelle und produktiven Quelldateien bleiben unverändert; der
abschließende Hashvergleich wird in `../final_verification.json` festgehalten.
"""

with (OUT / 'report.md').open('x', encoding='utf-8') as handle:
    handle.write(report)
decision = {
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'restart_variability_detected_candidate_not_finally_validated',
    'pwm_candidate_percent': 75, 'pwm_frequency_hz': 25000,
    'normal_reference_reproducibility_proven': False,
    'completed_recordings': 3, 'physical_starts_total': 6, 'aborted_starts_without_data': 3,
    'vector_ac_rms_summary_g': aggregate, 'actual_first_point_after_command_s': timing,
    'chronology': chronology,
    'observation_protocol_changed': True,
    'raw_metadata_retroactively_changed': False,
    'final_mechanical_standstill_confirmed_by_user': True,
    'final_standstill_confirmation_sha256': digest(BASE / 'final_standstill_confirmation.json'),
    'next_step': 'Prospectively standardise off-times and operating history, examine longer normal-operation time courses for settling, then collect normal reference data across separate starts before training.',
    'models_trained': False, 'thresholds_changed': False, 'induced_anomalies': False,
    'analysis_sha256': digest(OUT / 'report.json'), 'written_report_sha256': digest(OUT / 'report.md'),
}
with (OUT / 'decision.json').open('x', encoding='utf-8') as handle:
    json.dump(decision, handle, indent=2, ensure_ascii=False, allow_nan=False)
    handle.write('\n')
print(json.dumps({'written_report': str(OUT / 'report.md'), 'bytes': (OUT / 'report.md').stat().st_size,
                  'status': decision['status']}))
