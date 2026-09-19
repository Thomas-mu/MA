"""Offline same-window comparison; no hardware and no physical latency claims."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import shutil

import numpy as np
import common_comparison as common


RUNS = ('autoencoder_awaiting_call_03', 'isolation_forest_awaiting_call_02', 'rms_awaiting_call_01')


def read_rows(path):
    with Path(path).open(newline='') as handle:
        return list(csv.DictReader(handle))


def phase_of(row, start, end):
    first, last = int(row['window_start_ns']), int(row['window_complete_ns'])
    if last < start:
        return 'pre_cue'
    if first >= start and last <= end:
        return 'between_cues'
    if first >= end:
        return 'post_cue'
    return 'straddling'


def extract_windows(raw_rows, decisions, size):
    grouped = {}
    for row in raw_rows:
        grouped.setdefault(int(row['window_index']), []).append(row)
    windows = []
    for decision in decisions:
        index = int(decision['window'])
        samples = grouped.pop(index)
        if len(samples) != size:
            raise ValueError(f'Wrong sample count in window {index}')
        if int(samples[0]['host_monotonic_ns']) != int(decision['window_start_ns']) or int(samples[-1]['host_monotonic_ns']) != int(decision['window_complete_ns']):
            raise ValueError(f'Raw/decision alignment mismatch in window {index}')
        invalid = any(int(r[flag]) for r in samples for flag in ('gap', 'overrun', 'saturated'))
        if invalid or decision['error'] or decision['prediction'] not in ('0', '1'):
            raise ValueError('This pilot replay requires wholly valid input windows.')
        windows.append(np.asarray([[float(r[k]) for k in common.AXES] for r in samples], dtype=np.float64))
    if any(len(rows) >= size for rows in grouped.values()):
        raise ValueError('Unmatched complete raw window; refusing silent exclusion.')
    return windows, sum(len(rows) for rows in grouped.values())


def assign_ranks(entries):
    """Dense rank on source window index; ties stay ties, not runtime tie-breaks."""
    ordered = sorted({v['first_alarm_window_between_cues'] for v in entries.values()
                      if v['first_alarm_window_between_cues'] is not None})
    for entry in entries.values():
        index = entry['first_alarm_window_between_cues']
        entry['first_alarm_window_rank'] = ordered.index(index) + 1 if index is not None else None


def replay(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    plan = common.read_json(source/'plan.json')
    directory = source/'bundle'
    if common.sha256(directory/'bundle.json') != plan['bundle_sha256']:
        raise ValueError('Bundle changed since plan creation.')
    bundle = common.load_bundle(directory)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, output/'replay_source.py')
    functions = {m: common.scorer(m, bundle, directory, runtime='litert', threads=1)[0]
                 for m in common.METHODS}
    summary = {'scope': 'offline_same_raw_windows_not_live_latency_benchmark',
               'true_detection_delay_ms': None, 'physical_onset_verified': False,
               'thresholds_changed': False, 'bundle_sha256': plan['bundle_sha256'],
               'provenance': common.provenance(), 'recordings': {}, 'source_hashes': {}}
    output_rows = []
    for name in RUNS:
        path = source/'trials'/name
        meta = common.read_json(path/'run.json')
        review = common.read_json(path/'trial_review.json')
        if not review.get('include_in_descriptive_call_comparison'):
            raise ValueError(f'Run not approved for descriptive comparison: {name}')
        if meta['bundle_sha256'] != plan['bundle_sha256'] or meta['status'] not in ('stopped', 'completed'):
            raise ValueError('Source bundle or run status mismatch.')
        for filename, digest in meta['file_sha256'].items():
            if common.sha256(path/filename) != digest:
                raise ValueError(f'Original run artifact changed: {name}/{filename}')
        decisions = read_rows(path/'decisions.csv')
        windows, partial = extract_windows(read_rows(path/'raw.csv'), decisions, bundle['window_size'])
        if partial != meta['acquisition']['partial_samples_saved']:
            raise ValueError('Partial sample count mismatch.')
        cues = [json.loads(s) for s in (path/'cues.jsonl').read_text().splitlines()]
        starts = [c['monotonic_ns'] for c in cues if c['event']=='call_requested']
        ends = [c['monotonic_ns'] for c in cues if c['event']=='end_reported']
        if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0]:
            raise ValueError('Expected one ordered cue pair.')
        entries = {}
        for method, function in functions.items():
            alarms = {key: 0 for key in ('pre_cue', 'between_cues', 'post_cue', 'straddling')}
            first = None
            differences, mismatches = [], 0
            for raw, decision in zip(windows, decisions):
                score, prediction = common.classify_raw(raw, bundle['scaler'], function, bundle['thresholds'][method]['value'])
                phase = phase_of(decision, starts[0], ends[0])
                if prediction:
                    alarms[phase] += 1
                    if phase == 'between_cues' and first is None:
                        first = int(decision['window'])
                if method == meta['method']:
                    differences.append(abs(score-float(decision['score'])))
                    mismatches += prediction != int(decision['prediction'])
                output_rows.append(dict(recording=name, method=method, window=int(decision['window']),
                    source_window_start_ns=int(decision['window_start_ns']),
                    source_window_complete_ns=int(decision['window_complete_ns']),
                    source_complete_elapsed_s=(int(decision['window_complete_ns'])-meta['start_monotonic_ns'])/1e9,
                    phase=phase, score=score, threshold=bundle['thresholds'][method]['value'], prediction=prediction))
            entries[method] = dict(alarm_windows_by_phase=alarms, alarm_windows_total=sum(alarms.values()),
                first_alarm_window_between_cues=first, live_prediction_mismatches=mismatches if differences else None,
                maximum_live_score_difference=max(differences) if differences else None)
            if mismatches or (differences and max(differences) > 1e-5):
                raise ValueError(f'Replay differs from original live decisions: {name}/{method}')
        assign_ranks(entries)
        summary['recordings'][name] = dict(original_live_method=meta['method'], windows=len(windows),
            partial_samples_excluded=partial, methods=entries,
            ranking_has_no_precue_alarms=all(v['alarm_windows_by_phase']['pre_cue']==0 for v in entries.values()))
        for filename in ('run.json', 'raw.csv', 'decisions.csv', 'cues.jsonl', 'trial_review.json', 'capture_source.py'):
            summary['source_hashes'][str(path/filename)] = common.sha256(path/filename)
    common.write_rows(output/'decisions.csv', output_rows)
    common.write_json(output/'summary.json', summary)
    (output/'README.md').write_text(
        '# Replay identischer Rohfenster\n\n'
        'Jede der drei archivierten Aufnahmen wurde mit allen drei eingefrorenen Methoden ausgewertet. '
        'Fenstergrenzen wurden über Rohdaten und Originalentscheidungen geprüft. '
        'Unvollständige Schlussfenster sind nicht ausgewertet. Es wurde kein Sensor und kein Lüfter angesteuert.\n\n'
        'Rangfolge: erstes Alarmfenster vollständig zwischen den Chat-Markierungen. '
        'Gleiche Fensternummer bedeutet Gleichstand; Rechenzeiten lösen Gleichstände nicht auf. '
        'Alarme vor/nach den Markierungen werden separat gezählt. '
        'Das ist keine unabhängig gemessene Fehler-Erkennungsverzögerung und kein Ressourcenbenchmark. '
        'Eine nachträgliche Anwendung der anderen Methoden ist keine zusätzliche Live-Aufnahme.\n\n'
        'Die Original-Livemethode muss alle Vorhersagen reproduzieren (Score-Abweichung maximal 1e-5). '
        'Schwellenwerte, Modelle und Originaldaten bleiben unverändert.\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = replay(args.source, args.output)
    print(json.dumps(result['recordings'], indent=2))
