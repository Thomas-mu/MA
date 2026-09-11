"""Report the first two completed upright phases only; no hardware access."""
from pathlib import Path
import csv
import hashlib
import json

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]


def main():
    output=BASE/'initial_report.md'
    if output.exists():raise FileExistsError('Preserve the existing interim report')
    reports={p:json.loads((BASE/'analysis'/p/'summary.json').read_text()) for p in ('standstill','normal_before')}
    sessions={p:json.loads((BASE/f'{p}_session.json').read_text()) for p in reports}
    assert all(s['status']=='completed' for s in sessions.values())
    assert reports['standstill']['mounting_id']==reports['normal_before']['mounting_id']
    assert reports['standstill']['sensor']==reports['normal_before']['sensor']
    for r in reports.values():
        assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in r['input_sha256'].items())
    def fmt(x,n=3):return f'{x:.{n}f}'.replace('.',',')
    r=reports['normal_before'];s=sessions['normal_before'];p=r['primary_180_300'];q=r['quality']
    with (BASE/'analysis/standstill/five_second_rms.csv').open() as f:
        still_values=[float(row['vector_ac_rms_mg']) for row in csv.DictReader(f)]
    rows=[]
    for phase,a in reports.items():
        z=a['quality'];rms=a['all_window_summary'] if phase=='standstill' else a['primary_180_300']
        rows.append(f"| `{phase}` | {z['configured_duration_s']} | {format(z['xyz_points'], ',').replace(',', '.')} | {fmt(z['first_to_last_host_s'],6)} | {fmt(z['observed_xyz_s'],4)} | {fmt(z['host_interval_max_ms'])} | {z['fifo_max']} | {z['gap_count']} / {z['overrun_count']} / {z['saturated_count']} | {fmt(rms['mean_mg'])} |")
    table='\n'.join(rows)
    flags_clear=all(a['quality_flags_clear'] for a in reports.values())
    text=f'''# Aufrechte Aufstellung: Stillstandsreferenz und erster Normallauf

Zwischenbericht vom 11.09.2026. Aufbauversion **`{r['mounting_id']}`**. Die Phasen `standstill` und `normal_before` sind abgeschlossen. `airflow_modified` und `normal_after` wurden noch nicht ausgeführt. Dieser Bericht enthält ausschließlich neue Daten der aufrechten Aufstellung; liegende Aufnahmen werden nicht als direkte Referenz verwendet.

## Bestätigte Bedingungen und offene Geometriedetails

Die feste und sichere aufrechte Befestigung ist entsprechend der Nutzerangabe übernommen. Angeschlossene externe 12-V-Versorgung und vollständiger mechanischer Stillstand wurden vor der Anfangsphase getrennt vom Nutzer bestätigt; dokumentiert in [initial_release.json](initial_release.json). Sensorbefestigung und Lüfterposition sollten während der neuen Folge unverändert bleiben. Es wurden keine erneuten Fragen zum sichtbaren Lüfterlauf gestellt.

Die tatsächliche Auslassseite im Raum, Plattenmaße, Material, Halterungsdetails und Abstand sind noch nicht berichtet. Sollwerte und Herstellerzeichnung stehen getrennt davon in [protocol.md](protocol.md) und [geometry.json](geometry.json). Die Stillstandsaufnahme und der erste Betrieb wurden als ohne Platte freigegeben. Daraus wird keine vermessene Geometrie abgeleitet.

## Ablauf und Zeitbasis

Die 30-s-Stillstandsaufnahme lag bei 0 % PWM innerhalb der zusätzlichen Auszeit. Vom softwareseitigen Annahmezeitpunkt der Anfangsbestätigung bis zum ersten PWM-Befehlsaufruf vergingen **{fmt(s['additional_off_from_release_actual_s'],6)} s**. Dies ist keine gemessene gesamte mechanische Stillstands- oder Abkühlzeit; die zuvor vollständig verifizierte Gesamtauszeit ist unbekannt.

Der erste Betriebsbefehl auf 75 % bei 25 kHz wurde um **{s['command_invocation_utc']}** aufgerufen (UTC; Ortszeit Europe/Berlin = UTC+2). Die erste XYZ-Lesung folgte **{fmt(s['timing']['first_xyz_after_command_invocation_s']*1000)} ms nach Befehlsaufruf**, beziehungsweise {fmt(s['timing']['first_xyz_after_command_completion_s']*1000)} ms nach Befehlsabschluss. Elektrische Signalflanke und tatsächlicher Rotorstart wurden nicht gemessen.

Nach der 300-s-Erfassung wurde auf **0 % PWM** zurückgestellt und die Einstellung rückgelesen. Der Nullbefehl war um **{s['zero_command_completed_utc']}** abgeschlossen. Der Betriebspunkt wurde vor und nach der Aufnahme mit 75 % bestätigt; das Steuerjournal enthält genau einen 75-%- und einen 0-%-Stellvorgang. Eine mechanische Stillstandsbestätigung nach diesem Lauf liegt nicht vor.

## Messkette und Qualitätsprüfung

Beide neuen Phasen verwenden dieselbe rückgelesene Konfiguration: ADXL345, nominell 200 Hz, ±2 g, Full Resolution, FIFO-Stream, I²C-Bus 1/Adresse 0x53, konfigurierter Bustakt 100 kHz. Register: BW_RATE=0x0B, DATA_FORMAT=0x08, INT_ENABLE=0x00, FIFO_CTL=0x90, POWER_CTL=0x08. Die Software skaliert unverändert mit 0,0039 g/LSB.

| Phase | Soll-Dauer [s] | XYZ-Punkte | Spanne erste–letzte Lesung [s] | Beobachtet [XYZ/s] | Größter Hostabstand [ms] | FIFO max. | Gap / Overrun / Sättigung | Mittlerer Fenster-AC-RMS [mg] |
|---|---:|---:|---:|---:|---:|---:|---|---:|
{table}

Der RMS-Mittelwert bezieht sich beim Stillstand auf sechs 5-s-Fenster und beim Normalbetrieb auf 24 Fenster in 180–300 s. Pro XYZ-Punkt liegen drei einzelne Achsenwerte vor. Die Zahl gesetzter Qualitätsflags ist der Tabelle zu entnehmen; alle Flags über beide Aufnahmen frei: **{'ja' if flags_clear else 'nein'}**. Rohdatenhashes, steigende Hostzeitstempel, konsistente Zeitspalten, endliche XYZ-Werte und lückenlose Softwareindices wurden geprüft.

Die beobachtete Rate wird aus `(N−1)/(t_letzter−t_erster)` berechnet und bleibt von nominellen 200 Hz getrennt. Host-Leseabschlüsse sind keine unabhängig gemessenen Wandlungszeitpunkte. Ein lückenloser Softwareindex und nicht gesetzte Flags beweisen keine exakte Sensorverlustzahl; diese ist unbekannt. Sämtliche Host-Leseabstände, Lesedauern und Achsenkennwerte stehen in den verlinkten JSON-Auswertungen.

Die Stillstandsreferenz ist nicht völlig konstant: Vom ersten zum letzten 5-s-Fenster steigt der Vektor-AC-RMS von **{fmt(still_values[0])} auf {fmt(still_values[-1])} mg**, entsprechend {fmt(still_values[-1]-still_values[0])} mg bzw. {fmt(100*(still_values[-1]/still_values[0]-1))} %. Die Ursache ist mit diesen Daten nicht geklärt; das Signal wird deshalb nicht als konstantes reines Sensorrauschen interpretiert. Diese Beobachtung ändert die dokumentierte Nutzerbestätigung des mechanischen Stillstands nicht und wird nicht nachträglich als Lüfterrotation gedeutet.

## Vorläufiges Auswertefenster 180–300 Sekunden

Vektor-AC-RMS wird in jedem nicht überlappenden 5-s-Fenster nach Entfernung der jeweiligen drei Achsenmittelwerte berechnet. mg bedeutet 0,001 g Beschleunigung. Die Berechnung wurde algebraisch gegen die Summe der Achsenvarianzen geprüft. Die Zeitfenster beziehen sich im Betrieb auf den PWM-Befehlsaufruf und im Stillstand auf den Erfassungsaufruf. Der kurze Zeitraum vor der ersten XYZ-Lesung wird nicht aufgefüllt; Rohdaten knapp nach dem Auswerteende bleiben erhalten.

| Kennwert des ersten Normallaufs, 180–300 s | Ergebnis |
|---|---:|
| Mittlerer Fenster-AC-RMS | {fmt(p['mean_mg'])} mg |
| Standardabweichung der 24 Fenster, Divisor 24 | {fmt(p['std_mg_ddof0'])} mg |
| Minimum–Maximum der Fenster | {fmt(p['min_mg'])}–{fmt(p['max_mg'])} mg |
| Lineare Steigung | {fmt(p['linear_slope_mg_min'])} mg/min |
| Robuste Mediansteigung der Fensterpaare | {fmt(p['theil_sen_slope_mg_min'])} mg/min |
| Angepasste Änderung über 120 s | {fmt(p['fitted_120s_change_mg'])} mg / {fmt(p['fitted_120s_change_percent'])} % |
| Letzte 60 s minus erste 60 s im späten Abschnitt | {fmt(p['last60_minus_first60_mg'])} mg |

Die 180-s-Einlaufzeit bleibt für die neue Aufstellung ein Prüfkandidat. Ein gerichteter Verlauf innerhalb dieser Aufnahme ist von späteren Unterschieden zwischen den drei Betriebsläufen zu trennen. Die 24 Fenster sind keine unabhängigen Lüfterstarts. Weder die Trennung zum Stillstand noch diese einzelne Normalaufnahme belegt allgemeine Reproduzierbarkeit oder erfolgreiche Anomalieerkennung.

Im späten Abschnitt ist der lineare Trend im Verhältnis zur Fensterstreuung klein; die beiden 60-s-Hälften zeigen nicht denselben Richtungsbefund wie die geringe positive lineare Steigung. Daraus wird kein eindeutiger fortgesetzter Einlaufeffekt abgeleitet. Ob Unterschiede zwischen Normal- und verändertem Betrieb größer als normale Startschwankungen sind, bleibt bis zur Durchführung der übrigen Phasen offen.

![Stillstandsreferenz](analysis/standstill/phase_overview.png)

![Vollständiger erster Normallauf, später Abschnitt und Hostabstände](analysis/normal_before/phase_overview.png)

Auswertungen: [Stillstand](analysis/standstill/summary.json), [Normalbetrieb](analysis/normal_before/summary.json). Fensterdaten: [Stillstand](analysis/standstill/five_second_rms.csv), [Normalbetrieb](analysis/normal_before/five_second_rms.csv). Rohdateien und deren Hashes sind jeweils dort referenziert. PDFs liegen neben den PNG-Grafiken.

## Nächster manueller Schritt und Pause

Stellvorgabe: **0 % PWM bei 25 kHz**. Der Nutzer trennt nun vor dem Umbau die externe 12-V-Versorgung, wartet auf vollständigen mechanischen Stillstand und befestigt die Platte separat und kippsicher gemäß Plan: vorgesehen 60 × 120 mm, parallel zur Auslassseite, 100 mm Abstand. Platte und Halterung berühren weder Lüfter noch Sensor. Die tatsächlichen Angaben werden dokumentiert, soweit berichtet; Sollwerte werden nicht als Istwerte ausgegeben.

Erst nach „Umbau fertig, nächster Lauf freigegeben.“ beginnt die nächste 60-s-Zusatz-Auszeit und anschließend einmalig `airflow_modified`. Eine fehlende Nachricht ist keine Freigabe. Bis dahin erfolgt kein Start. Nach Entfernen der Platte ist für `normal_after` eine weitere eigene Freigabe erforderlich. Der Zustands- und Rückkehrvergleich folgt erst nach diesen Messungen. Keine Modelle wurden trainiert; Worddatei, Modelle und historische Dateien bleiben unverändert.
'''
    with output.open('x',encoding='utf-8') as f:f.write(text)
    print(str(output))


if __name__=='__main__':main()
