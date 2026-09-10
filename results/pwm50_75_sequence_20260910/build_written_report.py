"""Create new, separate pilot documentation from the completed analysis."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
OUT = BASE / 'comparison'
analysis = json.loads((OUT / 'report.json').read_text())
manifest = json.loads((BASE / 'completed_measurement_manifest.json').read_text())
records = analysis['records']
phases = analysis['phase_statistics']
names = {
    'standstill_before': 'Stillstand vorher',
    'operating50': '50 % PWM',
    'operating75': '75 % PWM',
    'standstill_after': 'Stillstand nachher',
}


def number(value, places=3):
    return f'{value:.{places}f}'.replace('.', ',')


def local(iso):
    return datetime.fromisoformat(iso).astimezone(ZoneInfo('Europe/Berlin')).strftime('%H:%M:%S')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exclusive_json(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


rows = []
axes = []
for name, r in records.items():
    q, s = r['quality_summary'], r['statistics']
    rows.append(
        f"| {name} | {number(r['pwm_percent'], 0)} | {local(r['started_utc'])}–{local(r['finished_utc'])} "
        f"| {r['xyz_points']} | {number(r['first_to_last_point_s'], 4)} "
        f"| {number(r['host_observed_rate_xyz_per_s'])} "
        f"| {q['gap_flagged_samples']}/{q['overrun_flagged_samples']}/{q['saturated_samples']} "
        f"| {number(s['vector_ac_rms_g'] * 1000)} |"
    )
    axes.append('| ' + name + ' | ' + ' | '.join(
        number(s[f'{metric}_{axis}_g'], 6)
        for metric in ('mean', 'std') for axis in 'xyz'
    ) + ' |')

phase_rows = []
for phase, label in names.items():
    v = phases[phase]['metrics']['vector_ac_rms_g']
    b = v['five_second_sections']
    phase_rows.append(
        f"| {label} | {number(v['mean'] * 1000)} "
        f"| {number(v['repeat_difference_absolute'] * 1000)} "
        f"| {number(v['relative_repeat_difference_percent'])} "
        f"| {number(b['min'] * 1000)}–{number(b['max'] * 1000)} "
        f"| {number(b['descriptive_cv_percent'])} |"
    )

margin_rows = []
for phase in ('operating50', 'operating75'):
    c = analysis['operating_point_comparison'][phase]
    margin_rows.append('| ' + names[phase] + ' | ' + ' | '.join(number(c[k] * 1000) for k in (
        'mean_increase_over_pre_g', 'mean_increase_over_post_g',
        'minimum_operating_minus_maximum_background_recording_g',
        'minimum_operating_minus_maximum_background_section_g',
    )) + ' |')

rates = [r['host_observed_rate_xyz_per_s'] for r in records.values()]
pre = phases['standstill_before']['metrics']['vector_ac_rms_g']['mean']
post = phases['standstill_after']['metrics']['vector_ac_rms_g']['mean']
elapsed = manifest['first_capture_start_to_last_capture_end_s']
mean_changes = [phases['standstill_after']['metrics'][f'mean_{axis}_g']['mean'] -
                phases['standstill_before']['metrics'][f'mean_{axis}_g']['mean'] for axis in 'xyz']
text = f"""# Pilotmessbericht: Stillstand → 50 % → 75 % → Stillstand

Messdatum: 10.09.2026. Auswertung ausschließlich der acht neuen Aufnahmen in
`data/pwm50_75_sequence_20260910/`. Zeitangaben in den Tabellen: Europe/Berlin,
CEST (UTC+2); Dateinamen, Rohmetadaten und Steuerjournale verwenden UTC.

## 1. Ergebnis und Geltungsbereich

**75 % PWM ist der bevorzugte vorläufige Betriebspunkt für die nächste Prüfung.**
Bei 75 % ist der Abstand zum Stillstand größer; zugleich sind die Differenz der
beiden vollständigen Aufnahmen und die absolute sowie relative Schwankung der
5-s-Abschnitte kleiner als bei 50 %. Die Empfehlung beruht damit auch auf der
beobachteten Wiederholbarkeit, nicht allein auf der höheren Schwingungsamplitude.

Alle acht getrennten 30-s-Aufnahmen wurden tatsächlich auf dem Raspberry Pi
erfasst. Die gewünschte Zustandsreihenfolge wurde eingehalten. Eine kurze,
ununterbrochene Versuchsfolge wurde jedoch **nicht vollständig erreicht**:
Zwischen Beginn der ersten und Ende der letzten Aufnahme lagen
{number(elapsed / 60, 2)} Minuten. Lange Wartezeiten auf Sichtbestätigungen und
ein nicht mehr verfügbarer Steuerprozess vor den Schlussreferenzen sind
dokumentiert. Die tatsächlichen Zeiten seit der PWM-Änderung waren ungleich.
Diese Einschränkungen begrenzen die endgültige Auswahl eines Betriebspunktes.

Zwei Dateien je Phase sind ein Pilotversuch, kein belastbarer statistischer
Nachweis. Die Dateien einer Phase stammen aus demselben ununterbrochenen
Betriebszustand und sind keine unabhängigen Neustartversuche. Die Trennung
Stillstand/Betrieb belegt keine Anomalieerkennung bei gleicher PWM.

## 2. Aufbau, Messkette und Steuerung

Der feststehende Aufbau wurde weiterverwendet: ARCTIC P12 Pro PST mit externer
12-V-Versorgung; ADXL345 entsprechend der vorgesehenen I²C-Beschaltung an einer
Ecke des Lüfterrahmens. Montagekennung:
`fan_frame_corner_adxl345_gpio18_v1`. Die Montage blieb laut Nutzerbestätigung
unverändert. Ein Neuaufbau oder eine Positionsänderung wurde nicht durchgeführt.

| Parameter | Für alle acht Aufnahmen dokumentierter Stand |
| --- | --- |
| Lüftersteuerung | BCM GPIO18, physischer Headerpin 12; physischer Pin 18 wäre GPIO24 |
| PWM-Ausgang | RP1 `pwmchip0/pwm2`, Pin-Funktion `a3` / `PWM0_CHAN2` |
| PWM-Frequenz | Stellvorgabe 25 kHz, Periode 40.000 ns, normale Polarität, aktiviert |
| Tastgrade | 0 %: 0 ns; 50 %: 20.000 ns; 75 %: 30.000 ns |
| ADXL345 | nominell 200 Hz ODR; ±2 g; Full Resolution; FIFO Stream |
| Registerrücklesung | BW_RATE 0x0b; DATA_FORMAT 0x08; FIFO_CTL 0x90; INT_ENABLE 0x00; POWER_CTL 0x08 |
| I²C | Bus 1, konfigurierte Busfrequenz 100 kHz |
| Skalierung | 0,0039 g je LSB; keine neue Kalibrierung durchgeführt |
| Aufnahmen | je 30 s zeitgesteuert; fünf Sekunden programmierte Pause innerhalb eines Paares |
| Zeitstempel | monotone Hostzeit beim Abschluss der Registerlesung |
| Drehzahl | nicht gemessen; kein bestätigter separater Tachokanal verwendet |

Die unveränderte Sensorkonfiguration wurde anhand aller acht Metadatensätze
verglichen. GPIO18 ist hier der Steuerausgang; er wurde nicht gleichzeitig als
Tachoeingang interpretiert. Die ausgelesene PWM-Konfiguration und Pin-Funktion
belegen eine Einstellung. Eine elektrische Signalmessung oder eine Drehzahlmessung
ersetzt dies nicht. Gleichmäßiger Lauf bzw. vollständiger Stillstand wurden durch
Sichtbestätigungen des Nutzers festgestellt.

Der bestehende `FanPWM`-Controller hielt während der Aufnahmegruppen seine
gemeinsame Steuerungssperre und überprüfte den Sollwert vor und nach jeder Datei.
Diese Sperre schützt gegen kooperierende Programme, nicht gegen beliebige direkte
GPIO-Schreibzugriffe. In den Prozessprüfungen gab es keinen gefundenen konkurrierenden
Controller. Keine Erkennungsmethode beeinflusste den Betriebspunkt.

## 3. Tatsächlicher Ablauf und Abweichungen

| Ereignis | Zeit CEST | Nachweis / Einordnung |
| --- | --- | --- |
| Anfangszustand | vor 09:48:35 | bestehende 0-%-Vorgabe rückgelesen; vollständiger Stillstand vom Nutzer bestätigt |
| 50 % eingestellt | 09:50:18 | Hardware-PWM: 20.000 / 40.000 ns; mindestens 30 s gewartet, anschließend Sichtbestätigung |
| Erste Aufnahme bei 50 % | 10:15:05 | protokollierte Zeit seit Stellbefehl ca. 1.487,56 s (24,79 min) |
| 75 % eingestellt | 10:16:44 | Hardware-PWM: 30.000 / 40.000 ns; mindestens 30 s gewartet, anschließend Sichtbestätigung |
| Erste Aufnahme bei 75 % | 10:18:28 | protokollierte Zeit seit Stellbefehl ca. 103,53 s |
| 0 % eingestellt | 10:20:04 | Hardware-PWM: 0 / 40.000 ns; zehn Sekunden Auslaufzeit vor Anfrage |
| Wiederaufnahme geprüft | ab 10:34:44 | ursprüngliche Toolsitzung nicht verfügbar; kein Python-Controller gefunden; PWM weiterhin 0 % |
| Schlussreferenzen | ab 10:36:21 | aktuelle Antwort „ja“ als Bestätigung vollständigen Stillstands dokumentiert; keine PWM-Schreibbefehle in der Fortsetzung |

Die Mindestwartezeit von 30 s wurde bei beiden Betriebspunkten eingehalten;
sie war nicht die tatsächliche einheitliche Einlaufzeit. Insbesondere die lange
Wartezeit bei 50 % kann einen Zeit- oder Erwärmungseffekt mit dem Betriebspunkt
vermischen. Eine solche Ursache wurde nicht gemessen.

Vor den Schlussreferenzen ließ sich die ursprüngliche Toolsitzung 65289 nicht
fortsetzen. Ursache und genauer Zeitpunkt ihres Endes sind unbekannt. Das originale
Sitzungsjournal enthält sechs abgeschlossene Aufnahmen und weiterhin den gespeicherten
Status `running`; es wurde nicht nachträglich korrigiert. Nach erneuter Prozess- und
PWM-Prüfung sowie der aktuellen Stillstandsbestätigung wurden die beiden fehlenden
Referenzen mit einem neuen, protokollierten Aufnahmeprozess ohne PWM-Änderung erfasst.
Das abgeleitete `completed_measurement_manifest.json` führt beide Quellsitzungen
mit Prüfsummen zusammen und kennzeichnet die fehlende Prozesskontinuität ausdrücklich.
Sein Status `completed` bedeutet, dass alle acht Aufnahmen vorliegen.

## 4. Einzelaufnahmen und Datenqualität

Die angeforderte Messdauer beträgt für jede Datei 30 s. Die unten angegebene
Zeitspanne umfasst den ersten bis letzten XYZ-Messpunkt, nicht Initialisierung und
Dateiabschluss. N zählt vollständige XYZ-Messpunkte; die Zahl einzelner Achsenwerte
ist 3N. Flagspalte: Lücke / FIFO-Überlauf / Sättigung.

| Aufnahme | PWM % | Beginn–Ende CEST | N XYZ | Zeitspanne s | Durchsatz XYZ/s | Flags | Vektor-AC-RMS mg |
| --- | ---: | --- | ---: | ---: | ---: | --- | ---: |
{chr(10).join(rows)}

Der beobachtete Durchsatz wurde aus `(N−1)/(t_letzter−t_erster)` berechnet und liegt
zwischen {number(min(rates))} und {number(max(rates))} vollständigen XYZ-Punkten/s.
Das sind {number((min(rates) / 200 - 1) * 100)} bis
{number((max(rates) / 200 - 1) * 100)} % über den nominell eingestellten 200 Hz.
30 s bei exakt 200 Hz entsprächen ungefähr 6.000 XYZ-Punkten; die tatsächlich
beobachteten rund 6.200 Punkte entsprechen ungefähr 206,7 Punkten/s. Ein
XYZ-Datensatz ist nicht mit drei zeitlich getrennten Abtastungen gleichzusetzen.
Die Erfassung wird zeitlich beendet und erzeugt daher keine fest vorgegebene
Messpunktzahl. Die früher genannten 6.205 Punkte sind mit diesem höheren beobachteten
Durchsatz vereinbar; die aktuelle Folge enthält je nach Datei 6.200 bis 6.207 Punkte.
Die Ursache der Abweichung wird durch diesen Pilotversuch nicht abschließend bestimmt.

Alle Hostzeitstempel sind streng monoton und die gespeicherten Messpunktindizes
lückenlos. Es wurden keine Lücken-, Überlauf- oder Sättigungsflags gesetzt. Die
größte Hostzeitdifferenz beträgt 9,565 ms; keine überschreitet zwei nominelle
Sensorperioden (10 ms). Die maximale beobachtete FIFO-Belegung beträgt 1. Der größte
Betrag eines einzelnen Achsenwertes beträgt 1,1427 g, innerhalb des konfigurierten
Bereichs. Endliche Werte, Zeitdarstellungen, Dateihashes und identische
Sensorkonfiguration wurden geprüft.

Die Hostzeitstempel sind keine Zeitstempel der internen Sensorwandlung. Die
nominale Zeitachse `sample_index / 200` darf nicht als gemessene Sensorzeit
interpretiert werden. Fehlende Flags beweisen nicht die exakte Zahl eventuell
verlorener physischer Wandlungen; diese bleibt unbekannt. Die Prüfungen liefern
keinen Nachweis von Aliasfreiheit oder kalibrierter absoluter Genauigkeit.

## 5. Achsenmittelwerte und Streuungen

Für jede vollständige Datei wird zunächst der jeweilige Achsenmittelwert entfernt:
`a_AC,i = a_i − mean(a)`. Die hier verwendete Standardabweichung hat den Nenner N
(`ddof=0`) und entspricht damit dem AC-RMS der betreffenden Achse.

`Vektor-AC-RMS = sqrt(mean(x_AC² + y_AC² + z_AC²)) = sqrt(σx² + σy² + σz²)`.

Es wird nicht durch √3 dividiert. Das Verfahren ist außerdem nicht gleich dem
AC-RMS des zuvor gebildeten Vektorbetrags. Alle Beschleunigungsangaben beruhen auf
der bestehenden LSB-Skalierung; mg bedeutet hier 0,001 g.

| Aufnahme | Mittel X g | Mittel Y g | Mittel Z g | σX g | σY g | σZ g |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(axes)}

Die stärkere AC-Amplitude bei 75 % tritt besonders auf der X-Achse auf. Das
zustandsabhängige Ergebnis bleibt nach Entfernung der Gleichanteile bestehen.
Die Gleichanteile enthalten unter anderem die statische Beschleunigung und
Sensoroffsets; die Mittelwertentfernung ist keine vollständige Sensorkalibrierung.

## 6. Wiederholbarkeit und gleich lange Zeitabschnitte

Jede Datei wurde zusätzlich in sechs nicht überlappende, durch die relative
Hostzeit definierte 5-s-Abschnitte `[0,5), …, [25,30)` zerlegt. Jeder Abschnitt
erhält eigene Achsenmittelwerte. Eventuelle Punkte ab 30 s gehören weiter zur
vollständigen Aufnahme, nicht zu diesen sechs Abschnitten. Die zwölf Abschnittswerte
pro Phase sind keine zwölf unabhängigen Versuche.

Die relative Wiederholungsdifferenz lautet `100 × |RMS2−RMS1| / Mittel(RMS1,RMS2)`.
Der deskriptive Variationskoeffizient (CV) beschreibt die Standardabweichung der
zwölf Abschnitts-RMS-Werte geteilt durch deren Mittelwert.

| Phase | Mittel der beiden RMS mg | Differenz mg | Differenz % | 5-s-RMS min–max mg | 5-s-CV % |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(phase_rows)}

![Vektor-AC-RMS der vollständigen Dateien und 5-s-Abschnitte sowie beobachteter Durchsatz](comparison.png)

Alle 48 Abschnittswerte sind in [five_second_metrics.csv](five_second_metrics.csv)
enthalten. Die Darstellung verbindet Messpunkte nur zur Lesbarkeit; sie zeigt keine
kontinuierliche Aufzeichnung in den Pausen.

| Betrieb | Abstand zum Anfangsmittel mg | Abstand zum Endmittel mg | Kleinster Dateiabstand zum gesamten Stillstand mg | Kleinster 5-s-Abstand zum gesamten Stillstand mg |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(margin_rows)}

Für die beiden letzten Spalten wurde jeweils der kleinste Betriebswert minus dem
größten Wert aus allen vier Stillstandsdateien bzw. allen 24 Stillstandsabschnitten
berechnet. In diesem Pilotdatensatz überlappen die Bereiche von Stillstand und 50 %,
Stillstand und 75 % sowie 50 % und 75 % weder für die vollständigen Aufnahmen noch
für die 5-s-Abschnitte. Das ist eine deskriptive Beobachtung, keine Klassifikationsgüte.

Bereits bei 50 % beträgt der Abstand zum Stillstandsmittel etwa 1,99–2,00 mg und
ist damit größer als die gemessene Wiederholungsdifferenz bei 50 % (0,287 mg) und
die größte Wiederholungsdifferenz der Stillstandsphasen (0,320 mg). Bei 75 % ist der
Abstand etwa 16,63–16,64 mg bei einer Wiederholungsdifferenz von 0,025 mg. Zugleich
ist die gesamte Spannweite der 5-s-Werte bei 75 % mit 0,856 mg kleiner als die
1,411 mg bei 50 %. Die besonders kleine Dateidifferenz bei 75 % darf angesichts
von nur zwei Wiederholungen nicht als garantierte Reproduzierbarkeit gelten.

## 7. Stillstand am Anfang und Ende

Das mittlere Vektor-AC-RMS änderte sich von {number(pre * 1000)} auf
{number(post * 1000)} mg, also um {number((post - pre) * 1000)} mg bzw.
{number(100 * (post - pre) / pre)} %. Die Bereiche der Anfangs- und
Schlussreferenzen überlappen. Die Schlussreferenzen schwanken untereinander
stärker (2,515 % statt 0,561 %), obwohl ihre Mittelwerte eng beieinander liegen.

Die Änderung der gemittelten Achsengleichanteile Ende minus Anfang beträgt
X {number(mean_changes[0] * 1000)} mg, Y {number(mean_changes[1] * 1000)} mg,
Z {number(mean_changes[2] * 1000)} mg. Eine Ursache dieser Änderungen wurde nicht
untersucht. Ähnliche Anfangs- und Endmittelwerte beweisen weder durchgängige
Stationarität noch das Fehlen zeitlicher Einflüsse während der dazwischenliegenden
Betriebsphasen.

## 8. Empfehlung und nächste Prüfung

Die Messkette ist für diesen beschreibenden RMS-Pilotvergleich verwendbar: Es
liegen vollständige, prüfbare Dateien ohne erkannte Qualitätsflags und eine
beobachtbare Zustandstrennung vor. **75 % PWM bei unveränderten 25 kHz ist ein
begründeter Kandidat, aber noch kein endgültig validierter Betriebspunkt.**

Vor der endgültigen Festlegung sollte eine weitere kontrollierte Normalbetriebsserie
die Reproduzierbarkeit über separate Neustarts prüfen. Dabei sollten 50 % und 75 %
mit vergleichbarer tatsächlicher Einlaufzeit, zeitnahen Sichtbestätigungen und
abwechselnder Reihenfolge aufgenommen werden; Stillstandsreferenzen bleiben
erforderlich. Der Aufnahmeprozess sollte über die Bestätigungswartezeiten hinweg
zuverlässig verfügbar bleiben. Eine feste Einlaufdauer ist prospektiv zu bestimmen
und mit Zeitverläufen zu prüfen; die bisherige Mindestwartezeit allein beweist
keine erreichte stationäre Drehzahl oder Schwingungsamplitude.

Spätere Normal- und Anomalieversuche müssen am jeweils gleichen PWM-Sollwert
stattfinden. Der hier beobachtete Unterschied 50 %/75 % darf nicht als künstlicher
Anomaliefall benutzt werden. Vor dem Methodenvergleich sind Messfenster und der
Umgang mit nominaler ODR gegenüber beobachtetem Durchsatz festzulegen. Bei der
späteren Prüfung eines zweiten normalen Betriebspunktes müssen Modelle,
Skalierung und Schwellen unverändert bleiben. Jetzt wurden keine Modelle trainiert,
keine Schwellen angepasst und keine künstlichen Anomalien erzeugt.

## 9. Endzustand und Nachvollziehbarkeit

Der letzte Stellbefehl war **0 % PWM bei 25 kHz** um 08:20:04 UTC / 10:20:04 CEST.
Vollständiger mechanischer Stillstand wurde anschließend vom Nutzer vor den beiden
Schlussreferenzen bestätigt. Die Schlussreferenzen erfolgten bei rückgelesenen 0 %;
die Fortsetzung änderte die PWM nicht. Eine automatische Drehzahl- oder
Stillstandsmessung wird damit nicht behauptet.

Rohdaten und Metadaten wurden separat und ohne Überschreiben vorhandener Dateien
gespeichert. Worddatei und historische Messprotokolle werden durch diesen Bericht
nicht verändert. Der abschließende Hashvergleich wird separat in
`../final_verification.json` festgehalten.

| Nachweis | Datei |
| --- | --- |
| Numerische Gesamtauswertung mit Definitionen und Hashes | [report.json](report.json) |
| Einzelaufnahmen und Qualitätskennzahlen | [recording_metrics.csv](recording_metrics.csv) |
| Alle 5-s-Abschnitte | [five_second_metrics.csv](five_second_metrics.csv) |
| Deskriptive Phasenvergleiche | [phase_contrasts.csv](phase_contrasts.csv) |
| Grafik als PDF | [comparison.pdf](comparison.pdf) |
| Ergänzende Spektren, keine Zuordnung zu RPM | [spectra.csv](spectra.csv) |
| Abgeleitetes vollständiges Manifest | [completed_measurement_manifest.json](../completed_measurement_manifest.json) |
| Unveränderte ursprüngliche Sitzung | [sequence_20260910_074455.json](../sequence_20260910_074455.json) |
| Ursprüngliche PWM-Befehle und Rücklesungen | [sequence_20260910_074455_fan.jsonl](../sequence_20260910_074455_fan.jsonl) |
| Fortsetzung mit Schlussreferenzen | [closing_references_20260910_083621.json](../closing_references_20260910_083621.json) |
| Nur lesende PWM-Prüfungen der Fortsetzung | [closing_references_20260910_083621_fan.jsonl](../closing_references_20260910_083621_fan.jsonl) |

Die Datengrundlage und die Auswertungsskripte sind über SHA-256-Prüfsummen
zugeordnet. Die ergänzenden Spektren begründen in diesem Bericht keine mechanische
Frequenzzuordnung oder Drehzahl. Die Entscheidung beruht auf den ausdrücklich
dargestellten AC-RMS- und Wiederholbarkeitskennzahlen.
"""

with (OUT / 'report.md').open('x', encoding='utf-8') as handle:
    handle.write(text)

exclusive_json(OUT / 'operating_point_recommendation.json', {
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'provisional_candidate_requires_restart_and_timing_check',
    'recommended_candidate_pwm_percent': 75,
    'pwm_frequency_hz': 25000,
    'final_operating_point_validated': False,
    'evidence': analysis['operating_point_comparison'],
    'reason': 'Larger observed background margin and lower whole-record repeat difference and absolute/relative five-second vector-AC-RMS variation than 50%, within this pilot.',
    'independent_restart_repeats_per_operating_point': 0,
    'files_per_phase': 2,
    'limitations': [
        'Two sequential files from each held state do not establish statistical reproducibility.',
        'Actual time since PWM command differs: about 1487.56s for first50% and103.53s for first75%.',
        'Sequence elapsed48.85min; original controller unavailable before final references; cause/time unknown.',
        'Standstill-versus-operation separation is not evidence of anomaly detection at fixed PWM.',
        'No measured RPM, electrical waveform, alias-freedom proof or new absolute sensor calibration.',
    ],
    'next_step': 'Controlled normal-operation repeats across separate restarts, comparable actual settling times, alternating50/75 order and beginning/end standstill references; then decide final point.',
    'later_anomaly_comparison_requires_same_pwm': True,
    'later_second_normal_point_requires_frozen_models_scaling_thresholds': True,
    'models_trained': False,
    'anomalies_induced': False,
    'final_pwm_setpoint_percent': 0,
    'mechanical_state_source': manifest['final_mechanical_state'],
    'analysis_path': str((OUT / 'report.json').relative_to(ROOT)),
    'analysis_sha256': sha(OUT / 'report.json'),
    'written_report_sha256': sha(OUT / 'report.md'),
})
print(json.dumps({'report': str(OUT / 'report.md'), 'recommendation_pwm_percent': 75,
                  'status': 'provisional', 'report_bytes': (OUT / 'report.md').stat().st_size}))
