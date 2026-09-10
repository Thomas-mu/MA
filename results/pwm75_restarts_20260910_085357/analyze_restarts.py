"""Descriptive comparison of three completed independent 75% starts."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
OUT = BASE / 'comparison'
HELPER = ROOT / 'results/pwm50_investigation_20260910/analyze_conditions.py'
spec = importlib.util.spec_from_file_location('pilot_numerics', HELPER)
numerics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(numerics)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(values):
    values = np.asarray(values, dtype=float)
    mean = float(np.mean(values))
    return {
        'n': len(values), 'mean': mean, 'min': float(values.min()),
        'max': float(values.max()), 'range': float(np.ptp(values)),
        'population_std': float(np.std(values)),
        'sample_std': float(np.std(values, ddof=1)),
        'descriptive_cv_percent': float(100 * np.std(values) / abs(mean)) if mean else None,
        'relative_range_percent': float(100 * np.ptp(values) / abs(mean)) if mean else None,
    }


def main():
    if OUT.exists():
        raise FileExistsError('Existing comparison must not be overwritten')
    records, sessions, spectra, aborted_attempts = {}, [], [], []
    input_hashes = {}
    for trial in (1, 2, 3):
        paths = [BASE / f'start_{trial}.json'] + sorted(BASE.glob(f'start_{trial}_attempt*.json'))
        candidates = [(path, json.loads(path.read_text())) for path in paths if path.exists()]
        completed = [(path, obj) for path, obj in candidates if obj.get('status') == 'completed']
        if len(completed) != 1:
            raise ValueError('Exactly one completed recording per trial required')
        session_path, session = completed[0]
        for path, obj in candidates:
            if obj.get('status') != 'completed':
                aborted_attempts.append({'session': str(path.relative_to(ROOT)), 'status': obj.get('status'),
                                         'reason': obj.get('error'), 'recording_present': 'recording' in obj,
                                         'final_pwm_percent': obj.get('final_readback', {}).get('pwm_configuration', {}).get('configured_duty_percent')})
                input_hashes[str(path.relative_to(ROOT))] = digest(path)
        if session['status'] != 'completed' or session['trial'] != trial:
            raise ValueError('Three completed separate starts required')
        if session['final_readback']['pwm_configuration']['configured_duty_percent'] != 0:
            raise ValueError('Final zero not verified')
        if session['requested_settling_s'] != 60:
            raise ValueError('Different prospective settling time')
        if not session['standstill_confirmation']['fan_observed_fully_stopped']:
            raise ValueError('Prestart standstill observation incomplete')
        if 'running_confirmation' in session:
            running_observation = session['running_confirmation']
            observation_source = str(session_path.relative_to(ROOT))
            observation_reported_after_capture = False
            if session['running_confirmation_received_monotonic_ns'] >= session['capture_deadline_monotonic_ns']:
                raise ValueError('Original timed confirmation was late')
        else:
            observation_path = BASE / f'running_observation_{session_path.stem}.json'
            running_observation = json.loads(observation_path.read_text())
            if running_observation.get('observed_during_recording') is not True:
                raise ValueError('Postcapture observation must explicitly refer to the recording interval')
            if running_observation.get('session') != str(session_path.relative_to(ROOT)):
                raise ValueError('Observation assigned to another session')
            input_hashes[str(observation_path.relative_to(ROOT))] = digest(observation_path)
            observation_source = str(observation_path.relative_to(ROOT))
            observation_reported_after_capture = True
        if (running_observation.get('fan_observed_running_uniformly') is not True or
                running_observation.get('mounting_unchanged') is not True):
            raise ValueError('Positive uniform-running/mounting observation incomplete')
        name = f'START_{trial}'
        path = ROOT / session['csv']
        r, spectral = numerics.load(name, path)
        r['trial'] = trial
        r['actual_first_point_after_setting_s'] = session['actual_first_point_after_setting_s']
        r['actual_last_point_after_setting_s'] = session['actual_last_point_after_setting_s']
        r['timing_needs_review'] = session['timing_needs_review']
        r['session'] = str(session_path.relative_to(ROOT))
        r['running_observation_source'] = observation_source
        r['running_observation_reported_after_capture'] = observation_reported_after_capture
        r['five_second_vector_rms_summary'] = describe([s['vector_ac_rms_g'] for s in r['five_second_sections']])
        records[name] = r
        sessions.append(session)
        spectra.extend(spectral)
        for f in (session_path, path, path.with_suffix('.json'), ROOT / session['fan_journal']):
            input_hashes[str(f.relative_to(ROOT))] = digest(f)
    config_keys = ('odr_hz', 'range_g', 'full_resolution', 'acquisition_mode', 'register_readback', 'i2c_clock_configured_hz')
    config = {k: records['START_1']['sensor'][k] for k in config_keys}
    if any({k: r['sensor'][k] for k in config_keys} != config for r in records.values()):
        raise ValueError('Sensor settings differ')
    if len({r['mounting_id'] for r in records.values()}) != 1 or any(r['pwm_percent'] != 75 for r in records.values()):
        raise ValueError('Mounting or PWM mismatch')
    metric_keys = list(records['START_1']['statistics'])
    summary = {key: describe([r['statistics'][key] for r in records.values()]) for key in metric_keys}
    pairwise = []
    for a, b in itertools.combinations(records, 2):
        ra, rb = records[a], records[b]
        va, vb = ra['statistics']['vector_ac_rms_g'], rb['statistics']['vector_ac_rms_g']
        sa, sb = ra['five_second_vector_rms_summary'], rb['five_second_vector_rms_summary']
        pairwise.append({
            'a': a, 'b': b, 'difference_b_minus_a_g': vb - va,
            'absolute_difference_g': abs(vb - va),
            'relative_pair_difference_percent': 100 * abs(vb - va) / ((va + vb) / 2),
            'five_second_range_overlap_g': max(0, min(sa['max'], sb['max']) - max(sa['min'], sb['min'])),
            'five_second_ranges_overlap': max(sa['min'], sb['min']) <= min(sa['max'], sb['max']),
        })
    old_path = ROOT / 'results/pwm50_75_sequence_20260910/comparison/report.json'
    old = json.loads(old_path.read_text())
    previous = {k: old['records'][k]['statistics']['vector_ac_rms_g'] for k in ('PWM75_1', 'PWM75_2')}
    report = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'three_restart_pilot_analysis_completed_no_training',
        'records': records, 'between_start_statistics': summary, 'pairwise': pairwise,
        'physical_starts_total': len(sessions) + len(aborted_attempts),
        'completed_recordings': len(sessions), 'aborted_attempts': aborted_attempts,
        'actual_settling_to_first_point_s': describe([r['actual_first_point_after_setting_s'] for r in records.values()]),
        'sensor_configuration': config,
        'previous75_pilot_context': {'source': str(old_path.relative_to(ROOT)), 'sha256': digest(old_path),
            'vector_ac_rms_g': previous, 'pooled_with_new_starts': False,
            'limitation': 'Earlier two files were from one held state with different time since PWM change.'},
        'input_sha256': input_hashes, 'analysis_sha256': digest(Path(__file__)),
        'numerical_helper_sha256': digest(HELPER),
        'definitions': {
            'xyz_rate': '(N-1)/(last-first host read completion); not nominal ODR or individual-axis-value rate',
            'axis_std': 'population std(ddof=0), equivalent to own-axis AC-RMS',
            'vector_ac_rms': 'sqrt(mean(sum((XYZ-mean(XYZ,axis=0))**2,axis=1)))',
            'sections': 'six nonoverlapping5-s host-time sections per file, own axis mean removal',
            'cv': '100*population_std/abs(mean), descriptive only',
        },
        'limitations': ['n=3 separate starts in one unchanged mounting, no statistical proof',
            '18short sections are not18independent starts', 'No anomaly detection evaluated',
            'No RPM measured', 'Same60-s timer, actual first-point delays reported separately',
            'After three chat-deadline aborts, capture proceeds on fixed timer and running observations are reported separately after capture; raw labels remain unchanged.',
            'Additional aborted starts and unequal off-times may affect thermal/history conditions; no temperature measurement or cold-start claim.'],
        'models_trained': False, 'induced_anomalies': False, 'final_pwm_setpoint_percent': 0,
    }
    OUT.mkdir()
    with (OUT / 'report.json').open('x') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')
    rows, blocks = [], []
    for name, r in records.items():
        rows.append({k: v for k, v in r.items() if not isinstance(v, (dict, list))} |
                    r['statistics'] | {'quality_' + k: v for k, v in r['quality_summary'].items()})
        blocks.extend({'name': name, **section} for section in r['five_second_sections'])
    pd.DataFrame(rows).to_csv(OUT / 'recording_metrics.csv', index=False)
    pd.DataFrame(blocks).to_csv(OUT / 'five_second_metrics.csv', index=False)
    pd.DataFrame(pairwise).to_csv(OUT / 'pairwise.csv', index=False)
    pd.DataFrame(spectra).to_csv(OUT / 'spectra.csv', index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), layout='constrained')
    for i, (name, r) in enumerate(records.items(), 1):
        values = np.array([s['vector_ac_rms_g'] for s in r['five_second_sections']]) * 1000
        axes[0].scatter(np.linspace(i - .12, i + .12, 6), values, alpha=.7, color=f'C{i-1}')
        axes[0].scatter(i, r['statistics']['vector_ac_rms_g'] * 1000, marker='D', color='black', s=45)
        axes[1].plot(np.arange(6) * 5 + 2.5, values, marker='o', label=f'Start {i}')
    axes[0].set(xticks=[1, 2, 3], xticklabels=['Start 1', 'Start 2', 'Start 3'],
                ylabel='Vektor-AC-RMS [mg]', title='Schwarz: gesamte 30 s; farbig: je 5 s')
    axes[1].set(xlabel='Abschnittsmitte seit Aufnahmebeginn [s]', ylabel='Vektor-AC-RMS [mg]',
                title='Sechs gleich lange Abschnitte pro Start')
    axes[1].legend()
    for ax in axes:
        ax.grid(alpha=.2)
        ax.ticklabel_format(axis='y', style='plain', useOffset=False)
    fig.suptitle('75 % PWM: drei separate Starts mit jeweils 60-s-Einlauftimer')
    fig.savefig(OUT / 'comparison.png', dpi=180)
    fig.savefig(OUT / 'comparison.pdf')
    plt.close(fig)
    for path, expected in input_hashes.items():
        if digest(ROOT / path) != expected:
            raise RuntimeError('Input changed during analysis')
    print(json.dumps({'output': str(OUT.relative_to(ROOT)),
                      'vector_ac_rms_summary': summary['vector_ac_rms_g'],
                      'actual_first_point_after_setting_s': report['actual_settling_to_first_point_s']}, indent=2))


if __name__ == '__main__':
    main()
