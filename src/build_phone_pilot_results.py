"""Create a separate, evidence-labelled result deck; preserve preparation and raw data.

Requires python-pptx, matplotlib, Chromium and pdftoppm. Never accesses hardware.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from build_phone_presentation import Deck, METHODS, NAVY, MUTED, TEAL, AMBER, fmt, sha256, export_pdf_and_previews
from replay_phone_pilot import RUNS, phase_of, read_rows


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def freeze(source, output):
    originals = [source/'plan.json', source/'protocol.md']
    for directory in ('bundle', 'trials', 'replay_v1'):
        originals.extend(p for p in (source/directory).rglob('*') if p.is_file())
    entries = []
    for original in sorted(originals):
        target = output/'sources'/original.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
        if sha256(original) != sha256(target):
            raise ValueError('Source changed during snapshot.')
        entries.append(dict(original=str(original), snapshot=str(target.relative_to(output)), sha256=sha256(target)))
    for name in ('build_phone_pilot_results.py', 'build_phone_presentation.py', 'replay_phone_pilot.py', 'snapshot_phone_report.py'):
        original = Path(__file__).parent/name
        target = output/'sources'/name
        shutil.copy2(original, target)
        entries.append(dict(original=str(original), snapshot=str(target.relative_to(output)), sha256=sha256(target)))
    write_json(output/'source_manifest.json', dict(created_utc=datetime.now(timezone.utc).isoformat(),
        scope='three_selected_live_pilots_and_offline_replay; all_restarted_attempts_preserved', sources=entries))


def load_evidence(source):
    plan = json.loads((source/'plan.json').read_text())
    replay = json.loads((source/'replay_v1/summary.json').read_text())
    records = {}
    for (key, label, color, method), run_name in zip(METHODS, RUNS):
        path = source/'trials'/run_name
        meta = json.loads((path/'run.json').read_text())
        summary = json.loads((path/'summary.json').read_text())
        review = json.loads((path/'trial_review.json').read_text())
        if meta['method'] != method or not review['include_in_descriptive_call_comparison']:
            raise ValueError('Unapproved source or method mismatch.')
        rows = read_rows(path/'decisions.csv')
        if len(rows) != summary['windows']:
            raise ValueError('Summary count mismatch.')
        cues = [json.loads(line) for line in (path/'cues.jsonl').read_text().splitlines()]
        starts = [c['monotonic_ns'] for c in cues if c['event']=='call_requested']
        ends = [c['monotonic_ns'] for c in cues if c['event']=='end_reported']
        if len(starts) != 1 or len(ends) != 1:
            raise ValueError('Expected exactly one call cue pair.')
        phases = {}
        for phase in ('pre_cue', 'between_cues', 'post_cue', 'straddling'):
            selected = [r for r in rows if phase_of(r, starts[0], ends[0])==phase]
            phases[phase] = dict(windows=len(selected), alarm_windows=sum(r['prediction']=='1' for r in selected))
        if sum(p['alarm_windows'] for p in phases.values()) != summary['alarm_windows']:
            raise ValueError('Phase alarm count mismatch.')
        stats = dict(summary, phases=phases,
            median_process_cpu_percent_one_core=statistics.median(float(r['process_cpu_percent_one_core']) for r in rows),
            cpu_frequency_khz_range=[min(float(r['cpu_frequency_khz']) for r in rows), max(float(r['cpu_frequency_khz']) for r in rows)],
            temperature_c_range=[min(float(r['temperature_c']) for r in rows), max(float(r['temperature_c']) for r in rows)],
            complete_span_s=(int(rows[-1]['window_complete_ns'])-int(rows[0]['window_start_ns']))/1e9,
            cue_start_s=(starts[0]-meta['start_monotonic_ns'])/1e9,
            cue_end_s=(ends[0]-meta['start_monotonic_ns'])/1e9,
            source_run=run_name)
        records[key] = dict(meta=meta, summary=stats, rows=rows, path=path, label=label, color=color, method=method)
    return plan, records, replay


def charts(output, records, replay):
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':11,
        'axes.spines.top':False, 'axes.spines.right':False, 'text.color':'#'+NAVY,
        'axes.labelcolor':'#'+NAVY, 'xtick.color':'#'+MUTED, 'ytick.color':'#'+MUTED})
    assets = output/'assets'; assets.mkdir()
    result = {}
    def save(fig, name):
        for ext in ('png', 'pdf'):
            fig.savefig(assets/f'{name}.{ext}', dpi=180, facecolor='white', bbox_inches='tight')
        plt.close(fig); result[name] = assets/f'{name}.png'

    fig, axes = plt.subplots(3, 1, figsize=(12, 5.1))
    for ax, (key, label, color, _) in zip(axes, METHODS):
        record=records[key]; rows=record['rows']; stats=record['summary']
        x=[float(r['elapsed_s']) for r in rows]
        ax.plot(x, [float(r['score'])/float(r['threshold']) for r in rows], color=color, lw=1.5)
        ax.axhline(1, color='#AB5E06', linestyle='--', lw=1.2)
        ax.axvspan(stats['cue_start_s'], stats['cue_end_s'], color='#CBD9E4', alpha=.3)
        ax.axvline(stats['cue_start_s'], color='#587084', linestyle=':', lw=1)
        ax.axvline(stats['cue_end_s'], color='#587084', linestyle=':', lw=1)
        ax.set_ylabel(label+'\nScore / Schwelle', fontsize=10)
        ax.set_ylim(bottom=0); ax.grid(alpha=.15)
    axes[-1].set_xlabel('Zeit seit Start der jeweiligen Aufnahme [s]; getrennte Anrufe')
    fig.tight_layout(h_pad=.45); save(fig, 'live_scores')

    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.4))
    for ax, name, short in zip(axes, RUNS, ('Aufnahme A (AE live)', 'Aufnahme B (IF live)', 'Aufnahme C (RMS live)')):
        entry=replay['recordings'][name]; methods=entry['methods']
        if not entry['ranking_has_no_precue_alarms']:
            raise ValueError('Narrative requires no precue alarms on the selected replay sources.')
        first=min(v['first_alarm_window_between_cues'] for v in methods.values())
        for i, (_, label, color, method) in enumerate(METHODS):
            v=methods[method]; offset=v['first_alarm_window_between_cues']-first
            ax.hlines(i, -.2, offset, color=color, alpha=.3, lw=4)
            ax.scatter(offset, i, s=330, color=color, zorder=3)
            ax.text(offset, i, str(v['first_alarm_window_rank']), color='white', ha='center', va='center', weight='bold', fontsize=13)
            ax.text(offset+.15, i, 'Fenster '+str(v['first_alarm_window_between_cues']), va='center', fontsize=9)
        ax.set(title=short, xlim=(-.3, 2.35), ylim=(2.6,-.6), yticks=[0,1,2],
               yticklabels=['AE','IF','RMS'], xticks=[0,1,2], xlabel='Fenster nach frühestem Alarm')
        ax.grid(alpha=.15, axis='x')
    fig.tight_layout(w_pad=1.6); save(fig, 'first_alarm_ranks')

    fig, axes = plt.subplots(1, 2, figsize=(12, 3.4), gridspec_kw={'width_ratios':[1,1.25]})
    counts=[records[k]['summary']['alarm_windows'] for k, *_ in METHODS]
    bars=axes[0].bar([m[1] for m in METHODS], counts, color=[m[2] for m in METHODS], width=.55)
    axes[0].bar_label(bars, padding=4); axes[0].set(title='Getrennte Live-Aufnahmen', ylabel='Alarmfenster', ylim=(0,max(counts)+3))
    matrix=np.array([[replay['recordings'][name]['methods'][method]['alarm_windows_total'] for _,_,_,method in METHODS] for name in RUNS])
    axes[1].imshow(matrix, cmap='Blues', vmin=0, vmax=max(14,int(matrix.max())), aspect='auto')
    axes[1].set(xticks=range(3), xticklabels=['AE','IF','RMS'], yticks=range(3),
               yticklabels=['Aufnahme A','Aufnahme B','Aufnahme C'], title='Replay: alle Methoden auf jeder Aufnahme')
    for i in range(3):
        for j in range(3): axes[1].text(j,i,str(matrix[i,j]),ha='center',va='center',fontsize=20,color='white' if matrix[i,j]>8 else '#'+NAVY)
    fig.tight_layout(w_pad=3); save(fig, 'alarm_counts')

    fig, ax=plt.subplots(figsize=(11.7,3.3))
    positions=np.arange(3); med=[records[k]['summary']['processing_median_ms'] for k,*_ in METHODS]
    p95=[records[k]['summary']['processing_p95_ms'] for k,*_ in METHODS]
    for i, (_, label, color, _) in enumerate(METHODS):
        ax.plot([med[i],p95[i]],[i,i],color=color,lw=3)
        ax.scatter(med[i],i,color=color,s=90,label='Median' if i==0 else None)
        ax.scatter(p95[i],i,color=color,s=90,marker='D',label='P95' if i==0 else None)
        ax.text(p95[i]*1.12,i,fmt(med[i],3)+' / '+fmt(p95[i],3)+' ms',va='center',fontsize=11)
    ax.set(xscale='log',xlim=(.15,100),ylim=(2.6,-.6),yticks=positions,yticklabels=[m[1] for m in METHODS],
           xlabel='Standardisierung + Score + Entscheidung [ms]; logarithmische Achse')
    ax.grid(alpha=.2,axis='x',which='both'); ax.legend(loc='lower right');fig.tight_layout();save(fig,'processing')

    fig,axes=plt.subplots(1,2,figsize=(12,3.5))
    for ax,field,title,ylab in [(axes[0],'median_process_cpu_percent_one_core','Median der Prozess-CPU','% eines Kerns'),
                              (axes[1],'sampled_peak_rss_mib','Maximal abgetastete Prozess-RSS','MiB')]:
        values=[records[k]['summary'][field] for k,*_ in METHODS]
        bars=ax.bar([m[1] for m in METHODS],values,color=[m[2] for m in METHODS],width=.55)
        ax.bar_label(bars,labels=[fmt(v,1) for v in values],padding=4)
        ax.set(title=title,ylabel=ylab,ylim=(0,max(values)*1.25));ax.grid(alpha=.15,axis='y')
    fig.tight_layout(w_pad=3);save(fig,'resources')
    return result


class ResultDeck(Deck):
    def slide(self, eyebrow, title, subtitle, notes):
        slide=super().slide(eyebrow,title,subtitle,notes)
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text.startswith('VORBEREITUNGSSTAND'):
                shape.text_frame.paragraphs[0].runs[0].text='PILOTERGEBNISSE · 19.09.2026 · Einzelanrufe + Offline-Replay · keine physische Latenzreferenz'
        return slide


def deck(output, records, replay, plan, assets):
    d=ResultDeck(); d.prs.core_properties.title='Handyvibration: Pilotergebnisse und fairer Fenstervergleich'
    d.prs.core_properties.subject='Drei Live-Einzelaufnahmen, identische Rohdaten im Replay, Ressourcen und Grenzen'
    total=sum(r['summary']['windows'] for r in records.values())
    s=d.slide('Ergebnisüberblick','Drei Methoden erkennen die eingebrachte Störung',
        'Explorativer Handyvibrations-Pilot auf dem Raspberry Pi 5 – keine allgemeine Güte- oder Defektdiagnose.',
        'Alle drei ausgewählten Live-Aufnahmen enthalten Alarmfenster zwischen Anruf-Freigabe und Ende-Rückmeldung; '
        'vollständig davor und danach liegen keine Alarmfenster. Physischer Vibrationsbeginn ist nicht gemessen. '
        'Im Offline-Replay identischer Daten: zweimal Gleichstand auf Fensterauflösung, einmal Autoencoder ein Fenster früher. '
        'Nur drei Einzelereignisse, keine statistische Rangfolge. Externe Tischvibration ist kein belegter Lüfterdefekt. '
        'Quellen: sources/trials/*/{run.json,decisions.csv,cues.jsonl}, replay_v1/summary.json.')
    d.box(s,.55,2.45,7.4,3.95)
    d.text(s,.85,2.8,6.8,1.15,'Zweimal Gleichstand.\nEinmal AE ein Fenster früher.',26,NAVY,True)
    d.text(s,.85,4.35,6.7,1.7,'Vergleich auf identischen Rohdaten\nRMS: kürzeste beobachtete Berechnung\nIF: höhere beobachtete Prozesslast',20)
    for i,(big,small) in enumerate([('3','ausgewählte Anrufversuche'),(str(total),'gültige Live-Fenster'),('75 %','PWM, keine Drehzahlmessung')]):
        y=2.45+i*1.32;d.box(s,8.25,y,4.5,1.12,'E6F2F1')
        d.text(s,8.5,y+.14,1.5,.57,big,27,TEAL,True);d.text(s,10.05,y+.15,2.4,.7,small,15)

    s=d.slide('Messprinzip und Kalibrierung','Gemeinsame Messkette, eingefrorene Schwellen',
        'Sensor → 128 × 3 Werte → Trainingsskalierung → eine Methode → Score > Schwelle ergibt Alarm.',
        'ADXL345, nominal 200 Hz; Fenstergröße und Schrittweite 128, nominal 0,64 s. Zeitstempel sind Host-Lesezeitstempel. '
        'Pro Lauf nur eine Methode, ohne Live-GUI, mit 20 Aufwärmfenstern und derselben Erfassungsversion. '
        'AE: Rekonstruktions-MSE; IF: negatives score_samples; RMS: quadratischer Mittelwert nach Standardisierung. '
        'Schwellen: P99 der normalen Validierung (97 Fenster); AE übernimmt die eingefrorene Keras-Kalibrierung. '
        'Validierung wurde beim AE auch für Early Stopping verwendet. Schwellen wurden nicht auf den Anrufen angepasst. '
        'Endgültiger Handyaufbau und Übertragbarkeit der Kalibrierung bleiben unbestätigt. Quellen: plan.json, bundle/bundle.json.')
    for i,((key,label,color,method),definition) in enumerate(zip(METHODS,['Rekonstruktionsfehler\nMSE über 384 Werte','Ausreißerbewertung\n−score_samples','Signalstärke\nRMS nach Skalierung'])):
        x=.55+4.15*i;d.box(s,x,2.55,3.91,2.35)
        d.text(s,x+.2,2.8,3.51,.45,label,21,color[1:],True)
        d.text(s,x+.2,3.5,3.51,.9,definition,18)
        d.text(s,x+.2,4.42,3.51,.35,'Schwelle '+fmt(plan['thresholds'][method]['value'],6),16,NAVY,True)
    d.box(s,.55,5.3,12.2,1.16,'FFF1DB')
    d.text(s,.82,5.48,11.65,.83,'P99 ist eine Kalibrierungsregel – nicht 99 % Erkennungsgenauigkeit.\nDer endgültige Handyaufbau wurde noch nicht unabhängig validiert.',19)

    s=d.slide('Live-Beobachtungen','Alle drei Läufe zeigen zeitlich begrenzte Alarme',
        'Getrennte Anrufe. Grau: Freigabe bis Rückmeldung, nicht die gemessene Vibrationsdauer.',
        'Jede Kurve gehört zu einem anderen Anruf und zur jeweils live aktiven Methode. Die x-Achse beginnt pro Aufnahme neu. '
        'Gestrichelt bei 1 liegt die eigene Schwelle; Score/Schwelle ist keine Wahrscheinlichkeit und keine gleiche Sensitivität. '
        'Graue Bereiche sind Chat-Markierungen, keine Ground Truth. Ein fehlender Alarm außerhalb ist kein Nachweis einer '
        'allgemeinen Fehlalarmrate. Vollständige Fenster: AE 184, IF 196, RMS 234. Quelle: decisions.csv und cues.jsonl.')
    d.picture(s,assets['live_scores'],.6,2.34,12.1,4.25)
    d.text(s,.7,6.68,12,.24,'Unterschiedliche Zeitachsen und Anrufverzögerungen erlauben keine Live-Geschwindigkeitsrangfolge.',12,MUTED)

    s=d.slide('Identische Daten für alle','Wer meldet zuerst auf denselben Daten?',
        'Jede gespeicherte Aufnahme wurde unverändert durch alle drei Methoden ausgewertet. Zahl im Punkt = Rang.',
        'Offline-Replay, keine zusätzliche Live-Aufnahme und kein Zeitbenchmark. Original-Fenstergrenzen wurden über '
        'window_index sowie erste/letzte Zeitstempel geprüft. Erste Alarmfenster vollständig zwischen den Chat-Markierungen: '
        'Aufnahme A: AE/IF/RMS jeweils 97; B: AE 93, IF/RMS 94; C: alle 155. Vor der Freigabe keine Alarme in allen neun Kombinationen. '
        'Gleiche Fensternummer bedeutet Gleichstand; Laufzeit ist kein Tie-Break. Reproduktion der 614 Original-Live-Entscheidungen '
        'ohne Abweichung, maximale Scoreabweichung 0. Ein Fenster Vorsprung ist nicht die absolute Verzögerung ab physischem Beginn. '
        'Quelle: replay_v1/summary.json und decisions.csv.')
    d.picture(s,assets['first_alarm_ranks'],.6,2.62,12.1,3.5)
    d.text(s,.75,6.27,11.85,.54,'A und C: Gleichstand. B: Autoencoder ein Fenster früher. Keine allgemeine Sieger-Rangliste.',19,TEAL,True)

    s=d.slide('Alarmhäufigkeit richtig lesen','Mehr Alarmfenster bedeuten nicht mehr Treffer',
        'Links: ursprüngliche Live-Läufe. Rechts: alle drei Methoden auf jeder identischen Rohaufnahme.',
        'Live: AE 11, IF 6, RMS 6 Alarmfenster. Replay-Matrix Zeilen A/B/C, Spalten AE/IF/RMS: '
        '11/6/8, 9/6/6, 9/6/6. Alle Replay-Alarme liegen vollständig zwischen den Chat-Markierungen. '
        'Ein Anruf kann mehrere intermittierende Vibrationsimpulse und mehrere Alarmfenster erzeugen. '
        'Fenster sind keine unabhängigen Ereignisse. Nicht aus 11 gegenüber 6 eine bessere Trefferquote ableiten. '
        'Fensterzahlen und Dauern unterscheiden sich. Keine physisch referenzierte Ereignis-Erkennungsrate verfügbar.')
    d.picture(s,assets['alarm_counts'],.6,2.6,12.1,3.5)
    d.text(s,.7,6.28,11.95,.5,'Ein Anruf = ein Versuch. 11 Alarmfenster sind nicht 11 unabhängig erkannte Fehler.',20,TEAL,True)

    s=d.slide('Berechnungsaufwand','RMS rechnet am kürzesten, IF deutlich länger',
        'Beobachtete Berechnungszeit im jeweiligen Live-Prozess; keine physische Fehler-Erkennungsverzögerung.',
        'processing_ms umfasst Standardisierung, Scoreberechnung und Entscheidung nach Fensterentnahme. '
        'Nicht nur reine Modell-Inferenz, nicht Wartezeit auf ein vollständiges Fenster. '
        'Dargestellt Median und P95 aller gültigen Fenster. P95 bedeutet 95 % der gemessenen Werte liegen darunter oder gleich. '
        'Drei getrennte Läufe, keine Wiederholungen; CPU-Takt dynamisch 1,5 bis 2,4 GHz. '
        'Die isolierte Algorithmuslaufzeit wurde nicht unter fixierter Systemumgebung gemessen. '
        'Quelle: ausgewählte decisions.csv, processing_ms. Kürzere Berechnung garantiert kein früheres Alarmfenster.')
    d.picture(s,assets['processing'],.6,2.65,12.1,3.4)
    d.text(s,.75,6.24,11.8,.58,'Entscheidend sind zwei Größen: wann die Schwelle überschritten wird – und wie lange die Rechnung dauert.',18,TEAL,True)

    s=d.slide('Einfluss auf den Raspberry Pi','Isolation Forest beansprucht mehr Prozess-RAM',
        'Einzelbetrieb ohne Mess-GUI. CPU und RAM enthalten Sensorerfassung, Auswertung und Protokollierung.',
        'CPU ist der Median der intervallweise erfassten Prozesswerte: 100 % entspricht einem Kern, nicht dem gesamten Pi. '
        'Keine zeitgewichtete Gesamtauslastung und kein systemweiter Energieverbrauch. RAM ist maximale abgetastete RSS '
        'während der Aufnahme, nicht Start-Peak oder inkrementeller Modellbedarf. Keine Baseline-Subtraktion. '
        'Erfassung lief jeweils allein; bestehende Betriebssystem-/Editorprozesse bleiben Umgebungseinflüsse. '
        'Temperatur und dynamischer CPU-Takt wurden protokolliert; keine kontrollierten Wiederholungen. '
        'Keine Messung elektrischer Leistungsaufnahme. Quelle: decisions.csv, Prozessfelder.')
    d.picture(s,assets['resources'],.6,2.63,12.1,3.48)
    d.text(s,.75,6.29,11.8,.51,'Beobachtete Prozesswerte, kein isolierter Modell-Benchmark und keine Leistungsmessung in Watt.',18,MUTED)

    s=d.slide('Dokumentation','Echte Screenshots der gespeicherten Berichte',
        'Drei Browser-Aufnahmen nach Messende; keine nachgebildete Live-GUI und kein Foto des Versuchsaufbaus.',
        'Hier gezeigt: Autoencoder-Bericht. Für alle drei ausgewählten Läufe liegen report_screenshot/report.png, '
        'report.html, browser.log und evidence.json vor. Screenshots wurden wirklich mit Chromium gerendert; '
        'Quell- und Bildhashes sind archiviert. Die Plots selbst sind CSV-basierte Exporte. '
        'Alle Originaldaten einschließlich zurückgesetzter Anläufe bleiben erhalten. Vollständige Dateien in sources/trials/.')
    d.picture(s,records['autoencoder']['path']/'report_screenshot/report.png',.55,2.32,8.0,4.43)
    d.box(s,8.8,2.7,3.96,3.5)
    d.text(s,9.04,2.97,3.48,.4,'Für jede Methode',21,NAVY,True)
    d.text(s,9.04,3.62,3.43,2.3,'Rohdaten und Scores\nCPU / RAM / Takt\nPNG- und PDF-Diagramme\nBrowser-Screenshot\nZeitmarken und SHA-256',16)

    s=d.slide('Transparenz und Grenzen','Pilotbefund – noch kein Zuverlässigkeitsnachweis',
        'Drei ausgewählte Läufe; drei frühere Anläufe wegen unklarer Anrufkoordination separat archiviert.',
        'Alle sechs Versuche: AE01 170 Fenster/30 Alarme, AE02 158/12 mit einem ungültigen Fenster, AE03 184/11; '
        'IF01 154/7, IF02 196/6; RMS01 234/6. Nutzer bat bei AE01/02 und IF01 um Wiederholung; keine Löschung. '
        'Die Auswahl sauber koordinierter Versuche ist kein Nachweis allgemeiner Fehlalarmfreiheit. '
        'Chat-Cues messen keinen physischen Beginn; Handyposition/Befestigung/Muster sind nicht unabhängig dokumentiert. '
        'Das Profil stammt aus früherem 75-%-Standlauf; bundle measurement_chain_status=unverified_legacy. '
        'Fehlende Wiederholungen, wechselnder Takt, Reihenfolge AE→IF→RMS und ungleiche Stimuli begrenzen Schlussfolgerungen. '
        'Die geprüften digitalen Qualitätsflags waren in den drei ausgewählten Läufen unauffällig, beweisen aber keine vollständig validierte Messkette.')
    limits=[('Zeitreferenz','Physischer Beginn und tatsächliche Vibrationsdauer fehlen.'),
            ('Übertragbarkeit','Ein Anruf je Methode; kein echter Lüfterdefekt getestet.'),
            ('Kalibrierung','Finaler Handyaufbau nicht verifiziert; Schwellen unverändert.'),
            ('Versuchsauswahl','Neustarts erhalten; Ressourcen ohne Wiederholungen.')]
    for i,(title,text) in enumerate(limits):
        y=2.6+.91*i;d.box(s,.6,y,12.1,.73)
        d.text(s,.84,y+.14,2.8,.39,title,18,AMBER,True)
        d.text(s,3.9,y+.16,8.45,.38,text,16)

    s=d.slide('Fazit für die Besprechung','Erste Ergebnisse sind da – die Grenzen sind klar',
        'Funktionsnachweis, fairer Fenstervergleich und Prozesslast können getrennt diskutiert werden.',
        'Kernaussage: Alle drei Methoden reagierten im jeweils ausgewählten Anrufintervall. Im gleichen Datenstrom '
        'gab es zwei Gleichstände und einmal einen Vorsprung von einem Fenster für AE. RMS hatte die geringste '
        'beobachtete Berechnungszeit, IF die höchste Prozess-RSS. Das belegt keine allgemeine Gewinner-Methode. '
        'Nächste wissenschaftliche Schritte: Aufbau dokumentieren und mit Normaldaten validieren; unabhängige '
        'physische Start-/Endreferenz, wiederholte reproduzierbare Stimuli, Reihenfolge wechseln; '
        'Ressourcen separat mit kontrollierter Umgebung und gleicher Laufzeit testen. '
        'Diese Schritte sind Empfehlungen, nicht bereits erledigt. Präsentation und Rohdaten sind getrennt von der Vorbereitung versioniert.')
    d.box(s,.6,2.55,6.0,3.85,'E6F2F1');d.box(s,6.85,2.55,5.9,3.85)
    d.text(s,.9,2.84,5.4,.45,'Heute belegt',23,TEAL,True)
    d.text(s,.9,3.62,5.35,2.15,'Live-Aufzeichnung funktioniert.\nVergleich auf gleichen Rohfenstern.\nProzesslast ist protokolliert.\nErgebnisse sind nachprüfbar.',19)
    d.text(s,7.14,2.84,5.33,.45,'Für belastbare Aussagen',23,NAVY,True)
    d.text(s,7.14,3.62,5.29,2.15,'Aufbau / Normalzustand validieren.\nPhysischen Beginn messen.\nMehrere Ereignisse wiederholen.\nRessourcen kontrolliert testen.',19)
    path=output/'handyvibration_ergebnisse.pptx';d.prs.save(path)
    (output/'speaker_notes.md').write_text('# Erläuterungen zu den Pilotergebnissen\n\n'+
        '\n\n'.join(f'## {i}. {title}\n\n{notes}' for i,(title,notes) in enumerate(d.notes,1))+'\n',encoding='utf-8')
    return path


def report(output, records, replay):
    lines=['# Handyvibration: Ergebnisse des explorativen Piloten', '',
        'Datum: 19.09.2026. Raspberry Pi 5, 75 % PWM (keine Drehzahlmessung). Drei ausgewählte Live-Einzelaufnahmen, jeweils eine Methode. '
        'Schwellen unverändert, kein verifizierter physischer Vibrationsbeginn. Keine allgemeine Erkennungs- oder Fehlalarmrate.', '',
        '## Live-Ergebnisse', '',
        '| Methode | Fenster | Alarmfenster vor / zwischen / nach Chat-Markierungen | Berechnung Median / P95 [ms] | CPU-Median [% eines Kerns] | Max. abgetastete RSS [MiB] |',
        '| --- | ---: | --- | ---: | ---: | ---: |']
    for key,label,*_ in METHODS:
        v=records[key]['summary'];p=v['phases'];
        phase=' / '.join(str(p[k]['alarm_windows'])+' von '+str(p[k]['windows']) for k in ('pre_cue','between_cues','post_cue'))
        lines.append(f"| {label} | {v['windows']} | {phase} | {fmt(v['processing_median_ms'],3)} / {fmt(v['processing_p95_ms'],3)} | {fmt(v['median_process_cpu_percent_one_core'],2)} | {fmt(v['sampled_peak_rss_mib'],2)} |")
    lines += ['', 'Je Lauf überlappen zwei Fenster die Chat-Abschnittsgrenzen und fehlen deshalb nur in den Phasensummen. '
              '614 vollständige Fenster insgesamt, 0 ungültig, 0 verworfen; digitale Lücken-/Überlauf-/Sättigungsflags unauffällig. '
              'Unvollständige Schlussfenster bleiben als Rohsamples archiviert. Ein Alarmfenster ist kein unabhängiger Fehlerfall.', '',
              '![Live-Scores](assets/live_scores.png)', '',
              '## Wer meldet zuerst auf identischen Eingaben?', '',
              'Offline wurden alle drei Methoden auf jede der drei Rohaufnahmen angewendet. '
              'Fenstergrenzen, Modelle und Schwellen bleiben gleich. Kein zusätzlicher Anruf und kein Ressourcenbenchmark.', '',
              '| Aufnahme | Erstes AE-Alarmfenster | Erstes IF-Alarmfenster | Erstes RMS-Alarmfenster |',
              '| --- | ---: | ---: | ---: |']
    for letter,name in zip('ABC',RUNS):
        e=replay['recordings'][name]['methods']
        lines.append('| '+letter+' | '+' | '.join(str(e[m]['first_alarm_window_between_cues']) for *_,m in METHODS)+' |')
    lines += ['', 'A und C: Gleichstand. B: Autoencoder ein Fenster früher. '
        'Gezählt wird der erste Alarm vollständig zwischen den Chat-Markierungen; in allen neun Replay-Kombinationen keine Alarme davor/danach. '
        'Alle 614 ursprünglichen Live-Vorhersagen wurden exakt reproduziert (maximale Score-Abweichung 0). '
        'Ein Fenstervorsprung ist keine absolut gemessene Fehler-Erkennungsverzögerung. '
        'Nominal: 128/200 = 0,64 s pro Fenster; Host-Zeitstempel sind keine unabhängige Störungsreferenz.', '',
        '![Nummerierte Alarmrangfolge](assets/first_alarm_ranks.png)', '',
        '## Ressourcen richtig interpretieren', '',
        'Berechnungszeit umfasst Standardisierung, Score und Entscheidung. CPU/RAM gelten für den gesamten Prozess inklusive Erfassung und Logging. '
        'CPU ist der Median der abgetasteten Intervallwerte, nicht zeitgewichtete oder systemweite Last. '
        'RSS ist der während der Aufnahme abgetastete Prozessspeicher, nicht Start-Peak oder isolierter Modellbedarf. '
        'Takt schwankte in den drei Läufen zwischen 1,5 und 2,4 GHz. Keine Wiederholungen, kein Energieverbrauch in Watt gemessen.', '',
        '![Berechnungszeiten](assets/processing.png)', '', '![Prozesslast](assets/resources.png)', '',
        '## Ausgewählte und wiederholte Anläufe', '',
        'Ausgewählt: AE03, IF02, RMS01. AE01/AE02 und IF01 wurden auf Nutzerwunsch wegen unklarer bzw. zu früher Anrufkoordination wiederholt. '
        'Sie bleiben vollständig in sources/trials/ erhalten und werden nicht stillschweigend als störungsfreie Läufe umgedeutet. '
        'AE01: 170 Fenster/30 Alarme; AE02: 158/12 plus 1 ungültiges Fenster; IF01: 154/7. '
        'Diese Auswahl erlaubt keine allgemeine Aussage zur Fehlalarmrate.', '',
        '## Wissenschaftliche Grenzen', '',
        'Chat-Freigabe und Rückmeldung messen nicht den physischen Vibrationsbeginn/-ende. '
        'Nur ein ausgewählter Anruf je Methode; keine belastbare Erkennungsquote. '
        'Handyposition, Kopplung und Vibrationsmuster sind nicht unabhängig dokumentiert; endgültige Aufbaukalibrierung fehlt. '
        'Das eingefrorene Profil trägt measurement_chain_status=unverified_legacy. '
        'Tischvibration simuliert eine externe Störung, keinen nachgewiesenen Lüfterdefekt.', '',
        '## Artefakte', '',
        '- handyvibration_ergebnisse.pptx und .pdf: zehn Ergebnisfolien.',
        '- speaker_notes.md: Erklärungen und Quellen je Folie.',
        '- assets/: Diagramme als PNG/PDF.',
        '- sources/trials/*/report_screenshot/: drei echte Browser-Screenshots der gespeicherten Berichte, keine Live-GUI.',
        '- sources/: unveränderte Quellenkopien einschließlich Neustarts, Bundle und Replay.',
        '- source_manifest.json und artifact_manifest.json: SHA-256-Nachweise.',
        '- pdf_export.json: dokumentierter Exportweg; PowerPoint-Zeilenumbrüche können abweichen.', '']
    (output/'results_report.md').write_text('\n'.join(lines),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();source=args.source.resolve();output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    freeze(source,output)
    plan,records,replay=load_evidence(output/'sources')
    write_json(output/'live_summary.json',{k:r['summary'] for k,r in records.items()})
    assets=charts(output,records,replay)
    report(output,records,replay)
    pptx=deck(output,records,replay,plan,assets)
    export_pdf_and_previews(pptx,output)
    files=[p for p in sorted(output.rglob('*')) if p.is_file()]
    write_json(output/'artifact_manifest.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),
        files=[dict(path=str(p.relative_to(output)),sha256=sha256(p)) for p in files]))
    print(json.dumps(dict(pptx=str(pptx),pdf=str(pptx.with_suffix('.pdf')),slides=10),indent=2))


if __name__=='__main__':
    main()
