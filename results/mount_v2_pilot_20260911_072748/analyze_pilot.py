"""Read-only analysis of the four new-mount pilot recordings; no model fitting."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
AXES = ('x', 'y', 'z')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(values):
    v = np.asarray(values, dtype=float)
    return dict(n=len(v), mean=float(v.mean()), minimum=float(v.min()),
                maximum=float(v.max()), range=float(np.ptp(v)),
                population_std=float(v.std(ddof=0)),
                descriptive_cv_percent=float(100 * v.std(ddof=0) / abs(v.mean())) if v.mean() else None)


def statistics(xyz):
    means = xyz.mean(axis=0)
    centered = xyz - means
    std = xyz.std(axis=0, ddof=0)
    ac = np.sqrt(np.mean(centered ** 2, axis=0))
    vector = float(np.sqrt(np.mean(np.sum(centered ** 2, axis=1))))
    if not np.allclose(std, ac, rtol=1e-12, atol=1e-15) or not np.isclose(vector, np.linalg.norm(std), rtol=1e-12):
        raise ValueError('AC-RMS identity failed')
    result = {'vector_ac_rms_g': vector}
    for i, axis in enumerate(AXES):
        result.update({f'mean_{axis}_g': float(means[i]), f'std_{axis}_g': float(std[i]),
                       f'ac_rms_{axis}_g': float(ac[i])})
    return result


def load(name, relative, duration, pwm, mounting_id):
    path = ROOT / relative
    meta_path = path.with_suffix('.json')
    meta = json.loads(meta_path.read_text())
    if (meta['status'] != 'completed' or meta['purpose'] != 'pilot'
            or meta['csv_sha256'] != digest(path) or meta['mounting_id'] != mounting_id
            or meta['configured_duration_seconds'] != duration
            or meta['fan_pwm_setpoint_percent'] != pwm or meta['fan_pwm_frequency_hz'] != 25000):
        raise ValueError(f'Incomplete or inconsistent input: {relative}')
    df = pd.read_csv(path, dtype=str, keep_default_na=False, skip_blank_lines=False)
    xyz = df[[f'{a}_g' for a in AXES]].to_numpy(dtype=float)
    ns = df.host_monotonic_ns.to_numpy(dtype=np.int64)
    if len(df) < 2 or len(df) != meta['summary']['samples'] or not np.isfinite(xyz).all():
        raise ValueError('Invalid XYZ values or sample count')
    if not (np.diff(ns) > 0).all():
        raise ValueError('Nonmonotonic timestamps; automatic section analysis stopped')
    if not np.array_equal(df.sample_index.to_numpy(dtype=np.int64), np.arange(len(df))):
        raise ValueError('Noncontiguous stored sample indices')
    t = (ns - ns[0]) / 1e9
    recorded_t = df.timestamp_s.to_numpy(dtype=float)
    time_error = float(np.max(np.abs(recorded_t - recorded_t[0] - t)))
    if time_error > 1e-10:
        raise ValueError('Relative and monotonic timestamp representations disagree')
    odr = meta['sensor']['odr_hz']
    if not np.allclose(df.sensor_time_estimate_s.to_numpy(dtype=float), np.arange(len(df)) / odr, atol=1e-12, rtol=0):
        raise ValueError('Nominal sensor-time estimate inconsistent')
    flags = {}
    for field in ('gap', 'overrun', 'saturated'):
        text = df[field].str.lower()
        if not text.isin(['true', 'false', '0', '1']).all():
            raise ValueError('Unknown quality flag value')
        flags[field] = text.isin(['true', '1']).to_numpy()
    for field, key in (('gap', 'gap_flagged_samples'), ('overrun', 'overrun_flagged_samples'), ('saturated', 'saturated_samples')):
        if int(flags[field].sum()) != meta['summary'][key]:
            raise ValueError('Quality counts differ from sidecar')
    dt_ms = np.diff(ns) / 1e6
    read_ms = df.read_duration_ns.to_numpy(dtype=np.int64) / 1e6
    if (read_ms < 0).any():
        raise ValueError('Negative host read duration')
    rate = (len(df) - 1) * 1e9 / int(ns[-1] - ns[0])
    if not np.isclose(rate, meta['summary']['observed_host_rate_hz'], atol=1e-10, rtol=0):
        raise ValueError('Recomputed throughput differs from sidecar')
    intervals = np.r_[np.nan, dt_ms]
    sections = []
    for start in range(0, duration, 5):
        mask = (t >= start) & (t < start + 5)
        sub_ns = ns[mask]
        if len(sub_ns) < 2:
            raise ValueError('Insufficient data in a five-second section')
        counts = {f'{key}_flagged_points': int(value[mask].sum()) for key, value in flags.items()}
        sections.append(dict(name=name, start_s=start, end_s=start + 5,
                             xyz_points=int(mask.sum()), observed_span_s=float((sub_ns[-1] - sub_ns[0]) / 1e9),
                             observed_rate_xyz_per_s=(len(sub_ns) - 1) * 1e9 / int(sub_ns[-1] - sub_ns[0]),
                             host_interval_max_ms=float(np.nanmax(intervals[mask])),
                             host_intervals_over_10ms=int((intervals[mask] > 10).sum()),
                             quality_flags_clear=not any(counts.values()), **counts, **statistics(xyz[mask])))
    long_intervals = [dict(ending_sample_index=int(i + 1), end_since_first_xyz_s=float(t[i + 1]),
                          interval_ms=float(dt_ms[i]), fifo_depth=int(df.fifo_depth.iloc[i + 1]),
                          **{k: bool(v[i + 1]) for k, v in flags.items()})
                      for i in np.flatnonzero(dt_ms > 10)]
    return dict(name=name, csv=relative, csv_sha256=digest(path), sidecar_sha256=digest(meta_path),
                started_utc=meta['started_at_utc'], finished_utc=meta['finished_at_utc'],
                requested_duration_s=duration, pwm_setpoint_percent=pwm, sensor=meta['sensor'],
                mounting_id=mounting_id, first_xyz_monotonic_ns=int(ns[0]), last_xyz_monotonic_ns=int(ns[-1]),
                quality=dict(xyz_points=len(df), individual_axis_values=3 * len(df), nominal_odr_hz=odr,
                             observed_rate_xyz_per_s=rate, rate_difference_percent=100 * (rate / odr - 1),
                             first_to_last_xyz_s=float(t[-1]), nonmonotonic_intervals=0,
                             timestamp_representations_max_error_s=time_error,
                             host_interval_min_ms=float(dt_ms.min()), host_interval_median_ms=float(np.median(dt_ms)),
                             host_interval_p99_ms=float(np.quantile(dt_ms, .99)), host_interval_max_ms=float(dt_ms.max()),
                             host_intervals_over_10ms=len(long_intervals),
                             read_duration_median_ms=float(np.median(read_ms)), read_duration_p99_ms=float(np.quantile(read_ms, .99)),
                             read_duration_max_ms=float(read_ms.max()), fifo_depth_max=int(df.fifo_depth.to_numpy(dtype=int).max()),
                             **{f'{k}_flagged_points': int(v.sum()) for k, v in flags.items()},
                             maximum_absolute_axis_g=float(np.abs(xyz).max()), lost_samples_exact=None,
                             points_outside_sections=int((t >= duration).sum()),
                             consecutive_identical_xyz_fraction=float((np.diff(xyz, axis=0) == 0).all(axis=1).mean())),
                statistics=statistics(xyz), five_second_sections=sections, host_intervals_over_10ms=long_intervals)


def main():
    before_path, session_path, after_path = (BASE / f for f in ('before_session.json', 'session.json', 'after_session.json'))
    before = json.loads(before_path.read_text())
    session = json.loads(session_path.read_text())
    if before['status'] != 'completed' or len(before['recordings']) != 2 or session['status'] != 'completed':
        raise ValueError('Two completed initial references and completed operating session required')
    if session['final_readback']['pwm_configuration']['configured_duty_percent'] != 0:
        raise ValueError('Operating session has not verified final zero')
    mounting_id = json.loads((BASE / 'mounting_version_initial.json').read_text())['mounting_id']
    records = [load(f'S_vor_{i + 1}', rec['csv'], 30, 0, mounting_id) for i, rec in enumerate(before['recordings'])]
    operating = load('B75_300s', session['csv'], 300, 75, mounting_id)
    records.append(operating)
    after = json.loads(after_path.read_text()) if after_path.exists() else None
    if after is not None:
        if after['status'] != 'completed' or len(after['recordings']) != 1:
            raise ValueError('Closing reference incomplete')
        records.append(load('S_nach', after['recordings'][0]['csv'], 30, 0, mounting_id))
    if any(r['sensor'] != records[0]['sensor'] for r in records):
        raise ValueError('Sensor configuration differs between recordings')
    out = BASE / ('analysis' if after else 'analysis_before_closing_reference')
    if out.exists():
        raise FileExistsError('Previous analysis must remain unchanged')
    blocks = operating['five_second_sections']
    minutes = [dict(minute=i + 1, vector_ac_rms_g=describe([b['vector_ac_rms_g'] for b in blocks[12*i:12*(i+1)]])) for i in range(5)]
    periods = {}
    for start, end in ((0, 30), (30, 60), (60, 120), (120, 180), (180, 240), (240, 300), (60, 300), (180, 300)):
        selected = [b for b in blocks if start <= b['start_s'] and b['end_s'] <= end]
        values = [b['vector_ac_rms_g'] for b in selected]
        periods[f'{start}_{end}'] = dict(five_second_rms_g=describe(values),
                                       descriptive_slope_g_per_minute=float(60*np.polyfit([b['start_s'] + 2.5 for b in selected], values, 1)[0]))
    reference_records = [r for r in records if r['pwm_setpoint_percent'] == 0]
    reference_values = [b['vector_ac_rms_g'] for r in reference_records for b in r['five_second_sections']]
    pre_values = [r['statistics']['vector_ac_rms_g'] for r in records[:2]]
    comparisons = dict(before_full_record_rms_g=pre_values, before_absolute_repeat_difference_g=abs(pre_values[1] - pre_values[0]),
                       before_repeat_difference_percent_of_mean=100 * abs(pre_values[1] - pre_values[0]) / np.mean(pre_values),
                       standstill_five_second_rms_g=describe(reference_values),
                       operating_blocks_within_standstill_minmax=[b['start_s'] for b in blocks if min(reference_values) <= b['vector_ac_rms_g'] <= max(reference_values)],
                       minimum_operating_to_maximum_standstill_block_ratio=min(b['vector_ac_rms_g'] for b in blocks) / max(reference_values))
    if after:
        last = records[-1]['statistics']
        comparisons.update(after_full_record_rms_g=last['vector_ac_rms_g'],
                           after_minus_before_mean_g=last['vector_ac_rms_g'] - float(np.mean(pre_values)),
                           after_change_percent=100 * (last['vector_ac_rms_g'] / float(np.mean(pre_values)) - 1),
                           after_minus_before_axis_means_g={a: last[f'mean_{a}_g'] - float(np.mean([r['statistics'][f'mean_{a}_g'] for r in records[:2]])) for a in AXES})
    events = [json.loads(line) for line in (BASE / 'fan.jsonl').read_text().splitlines()]
    intent = next(e for e in events if e['event'] == 'sysfs_write_intent' and e.get('value') == 30000)
    readback = next(e for e in events if e['event'] == 'sysfs_write_readback' and e.get('expected') == 30000)
    first = operating['first_xyz_monotonic_ns']
    timing = {**session['timing'], 'command_invocation_utc': session['command_invocation_utc'],
              'command_completed_utc': session['command_completed_utc'], 'zero_command_completed_utc': session['zero_command_completed_utc'],
              'first_xyz_after_duty_write_intent_s': (first - intent['monotonic_ns']) / 1e9,
              'first_xyz_after_duty_write_readback_s': (first - readback['monotonic_ns']) / 1e9}
    inputs = {str(p.relative_to(ROOT)): digest(p) for p in (before_path, session_path, BASE/'fan.jsonl', BASE/'safety_confirmation.json')}
    if after:
        inputs.update({str(p.relative_to(ROOT)): digest(p) for p in (after_path, BASE/'after_standstill_confirmation.json')})
    for r in records:
        p = ROOT / r['csv']
        inputs.update({r['csv']: r['csv_sha256'], str(p.with_suffix('.json').relative_to(ROOT)): r['sidecar_sha256']})
    report = dict(created_utc=datetime.now(timezone.utc).isoformat(), mounting_id=mounting_id,
                  status='complete_pilot_descriptive_analysis' if after else 'provisional_closing_reference_pending',
                  records=records, operating_minutes=minutes, operating_periods=periods, comparisons=comparisons,
                  timing=timing, input_sha256=inputs, source_sha256=digest(Path(__file__)),
                  old_measurement_values_used=False, trained_models=False, induced_anomalies=False,
                  general_reproducibility_proven=False, final_pwm_setpoint_percent=0,
                  closing_mechanical_standstill_confirmed=bool(after),
                  definitions={'vector_ac_rms':'sqrt(mean(sum((XYZ - own_section_axis_means)**2, axis=1)))',
                               'axis_std':'population standard deviation, ddof=0',
                               'five_second_origin':'first acquired XYZ host timestamp; command offset documented separately',
                               'minute_statistics':'distribution of twelve five-second RMS values, not a single sixty-second detrending',
                               'quality':'finite points retained, no interpolation, no silent exclusion of flagged points',
                               'timestamps':'host read completion; not measured sensor conversion time',
                               'reference_repetitions':'two before, one after; sections are not independent startup repeats'})
    out.mkdir()
    with (out/'report.json').open('x') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, allow_nan=False)
    pd.DataFrame([b for r in records for b in r['five_second_sections']]).to_csv(out/'five_second_sections.csv', index=False)
    pd.DataFrame([dict(name=r['name'], **r['quality'], **r['statistics']) for r in records]).to_csv(out/'recording_summary.csv', index=False)
    plot(report, out)
    for name, expected in inputs.items():
        if digest(ROOT/name) != expected:
            raise RuntimeError('Input changed during analysis')
    print(json.dumps({'out':str(out.relative_to(ROOT)), 'records':[{k:r[k] for k in ('name','quality','statistics')} for r in records],
                      'minutes':minutes, 'comparisons':comparisons, 'timing':timing}, indent=2))


def plot(report, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    operation = next(r for r in report['records'] if r['pwm_setpoint_percent'] == 75)
    refs = [r for r in report['records'] if r['pwm_setpoint_percent'] == 0]
    blocks = operation['five_second_sections']
    offset = report['timing']['first_xyz_after_command_completion_s']
    time = [b['start_s'] + 2.5 + offset for b in blocks]
    fig, axes = plt.subplots(3, 1, figsize=(11.8, 10), layout='constrained')
    axes[0].plot(time, [1000*b['vector_ac_rms_g'] for b in blocks], 'o-', markersize=3, label='Vektor-AC-RMS je 5 s')
    values = [b['vector_ac_rms_g']*1000 for r in refs for b in r['five_second_sections']]
    axes[0].axhspan(min(values), max(values), color='gray', alpha=.25, label='Bereich der neuen Stillstandsabschnitte')
    for m in report['operating_minutes']:
        axes[0].hlines(m['vector_ac_rms_g']['mean']*1000, (m['minute']-1)*60+offset, m['minute']*60+offset,
                       color='C1', lw=2, label='Mittel der 12 Abschnittswerte' if m['minute']==1 else None)
    flagged = [b for b in blocks if not b['quality_flags_clear']]
    if flagged:
        axes[0].scatter([b['start_s']+2.5+offset for b in flagged], [1000*b['vector_ac_rms_g'] for b in flagged],
                        marker='x', color='red', label='Qualitätsflag', zorder=5)
    for a in AXES:
        axes[1].plot(time, [1000*b[f'ac_rms_{a}_g'] for b in blocks], label=a.upper())
    for ax in axes[:2]:
        ax.set(xlim=(0,301), xlabel='Zeit seit Abschluss des 75-%-PWM-Stellbefehls [s]')
    axes[0].set(ylabel='Vektor-AC-RMS [mg]', title='Einmaliger 300-s-Betrieb; eigene Achsenmittelwerte je Abschnitt entfernt')
    axes[1].set(ylabel='Achsen-AC-RMS [mg]', title='Achsenbeiträge desselben Betriebslaufs')
    for i,r in enumerate(refs):
        b = r['five_second_sections']
        axes[2].plot(np.arange(6)*5+2.5, [1000*x['vector_ac_rms_g'] for x in b], 'o-', label=r['name'])
    axes[2].set(xlabel='Zeit seit erstem XYZ-Punkt der jeweiligen Stillstandsaufnahme [s]',
                ylabel='Vektor-AC-RMS [mg]', title='Separate Stillstandsreferenzen der neuen Montage, je 30 s', xlim=(0,30))
    for ax in axes:
        ax.grid(alpha=.25)
        ax.legend(loc='best')
    suffix = '' if report['closing_mechanical_standstill_confirmed'] else ' – Schlussreferenz noch ausstehend'
    fig.suptitle('Neue vorläufige Schraubbefestigung: 75 % PWM, 25 kHz, nominell 200 Hz'+suffix+'\n'
                 f'Erster XYZ-Punkt {offset*1000:.2f} ms nach Befehlsabschluss; ein Betriebslauf, kein Reproduzierbarkeitsnachweis', fontsize=11)
    fig.savefig(out/'pilot_rms.png', dpi=180)
    fig.savefig(out/'pilot_rms.pdf')
    plt.close(fig)


if __name__ == '__main__':
    main()
