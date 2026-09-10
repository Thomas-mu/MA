"""Neue Drei-Aufnahmen-Auswertung; Erstberichte bleiben unverändert."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
PAIR = OUT.parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(PAIR))
sys.path.insert(0, str(ROOT / 'src'))
import analyze_pair
from fft_pilot import spectrum

NAMES = ['standstill', 'operating25', 'operating25_repeat']
LABELS = ['S₀: Stillstand', 'B₁: 25 % PWM', 'B₁-Wiederholung: 25 % PWM']
COLORS = ['#35648a', '#c96322', '#45894b']
CANDIDATES = [('x_g', 54.53960990461015), ('x_g', 71.50748854159997), ('y_g', 23.027835293057617)]


def main():
    if (OUT / 'three_recordings.json').exists():
        raise FileExistsError('Preserve completed reports')
    initial = json.loads((PAIR / 'paired_report.json').read_text())
    records = dict(initial['records'])
    spectra = {n: pd.read_csv(PAIR / (n + '_fft') / 'spectra.csv') for n in NAMES[:2]}
    repeat = ROOT / 'data/controlled_20260909/operating25_repeat_20260909_203210.csv'
    analyze_pair.OUT = OUT
    records[NAMES[2]], spectra[NAMES[2]] = analyze_pair.load_recording(NAMES[2], repeat)
    hashes = {str(path.relative_to(ROOT)): analyze_pair.digest(path)
              for r in records.values() for path in [ROOT / r['input_csv'], (ROOT / r['input_csv']).with_suffix('.json')]}
    # Check both originals against immutable first-analysis provenance.
    for name in NAMES[:2]:
        for path, expected in records[name]['hashes'].items():
            assert hashes[path] == expected
    bands = {}
    for band in analyze_pair.BANDS:
        bands[band] = {}
        for name in NAMES[1:]:
            bands[band][name] = {}
            for axis in analyze_pair.AXES + ['xyz_sum']:
                baseline = records[NAMES[0]]['band_power_g2'][band][axis]
                operating = records[name]['band_power_g2'][band][axis]
                bands[band][name][axis] = {
                    'operating_to_S0_db': float(10 * np.log10(operating / baseline)),
                    'conditional_excess_snr_db': float(10 * np.log10((operating - baseline) / baseline)) if operating > baseline else None,
                    'excess_power_g2': operating - baseline}
    sections = {}
    for name in NAMES:
        d = pd.read_csv(ROOT / records[name]['input_csv'])
        t = d.host_monotonic_ns.to_numpy(dtype=np.int64)
        t = (t - t[0]) / 1e9
        sections[name] = {}
        for axis in analyze_pair.AXES:
            results = []
            for start in range(0, 30, 5):
                mask = (t >= start) & (t < start + 5)
                values = d.loc[mask, axis].to_numpy()
                local_t = t[mask]
                fs = (len(values) - 1) / (local_t[-1] - local_t[0])
                windows = [spectrum(values[i:i+512], fs) for i in range(0, len(values)-512+1, 256)]
                results.append((windows[0][0], np.mean([w[2] for w in windows], axis=0)))
            sections[name][axis] = results
    candidates = []
    for axis, center in CANDIDATES:
        item = {'axis': axis, 'fixed_candidate_frequency_hz': center,
                'fixed_band_hz': [center - .8, center + .8], 'recordings': {}}
        baseline = spectra[NAMES[0]].query('axis == @axis')
        baseline_power = analyze_pair.integrate_band(baseline.frequency_hz.to_numpy(), baseline.mean_psd_g2_per_hz.to_numpy(), center - .8, center + .8)
        for name in NAMES:
            s = spectra[name].query('axis == @axis')
            f, p = s.frequency_hz.to_numpy(), s.mean_psd_g2_per_hz.to_numpy()
            power = analyze_pair.integrate_band(f, p, center - .8, center + .8)
            band_mask = np.abs(f - center) <= .8
            peak_i = np.where(band_mask)[0][np.argmax(p[band_mask])]
            neighborhood = (np.abs(f - center) <= 5) & (np.abs(f - center) >= 1.2)
            result = {'power_g2': power, 'ratio_to_full_S0_db': float(10 * np.log10(power / baseline_power)),
                      'local_peak_hz': float(f[peak_i]),
                      'local_peak_to_neighbor_median_db': float(10 * np.log10(p[peak_i] / np.median(p[neighborhood]))),
                      'five_second_sections': []}
            for i, (f, p) in enumerate(sections[name][axis]):
                power = analyze_pair.integrate_band(f, p, center - .8, center + .8)
                band_mask = np.abs(f - center) <= .8
                peak_i = np.where(band_mask)[0][np.argmax(p[band_mask])]
                result['five_second_sections'].append({'start_seconds': i * 5,
                                                       'power_g2': power,
                                                       'ratio_to_full_S0_db': float(10 * np.log10(power / baseline_power)),
                                                       'local_peak_hz': float(f[peak_i])})
            item['recordings'][name] = result
        candidates.append(item)
    report = {'purpose': 'provisional_repeatability_diagnostic_pending_S1',
              'source_script_sha256': analyze_pair.digest(Path(__file__)),
              'source_hashes': hashes, 'records': records,
              'bands': bands, 'fixed_candidates': candidates,
              'method': 'Same validated 512-sample Hann PSD and common endpoint integration as initial paired report. Fixed candidates and ±0.8 Hz bands inherited from first operating recording; no search or retuning on repeat. Five-second sections include section-specific mean removal and observed host-rate frequency axis.',
              'S1_state': 'not_yet_recorded_pending_operator_visual_standstill_confirmation',
              'recommendation': 'No final measurement-parameter or training release from three recordings; complete confirmed S1 to assess whether background changed. Negative conditional excess SNR alone is not proof of absence of signal.',
              'limitations': ['Separate temporal repeat at one operating point, not independent population replication.',
                              'S0 is the sole reference; evolving background and temporal effects remain confounded with operation until S1.',
                              'No measured RPM and no physical assignment of candidate frequencies.',
                              'No established useful band, anti-alias validation or formal acceptance limits.',
                              'No changes to measurement parameters, model, scaler or thresholds.']}
    for path, expected in hashes.items():
        assert analyze_pair.digest(ROOT / path) == expected
    (OUT / 'three_recordings.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    fig, panels = plt.subplots(2, 2, figsize=(11.7, 8.3), constrained_layout=True)
    for axis, panel in zip(analyze_pair.AXES, panels.flat):
        for name, label, color in zip(NAMES, LABELS, COLORS):
            s = spectra[name].query('axis == @axis')
            panel.semilogy(s.frequency_hz, s.mean_psd_g2_per_hz, label=label, color=color, alpha=.8)
        panel.set(xlabel='Frequenz / Hz (FIFO-Durchsatz)', ylabel='PSD / g² Hz⁻¹', title=axis[0].upper() + '-Achse', xlim=(0, 105))
        panel.grid(alpha=.25)
    for name, label, color in zip(NAMES, LABELS, COLORS):
        r = records[name]['five_second_sections']
        panels[1, 1].plot([s['start_seconds'] + 2.5 for s in r], [s['vector_ac_rms_g'] * 1000 for s in r], 'o-', label=label, color=color)
    panels[1, 1].set(xlabel='Zeit in jeweiliger Aufnahme / s', ylabel='Vektor-AC-RMS / mg', title='5-s-Abschnitte')
    panels[1, 1].legend(fontsize=8)
    panels[1, 1].grid(alpha=.25)
    panels[0, 0].legend(fontsize=8)
    fig.suptitle('Vorläufige Wiederholungsprüfung: S₀, B₁ und B₁-Wiederholung\nJe 30 s, 200 Hz Soll-ODR, ±2 g; nachfolgender Stillstand S₁ steht aus', fontsize=12)
    fig.savefig(OUT / 'three_recordings.png', dpi=180)
    fig.savefig(OUT / 'three_recordings.pdf')
    plt.close(fig)
    rows = ['# Vorläufige Wiederholungsprüfung: drei Aufnahmen', '',
            'Die bestehenden Erstberichte bleiben unverändert. Diese Ergänzung vergleicht S₀, B₁ und die bei unveränderten 25 % PWM aufgenommene B₁-Wiederholung. S₁ ist noch nicht aufgenommen; die neue Sichtbestätigung des Stillstands steht aus. Keine Drehzahlmessung liegt vor.', '',
            '| Kennwert | S₀ | B₁ | B₁-Wiederholung |', '|---|---:|---:|---:|']
    for label, getter, fmt in [
        ('Samples', lambda r: r['timing']['samples'], '.0f'),
        ('FIFO-Durchsatz / Hz', lambda r: r['timing']['host_observed_fifo_rate_hz'], '.3f'),
        ('Größtes Hostintervall / ms', lambda r: r['timing']['host_interval_max_ms'], '.3f'),
        ('Vektor-AC-RMS / g', lambda r: r['statistics']['vector_ac_rms_g'], '.6f'),
        ('AC-RMS des Betrags / g', lambda r: r['statistics']['magnitude_ac_rms_g'], '.6f'),
    ]:
        rows.append('| ' + label + ' | ' + ' | '.join(f'{getter(records[n]):{fmt}}' for n in NAMES) + ' |')
    rows.extend(['', 'Alle drei Aufnahmen erfüllen die implementierten Eingangsprüfungen: abgeschlossene FIFO-Erfassung, verifizierter CSV-Hash, gültige lückenlose Sampleindizes und keine gesetzten Qualitätsflags. Diese technische Qualität bestätigt noch keine ausreichende Trennung von Nutzsignal und Hintergrund.', '',
                 '| Diagnoseband / XYZ-Summe | B₁ relativ S₀ | B₁-Wiederholung relativ S₀ |', '|---|---:|---:|'])
    for band, limits in analyze_pair.BANDS.items():
        rows.append(f'| {limits[0]:g}–{limits[1]:g} Hz | {bands[band][NAMES[1]]["xyz_sum"]["operating_to_S0_db"]:.3f} dB | {bands[band][NAMES[2]]["xyz_sum"]["operating_to_S0_db"]:.3f} dB |')
    rows.extend(['', '| Fester Kandidat, ±0,8 Hz | B₁ relativ S₀ | Wiederholung relativ S₀ | 5-s-Bereich S₀ relativ eigenem Gesamtmittel | 5-s-Bereich Wiederholung relativ S₀ |', '|---|---:|---:|---:|---:|'])
    for c in candidates:
        vals = {n: [s['ratio_to_full_S0_db'] for s in c['recordings'][n]['five_second_sections']] for n in NAMES}
        rows.append(f'| {c["axis"][0].upper()} {c["fixed_candidate_frequency_hz"]:.2f} Hz | {c["recordings"][NAMES[1]]["ratio_to_full_S0_db"]:.2f} dB | {c["recordings"][NAMES[2]]["ratio_to_full_S0_db"]:.2f} dB | {min(vals[NAMES[0]]):.2f}…{max(vals[NAMES[0]]):.2f} dB | {min(vals[NAMES[2]]):.2f}…{max(vals[NAMES[2]]):.2f} dB |')
    rows.extend(['', 'Die Kandidatenfrequenzen und Bandbreiten wurden aus der ersten Aufnahme unverändert übernommen. Es erfolgt keine neue Kandidatensuche oder Anpassung an die Wiederholung. Verglichen wird die integrierte Leistung; eine lokale Maximalfrequenz in einem eingeschränkten Suchbereich ist kein unabhängiger Nachweis einer stabilen Linie.', '',
                 'Die vollständigen Achsenwerte, Minima/Maxima, Zeitabschnitte, Diagnosebandleistungen und bedingten Überschuss-SNR-Werte stehen in `three_recordings.json`. Negative Überschuss-SNR-Werte bedeuten unter den dokumentierten Additivitätsannahmen, dass der geschätzte zusätzliche Beitrag kleiner ist als der Hintergrund; daraus folgt nicht die Abwesenheit eines Signals.', '',
                 'Eine nachfolgende kontrollierte Stillstandsreferenz wird benötigt, um die unveränderte Hintergrundleistung zumindest empirisch gegenzuprüfen. Bis dahin bleibt die Messparameter- und Trainingsfreigabe offen. Die Begründung einer möglichen höheren ODR und die Grenzen von 200 Hz werden in `provisional_recommendation.md` zusammengeführt.', ''])
    (OUT / 'three_recordings.md').write_text('\n'.join(rows))
    print(json.dumps({'repeat_statistics': records[NAMES[2]]['statistics'],
                      'repeat_sections_rms': [s['vector_ac_rms_g'] for s in records[NAMES[2]]['five_second_sections']],
                      'bands': {b: {n: r['xyz_sum'] for n, r in v.items()} for b, v in bands.items()},
                      'candidates': [{'axis': c['axis'], 'frequency': c['fixed_candidate_frequency_hz'],
                                      'records': {n: {'ratio_db': r['ratio_to_full_S0_db'],
                                                      'peak_hz': r['local_peak_hz'],
                                                      'local_prominence_db': r['local_peak_to_neighbor_median_db'],
                                                      'section_db': [s['ratio_to_full_S0_db'] for s in r['five_second_sections']]}
                                                  for n, r in c['recordings'].items()}} for c in candidates]}, indent=2))


if __name__ == '__main__':
    main()
