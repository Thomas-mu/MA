"""Offline report for the completed v4 sequence; no control or sensor access."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
PHASES = ('standstill', 'normal_before', 'airflow_modified', 'normal_after')


def fmt(x, digits=3):
    return 'unbekannt' if x is None else f'{x:.{digits}f}'.replace('.', ',')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] + ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows])


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    path = BASE / 'final_sequence_report.md'
    if path.exists():
        raise FileExistsError('Preserve existing report')
    sessions = {p: json.loads((BASE / f'{p}_session.json').read_text()) for p in PHASES}
    reports = {p: json.loads((BASE / 'analysis' / p / 'summary.json').read_text()) for p in PHASES}
    comparison = json.loads((BASE / 'analysis/sequence_comparison/comparison.json').read_text())
    for p in PHASES:
        assert sessions[p]['status'] == 'completed'
        assert sessions[p]['final_readback']['pwm_configuration']['configured_duty_percent'] == 0
        assert reports[p]['sensor'] == reports['standstill']['sensor']
        for relative, expected in reports[p]['input_sha256'].items():
            assert digest(ROOT / relative) == expected
    timing_rows, quality_rows, axis_rows, primary_rows, groups, refs = [], [], [], [], [], []
    for p in PHASES:
        s, r = sessions[p], reports[p]
        q = r['quality']
        quality_rows.append([f'`{p}`', q['configured_duration_s'], q['xyz_points'], fmt(q['first_to_last_host_s'], 6), fmt(q['observed_xyz_s'], 4), fmt(q['host_interval_max_ms']), q['host_intervals_over_10ms'], q['fifo_max'], f"{q['gap_count']} / {q['overrun_count']} / {q['saturated_count']}"])
        axis_rows.append([f'`{p}`', *[fmt(v, 6) for v in q['axis_means_g']], *[fmt(1000 * v) for v in q['axis_std_g_ddof0']]])
        refs.append(f"- `{p}`: [Rohdaten](../../{s['csv']}), [Metadaten](../../{Path(s['csv']).with_suffix('.json')}), [Sitzung]({p}_session.json), [Steuerjournal]({p}_fan.jsonl), [Kennwerte](analysis/{p}/summary.json), [5-s-Fenster](analysis/{p}/five_second_rms.csv).")
        if p == 'standstill':
            continue
        a = r['primary_180_300']
        timing_rows.append([f'`{p}`', s['command_invocation_utc'], s['timing']['first_xyz_utc_estimate'], fmt(1000 * s['timing']['first_xyz_after_command_invocation_s']), fmt(s['additional_off_from_release_actual_s'], 6), fmt(s.get('total_off_since_previous_zero_s'), 6), s['zero_command_completed_utc']])
        primary_rows.append([f'`{p}`', fmt(a['mean_mg']), fmt(a['std_mg_ddof0']), f"{fmt(a['min_mg'])}–{fmt(a['max_mg'])}", fmt(a['linear_slope_mg_min']), fmt(a['theil_sen_slope_mg_min']), fmt(a['fitted_120s_change_percent']), fmt(a['last60_minus_first60_mg'])])
        groups.append([f'`{p}`', *[fmt(v) for v in a['four_30s_means_mg']]])
    sections = [f'''# Messbericht: aufrechte Aufstellung, Normal → Platte → Normal

Erstellt am {datetime.now(timezone.utc).isoformat()}. Aufbauversion **`{comparison['mounting_id']}`**. Die neue 30-s-Stillstandsreferenz und alle drei freigegebenen 300-s-Betriebsaufnahmen sind abgeschlossen. Ausschließlich Daten dieser Aufbauversion werden direkt verglichen. Frühere liegende oder zwischenzeitlich verschobene Aufstellungen bleiben getrennt erhalten.

## Aufbau und belegte Randbedingungen

Der Lüfter steht aufrecht. Die neue Position nach der berichteten Bewegung zum Einpassen der Platte wurde als eigene Aufbauversion v4 dokumentiert und mit neuen Referenzen begonnen. Die feste und sichere Aufstellung wurde als Nutzerangabe übernommen. Der ADXL345 ist mit zwei Schrauben am äußeren, feststehenden Lüfterrahmen befestigt; die Platine sitzt schräg. Lüfterposition, Sensorbefestigung und Sensoreinstellungen sollten innerhalb dieser Folge unverändert bleiben. Beim Einsetzen der Platte berichtete der Nutzer ausdrücklich, nur die Platte bewegt zu haben. Eine unabhängige Vermessung oder Sichtbeobachtung durch die Software liegt nicht vor.

Angeschlossene externe 12-V-Versorgung und die jeweilige Phasenfreigabe wurden durch Nutzernachrichten dokumentiert. Vollständiger mechanischer Stillstand vor der Anfangsreferenz wurde vom Nutzer bestätigt. Vor den manuellen Umbauten war die externe Versorgung zu trennen und vollständiger Stillstand abzuwarten; dies wurde beim Einsetzen als durchgeführt berichtet. Das Entfernen der Platte und die wieder angeschlossene Versorgung wurden für den letzten Lauf ausdrücklich bestätigt. Es wurden keine Fragen zum sichtbaren Lauf gestellt. Aus fehlenden Beobachtungen wird kein mechanischer Zustand abgeleitet.

Geplant war eine separat und kippsicher befestigte Platte von **60 × 120 mm**, parallel zur Auslassseite, mit **100 mm Abstand** zur äußeren Rahmenebene und ohne Berührung von Lüfter oder Sensor. Die vorgesehene Überdeckung betrifft die rechte Hälfte der projizierten Rahmenfläche bei Blick in den Auslass; dies ist keine Angabe über den tatsächlichen Volumenstrom. Tatsächliche Maße, Material, Abstand, Ausrichtung, Halterungsdetails, räumliche Auslassidentifikation und Parkabstand in den Normalphasen wurden nicht vermessen oder konkret berichtet. Diese Angaben bleiben unbekannt. Das eingesetzte bzw. entfernte Bauteil ist eine bestätigte Versuchsbedingung, kein direkt gemessener Luftstrom. Die erhaltene Herstellerzeichnung bezeichnet die beabsichtigte Auslassrichtung, belegt aber keine Istorientierung des Aufbaus.

Belege: [Aufbauversion](mounting.json), [Sollgeometrie](geometry.json), [Plattenphase](airflow_modified_geometry.json), [Rückkehrphase](normal_after_geometry.json), [Anfangsfreigabe](initial_release.json), [Plattenfreigabe](airflow_modified_release.json), [letzte Freigabe](normal_after_release.json). Die `mounting`-Kopie in den Metadaten ist der erhaltene Anfangszustand; den aktuellen Plattenzustand benennt jeweils die Phasengeometrie. Originalwortlaut und technische Normalisierung der Freigaben sind getrennt gespeichert.

## Steuerung und tatsächliche Zeitpunkte

Alle Betriebsläufe verwenden **75 % PWM bei 25 kHz**, anschließend **0 %**. GPIO18 ist die BCM-Nummer und entspricht dem physischen Pin 12. Verwendet wurde die bestehende RP1-Hardware-PWM, Kanal 2, Pin-Funktion `a3` / `PWM0_CHAN2`, Periode 40.000 ns, Tastzeit im Betrieb 30.000 ns. Die Steuerjournale belegen pro Betriebslauf genau einen 75-%- und einen 0-%-Stellvorgang. Zugriffssperren und Prozessprüfung verhindern konkurrierende kooperierende Steuerungen. Zusätzliche Kontrollablesungen veränderten keine PWM-Vorgabe. Es gab keine erkennungsabhängige Steuerung, Antwortfristen oder automatischen Wiederholungsstarts.

Alle Tabellenzeitpunkte sind **UTC**; Ortszeit Europe/Berlin liegt am Versuchstag zwei Stunden später. Der Aufnahmebeginn bezeichnet die erste vollständige XYZ-Lesung. Deren UTC-Schätzung wird aus den gemeinsam erfassten UTC- und monotonen Hostzeiten des Befehlsaufrufs abgeleitet. Elektrische Signalflanke, Rotorstart und tatsächliche Drehzahl wurden nicht gemessen.
''', table(['Phase', 'PWM-Aufruf [UTC]', 'Erste XYZ-Lesung [UTC]', 'Versatz ab Aufruf [ms]', 'Zusatz-Auszeit ab Freigabe [s]', 'Abstand zum vorigen Nullbefehlsabschluss [s]', 'Nullbefehlsabschluss [UTC]'], timing_rows), '''
Vorgesehen waren einheitlich 60 s zusätzliche Auszeit ab softwareseitig angenommener Freigabe. Der erste Start erfolgte wegen Vorbereitung und vorangehender Stillstandsaufnahme erst nach **84,097 s**; die Abweichung bleibt ausdrücklich dokumentiert und wurde nicht durch einen Wiederholungsstart ersetzt. Bei den späteren Starts wird die tatsächlich erzielte Zeit in der Tabelle ausgewiesen. Der Abstand zwischen Null- und Startbefehl ist weder eine gemessene mechanische Stillstandsdauer noch eine identische Abkühl- oder Versorgungsauszeit. Insbesondere sind die gesamten Auszeiten der drei Läufe nicht gleich.

## Messkette, Datenqualität und Zeitbasis

Die rückgelesene Konfiguration ist in allen vier Aufnahmen gleich: ADXL345, nominell **200 Hz**, ±2 g, Full Resolution, FIFO-Stream, Skalierung 0,0039 g/LSB. I²C-Bus 1, Adresse 0x53, konfigurierter Bustakt 100 kHz; BW_RATE=0x0B, DATA_FORMAT=0x08, INT_ENABLE=0x00, FIFO_CTL=0x90, POWER_CTL=0x08. Gerätekennung und Registerzustand wurden mit der vorhandenen Software geprüft.
''', table(['Phase', 'Soll-Dauer [s]', 'XYZ-Punkte', 'Erste–letzte Hostlesung [s]', 'Beobachtet [XYZ/s]', 'Hostabstand max. [ms]', 'Abstände >10 ms', 'FIFO max.', 'Gap / Overrun / Sättigung'], quality_rows), '''
Eine Datenzeile enthält einen vollständigen XYZ-Messpunkt und damit drei einzelne Achsenwerte. Die beobachtete Rate wird als `(N−1)/(t_letzter−t_erster)` aus den monotonen Host-Leseabschlüssen ermittelt. Sie wird getrennt von nominellen 200 Hz berichtet. Die Spalte `sample_index / 200` ist nur eine nominelle Zeitschätzung; sie wird nicht für die hier verwendeten 5-s-Grenzen herangezogen. Eine unabhängige Kalibrierung der Wandlungszeitbasis liegt nicht vor.

Gesichert aus dem vorhandenen Code: Eine 6-Byte-XYZ-Lesung wird nur nach positivem FIFO-Füllstand übernommen. Der FIFO wird an der Aufnahmegrenze zurückgesetzt. Die Software erzeugt keine zusätzlichen interpolierten Messpunkte und erzwingt keine Schleifenrate von 207 Hz. Mehrfach identische quantisierte XYZ-Tupel sind nicht allein ein Beleg für Mehrfachzählung. Die genaue Ursache der Abweichung zwischen nomineller und beobachteter Rate bleibt offen; die Sensorzeitbasis wurde nicht unabhängig gemessen. Host-Leseabschlüsse sind keine Sensor-Wandlungszeitstempel.

Rohdatenhashes, endliche XYZ-Werte, steigende Hostzeitstempel, konsistente Zeitspalten und fortlaufende Softwareindices wurden geprüft. Der implementierte Gap-Indikator umfasst Überlaufverdacht oder einen Hostabstand über `32 / 200 = 0,160 s`. Kürzere auffällige Hostabstände werden deshalb zusätzlich gesondert ausgewertet. Overrun wird aus dem Statusbit oder einem vollen FIFO abgeleitet; Sättigung anhand der Rohwerte am konfigurierten Messbereichsrand. Fehlende Flags und fortlaufende Softwareindices beweisen keine exakte physische Sensorverlustzahl; diese bleibt unbekannt.

Achsenmittelwerte und Streuungen beziehen sich in der folgenden Tabelle auf die jeweils gesamte Rohaufnahme. mg bezeichnet 0,001 g Beschleunigung; die Streuung verwendet den Divisor N.
''', table(['Phase', 'Mittel X [g]', 'Mittel Y [g]', 'Mittel Z [g]', 'Streuung X [mg]', 'Streuung Y [mg]', 'Streuung Z [mg]'], axis_rows), '''
## Vektor-AC-RMS und zeitliche Veränderungen

Für jedes nicht überlappende 5-s-Fenster werden zunächst dessen drei Achsenmittelwerte entfernt. Danach wird `sqrt(mean(x_ac² + y_ac² + z_ac²))` berechnet. Die Berechnung wurde gegen die Summe der Achsenvarianzen geprüft. Die Fenster beziehen sich im Betrieb auf den PWM-Befehlsaufruf, im Stillstand auf den Erfassungsaufruf. Die kurze Zeit bis zur ersten Lesung wird nicht aufgefüllt. Rohdatenpunkte nach 300 s bleiben gespeichert, liegen aber außerhalb der festgelegten Auswertefenster.

Pro Betriebslauf liegen 60 Fenster vor, davon 24 in **180–300 s**. Diese Einlaufzeit ist für die aktuelle Aufstellung weiterhin ein Prüfkandidat. Nachfolgend stehen getrennt das mittlere Niveau und zeitliche Trendkennwerte innerhalb jedes Laufs. Die Fensterstandardabweichung verwendet den Divisor 24. Die Fenster sind keine unabhängigen Versuchsreplikate.
''', table(['Phase', 'RMS-Mittel [mg]', 'Fenster-SD [mg]', 'Fensterbereich [mg]', 'Lineare Steigung [mg/min]', 'Robuste Mediansteigung [mg/min]', 'Angepasste 120-s-Änderung [%]', 'Letzte–erste 60 s [mg]'], primary_rows), '\nVier aufeinanderfolgende 30-s-Gruppen des späten Abschnitts, jeweils Mittelwert der enthaltenen sechs 5-s-RMS-Werte:\n', table(['Phase', '180–210 s [mg]', '210–240 s [mg]', '240–270 s [mg]', '270–300 s [mg]'], groups), '''
![Vollständiger Zustandsvergleich, später Abschnitt und zeitliche Veränderungen](analysis/sequence_comparison/sequence_comparison.png)

[Vergleichsgrafik als PDF](analysis/sequence_comparison/sequence_comparison.pdf), [Vergleichszahlen als JSON](analysis/sequence_comparison/comparison.json). Die dritte Grafikachse entfernt zusätzlich den jeweiligen späten RMS-Laufmittelwert, um zeitliche Veränderungen ohne den Niveauunterschied zu zeigen; dies ist keine neue Entfernung der XYZ-Gleichanteile.

![Rückkehrreferenz mit Host-Leseabständen](analysis/normal_after/phase_overview.png)

## Rückkehr und Grenzen des Zustandsvergleichs
''']
    shift = comparison['normal_after_minus_before_mg']
    sections.append(f"Der späte Mittelwert der Rückkehrreferenz unterscheidet sich vom vorherigen Normalmittel um **{fmt(shift)} mg ({fmt(comparison['normal_after_minus_before_percent'])} %)**. Die beobachteten Normal-Fensterbereiche überlappen: **{'ja' if comparison['normal_observed_ranges_overlap'] else 'nein'}**. **{comparison['after_windows_inside_observed_before_range']} von 24** Rückkehrfenstern liegen innerhalb des beobachteten Bereichs der vorherigen Normalaufnahme. Dies ist eine beschreibende Bereichsprüfung, kein Konfidenz- oder Toleranzintervall und kein vorher festgelegtes Akzeptanzkriterium.")
    contrasts = []
    for p, c in comparison['altered_contrasts'].items():
        contrasts.append([f'Platte minus `{p}`', fmt(c['mean_difference_mg']), fmt(c['percent_of_normal_mean']), 'ja' if c['observed_ranges_overlap'] else 'nein', 'ja' if c['absolute_difference_exceeds_observed_normal_mean_shift'] else 'nein'])
    sections.append(table(['Vergleich', 'Mittelwertdifferenz [mg]', 'Relativ zum Normalmittel [%]', 'Fensterbereiche überlappen', 'Abstand größer als normaler Mittelwertwechsel'], contrasts))
    sections.append(f"Die quadratisch gemittelte Streuung innerhalb der beiden späten Normalaufnahmen beträgt {fmt(comparison['normal_within_rms_std_mg'])} mg. Der oben ausgewiesene Wechsel zwischen deren Mittelwerten ist eine andere Größe. Nur ein Normal→Platte→Normal-Durchlauf wurde ausgeführt. Aussagen über normale Startvariabilität beruhen damit auf zwei zeitlich getrennten Normalaufnahmen; sie sind keine belastbare Verteilungsschätzung.")
    sections.append('''Die Stillstandsreferenz wurde einmal zu Beginn erfasst; eine zweite abschließende Stillstandsaufnahme gehört nicht zu dieser freigegebenen Folge. Ihre sechs 5-s-Fenster beschreiben nur diese Anfangsreferenz. Ein Unterschied zwischen Stillstand und Betrieb ist kein Nachweis erfolgreicher Anomalieerkennung.

Die Platte bezeichnet einen kontrollierten veränderten Betriebszustand. Es wurde weder ein Defekt nachgewiesen noch ein Modell trainiert oder eine Erkennungsleistung gemessen. Eine einzelne Folge belegt keine allgemeine Reproduzierbarkeit. Unbekannte Istgeometrie, unterschiedliche gesamte Auszeiten, nicht gemessene Drehzahl und die nicht unabhängig kalibrierte Sensorzeitbasis begrenzen die Interpretation. Zeitliche Entwicklungen innerhalb der Läufe dürfen nicht allein als Unterschiede zwischen Bedingungen interpretiert werden; umgekehrt widerlegen unterschiedliche Laufmittelwerte allein keine geeignete Einlaufzeit.

## Dateien und Abschluss
''')
    sections.append('\n'.join(refs))
    sections.append(f"Nach dem letzten Lauf wurde **0 % PWM bei 25 kHz** eingestellt und mit korrekter PWM-Pin-Funktion rückgelesen. Nullbefehlsabschluss: **{sessions['normal_after']['zero_command_completed_utc']}**. Ein abschließender mechanischer Stillstand wurde nicht beobachtet. Es ist kein weiterer Start vorgesehen. Worddatei, Modelle und historische Dateien bleiben unverändert.")
    with path.open('x', encoding='utf-8') as handle:
        handle.write('\n\n'.join(sections) + '\n')
    print(path)


if __name__ == '__main__':
    main()
