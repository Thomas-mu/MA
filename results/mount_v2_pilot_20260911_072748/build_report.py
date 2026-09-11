"""Generate the separate new-mount report from completed, hashed pilot data."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
OUT = BASE / 'analysis'
ROOT = BASE.parents[1]


def main():
    report_path = OUT / 'report.json'
    report = json.loads(report_path.read_text())
    if report['status'] != 'complete_pilot_descriptive_analysis':
        raise ValueError('Closing reference required')
    for name in ('report.md', 'decision.json', 'operating_detail.png', 'operating_detail.pdf'):
        if (OUT / name).exists():
            raise FileExistsError(name)
    refs = [r for r in report['records'] if r['pwm_setpoint_percent'] == 0]
    op = next(r for r in report['records'] if r['pwm_setpoint_percent'] == 75)
    tail = report['operating_periods']['180_300']['five_second_rms_g']
    c, timing = report['comparisons'], report['timing']
    safety = json.loads((BASE/'safety_confirmation.json').read_text())
    observation = json.loads((BASE/'operating_observation.json').read_text())
    stop = json.loads((BASE/'after_standstill_confirmation.json').read_text())
    evidence_files = [report_path, BASE/'safety_confirmation.json', BASE/'operating_observation.json',
                      BASE/'before_standstill_confirmation.json', BASE/'after_standstill_confirmation.json',
                      BASE/'mounting_details.json', Path(__file__)]
    decision = dict(created_utc=datetime.now(timezone.utc).isoformat(), mounting_id=report['mounting_id'],
                    status='provisionally_suitable_for_further_normal_repeatability_pilots',
                    final_pwm_setpoint_percent=0, final_pwm_frequency_hz=25000,
                    full_mechanical_stop_user_confirmed=stop['fan_observed_fully_stopped'],
                    operating_observation=observation, safety_confirmation=safety,
                    future_normal_anomaly_comparison_pwm_percent=75,
                    recommended_next_experiment={'independent_starts':3, 'duration_each_s':300,
                      'record_from_command':True, 'identical_new_mounting':True,
                      'primary_comparison_window_s':[180,300], 'window_status':'prospective candidate for next test, not validated settling time',
                      'required_confirmations':'full standstill before each start and after shutdown; no reply deadlines or automatic retries'},
                    general_reproducibility_proven=False, training_authorized_by_this_analysis=False,
                    anomaly_recognition_proven=False, induced_anomalies=False, measured_rpm=None,
                    no_old_measurement_values_pooled=True,
                    source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence_files})
    with (OUT/'decision.json').open('x') as f:
        json.dump(decision,f,indent=2,ensure_ascii=False,allow_nan=False)
    lines = [
        '# Pilotversuch mit neuer vorläufiger Sensorbefestigung', '',
        'Durchgeführt am 11.09.2026 auf dem Raspberry Pi. Die neue Montage liefert in diesem einzelnen Betriebslauf eine deutliche Trennung vom Stillstand und geringe Schwankungen im späteren Verlauf. Sie ist vorläufig für weitere Normalversuche geeignet. Allgemeine Reproduzierbarkeit, eine verbindliche Einlaufzeit und Anomalieerkennung sind noch nicht nachgewiesen.', '',
        '## Aufbau und bestätigte Bedingungen', '',
        f'Aufbaukennung: `{report["mounting_id"]}`. Der ADXL345 ist nach Nutzerangabe mit zwei Schrauben am äußeren, feststehenden Lüfterrahmen befestigt; die Platine sitzt schräg. Ein Winkel oder eine Zuordnung der Sensorachsen zu Lüfterachsen wurde nicht vermessen. Befestigung und Unterlage des Lüfters sind nicht genauer beschrieben. Diese Angaben begrenzen die spätere Rekonstruktion des Aufbaus, ohne einen erneuten Umbau zu verlangen.', '',
        'Die vollständige Prüfung bei getrennter Stromversorgung wurde ausdrücklich bestätigt: Rotor frei, Kabel gesichert, keine erkennbaren Kurzschlüsse, Platine fest und nicht verbogen. Die externe 12-V-Versorgung war für die Referenzen und den Betrieb angeschlossen. Der vollständige Stillstand vor den ersten Referenzen sowie nach dem Betrieb wurde per Nutzerbeobachtung bestätigt. Der gleichmäßige Lauf nach dem Anlaufen und fehlende sichtbare Lockerung oder Berührung wurden nachträglich bestätigt. Das sind Nutzerbeobachtungen, keine Drehzahlmessungen.', '',
        'Die anfänglichen, mehrdeutigen Antworten und die damaligen offenen Prüfpunkte bleiben unverändert gespeichert. Die spätere eindeutige Bestätigung steht in `../safety_confirmation.json`; sie löst den früheren offenen Status aus `../mounting_details.json` auf. Die Rohdaten-Metadaten wurden nachträglich nicht umetikettiert. Die separate Laufbeobachtung steht in `../operating_observation.json`.', '',
        '## Durchführung und Sensorparameter', '',
        'BCM-GPIO18 entspricht physischem Pin 12. Verwendet wurde die vorhandene Hardware-PWM `pwmchip0/pwm2`, Pin-Funktion `a3/PWM0_CHAN2`, normale Polarität, 40.000 ns Periodendauer (25 kHz). 75 % entsprechen 30.000 ns Tastdauer, 0 % entsprechen 0 ns. Die Steuerung hielt den Betriebspunkt während der Aufnahme konstant und protokollierte Befehle, Rücklesungen und Zeitpunkte. Es gab einen Start und keine Ersatzstarts oder Antwortfristen. Sensor und Lüftersteuerung wurden exklusiv verwendet.', '',
        'Sensorerkennung mit der vorhandenen Software: ADXL345, Gerätekennung 0xE5, I²C-Bus 1, Adresse 0x53. In allen vier Aufnahmen identisch: nominell 200 Hz, ±2 g, Full Resolution, 0,0039 g/LSB, FIFO-Stream, konfigurierte I²C-Taktfrequenz 100 kHz. Registerrücklesung: BW_RATE 0x0B, DATA_FORMAT 0x08, INT_ENABLE 0x00, FIFO_CTL 0x90, POWER_CTL 0x08. Frühere Standby-Register wurden beim Schließen der Verbindung wiederhergestellt; sie sind kein früherer Messbetriebspunkt.', '',
        '| Aufnahme | Journalbeginn, MESZ | Dauer, Soll | XYZ-Punkte | Einzelne Achsenwerte | Beobachtet, XYZ/s |',
        '|---|---|---:|---:|---:|---:|',
    ]
    for r in report['records']:
        local=datetime.fromisoformat(r['started_utc']).astimezone(ZoneInfo('Europe/Berlin')).strftime('%H:%M:%S.%f')[:-3]
        q=r['quality']
        lines.append(f'| {r["name"]} | {local} | {r["requested_duration_s"]} s | {q["xyz_points"]:,} | {q["individual_axis_values"]:,} | {q["observed_rate_xyz_per_s"]:.5f} |')
    lines += ['', 'Die beiden Anfangsreferenzen sind durch eine Pause von fünf Sekunden getrennt. Die Schlussreferenz begann rund vier Minuten zehn Sekunden nach der Rückstellung auf 0 %, nach der erforderlichen Sichtbestätigung. Die Referenzen haben damit keine identische Wartezeit seit dem Ausschalten; ein schneller Nachlauf- oder Abkühlverlauf ist daraus nicht bestimmbar.', '',
              f'Der 75-%-Befehl wurde um 09:44:41,025 MESZ aufgerufen und um 09:44:41,070 abgeschlossen. Erster XYZ-Punkt: **{timing["first_xyz_after_command_completion_s"]*1000:.3f} ms nach Befehlsabschluss**, {timing["first_xyz_after_command_invocation_s"]*1000:.3f} ms nach Befehlsaufruf und {timing["first_xyz_after_duty_write_readback_s"]*1000:.3f} ms nach der Tastdauer-Rücklesung. Die Spanne vom ersten bis letzten XYZ-Punkt beträgt {timing["first_to_last_xyz_s"]:.6f} s. Der elektrische Signalbeginn und der mechanische Rotorstart wurden nicht gemessen.', '',
              'Die Rückstellung auf 0 % war um 09:49:41,402 MESZ abgeschlossen. Nach zehn Sekunden Auslaufzeit wurden 0 % zurückgelesen. Die spätere Sichtbestätigung erlaubte die Schlussreferenz. Nach deren Abschluss blieb die Vorgabe bei 0 %. Ein Tachosignal wurde nicht ausgewertet; tatsächliche Drehzahl und elektrische Signalform sind nicht belegt.', '']
    append_results(lines, report, refs, op, tail, c)
    with (OUT/'report.md').open('x',encoding='utf-8') as f:
        f.write('\n'.join(lines)+'\n')
    detail_plot(report, op)
    print(json.dumps({'report':str(OUT/'report.md'),'decision':str(OUT/'decision.json')}))


def append_results(lines, report, refs, op, tail, c):
    lines += ['## Datenqualität und Zeitbasis', '',
        'Alle CSV-Hashes stimmen mit den Metadaten überein. Die Zeitstempel sind streng monoton, die gespeicherten Indizes fortlaufend und die XYZ-Werte endlich. Alle Lücken-, Überlauf- und Sättigungsflags sind null. Kein Wert wurde entfernt oder interpoliert. Fortlaufende Softwareindizes und ungesetzte Flags beweisen keine exakt verlustfreie interne Sensorabtastung; die genaue Zahl verlorener Sensorwerte bleibt unbekannt.', '',
        '| Aufnahme | Host-Abstand Median / P99 / Maximum [ms] | Abstände > 10 ms | FIFO-Maximum | maximale absolute Achse [g] |',
        '|---|---:|---:|---:|---:|']
    for r in report['records']:
        q=r['quality']
        lines.append(f'| {r["name"]} | {q["host_interval_median_ms"]:.3f} / {q["host_interval_p99_ms"]:.3f} / {q["host_interval_max_ms"]:.3f} | {q["host_intervals_over_10ms"]} | {q["fifo_depth_max"]} | {q["maximum_absolute_axis_g"]:.4f} |')
    lines += ['', 'Nur in S_vor_1 gab es drei Host-Abstände über 10 ms: 13,296, 12,317 und 12,336 ms, etwa 22,44–22,51 s nach dem ersten Punkt. Der FIFO erreichte höchstens zwei Einträge. Die Software setzt das Lückenflag bei Überlaufverdacht oder bei einem Host-Abstand über 32/200 s = 160 ms. Ein Abstand über 10 ms allein setzt deshalb kein Lückenflag. Die aufgezeichnete Dauer des erfolgreichen Registerlesevorgangs lag im Median bei etwa 1,74 ms; alle Quantile und Maxima stehen in `recording_summary.csv`.', '',
        'Der beobachtete Durchsatz wird als (N−1)/(letzter−erster Hostzeitpunkt) berechnet. Er beträgt 206,976–207,045 XYZ/s und liegt etwa 3,49–3,52 % über der konfigurierten ODR. 200 × 30 ergäbe nominell 6.000 XYZ-Punkte; tatsächlich wurden 6.208 beziehungsweise 6.209 vollständige XYZ-Tupel erfasst. Dies ist keine Verwechslung mit einzelnen Achsenwerten. Die Hostzeiten markieren Leseabschlüsse. Die Spalte `sensor_time_estimate_s = sample_index/200` ist nur eine nominelle Konstruktion und keine zweite unabhängige Zeitmessung. Die Abweichung lässt sich hiermit beschreiben, aber nicht eindeutig auf einen Hardwaretakt oder eine andere Ursache zurückführen. Sie bleibt vor der Festlegung frequenzbezogener Messparameter zu klären.', '',
        '## Vektor-AC-RMS und Referenzvergleich', '',
        'Verwendet wird sqrt(mean((X−MittelX)²+(Y−MittelY)²+(Z−MittelZ)²)). In jedem der 60 Betriebsabschnitte und sechs Abschnitte je Stillstandsaufnahme werden die jeweiligen drei Achsenmittelwerte neu entfernt. Die Abschnitte dauern nominell jeweils fünf Sekunden ab dem ersten XYZ-Punkt; sie enthalten 1.033–1.036 Punkte. Die Randpunkte liegen diskret innerhalb dieser Zeitintervalle. Achsenstreuungen sind Populationsstandardabweichungen (ddof=0). 1 mg bezeichnet hier 0,001 g Beschleunigung.', '',
        '| Aufnahme | Mittel X / Y / Z [g] | Streuung X / Y / Z [mg] | Vektor-AC-RMS der Gesamtaufnahme [mg] |',
        '|---|---:|---:|---:|']
    for r in report['records']:
        s=r['statistics']
        means=' / '.join(f'{s[f"mean_{a}_g"]:.5f}' for a in ('x','y','z'))
        stds=' / '.join(f'{1000*s[f"std_{a}_g"]:.3f}' for a in ('x','y','z'))
        lines.append(f'| {r["name"]} | {means} | {stds} | {s["vector_ac_rms_g"]*1000:.3f} |')
    lines += ['',
        f'Die beiden Anfangsreferenzen unterscheiden sich um {c["before_absolute_repeat_difference_g"]*1000:.3f} mg ({c["before_repeat_difference_percent_of_mean"]:.2f} % ihres Mittels). Die Schlussreferenz liegt {abs(c["after_minus_before_mean_g"])*1000:.3f} mg beziehungsweise {abs(c["after_change_percent"]):.2f} % unter dem Anfangsmittel und innerhalb der beiden Anfangswerte. Die 5-s-Werte aller Stillstandsreferenzen reichen von {c["standstill_five_second_rms_g"]["minimum"]*1000:.3f} bis {c["standstill_five_second_rms_g"]["maximum"]*1000:.3f} mg und überlappen. Eine einzelne Schlussreferenz erlaubt keine Bestimmung der Wiederholungsstreuung am Ende.', '',
        'Die Änderung der Achsenmittelwerte nach dem Betrieb gegenüber dem Anfangsmittel beträgt X −0,278 mg, Y −0,285 mg und Z +0,095 mg. Daraus ergibt sich kein auffälliger dauerhafter Lagewechsel in diesen Referenzen; kleine Bewegungen sind damit nicht ausgeschlossen. Die absoluten Gleichanteile sind unkalibrierte Sensorwerte in der schrägen Montage und kein Nachweis einer korrekten Beschleunigungskalibrierung.', '',
        '## Verlauf während des einzigen Starts', '',
        'Der erste 5-s-Abschnitt liegt bei 20,734 mg, der folgende bei 204,615 mg. Anschließend sinkt das Niveau in Richtung 196 mg. Die 5-s-Zusammenfassung erlaubt keine genaue Bestimmung des mechanischen Startzeitpunkts.', '',
        '| Minute | Mittel der zwölf 5-s-RMS-Werte [mg] | Minimum–Maximum [mg] | Streuung der Abschnittswerte [mg] |',
        '|---|---:|---:|---:|']
    for minute in report['operating_minutes']:
        d=minute['vector_ac_rms_g']
        lines.append(f'| {minute["minute"]} | {d["mean"]*1000:.3f} | {d["minimum"]*1000:.3f}–{d["maximum"]*1000:.3f} | {d["population_std"]*1000:.3f} |')
    lines += ['',
        f'Von Minute 2 zu Minute 5 fällt der Abschnittsmittelwert um 0,82 %. Die letzten 120 s liegen bei {tail["mean"]*1000:.3f} mg; die Standardabweichung der 24 Abschnittswerte beträgt {tail["population_std"]*1000:.3f} mg (CV {tail["descriptive_cv_percent"]:.3f} %), der Bereich {tail["minimum"]*1000:.3f}–{tail["maximum"]*1000:.3f} mg. Das spricht für eine Beruhigung in diesem Lauf, beweist aber weder vollständige Stationarität noch eine allgemein gültige Einlaufzeit. Die Abschnitte sind zeitlich benachbart und keine unabhängigen Wiederholungen.', '',
        'Das Mittel der letzten 120 s beträgt etwa das 14,5-Fache des Mittels der beiden 30-s-Anfangsreferenzen. Selbst der kleinste 5-s-Wert in den letzten 120 s liegt etwa 11,6-mal über dem größten Stillstandsabschnitt. Der Abstand zum Stillstand ist somit erheblich größer als die hier beobachteten Stillstands- und späteren Betriebsschwankungen. Diese rein deskriptive Trennung ist kein Nachweis einer Anomalieerkennung bei gleicher PWM.', '',
        '![RMS-Verlauf und neue Stillstandsreferenzen](pilot_rms.png)', '',
        '![Detail des Betriebsverlaufs ab fünf Sekunden](operating_detail.png)', '',
        '## Konkreter nächster Schritt', '',
        'Drei weitere, unabhängige Normalstarts bei 75 % und unveränderter neuer Montage untersuchen, jeweils mit durchgehenden 300 s ab Stellbefehl. Vor jedem Start vollständigen Stillstand bestätigen, anschließend wieder 0 % einstellen. Keine Antwortfristen oder automatischen Ersatzstarts. Für diesen nächsten Versuch den Bereich 180–300 s vorab als primären Vergleichsabschnitt festlegen und zugleich den gesamten Einlaufverlauf aufzeichnen. Die 180 s sind ein zu prüfender Kandidat auf Grundlage dieses Piloten, keine bereits validierte Einlaufzeit.', '',
        'Zwischen den Starts sowohl Abschnittsniveaus als auch Verläufe, Achsenmittelwerte und Qualitätsbefunde vergleichen. Erst danach Messparameter und Toleranzen begründet festlegen. Die Abweichung der Zeitbasis bleibt separat zu prüfen, bei Bedarf mit unabhängiger Erfassung des Datenbereitschaftssignals; hierfür wurde jetzt keine Verkabelung geändert. Spätere normale und anomale Messungen müssen denselben gewählten PWM-Betriebspunkt verwenden. Eine höhere Schwingungsamplitude allein rechtfertigt keine Modellfreigabe.', '',
        '## Dateien und Erhalt bestehender Arbeit', '',
        'Rohaufnahmen und Metadaten liegen ausschließlich im neuen Verzeichnis `../../../data/mount_v2_pilot_20260911_072748/`. Jede CSV besitzt eine eigene JSON-Datei mit Zeit, Messdauer, Aufbaukennung, PWM-Vorgabe, Sensorkonfiguration und Qualitätszusammenfassung. Alle vier Rohdatenpaare sind über SHA-256 abgesichert. `report.json`, `recording_summary.csv` und `five_second_sections.csv` enthalten die maschinenlesbaren Ergebnisse. Die Grafiken liegen zusätzlich als PDF vor. `decision.json` trennt die Pilotbewertung von offenen Nachweisen.', '',
        'Die vorläufige Auswertung vor Eingang der Schlussreferenz bleibt unter `../analysis_before_closing_reference/` erhalten; dieser Bericht verwendet die vollständige Folge. Lüfterbefehle und Rücklesungen stehen in `../fan.jsonl`, die beiden Stillstandsphasen in `../before_fan.jsonl` und `../after_fan.jsonl`. Die abschließende Prüfung des Dateierhalts und der Steuerung wird separat in `../final_verification.json` festgehalten.', '',
        'Es wurden keine alten Messwerte als Referenz verwendet, keine Modelle trainiert, keine Anomalien erzeugt und keine historischen Protokolle oder Worddateien bearbeitet.']


def detail_plot(report, op):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    offset=report['timing']['first_xyz_after_command_completion_s']
    blocks=[b for b in op['five_second_sections'] if b['start_s']>=5]
    fig,ax=plt.subplots(figsize=(10.5,4.6),layout='constrained')
    ax.plot([b['start_s']+2.5+offset for b in blocks], [1000*b['vector_ac_rms_g'] for b in blocks],
            'o-',markersize=3,label='Vektor-AC-RMS je 5 s')
    for minute in report['operating_minutes'][1:]:
        ax.hlines(1000*minute['vector_ac_rms_g']['mean'],(minute['minute']-1)*60+offset,
                  minute['minute']*60+offset,color='C1',lw=2,label='Minutenmittel' if minute['minute']==2 else None)
    ax.axvspan(180+offset,300+offset,color='C2',alpha=.1,label='Kandidat für nächsten Vergleich: 180–300 s')
    ax.set(xlim=(5,301),xlabel='Zeit seit Abschluss des 75-%-PWM-Stellbefehls [s]',ylabel='Vektor-AC-RMS [mg]',
           title='Detail ab 5 s: langsamer Rückgang und spätere Schwankungen\nErster Anlaufabschnitt in der Gesamtgrafik; kein Reproduzierbarkeitsnachweis')
    ax.grid(alpha=.25)
    ax.legend(loc='best')
    fig.savefig(OUT/'operating_detail.png',dpi=180)
    fig.savefig(OUT/'operating_detail.pdf')
    plt.close(fig)


if __name__=='__main__':
    main()
