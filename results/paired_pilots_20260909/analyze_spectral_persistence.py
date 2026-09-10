"""Explorative Persistenzprüfung lokaler Spektralmaxima, keine Drehzahlbestimmung."""
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
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fft_pilot import spectrum
from analyze_pair import INPUTS, AXES, integrate_band


def main():
    destination = OUT / 'spectral_persistence.json'
    if destination.exists():
        raise FileExistsError(destination)
    report = {'method': 'Explorative local maxima in full operating PSD, ranked by ratio to median within ±5 Hz excluding ±1.2 Hz; five separated candidates per axis. These widths and ranking are diagnostic choices, not predeclared acceptance criteria. Each 5 s section uses 512-sample Hann PSDs with 256-sample hop and its own host-observed FIFO rate. Candidate-band power is integrated over fixed ±0.8 Hz and compared with the full standstill PSD in the same band. Candidate selection and checking use the same operating data; no independent significance test.',
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'rpm_measured': None, 'candidates': {}, 'section_count': 6}
    meta = json.loads((OUT / 'paired_report.json').read_text())
    operating = pd.read_csv(INPUTS['operating25'])
    times = operating.host_monotonic_ns.to_numpy(dtype=np.int64)
    times = (times - times[0]) / 1e9
    full_spectra = {n: pd.read_csv(OUT / (n + '_fft') / 'spectra.csv') for n in INPUTS}
    fig, panels = plt.subplots(3, 1, figsize=(11.7, 8.3), constrained_layout=True)
    for axis, panel in zip(AXES, panels):
        op = full_spectra['operating25'].query('axis == @axis')
        off = full_spectra['standstill'].query('axis == @axis')
        f = op.frequency_hz.to_numpy()
        p = op.mean_psd_g2_per_hz.to_numpy()
        fs0 = off.frequency_hz.to_numpy()
        ps0 = off.mean_psd_g2_per_hz.to_numpy()
        maxima = np.where((p[1:-1] > p[:-2]) & (p[1:-1] >= p[2:]))[0] + 1
        choices = []
        for i in maxima:
            if not 5 <= f[i] <= 90:
                continue
            near = (np.abs(f - f[i]) <= 5) & (np.abs(f - f[i]) >= 1.2)
            local = float(np.median(p[near]))
            choices.append((float(10 * np.log10(p[i] / local)), int(i)))
        choices.sort(reverse=True)
        selected = []
        for prominence, index in choices:
            if any(abs(f[index] - f[j]) < 2 for _, j in selected):
                continue
            selected.append((prominence, index))
            if len(selected) == 5:
                break
        sections = []
        for start in range(0, 30, 5):
            mask = (times >= start) & (times < start + 5)
            v = operating.loc[mask, axis].to_numpy()
            t = times[mask]
            rate = (len(v) - 1) / (t[-1] - t[0])
            segments = [spectrum(v[i:i+512], rate) for i in range(0, len(v)-512+1, 256)]
            sections.append((segments[0][0], np.mean([s[2] for s in segments], axis=0)))
        candidates = []
        for prominence, i in selected:
            frequency = float(f[i])
            low, high = frequency - .8, frequency + .8
            noise = integrate_band(fs0, ps0, low, high)
            powers = []
            for index, (section_f, section_p) in enumerate(sections):
                band = (section_f >= low) & (section_f <= high)
                peak_index = np.where(band)[0][np.argmax(section_p[band])]
                neighbors = (np.abs(section_f - frequency) <= 5) & (np.abs(section_f - frequency) >= 1.2)
                section_power = integrate_band(section_f, section_p, low, high)
                powers.append({'section_start_seconds': index * 5,
                               'local_peak_hz': float(section_f[peak_index]),
                               'local_peak_to_neighbor_median_db': float(10 * np.log10(section_p[peak_index] / np.median(section_p[neighbors]))),
                               'candidate_band_operating_to_full_standstill_db': float(10 * np.log10(section_power / noise))})
            candidate = {'frequency_hz': frequency,
                         'full_operating_peak_to_neighbor_median_db': prominence,
                         'full_operating_to_standstill_peak_bin_db': float(10 * np.log10(p[i] / np.interp(f[i], fs0, ps0))),
                         'candidate_band_hz': [low, high],
                         'full_candidate_band_operating_to_standstill_db': float(10 * np.log10(integrate_band(f, p, low, high) / noise)),
                         'sections': powers}
            candidates.append(candidate)
            panel.plot([2.5 + 5 * i for i in range(6)],
                       [s['candidate_band_operating_to_full_standstill_db'] for s in powers],
                       'o-', label=f'{frequency:.2f} Hz', alpha=.85)
        report['candidates'][axis] = candidates
        panel.axhline(0, color='black', linewidth=.8, linestyle='--')
        panel.set(title=axis[0].upper() + '-Achse', ylabel='Bandverhältnis / dB', xlabel='Zeit im Betriebspiloten / s',
                  xticks=np.arange(0, 31, 5))
        panel.grid(alpha=.25)
        panel.legend(ncol=5, fontsize=8, loc='lower left')
    report['interpretation_limits'] = [
        'Local maxima and positive ratios are not line-detection proofs; no confidence interval or repeat run.',
        'Section peak search is constrained around a candidate selected from the same full recording and therefore cannot independently prove frequency stability.',
        'Several candidate bands are intermittently below or close to the standstill average; a candidate consistently above it can motivate a repeat, not a rotational assignment.',
        'Comparison with a full standstill mean suppresses its time variation; underlying 5 s standstill RMS variation remains relevant.',
    ]
    destination.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    fig.suptitle('Explorative Spektralkandidaten: Leistung in ±0,8 Hz\n5-s-Betriebsabschnitte relativ zum mittleren Stillstand; keine Drehzahlzuordnung', fontsize=12)
    fig.savefig(OUT / 'spectral_persistence.png', dpi=180)
    fig.savefig(OUT / 'spectral_persistence.pdf')
    plt.close(fig)
    print(json.dumps({a: [{'frequency_hz': c['frequency_hz'],
                          'full_prominence_db': c['full_operating_peak_to_neighbor_median_db'],
                          'band_ratio_full_db': c['full_candidate_band_operating_to_standstill_db'],
                          'section_band_ratios_db': [s['candidate_band_operating_to_full_standstill_db'] for s in c['sections']]} for c in v]
                      for a, v in report['candidates'].items()}, indent=2))


if __name__ == '__main__':
    main()
