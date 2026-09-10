"""Read-only comparison of all six controlled pilots; no model fitting.

Run after the complete acquisition sequence. Existing inputs and prior analyses
are preserved; output directory must be new. Recording-level repeats and short
within-recording sections are deliberately kept separate.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
OUT = BASE / 'comparison'
sys.path.insert(0, str(ROOT / 'src'))
from fft_pilot import _validate_recording, spectrum

AXES = ['x_g', 'y_g', 'z_g']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def statistics(xyz):
    mean = xyz.mean(axis=0)
    centered = xyz - mean
    std = xyz.std(axis=0, ddof=0)
    rms = np.sqrt(np.mean(centered ** 2, axis=0))
    if not np.allclose(std, rms, rtol=1e-12, atol=1e-15):
        raise ValueError('AC-RMS and population standard deviation disagree')
    result = {'mean_' + axis: float(mean[i]) for i, axis in enumerate(AXES)}
    result.update({'std_' + axis: float(std[i]) for i, axis in enumerate(AXES)})
    result.update({'ac_rms_' + axis: float(rms[i]) for i, axis in enumerate(AXES)})
    result.update({'min_' + axis: float(xyz[:, i].min()) for i, axis in enumerate(AXES)})
    result.update({'max_' + axis: float(xyz[:, i].max()) for i, axis in enumerate(AXES)})
    result['vector_ac_rms_g'] = float(np.sqrt(np.mean(np.sum(centered ** 2, axis=1))))
    result['magnitude_ac_rms_g'] = float(np.std(np.linalg.norm(xyz, axis=1), ddof=0))
    result['mean_vector_norm_g'] = float(np.linalg.norm(mean))
    return result


def load(name, path):
    meta_path = path.with_suffix('.json')
    meta = json.loads(meta_path.read_text())
    if meta['status'] != 'completed' or meta['purpose'] != 'pilot' or meta['csv_sha256'] != digest(path):
        raise ValueError(f'Incomplete/unverified pilot: {path}')
    data = pd.read_csv(path, dtype=str, keep_default_na=False, skip_blank_lines=False)
    xyz, odr, rate = _validate_recording(data, meta, 512)
    ns = data.host_monotonic_ns.to_numpy(dtype=np.int64)
    t = (ns - ns[0]) / 1e9
    stored_time = data.timestamp_s.to_numpy(dtype=float)
    time_error = float(np.max(np.abs((stored_time - stored_time[0]) - t)))
    if time_error > 1e-10:
        raise ValueError('Relative and nanosecond timestamps disagree')
    nominal = data.sensor_time_estimate_s.to_numpy(dtype=float)
    if not np.allclose(nominal, np.arange(len(data)) / odr, rtol=0, atol=1e-12):
        raise ValueError('Nominal sensor-time column differs from documented construction')
    index = np.arange(len(data), dtype=float)
    slope, intercept = np.polyfit(index, t, 1)
    residual = t - (slope * index + intercept)
    intervals_ms = np.diff(ns) / 1e6
    record = {'name': name, 'csv': str(path.relative_to(ROOT)), 'csv_sha256': digest(path),
              'sidecar_sha256': digest(meta_path), 'started_utc': meta['started_at_utc'],
              'finished_utc': meta['finished_at_utc'], 'sensor': meta['sensor'],
              'state': meta['state'], 'pwm_percent': meta['fan_pwm_setpoint_percent'],
              'mounting_id': meta['mounting_id'], 'xyz_points': len(data),
              'individual_axis_values': 3 * len(data), 'requested_duration_s': meta['configured_duration_seconds'],
              'first_to_last_point_s': float(t[-1]), 'timestamp_last_relative_s': float(stored_time[-1]),
              'host_observed_rate_xyz_per_s': rate, 'linear_fit_rate_xyz_per_s': float(1 / slope),
              'nominal_odr_hz': odr, 'rate_difference_percent': float(100 * (rate / odr - 1)),
              'nominal_expected_count_for_requested_duration': odr * meta['configured_duration_seconds'],
              'nominal_sensor_time_last_s': float(nominal[-1]),
              'host_interval_mean_ms': float(intervals_ms.mean()),
              'host_interval_min_ms': float(intervals_ms.min()),
              'host_interval_p50_ms': float(np.median(intervals_ms)),
              'host_interval_p99_ms': float(np.quantile(intervals_ms, .99)),
              'host_interval_max_ms': float(intervals_ms.max()),
              'fit_time_residual_p99_abs_ms': float(np.quantile(np.abs(residual), .99) * 1000),
              'timestamp_representations_max_disagreement_s': time_error,
              'quality_summary': meta['summary'], 'statistics': statistics(xyz), 'five_second_sections': []}
    for start in range(0, 30, 5):
        mask = (t >= start) & (t < start + 5)
        sub_t = t[mask]
        record['five_second_sections'].append({
            'start_s': start, 'end_s': start + 5, 'xyz_points': int(mask.sum()),
            'host_rate_xyz_per_s': float((len(sub_t) - 1) / (sub_t[-1] - sub_t[0])),
            **statistics(xyz[mask])})
    spectral_rows = []
    for i, axis in enumerate(AXES):
        segments = [spectrum(xyz[k:k+512, i], rate) for k in range(0, len(xyz)-511, 256)]
        f = segments[0][0]
        psd = np.mean([s[2] for s in segments], axis=0)
        spectral_rows.extend({'name': name, 'axis': axis, 'frequency_hz': float(freq),
                              'psd_g2_per_hz': float(power)} for freq, power in zip(f, psd))
    return record, spectral_rows


def main():
    if OUT.exists():
        raise FileExistsError('Existing comparison must be preserved')
    sessions = sorted(BASE.glob('measurement_sequence_*.json'))
    if len(sessions) != 1:
        raise ValueError('One completed acquisition session required')
    sequence = json.loads(sessions[0].read_text())
    if sequence['status'] != 'completed' or len(sequence['recordings']) != 3 or 'final_zero_readback' not in sequence:
        raise ValueError('Sequence/final0% incomplete')
    inputs = [('S0', ROOT / 'data/controlled_20260909/standstill_20260909_200838.csv'),
              ('B25_1', ROOT / 'data/controlled_20260909/operating25_20260909_201158.csv'),
              ('B25_2', ROOT / 'data/controlled_20260909/operating25_repeat_20260909_203210.csv')]
    inputs += list(zip(['S1', 'B50_1', 'B50_2'], [ROOT / r['csv'] for r in sequence['recordings']]))
    records, spectra = {}, []
    for name, path in inputs:
        records[name], rows = load(name, path)
        spectra.extend(rows)
    config_keys = ['odr_hz', 'range_g', 'full_resolution', 'acquisition_mode', 'register_readback', 'i2c_clock_configured_hz']
    reference_config = {k: records['S0']['sensor'][k] for k in config_keys}
    if any({k: r['sensor'][k] for k in config_keys} != reference_config for r in records.values()):
        raise ValueError('Sensor configurations differ')
    if len({r['mounting_id'] for r in records.values()}) != 1:
        raise ValueError('Mount identifiers differ')
    groups = {'stillstand': ['S0', 'S1'], 'pwm25': ['B25_1', 'B25_2'], 'pwm50': ['B50_1', 'B50_2']}
    keys = ['mean_' + a for a in AXES] + ['std_' + a for a in AXES] + ['vector_ac_rms_g', 'magnitude_ac_rms_g']
    summaries = {}
    for group, names in groups.items():
        summaries[group] = {'recordings': names, 'metrics': {}}
        for key in keys:
            vals = [records[n]['statistics'][key] for n in names]
            blocks = [section[key] for n in names for section in records[n]['five_second_sections']]
            summaries[group]['metrics'][key] = {'mean_of_recordings': float(np.mean(vals)),
                                               'recording_min': min(vals), 'recording_max': max(vals),
                                               'absolute_repeat_difference': float(np.ptp(vals)),
                                               'five_second_min': min(blocks), 'five_second_max': max(blocks)}
    contrasts = []
    for a, b in [('stillstand', 'pwm25'), ('stillstand', 'pwm50'), ('pwm25', 'pwm50')]:
        for key in keys:
            left, right = summaries[a]['metrics'][key], summaries[b]['metrics'][key]
            difference = right['mean_of_recordings'] - left['mean_of_recordings']
            repeat_range = max(left['absolute_repeat_difference'], right['absolute_repeat_difference'])
            contrasts.append({'a': a, 'b': b, 'metric': key, 'difference_b_minus_a': difference,
                              'largest_within_state_repeat_difference': repeat_range,
                              'difference_exceeds_both_repeat_differences': abs(difference) > repeat_range,
                              'difference_to_repeat_range_ratio': abs(difference) / repeat_range if repeat_range else None,
                              'recording_ranges_overlap': max(left['recording_min'], right['recording_min']) <= min(left['recording_max'], right['recording_max']),
                              'five_second_ranges_overlap': max(left['five_second_min'], right['five_second_min']) <= min(left['five_second_max'], right['five_second_max'])})
    report = {'created_utc': datetime.now(timezone.utc).isoformat(), 'status': 'descriptive_pilot_comparison_no_training',
              'source_script_sha256': digest(Path(__file__)), 'records': records, 'groups': summaries, 'contrasts': contrasts,
              'sensor_configuration_equal': reference_config, 'final_setpoint_percent': 0,
              'final_mechanical_standstill_confirmed': False,
              'definitions': {'std': 'population std(ddof=0), in g; equals axis AC-RMS after own mean removal',
                              'vector_ac_rms_g': 'sqrt(mean(sum((XYZ-mean(XYZ,axis=0))^2,axis=1))); not divided by sqrt(3)',
                              'magnitude_ac_rms_g': 'std(norm(XYZ),ddof=0); separate diagnostic, not vector AC-RMS',
                              'sampling_rate': '(N-1)*1e9/(last_host_ns-first_host_ns); XYZ points/s; independently cross-checked against timestamp_s and linear fit',
                              'five_second_sections': 'non-overlapping host-time sections, each detrended separately; not independent experimental repetitions',
                              'spectra': '512-point symmetric Hann;256-point hop; each segment mean removed; observed host throughput as frequency estimate'},
              'limitations': ['Only two recordings per state; descriptive comparisons, no significance or anomaly detection proof.',
                              'S0 and25% recorded previous day; S1 and50% current day. State/time are partly confounded, despite unchanged declared mounting.',
                              'S1 is not an immediate bracket after previous25% recordings; overnight background constancy is unproven.',
                              'Two50% recordings share one continuous operating episode; they do not establish independent restart repeatability.',
                              'No independent sensor timing or test-fan RPM measured;0% is a setting, not observed final standstill.',
                              'No quality flags does not establish exact zero physically lost samples or alias freedom.'],
              'timing_sources': [{'title': 'ADXL345 datasheet Rev.G', 'url': 'https://www.analog.com/media/en/technical-documentation/data-sheets/adxl345.pdf', 'use': 'FIFO/XYZ access,ODR register and interface constraints'},
                                 {'title': 'Analog Devices staff ChrisM,7Jan2022: ADXL345 sample count and internal clock', 'url': 'https://ez.analog.com/condition-based-monitoring/f/q-a/553781/adxl345---number-of-samples-for-odr---3200', 'use': 'internal RC clock with stated±10% accuracy; DATA_READY recommended for independent timing. Plausible mechanism, not measured cause on this bench.'}]}
    OUT.mkdir()
    (OUT/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    flat = []
    blocks = []
    for name, r in records.items():
        flat.append({k: v for k, v in r.items() if not isinstance(v, (dict, list))} | r['statistics'])
        blocks.extend({'name': name, 'pwm_percent': r['pwm_percent']} | s for s in r['five_second_sections'])
    pd.DataFrame(flat).to_csv(OUT/'recording_metrics.csv', index=False)
    pd.DataFrame(blocks).to_csv(OUT/'five_second_metrics.csv', index=False)
    pd.DataFrame(contrasts).to_csv(OUT/'state_contrasts.csv', index=False)
    pd.DataFrame(spectra).to_csv(OUT/'spectra.csv', index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    names = ['S0', 'S1', 'B25_1', 'B25_2', 'B50_1', 'B50_2']
    colors = ['#35648a']*2 + ['#c96322']*2 + ['#45894b']*2
    for i, (name, color) in enumerate(zip(names, colors)):
        r = records[name]
        block = [s['vector_ac_rms_g']*1000 for s in r['five_second_sections']]
        axes[0].plot([i]*len(block), block, 'o', color=color, alpha=.35, markersize=5)
        axes[0].plot(i, r['statistics']['vector_ac_rms_g']*1000, 'D', color=color, markersize=8)
        axes[1].plot(i, r['host_observed_rate_xyz_per_s'], 'D', color=color)
    axes[0].set(ylabel='Vektor-AC-RMS / mg', title='Raute: Gesamtaufnahme; Kreise: sechs 5-s-Abschnitte')
    axes[1].axhline(200, color='gray', linestyle='--', label='Soll-ODR 200 Hz')
    axes[1].set(ylabel='XYZ-Messpunkte / s', title='Beobachteter FIFO-Durchsatz aus Hostzeit')
    axes[1].legend()
    for ax in axes:
        ax.set_xticks(range(len(names)), names, rotation=25)
        ax.grid(alpha=.25)
    fig.suptitle('Stillstand, 25 % und 50 % PWM – deskriptiver Pilotvergleich\nJe 30 s; gleiche Sensoreinstellungen, Aufnahmen an zwei Tagen')
    fig.savefig(OUT/'comparison.png', dpi=180)
    fig.savefig(OUT/'comparison.pdf')
    plt.close(fig)
    for r in records.values():
        p=ROOT/r['csv']
        if digest(p)!=r['csv_sha256'] or digest(p.with_suffix('.json'))!=r['sidecar_sha256']:
            raise RuntimeError('Raw input changed during analysis')
    print(json.dumps({'output': str(OUT.relative_to(ROOT)), 'records': {n: {'n':r['xyz_points'], 'fs':r['host_observed_rate_xyz_per_s'], 'vector_ac_rms_g':r['statistics']['vector_ac_rms_g']} for n,r in records.items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
