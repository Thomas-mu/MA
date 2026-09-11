"""Offline spectral comparison; no hardware acquisition or control."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fft_pilot import spectrum, _validate_recording

FIRST = ROOT / 'results/upright_position_v4_sequence_20260911_104025'
FOLLOW = ROOT / 'results/upright_v4_normal_followup_20260911_112731'
SOURCES = {p: FIRST for p in ['standstill', 'normal_before', 'airflow_modified', 'normal_after']}
SOURCES['normal_followup'] = FOLLOW
BANDS = [(0, 10), (10, 30), (30, 60), (60, 90), (90, np.inf)]
NORMALS = ['normal_before', 'normal_after', 'normal_followup']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summed_spectrum(values, fs):
    axis_psd = []
    window = np.hanning(len(values))
    for axis in range(3):
        f, _, density = spectrum(values[:, axis], fs)
        expected = np.sum(((values[:, axis] - values[:, axis].mean()) * window) ** 2) / np.sum(window ** 2)
        assert np.isclose(density.sum() * fs / len(values), expected, rtol=1e-11, atol=1e-18)
        axis_psd.append(density)
    return f, np.asarray(axis_psd)


def band_summary(f, power):
    positive = f > 0
    total = float(power[positive].sum())
    bands = []
    for low, high in BANDS:
        mask = positive & (f >= low) & (f < high)
        energy = float(power[mask].sum())
        bands.append({'low_hz': low, 'high_hz': None if np.isinf(high) else high,
                      'power_g2': energy, 'rms_mg': float(1000 * np.sqrt(energy)),
                      'fraction': energy / total if total else None})
    return bands


def analyze_phase(phase, folder):
    s_path = folder / f'{phase}_session.json'
    session = json.loads(s_path.read_text())
    csv = ROOT / session['csv']; meta_path = csv.with_suffix('.json')
    meta = json.loads(meta_path.read_text())
    assert session['status'] == meta['status'] == 'completed'
    assert meta['purpose'] == 'pilot' and sha(csv) == meta['csv_sha256']
    assert session['mounting_id'] == 'fan_upright_position_v4_20260911_103726'
    assert session['sensor'] == meta['sensor']
    d = pd.read_csv(csv, dtype=str, keep_default_na=False, skip_blank_lines=False)
    xyz, nominal, fs = _validate_recording(d, meta, 1024)
    ns = d.host_monotonic_ns.to_numpy(dtype=np.int64)
    origin = session['record_invoked_monotonic_ns'] if phase == 'standstill' else session['command_invocation_monotonic_ns']
    times = (ns - origin) / 1e9
    low, high = (0, 30) if phase == 'standstill' else (180, 300)
    selected = xyz[(times >= low) & (times < high)]
    starts = list(range(0, len(selected) - 1024 + 1, 512))
    assert starts
    values = [summed_spectrum(selected[i:i + 1024], fs) for i in starts]
    frequencies = values[0][0]
    psd_axes = np.mean([v[1] for v in values], axis=0)
    psd = psd_axes.sum(axis=0)
    df = fs / 1024; power = psd * df
    peak_candidates = [i for i in range(1, len(psd) - 1) if frequencies[i] >= 1 and psd[i] >= psd[i-1] and psd[i] > psd[i+1]]
    chosen = []
    for i in sorted(peak_candidates, key=lambda i: psd[i], reverse=True):
        if all(abs(frequencies[i] - frequencies[j]) >= 1 for j in chosen):
            chosen.append(i)
        if len(chosen) == 5:
            break
    rows = []
    for start in range(0, 30 if phase == 'standstill' else 300, 5):
        a = xyz[(times >= start) & (times < start + 5)]
        f, axis_density = summed_spectrum(a, fs)
        density = axis_density.sum(axis=0); p = density * fs / len(a)
        peak = np.flatnonzero(f >= 1)[np.argmax(density[f >= 1])]
        row = {'phase': phase, 'start_s': start, 'end_s': start + 5, 'xyz_points': len(a),
               'vector_ac_rms_mg': float(1000 * np.sqrt(a.var(axis=0).sum())),
               'hann_psd_rms_mg': float(1000 * np.sqrt(p.sum())), 'largest_psd_bin_hz': float(f[peak])}
        for i, band in enumerate(band_summary(f, p)):
            row[f'band_{i}_power_g2'] = band['power_g2']; row[f'band_{i}_fraction'] = band['fraction']
        rows.append(row)
    result = {'phase': phase, 'mounting_id': session['mounting_id'], 'sensor': meta['sensor'],
              'primary_interval_s': [low, high], 'nominal_odr_hz': nominal, 'observed_rate_hz': fs,
              'nominal_frequency_factor': nominal / fs, 'segment_samples': 1024, 'overlap_samples': 512,
              'segments': len(starts), 'segment_duration_s': 1024/fs, 'frequency_bin_spacing_hz': df,
              'selected_xyz_points': len(selected), 'tail_points_not_in_complete_fft_segment': len(selected) - starts[-1] - 1024,
              'hann_psd_rms_mg': float(1000*np.sqrt(power.sum())),
              'mean_5s_ac_rms_mg': float(np.mean([row['vector_ac_rms_mg'] for row in rows if row['start_s'] >= low])),
              'bands': band_summary(frequencies, power),
              'largest_separated_local_psd_bins': [{'frequency_hz': float(frequencies[i]), 'nominal_scaled_hz': float(frequencies[i] * nominal/fs), 'density_g2_per_hz': float(psd[i])} for i in chosen],
              'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in [csv, meta_path, s_path]}}
    return result, frequencies, psd_axes, rows


def main():
    out = BASE / 'analysis'
    if out.exists():
        raise FileExistsError('No overwrite of existing spectral analysis')
    values = {phase: analyze_phase(phase, folder) for phase, folder in SOURCES.items()}
    assert all(v[0]['sensor'] == values['standstill'][0]['sensor'] for v in values.values())
    normal_masks = [(v[1] >= 1) & (v[1] < 90) for p, v in values.items() if p != 'standstill']
    assert all(np.array_equal(m, normal_masks[0]) for m in normal_masks)
    mask = normal_masks[0]
    pairs = []
    operating = [p for p in SOURCES if p != 'standstill']
    for index, left in enumerate(operating):
        for right in operating[index + 1:]:
            a = values[left][2].sum(axis=0)[mask]; b = values[right][2].sum(axis=0)[mask]
            a, b = a/a.sum(), b/b.sum()
            pairs.append({'left': left, 'right': right,
                          'cosine_normalized_shape_1_90hz': float(a@b / np.sqrt((a@a)*(b@b))),
                          'total_variation_normalized_shape_1_90hz': float(.5*np.abs(a-b).sum()),
                          'max_frequency_bin_mismatch_hz': float(np.max(np.abs(values[left][1][mask]-values[right][1][mask]))),
                          'note': 'Same FFT bin indices; observed frequency grids differ slightly. No interpolation, classification threshold, or inference of significance.'})
    out.mkdir()
    for phase, (r, f, axes, rows) in values.items():
        with (out / f'{phase}_summary.json').open('x') as handle:
            json.dump(r, handle, indent=2, ensure_ascii=False, allow_nan=False)
        frame = pd.DataFrame({'frequency_hz_observed': f, 'frequency_hz_nominal': f*200/r['observed_rate_hz'],
                              'psd_x_g2_per_hz': axes[0], 'psd_y_g2_per_hz': axes[1],
                              'psd_z_g2_per_hz': axes[2], 'summed_xyz_psd_g2_per_hz': axes.sum(axis=0)})
        frame.to_csv(out / f'{phase}_spectra.csv', index=False)
        pd.DataFrame(rows).to_csv(out / f'{phase}_five_second_spectral_bands.csv', index=False)
    result = {'created_utc': datetime.now(timezone.utc).isoformat(),
              'phases': {p: v[0] for p, v in values.items()}, 'shape_comparisons': pairs,
              'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__), ROOT/'src/fft_pilot.py']},
              'limitations': ['No independently measured sensor conversion times or RPM.',
                              'Aliasing and useful bandwidth are not validated by these spectra.',
                              'Three normal starts and one plate state are descriptive pilot data.',
                              'Overlapping FFT segments and adjacent windows are not independent repetitions.',
                              'Hann-weighted spectral RMS is not numerically identical to unweighted 5-s AC-RMS.'],
              'models_trained': False, 'hardware_commands_sent': []}
    with (out / 'comparison.json').open('x') as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False, allow_nan=False)
    for phase, v in values.items():
        assert all(sha(ROOT/p)==h for p,h in v[0]['input_sha256'].items())
    print(json.dumps({'phase_peaks_and_bands': {p: {'peaks': v[0]['largest_separated_local_psd_bins'], 'bands': v[0]['bands']} for p,v in values.items()}, 'shape_comparisons': pairs}, indent=2))


if __name__ == '__main__':
    main()
