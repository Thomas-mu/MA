from pathlib import Path
import json,hashlib
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
base=Path(Path('/tmp/edge_ai_adapter_result_path').read_text())
r=base/'paced_replay_all_methods'
report=json.loads((r/'replay_report.json').read_text())
rows=[json.loads(line) for line in (r/'decisions.jsonl').read_text().splitlines()]
old=json.loads(Path('results/upright_v4_frozen_airflow_test_20260912_073015/normal_before_evaluation/scores.json').read_text()) if Path('results/upright_v4_frozen_airflow_test_20260912_073015/normal_before_evaluation/scores.json').exists() else None
# Locate the archived individual evaluator score artifact by recording identity.
if old is None:
    for p in Path('results/upright_v4_frozen_airflow_test_20260912_073015').rglob('scores.json'):
        candidate=json.loads(p.read_text())
        if candidate and len(candidate)==582 and candidate[0].get('phase')=='normal_before':
            old=candidate;break
assert old is not None,'Archived exact comparison unavailable'
lookup={(x['window_index_in_recording'],x['method']):x for x in old}
exact=all(x['score']==lookup[(x['window_index_in_recording'],x['method'])]['score'] and x['decision']==lookup[(x['window_index_in_recording'],x['method'])]['decision'] for x in rows)
assert exact and len(rows)==582
resources=pd.read_csv(r/'resources.csv')
fig,axes=plt.subplots(5,1,figsize=(11,12))
for ax,method in zip(axes[:3],report['per_method']):
    m=[x for x in rows if x['method']==method]
    ax.plot([(x['start_since_command_s']+x['last_since_command_s'])/2 for x in m],[x['score'] for x in m],linewidth=1)
    ax.axhline(m[0]['threshold'],color='black',linestyle='--',label='eingefrorene Schwelle')
    ax.set_ylabel(method+'\nScore');ax.set_xlabel('Quellzeit seit PWM-Stellbefehl (s)');ax.legend(fontsize=8);ax.grid(alpha=.2)
elapsed=(resources.monotonic_ns-resources.monotonic_ns.iloc[0])/1e9
axes[3].plot(elapsed,resources.process_cpu_percent_one_core);axes[3].set_ylabel('CPU (%)\n100 % = ein Kern')
axes[4].plot(elapsed,resources.process_rss_bytes/2**20);axes[4].set_ylabel('RSS (MiB)')
for a in axes[3:]:a.set_xlabel('Replayzeit ab erster Ressourcenstichprobe (s)');a.grid(alpha=.2)
fig.suptitle('Offline-Replay vorhandener v4-Daten – keine neue Sensoraufnahme\nDrei Methoden gemeinsam; teilweise parallele Softwaretests, kein isolierter Ressourcenbenchmark')
fig.tight_layout()
for ext in ('png','pdf'):fig.savefig(base/('replay_verification.'+ext),dpi=140)
plt.close(fig)
lines=['# Softwarefortschritt: 50-%-Normaltest und eingefrorener Live-Datenweg','',
'Es wurden keine neuen Hardwaremessungen ausgeführt und keine PWM-Einstellungen verändert. Modelle, Scaler, Schwellen, Worddatei und historische Quellen bleiben unverändert. Die spätere ausdrückliche Nutzerfreigabe für automatische Starts/Stopps ist dokumentiert; die aktuelle Anfangsbereitschaft ohne Platte ist noch offen.','',
'## Umgesetzt und geprüft','',
'- Separater 50-%-Aufnahme-/Importadapter mit vollständigem Protokoll, 20000 ns Tastzeit bei 40000 ns Periode, NORMAL-Label und unverändertem Modellpaket.',
'- Drei vorab autorisierte Starts möglich. Initiale Bereitschaft bleibt erforderlich; später jeweils geprüfte Software-Nullstellung und mindestens 60 s zusätzliche Auszeit. Kein behaupteter mechanischer Stillstand und keine automatischen Ersatzstarts.',
'- Neue Streaming-Fensterbildung beginnt beim ersten XYZ-Punkt in [180,300), umfasst 128 Punkte ohne Überlappung und speichert den gesamten Rohverlauf. Der eingefrorene Fenster-/Qualitätskern bleibt unverändert.',
'- Pro Fenster Float64 in ursprünglicher Achsenreihenfolge und F-Speicherordnung, achsenweise Zentrierung, danach Float32 und gespeicherter Scaler. Alle Methoden erhalten Kopien desselben standardisierten Fensters.',
'- Begrenzte Entscheidungsqueue mit expliziten Verwerfungsereignissen, Fehlermeldungen und Rohdatensicherung; Ressourcenstichproben alle 100 ms. INVALID ist keine Normalentscheidung.',
'- Sensor-Reader und injizierbarer Live-Recorder sind angebunden; der vorhandene Capture-Lebenszyklus muss den PWM-Befehl und die abschließende Nullstellung weiterhin besitzen. Die bisherige GUI und Legacy-Live-CLI wurden nicht stillschweigend umgestellt.','',
'**Softwaretests: 130 bestanden.** Darunter exakte Eingangs-/Scoregleichheit auf 194 echten archivierten Fenstern, Grenzen bei 180/300 s, Qualitätsfehler einschließlich fensterübergreifender Host-Lücke, langsamer Auswerter, teilweise Rohdatensicherung bei Leserfehler und unterbundener Folgestart bei Fehler. Die zahlreichen Joblib-/NumPy-Hinweise sind DeprecationWarnings beim Laden des vorhandenen Pakets; keine Testfehler.','',
'## Tatsächlich ausgeführte Offline-Prüfung','',
'Eine vorhandene vollständige 300-s-Normalaufnahme wurde mit ihren ursprünglichen Host-Zeitabständen abgespielt. Das ist weder eine unabhängige neue Testaufnahme noch Sensor-Livebetrieb. Ressourcen werden dem einen Prozess mit allen drei Methoden zugerechnet. Zeitweise liefen zusätzlich Softwaretests: Die Zahlen sind ein Entwicklungs-/Belastungscheck, kein kontrollierter isolierter Methodenbenchmark.','',
'Alle **582 Scores und Entscheidungen (194 Fenster × 3)** entsprechen exakt den archivierten Ergebnissen. Keine neue Parameterauswahl.','',
'| Methode | Gültig | Ungültig | Alarme auf vorhandenen Normaldaten | P99 komplett→Entscheidung (ms) |',
'|---|---:|---:|---:|---:|']
for m,s in report['per_method'].items():lines.append(f"| {m} | {s['valid_windows']} | {s['invalid_windows']} | {s['false_alarms']} | {s['complete_to_decision_ms']['p99']:.3f} |")
lines += ['',f"Verworfene Entscheidungsfenster: **{report['windows_dropped']}**. Unvollständiger Rest im ausgewählten Abschnitt: {report['trailing_selected_xyz']} XYZ-Punkte. Alle {report['raw_xyz']} Rohpunkte gespeichert. Nominelle 200 Hz und beobachtete {report['source_quality']['observed_xyz_per_second']:.6f} XYZ/s bleiben getrennt. Die genaue physische Verlustzahl bleibt unbekannt.",'',
'![Replayprüfung](replay_verification.png)','',
'Komplett→Entscheidung umfasst die neue Fensteraufbereitung, Queue und Methodenausführung ab dem zugeordneten Replay-Ankunftszeitpunkt. Die Dauer des Scorer-Aufrufs enthält bei TFLite Tensortransfers, invoke und MSE; sie ist **keine isolierte invoke-Latenz**. Inferenzreihenfolge im gemeinsamen Prozess beeinflusst die späteren Methoden. Die Ressourcenstichproben erfassen keinen garantierten kurzfristigen RSS-Höchstwert; Prozess-Lebenszeitspitzen werden zusätzlich gespeichert. Kalter Modellstart und CPU-Last je isolierter Methode sind noch gesondert zu messen.','',
'## Steuerungsstatus und weitere Durchführung','',
'Die rein lesende Kontrolle um 09:09:05 UTC (11:09:05 Ortszeit) bestätigte GPIO18/physisch 12 in a3/PWM0_CHAN2, Periode 40000 ns, Tastzeit 0 ns, enable=1, normale Polarität. fuser meldete keine Belegung der geprüften Sensor-/GPIO-Geräte. Es gab keinen Stellbefehl. Mechanischer Stillstand wurde in diesem Arbeitsabschnitt nicht beobachtet.','',
'Das neue eingefrorene Protokoll liegt in [upright_v4_second_pwm50_20260912_091000](../upright_v4_second_pwm50_20260912_091000/protocol.md). Es verlangt zunächst die aktuelle Bestätigung: Platte entfernt, Aufbau v4 unverändert, Lüfter still, 12-V-Versorgung angeschlossen. Es wurde keine entsprechende Anfangsfreigabe erfunden und keine Aufnahme gestartet. Danach kann die genehmigte Dreierfolge ohne weitere Laufbeobachtungsfragen ablaufen.','',
'## Noch fehlende Nachweise, in Reihenfolge','',
'1. Drei neue NORMAL-Aufnahmen bei 50 %: 15 min Aufnahme plus mindestens 3 × 60 s zusätzliche Auszeit. Vorab festgelegter Vergleich mit allen sechs früheren unabhängigen 75-%-Normalläufen; keine nachträgliche Schwellenänderung.',
'2. Prospektives Sensor-Live-Protokoll mit dem neuen Recorder, Methodenauswahl vor Start und vollständiger Erfassung der Verarbeitungszeiten, Rohdaten-/Pufferverluste und ungültigen/fehlenden Entscheidungen. Für getrennte Ressourcenvergleiche je Methode frischer Prozess; drei Wiederholungen je Methode ergeben 45 min Aufnahme plus Auszeiten. Der gemeinsame Replay-Prozess ersetzt diese Messungen nicht.',
'3. Isolierte TFLite-invoke-Zeit und kalter Modellstart getrennt instrumentieren und per Score-Parität prüfen. Die vorhandenen Scorer-Dauern bereits ehrlich als Gesamtaufruf verwenden.',
'4. Falls die GUI Teil des Nachweises bleibt: dieselbe neue Vorverarbeitung auch dort explizit anbinden, dann Zusatzlast gegenüber Sensor-Livebetrieb ohne GUI messen. Das alte GUI-Profil bleibt für das v4-Pilotpaket ungeeignet.',
'5. Abschlussbewertung und spätere Word-Übernahme erst auf Basis der tatsächlich vorliegenden Nachweise. Keine neue Modellversion und keine künstlichen Anomalien in diesem Auftrag.','',
'Für den nächsten kleinsten Versuch genügt der erste vorab geplante 50-%-Normallauf (300 s + 60 s zusätzliche Auszeit). Bei der freigegebenen automatischen Dreierfolge ist zwischen den Läufen kein manueller Umbau nötig. Die Anfangsbedingungen müssen einmal aktuell bestätigt werden.','',
'Verbleibender Softwareaufwand geschätzt: 2–4 h für kontrollierte Sensor-Live-/Ressourcenprotokolle, isolierte invoke-/Kaltstartinstrumentierung und Auswertung; optional weitere 2–4 h für GUI-Anbindung und Vergleich. Diese Schätzung ersetzt keine gemessene Bearbeitungsdauer.']
(base/'implementation_report.md').write_text('\n'.join(lines)+'\n')
previous=json.loads((base/'preservation.json').read_text())
changed=[p for p,h in previous.items() if not Path(p).exists() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
assert not changed,changed
verification={'protected_files':len(previous),'changed_protected_files':changed,'tests_passed':130,
 'exact_stream_windows':194,'exact_replay_scores_and_decisions':len(rows),'new_hardware_captures':0,
 'PWM_writes':0,'current_initial_readiness_received':False,
 'protocol_path':'results/upright_v4_second_pwm50_20260912_091000/protocol.json',
 'new_sources_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('src').glob('*.py') if str(p) not in previous}}
(base/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
print(json.dumps(verification,indent=2))
