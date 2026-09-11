"""Analyze one300-s startup; own mean removal within each consecutive5-s block."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
OUT = BASE / 'analysis'
HELPER = ROOT / 'results/pwm50_investigation_20260910/analyze_conditions.py'
spec = importlib.util.spec_from_file_location('pilot_numerics', HELPER)
numerics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(numerics)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(values):
    v = np.asarray(values, dtype=float)
    return {'n': len(v), 'mean': float(v.mean()), 'min': float(v.min()), 'max': float(v.max()),
            'range': float(np.ptp(v)), 'population_std': float(v.std()),
            'descriptive_cv_percent': float(100 * v.std() / abs(v.mean())) if v.mean() else None}


def main():
    if OUT.exists():
        raise FileExistsError('Existing analysis must not be overwritten')
    session_path = BASE / 'session.json'
    session = json.loads(session_path.read_text())
    if session.get('status') != 'completed' or session['requested_duration_s'] != 300:
        raise ValueError('One completed300-s capture required')
    if session['final_readback']['pwm_configuration']['configured_duty_percent'] != 0:
        raise ValueError('Final zero not verified')
    path = ROOT / session['csv']
    meta_path = path.with_suffix('.json')
    meta = json.loads(meta_path.read_text())
    if meta['status'] != 'completed' or meta['purpose'] != 'pilot' or digest(path) != meta['csv_sha256']:
        raise ValueError('Incomplete or hash-mismatched pilot')
    df = pd.read_csv(path, dtype=str, keep_default_na=False, skip_blank_lines=False)
    xyz = df[['x_g', 'y_g', 'z_g']].to_numpy(dtype=float)
    ns = df.host_monotonic_ns.to_numpy(dtype=np.int64)
    indices = df.sample_index.to_numpy(dtype=np.int64)
    if not np.isfinite(xyz).all() or not (np.diff(ns) > 0).all():
        raise ValueError('Nonfinite values or nonmonotonic time; automatic block comparison stopped')
    if not np.array_equal(indices, np.arange(len(df))):
        raise ValueError('Stored sample indices not contiguous')
    if len(df) != meta['summary']['samples']:
        raise ValueError('Sample count mismatch')
    flags = {}
    for key in ('gap', 'overrun', 'saturated'):
        values = df[key].str.lower()
        if not values.isin(['true', 'false', '0', '1']).all():
            raise ValueError('Unknown quality flag values')
        flags[key] = values.isin(['true', '1']).to_numpy()
    t = (ns - ns[0]) / 1e9
    timestamp = df.timestamp_s.to_numpy(dtype=float)
    if not np.allclose(timestamp - timestamp[0], t, rtol=0, atol=1e-10):
        raise ValueError('Relative and monotonic timestamp representations disagree')
    odr = meta['sensor']['odr_hz']
    if not np.allclose(df.sensor_time_estimate_s.to_numpy(dtype=float), np.arange(len(df)) / odr, rtol=0, atol=1e-12):
        raise ValueError('Nominal timestamp construction inconsistent')
    dt_ms = np.diff(ns) / 1e6
    rate = (len(df) - 1) * 1e9 / int(ns[-1] - ns[0])
    offset = (int(ns[0]) - meta['pwm_command_completed_monotonic_ns']) / 1e9
    if not np.isclose(offset, session['timing']['first_xyz_after_command_completion_s'], rtol=0, atol=1e-12):
        raise ValueError('Command/sample offset inconsistent')
    blocks = []
    for index in range(60):
        start, end = index * 5, (index + 1) * 5
        mask = (t >= start) & (t < end)
        if int(mask.sum()) < 2:
            raise ValueError('A5-s block contains fewer than two points')
        block_ns = ns[mask]
        counts = {key + '_flagged_points': int(value[mask].sum()) for key, value in flags.items()}
        blocks.append({
            'block': index + 1, 'start_since_first_xyz_s': start, 'end_since_first_xyz_s': end,
            'start_since_command_completion_s': start + offset,
            'end_since_command_completion_s': end + offset,
            'center_since_command_completion_s': (start + end) / 2 + offset,
            'xyz_points': int(mask.sum()),
            'host_rate_xyz_per_s': (int(mask.sum()) - 1) * 1e9 / int(block_ns[-1] - block_ns[0]),
            **numerics.statistics(xyz[mask]), **counts,
            'quality_flags_clear': not any(counts.values()),
        })
    minutes = []
    for index in range(5):
        selected = blocks[index * 12:(index + 1) * 12]
        values = [b['vector_ac_rms_g'] for b in selected]
        slope = np.polyfit([b['center_since_command_completion_s'] for b in selected], values, 1)[0]
        minutes.append({'minute': index + 1, 'start_since_first_xyz_s': index * 60,
                        'end_since_first_xyz_s': (index + 1) * 60,
                        'five_second_vector_ac_rms_g': describe(values),
                        'linear_slope_g_per_minute': float(slope * 60),
                        'flagged_blocks': sum(not b['quality_flags_clear'] for b in selected)})
    intervals = {}
    for start, end in ((0, 30), (30, 60), (0, 60), (60, 120), (120, 180), (180, 240), (240, 300), (60, 300), (180, 300)):
        selected = [b for b in blocks if b['start_since_first_xyz_s'] >= start and b['end_since_first_xyz_s'] <= end]
        vals = [b['vector_ac_rms_g'] for b in selected]
        slope = np.polyfit([b['center_since_command_completion_s'] for b in selected], vals, 1)[0]
        intervals[f'{start}_{end}'] = {'start_since_first_xyz_s': start, 'end_since_first_xyz_s': end,
                                      'five_second_vector_ac_rms_g': describe(vals),
                                      'linear_slope_g_per_minute': float(slope * 60),
                                      'flagged_blocks': sum(not b['quality_flags_clear'] for b in selected)}
    events = [json.loads(line) for line in (BASE / 'fan.jsonl').read_text().splitlines()]
    intent = next(e for e in events if e['event'] == 'sysfs_write_intent' and e.get('value') == 30000)
    readback = next(e for e in events if e['event'] == 'sysfs_write_readback' and e.get('expected') == 30000)
    timing = {**session['timing'], 'duty_write_intent_utc': intent['utc'],
              'duty_write_readback_utc': readback['utc'],
              'duty_write_intent_monotonic_ns': intent['monotonic_ns'],
              'duty_write_readback_monotonic_ns': readback['monotonic_ns'],
              'first_xyz_after_duty_write_intent_s': (int(ns[0]) - intent['monotonic_ns']) / 1e9,
              'first_xyz_after_duty_write_readback_s': (int(ns[0]) - readback['monotonic_ns']) / 1e9}
    quality = {
        'xyz_points': len(df), 'individual_axis_values': 3 * len(df), 'nominal_odr_hz': odr,
        'observed_host_rate_xyz_per_s': rate, 'rate_difference_percent': 100 * (rate / odr - 1),
        'first_to_last_xyz_s': float(t[-1]), 'nonmonotonic_host_intervals': 0,
        'host_interval_p50_ms': float(np.median(dt_ms)), 'host_interval_p99_ms': float(np.quantile(dt_ms, .99)),
        'host_interval_max_ms': float(dt_ms.max()), 'host_intervals_over_two_nominal_periods': int((dt_ms > 2000 / odr).sum()),
        'fifo_depth_max': int(df.fifo_depth.to_numpy(dtype=int).max()),
        **{key + '_flagged_points': int(value.sum()) for key, value in flags.items()},
        'maximum_absolute_axis_g': float(np.abs(xyz).max()), 'lost_samples_exact': None,
        'points_outside_sixty_sections': int((t >= 300).sum()),
        'flagged_five_second_blocks': [b['block'] for b in blocks if not b['quality_flags_clear']],
    }
    for field, name in (('gap', 'gap_flagged_samples'), ('overrun', 'overrun_flagged_samples'), ('saturated', 'saturated_samples')):
        if quality[field + '_flagged_points'] != meta['summary'][name]:
            raise ValueError('Quality count differs from recording summary')
    inputs = {str(f.relative_to(ROOT)): digest(f) for f in (session_path, path, meta_path, BASE / 'fan.jsonl')}
    report = {'created_utc': datetime.now(timezone.utc).isoformat(),
              'status': 'single_300s_startup_descriptive_analysis', 'csv': session['csv'],
              'input_sha256': inputs, 'analysis_source_sha256': digest(Path(__file__)),
              'numerical_helper_sha256': digest(HELPER), 'sensor_configuration': meta['sensor'],
              'timing': timing, 'quality': quality, 'whole_record_statistics': numerics.statistics(xyz),
              'five_second_blocks': blocks, 'minutes': minutes, 'time_intervals': intervals,
              'definitions': {'vector_ac_rms': 'sqrt(mean(sum((XYZ - own_block_axis_means)**2, axis=1)))',
                              'block_axis_std': 'population std(ddof=0)',
                              'block_origin': 'first actual XYZ host read completion; command-offset shown separately',
                              'minute_summary': 'summary of twelve5-s RMS values, not RMS computed after one60-s mean removal',
                              'quality_policy': 'All finite values retained; flags reported per block, no silent exclusion or interpolation',
                              'stabilization': 'descriptive time trend and fluctuations only; no validated pass threshold'},
              'normal_operation_observation': 'reported separately after capture, never inferred from PWM',
              'general_reproducibility_proven': False, 'models_trained': False, 'word_changed': False,
              'final_pwm_setpoint_percent': 0}
    OUT.mkdir()
    with (OUT / 'report.json').open('x') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')
    pd.DataFrame(blocks).to_csv(OUT / 'five_second_rms.csv', index=False)
    pd.DataFrame([{k: v for k, v in minute.items() if not isinstance(v, dict)} |
                  minute['five_second_vector_ac_rms_g'] for minute in minutes]).to_csv(OUT / 'minute_summary.csv', index=False)
    plot(report)
    for filename, expected in inputs.items():
        if digest(ROOT / filename) != expected:
            raise RuntimeError('Input changed during analysis')
    print(json.dumps({'quality': quality, 'timing': timing, 'minutes': minutes, 'intervals': intervals}, indent=2))


def plot(report):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    blocks = report['five_second_blocks']
    t = [b['center_since_command_completion_s'] for b in blocks]
    fig, axes = plt.subplots(2, 1, figsize=(11.8, 7), sharex=True, layout='constrained')
    axes[0].plot(t, [1000 * b['vector_ac_rms_g'] for b in blocks], marker='o', markersize=3.5,
                 label='Vektor-AC-RMS je 5 s', color='C0')
    offset = report['timing']['first_xyz_after_command_completion_s']
    for minute in report['minutes']:
        start, end = minute['start_since_first_xyz_s'] + offset, minute['end_since_first_xyz_s'] + offset
        mean = minute['five_second_vector_ac_rms_g']['mean'] * 1000
        axes[0].hlines(mean, start, end, colors='C1', linewidth=2.5,
                       label='Mittel der 12 Abschnittswerte' if minute['minute'] == 1 else None)
    for axis in 'xyz':
        axes[1].plot(t, [1000 * b[f'ac_rms_{axis}_g'] for b in blocks], label=f'{axis.upper()}-AC-RMS', linewidth=1.3)
    flagged = [b for b in blocks if not b['quality_flags_clear']]
    if flagged:
        axes[0].scatter([b['center_since_command_completion_s'] for b in flagged],
                        [1000 * b['vector_ac_rms_g'] for b in flagged], marker='x', s=65, color='red', label='Qualitätsflag')
    axes[0].set(ylabel='Vektor-AC-RMS [mg]', title='Eigene Achsenmittelwerte in jedem 5-s-Abschnitt entfernt')
    axes[1].set(ylabel='Achsen-AC-RMS [mg]', xlabel='Zeit seit Abschluss des 75-%-PWM-Stellbefehls [s]', xlim=(0, 301))
    for ax in axes:
        ax.grid(alpha=.25)
        ax.legend(loc='best')
        ax.ticklabel_format(axis='y', style='plain', useOffset=False)
    fig.suptitle('75 % PWM bei 25 kHz: einmaliger fünfminütiger Einlaufversuch\n'
                 f'Erster XYZ-Punkt {offset * 1000:.1f} ms nach Befehlsabschluss; nominell 200 Hz')
    fig.savefig(OUT / 'startup_rms.png', dpi=180)
    fig.savefig(OUT / 'startup_rms.pdf')
    plt.close(fig)


if __name__ == '__main__':
    main()
