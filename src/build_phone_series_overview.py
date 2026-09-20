"""Create a readable supplement from the frozen ten-call comparison outputs.

No rescoring, label changes, source edits, or hardware access. Every output
directory is new. Absolute technical timestamps remain in the archived source.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import sys


LABELS = {'tflite_autoencoder': 'Autoencoder', 'isolation_forest': 'Isolation Forest', 'rms': 'RMS'}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def build(analysis, output):
    analysis, output = Path(analysis).resolve(), Path(output).resolve()
    with (analysis / 'trial_comparison.csv').open() as f:
        rows = list(csv.DictReader(f))
    summary = read_json(analysis / 'summary.json')
    benchmark = read_json(analysis / 'processing_benchmark.json')
    temperatures = [r['temperature_celsius_before'] for r in benchmark['thermal_conditions']
                    if r['temperature_celsius_before'] is not None]
    source = analysis / 'source'
    run = read_json(source / 'run.json')
    config = read_json(source / 'config.json')
    started = read_json(source / 'started.json')
    cues = [json.loads(line) for line in (source / 'cues.jsonl').read_text().splitlines()]
    journal = [json.loads(line) for line in (source / 'fan.jsonl').read_text().splitlines()]
    assert len(rows) == 30 and len(cues) == 20
    trials = []
    for number in range(1, 11):
        selected = {r['method']: r for r in rows if int(r['trial']) == number}
        assert set(selected) == set(LABELS)
        available = {m: int(r['first_new_alarm_window']) for m, r in selected.items() if r['first_new_alarm_window']}
        earliest = min(available.values()) if available else None
        trials.append(dict(trial=number, earliest_methods=[m for m, w in available.items() if w == earliest],
                           missing_methods=[m for m in LABELS if m not in available],
                           methods={m: {k: r[k] for k in (
                               'first_alarm_window', 'first_alarm_is_new', 'first_alarm_previous_decision',
                               'first_new_alarm_window', 'first_new_alarm_complete_relative_s',
                               'first_new_alarm_difference_to_earliest_s', 'issues')} for m, r in selected.items()}))
    sole = {m: sum(t['earliest_methods'] == [m] for t in trials) for m in LABELS}
    ties = [t['trial'] for t in trials if len(t['earliest_methods']) > 1]
    starts = {c['number']: c['monotonic_ns'] for c in cues if c['event'] == 'call_requested'}
    ends = {c['number']: c['monotonic_ns'] for c in cues if c['event'] == 'end_reported'}
    checks = [e for e in journal if e['event'] == 'setting_verified']
    changes = [e for e in journal if e['event'] == 'transaction_begin']
    invariant = all(e['state']['pwm_configuration']['period_ns'] == 40000
                    and e['state']['pwm_configuration']['duty_cycle_ns'] == 30000
                    and e['state']['pwm_configuration']['enable'] == 1
                    and e['state']['pwm_configuration']['polarity'] == 'normal'
                    and e['state']['pwm_mux_confirmed'] for e in checks)
    archived_hashes = {name: digest(source / name) == expected for name, expected in run['file_sha256'].items()}
    bundle = read_json(source / 'bundle/bundle.json')
    bundle_hashes = {name: digest(source / 'bundle' / name) == expected for name, expected in bundle['artifact_sha256'].items()}
    quality_samples = []
    with (source / 'raw.csv').open() as f:
        for r in csv.DictReader(f):
            if any(int(r[k]) for k in ('gap', 'overrun', 'saturated')):
                quality_samples.append({k: int(r[k]) for k in ('sample_index', 'window_index', 'host_monotonic_ns', 'gap', 'overrun', 'saturated')})
    audit = dict(capture_status=run['status'], samples=run['acquisition']['samples_captured'],
        complete_windows=run['acquisition']['windows_formed'], partial_samples=run['acquisition']['partial_samples_saved'],
        warmup_seconds=config['warmup_seconds'],
        normal_lead_in_seconds=(starts[1] - started['normal_start_monotonic_ns']) / 1e9,
        rest_seconds_before_trials={str(n): (starts[n] - ends[n-1]) / 1e9 for n in range(2, 11)},
        postrun_recorded_seconds=(run['acquisition']['last_sample_host_monotonic_ns'] - ends[10]) / 1e9,
        marker_pairs=10, pwm_set_transactions=len(changes), successful_pwm_checks=len(checks),
        all_pwm_checks_at_requested_point=invariant,
        no_setting_change_after_start=all(e['monotonic_ns'] < started['start_monotonic_ns'] for e in changes),
        pwm_readback=config['pwm_readback']['pwm_configuration'],
        waveform_or_rpm_measured=False, acquisition=run['acquisition'],
        quality_samples=quality_samples, source_hash_verification=archived_hashes,
        bundle_hash_verification=bundle_hashes)
    assert invariant and all(archived_hashes.values()) and all(bundle_hashes.values())
    metrics = dict(trials_planned=10, first_alarm_equals_first_new_for_all_rows=all(
        r['first_alarm_window'] == r['first_new_alarm_window'] for r in rows),
        sole_earliest_counts=sole, tied_trials=ties, trials=trials,
        normal_summary=summary['methods'], benchmark=benchmark['methods'],
        comparison_rule='Differences between completion timestamps of first new alarm windows; no vibration-onset latency.',
        analysis_input_sha256={name: digest(analysis / name) for name in (
            'trial_comparison.csv', 'window_results.csv', 'normal_phases.csv', 'summary.json',
            'processing_benchmark.json', 'analysis_rules.json')})
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'technical_audit.json', audit)
    write_json(output / 'comparison_overview.json', metrics)
    shutil.copy2(__file__, output / 'build_phone_series_overview.py')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    for (method, label), offset, marker, color in zip(LABELS.items(), (-.18, 0, .18), ('o', 's', '^'), ('#2878b5', '#2c8b57', '#c96f14')):
        valid = [t for t in trials if t['methods'][method]['first_new_alarm_window']]
        ax.scatter([float(t['methods'][method]['first_new_alarm_difference_to_earliest_s']) for t in valid],
                   [t['trial'] + offset for t in valid], label=label, marker=marker, color=color, s=55, zorder=3)
    ax.axvline(0, color='grey', linewidth=.7)
    ax.set(yticks=list(range(1, 11)), yticklabels=[f'Versuch {n}' for n in range(1, 11)],
           xlabel='Abstand zum frühesten neuen Alarmfenster [s]',
           title='Erste neue Alarmfenster in zehn Suchbereichen\nVergleich gespeicherter Fenster; keine Reaktionszeit seit Vibrationsbeginn')
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=.25)
    ax.legend(loc='lower right')
    for suffix in ('png', 'pdf'):
        fig.savefig(output / f'erste_alarmfenster.{suffix}', dpi=180)
    plt.close(fig)

    def link(path):
        import os
        return os.path.relpath(path, output)
    csv_link = link(analysis / 'trial_comparison.csv')
    lines = ['# Zehn Smartphoneversuche bei 75 % PWM und 25 kHz', '',
        'Die Serie wurde mit dem Google Pixel 9a am unveränderten Aufbau als eine durchgehende Aufnahme durchgeführt. '
        'Das bestehende Profil `standlauf_pwm75_200hz`, die Modelle, Standardisierung, 128/128-Fenster und Schwellen blieben unverändert. '
        'Der Betriebspunkt wurde vor Aufnahme und Einlaufzeit gesetzt, rückgelesen und gespeichert. '
        f'Alle {len(checks)} erfolgreichen Kontrollrücklesungen bestätigten 75 % bei 25 kHz; nach Aufnahmestart gab es keinen Stellbefehl. '
        'Dies belegt die PWM-Konfiguration, keine gemessene Drehzahl oder elektrische Wellenform.', '',
        f'Nach 30 s Einlauf wurden {audit["normal_lead_in_seconds"]:.3f} s Normalvorlauf erfasst. '
        f'Zwischen den Rückmeldungen und der nächsten Aufforderung lagen jeweils mindestens {min(audit["rest_seconds_before_trials"].values()):.3f} s. '
        f'Der kontrollierte Stopp erfolgte nach {audit["postrun_recorded_seconds"]:.3f} s gespeichertem Nachlauf. '
        f'Gesichert wurden {summary["samples_saved"]} Samples über {summary["recorded_observation_duration_s"]:.3f} s. '
        'Alle zehn Versuche sind enthalten.', '',
        '## Ergebnisse', '',
        'Alle drei Verfahren lieferten in jedem der zehn Suchbereiche ein neues, eindeutig einem gespeicherten Fenster zugeordnetes Alarmfenster. '
        'In allen 30 Kombinationen aus Versuch und Verfahren war das unmittelbar vorhergehende Fenster gültig und NORMAL; '
        'der erste Alarm war damit kein bereits bestehender Alarm. Es gab keine fehlenden ersten Alarme und keine alarmierenden Randfenster.', '',
        f'Der Autoencoder hatte in {sole["tflite_autoencoder"]}/10 Versuchen allein das früheste neue Alarmfenster '
        '(Versuch 1 bis 6 und Versuch 10). In Versuch 7 bis 9 bestand Gleichstand aller drei Verfahren (3/10). '
        'Isolation Forest und RMS waren in keinem Versuch allein zuerst. '
        'Diese Beobachtung betrifft die wiederholte Untersuchung an diesem Aufbau und belegt keine allgemeine Überlegenheit.', '',
        '| Versuch | AE: Fenster | IF: Fenster | RMS: Fenster | IF nach frühestem Fenster [s] | RMS nach frühestem Fenster [s] |',
        '|---|---:|---:|---:|---:|---:|']
    for t in trials:
        m = t['methods']
        lines.append(f'| Versuch {t["trial"]} | {m["tflite_autoencoder"]["first_new_alarm_window"]} | {m["isolation_forest"]["first_new_alarm_window"]} | {m["rms"]["first_new_alarm_window"]} | {float(m["isolation_forest"]["first_new_alarm_difference_to_earliest_s"]):.6f} | {float(m["rms"]["first_new_alarm_difference_to_earliest_s"]):.6f} |')
    lines += ['', '![Erste neue Alarmfenster](erste_alarmfenster.png)', '',
        'Die Abstände wurden aus den Aufnahmezeitstempeln der Fensterenden berechnet. '
        'Die Marker begrenzen Suchbereiche und sind keine gemessenen Vibrationsgrenzen. '
        'Die Suchbereiche dauern etwa 33 bis 123 s und enthalten auch Wartezeit bis zum Anruf bzw. zur Rückmeldung; '
        'diese Zeiten sind keine Anruf- oder Vibrationsdauern. Eine feste Dauer wurde nicht eingesetzt. '
        'Es wurden keine zusätzlichen Vibrationslabels aus den Ergebnissen einer Methode erzeugt.', '',
        '## Normalbetrieb und Datenqualität', '',
        'In 490,323 s dokumentierten Normalphasen nach der Einlaufzeit lagen pro Verfahren 783 gültige, vollständig enthaltene Fenster vor. '
        'Alle Verfahren hatten darin 0 Alarmfenster (0/783; 0 %). Dies ist der beobachtete Alarmfensteranteil in dieser Serie, '
        'keine allgemeine Fehlalarmrate. Fenster an Phasengrenzen werden separat ausgewiesen; sie enthalten hier ebenfalls keine Alarme.', '',
        'Ein Sample trägt gleichzeitig ein Lücken- und FIFO-Überlaufflag: Sample 97.219 in Fenster 760, bei 469,015 s relativer Aufnahmezeit. '
        'Das gesamte betroffene Fenster liegt in der Ruhephase zwischen Versuch 4 und 5. '
        'Zusätzlich bleibt das unvollständige Schlussfenster mit 109 Samples gespeichert. '
        'Beide Fenstergruppen erscheinen für alle Verfahren als INVALID und zählen nicht zum Nenner gültiger Fenster. '
        'Es gab keine Sättigungen und keine verworfenen Queuefenster. Die exakte Zahl möglicherweise beim FIFO-Überlauf verlorener Sensorsamples ist unbekannt. '
        'Insgesamt sind 1.806 Fenstergruppen mit jeweils drei Ergebniszeilen gespeichert; 1.804 Gruppen sind gültig.', '',
        '## Separate Verarbeitungszeit auf dem Raspberry Pi', '',
        'Der Benchmark wurde nach dem Aufnahmestopp auf dem Raspberry Pi 5 ausgeführt. '
        'Jedes Verfahren erhielt dieselben 1.804 gültigen gespeicherten Fenster in sechs Runden '
        '(10.824 Messungen je Verfahren). Alle sechs Methodenreihenfolgen wurden verwendet; '
        'je Methode und Runde gingen 20 ungemessene Aufwärmberechnungen voraus. '
        'Gemessen wurde vom unskalierten Fenster im RAM über die vorhandene Standardisierung bis Score und Schwellenentscheidung. '
        'Dateizugriff, Modellladen und Plotten liegen außerhalb der Messung. Die konfigurierte Threadzahl war 1. '
        f'Die protokollierte Temperatur vor den Runden lag zwischen {min(temperatures):g} und {max(temperatures):g} °C. '
        'Der reguläre Betriebssystem- und Desktopbetrieb blieb bestehen; die Messung beansprucht keine vollständig isolierte Rechnerlast.', '',
        '| Verfahren | Median [ms] | P95 [ms] | Gemessene Fenster |', '|---|---:|---:|---:|']
    for method, label in LABELS.items():
        b = benchmark['methods'][method]
        lines.append(f'| {label} | {b["median_ms"]:.6f} | {b["p95_ms"]:.6f} | {b["measured_windows"]} |')
    lines += ['', 'Diese Werte beschreiben Rechenzeit. Während der Aufnahme wurde keine Live-Inferenz ausgeführt; '
        'es gibt daher keine gemessenen Live-Ausgabezeitpunkte und keine nachträglich bestimmbare Live-Reaktionszeit.', '',
        '## Dateien und Reproduktion', '',
        f'- [Vergleich pro Versuch]({csv_link})',
        f'- [Score, Schwelle und Entscheidung je Fenster und Verfahren]({link(analysis / "window_results.csv")})',
        f'- [Normalphasen einschließlich Nenner und Beobachtungsdauer]({link(analysis / "normal_phases.csv")})',
        f'- [Rohwerte des separaten Benchmarks]({link(analysis / "processing_benchmark.csv")})',
        f'- [Vollständige Rohaufnahme]({link(source / "raw.csv")})',
        f'- [Marker]({link(source / "cues.jsonl")}) und [Versuchskonfiguration]({link(source / "config.json")})',
        '- [Technischer Audit einschließlich Hashprüfungen](technical_audit.json)',
        f'- [Vorab festgelegte Auswertungsregeln]({link(source / "analysis_rules.json")})', '',
        'Abbildungen mit XYZ, Scores relativ zur Schwelle und ersten Alarmfenstern:', '']
    lines += [f'- [Versuch {n}]({link(analysis / "figures" / f"versuch_{n:02d}.png")})' for n in range(1, 11)]
    lines += ['', f'[Gesamte XYZ-Serie]({link(analysis / "figures/serie_xyz.png")}) · [Übersichtsdiagramm als PDF](erste_alarmfenster.pdf)', '',
        'Reproduktion in einem neuen Ergebnisordner (der Benchmark misst dabei neue Laufzeiten):', '', '```bash',
        f'{shlex.quote(sys.executable)} {shlex.quote(str(analysis / "analyze_phone_series.py"))} --run {shlex.quote(str(source))} --output NEUER_ERGEBNISORDNER --runtime litert --threads 1 --benchmark',
        f'{shlex.quote(sys.executable)} {shlex.quote(str(output / "build_phone_series_overview.py"))} --analysis NEUER_ERGEBNISORDNER --output NEUER_ERGEBNISORDNER/report_assets',
        '```', '']
    with (output / 'bericht.md').open('x', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return metrics


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.analysis, args.output)['sole_earliest_counts']))
