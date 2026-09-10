"""Reproduzierbare, ausschließlich lesende Analyse des kontrollierten Pilotpaars.

Aufruf aus Repositorywurzel: .venv/bin/python results/paired_pilots_20260909/analyze_pair.py
Die Analyse schreibt ausschließlich neue Dateien in ihr eigenes Ergebnisverzeichnis.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from fft_pilot import analyze, _validate_recording

OUT = Path(__file__).resolve().parent
AXES = ['x_g', 'y_g', 'z_g']
INPUTS = {
    'standstill': ROOT / 'data/controlled_20260909/standstill_20260909_200838.csv',
    'operating25': ROOT / 'data/controlled_20260909/operating25_20260909_201158.csv',
}
BANDS = {'1_to_90_hz': [1., 90.], '5_to_80_hz': [5., 80.]}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integrate_band(frequencies, psd, low, high):
    # Include exact equal endpoints despite slightly different observed rates.
    interior = (frequencies > low) & (frequencies < high)
    f = np.r_[low, frequencies[interior], high]
    return float(np.trapezoid(np.interp(f, frequencies, psd), f))


def stats(values):
    ac = values - values.mean(axis=0)
    return {
        'axes': {axis: {'mean_g': float(values[:, i].mean()),
                       'min_g': float(values[:, i].min()),
                       'max_g': float(values[:, i].max()),
                       'ac_rms_g': float(np.sqrt(np.mean(ac[:, i] ** 2)))}
                 for i, axis in enumerate(AXES)},
        'vector_ac_rms_g': float(np.sqrt(np.mean(np.sum(ac * ac, axis=1)))),
        'magnitude_ac_rms_g': float(np.std(np.linalg.norm(values, axis=1))),
    }


def load_recording(name, path):
    meta = json.loads(path.with_suffix('.json').read_text())
    before = {str(p.relative_to(ROOT)): digest(p) for p in [path, path.with_suffix('.json')]}
    fft = analyze(path, OUT / (name + '_fft'), nperseg=512)
    data = pd.read_csv(path, dtype=str, keep_default_na=False, skip_blank_lines=False)
    xyz, odr, rate = _validate_recording(data, meta, 512)
    ns = data.host_monotonic_ns.to_numpy(dtype=np.int64)
    t = (ns - ns[0]) / 1e9
    dt_ms = np.diff(ns) / 1e6
    spectra = pd.read_csv(OUT / (name + '_fft') / 'spectra.csv')
    result = {'input_csv': str(path.relative_to(ROOT)), 'hashes': before,
              'started_at_utc': meta['started_at_utc'], 'finished_at_utc': meta['finished_at_utc'],
              'state': meta['state'], 'mounting_id': meta['mounting_id'],
              'physical_state_source': meta['physical_state_source'],
              'pwm_setpoint_percent': meta['fan_pwm_setpoint_percent'],
              'rpm_measured': None, 'statistics': stats(xyz),
              'timing': {'samples': len(data), 'host_span_seconds': float(t[-1]),
                         'configured_duration_seconds': meta['configured_duration_seconds'],
                         'configured_odr_hz': odr, 'host_observed_fifo_rate_hz': rate,
                         'rate_deviation_from_nominal_percent': (rate / odr - 1) * 100,
                         'host_interval_min_ms': float(dt_ms.min()),
                         'host_interval_p50_ms': float(np.median(dt_ms)),
                         'host_interval_p99_ms': float(np.percentile(dt_ms, 99)),
                         'host_interval_max_ms': float(dt_ms.max()),
                         'host_intervals_over_10_ms': int(np.sum(dt_ms > 10)),
                         'nonmonotonic_host_intervals': int(np.sum(dt_ms <= 0)),
                         'sample_indices_contiguous': True,
                         'fifo_depth_max': int(data.fifo_depth.astype(int).max()),
                         'consecutive_equal_xyz_fraction': float(np.mean(np.all(np.diff(xyz, axis=0) == 0, axis=1))),
                         'gap_flagged_samples': int(data.gap.str.lower().isin(['true', '1']).sum()),
                         'overrun_flagged_samples': int(data.overrun.str.lower().isin(['true', '1']).sum()),
                         'saturated_flagged_samples': int(data.saturated.str.lower().isin(['true', '1']).sum()),
                         'lost_samples_exact': None},
              'five_second_sections': [], 'band_power_g2': {},
              'largest_psd_bin_hz': {a: fft['axes'][a]['largest_psd_bin_hz'] for a in AXES},
              'high_band_power_fraction': {a: fft['axes'][a]['psd_high_band_fraction'] for a in AXES},
              'frequency_bin_spacing_hz': fft['frequency_bin_spacing_hz']}
    for start in range(0, 30, 5):
        selected = (t >= start) & (t < start + 5)
        sub = xyz[selected]
        subt = t[selected]
        result['five_second_sections'].append({
            'start_seconds': start, 'stop_seconds': start + 5,
            'samples': int(selected.sum()), 'host_span_seconds': float(subt[-1] - subt[0]),
            'host_observed_fifo_rate_hz': float((len(subt) - 1) / (subt[-1] - subt[0])),
            **stats(sub)})
    for band, (low, high) in BANDS.items():
        powers = {}
        for axis in AXES:
            s = spectra[spectra.axis == axis]
            powers[axis] = integrate_band(s.frequency_hz.to_numpy(), s.mean_psd_g2_per_hz.to_numpy(), low, high)
        powers['xyz_sum'] = sum(powers.values())
        result['band_power_g2'][band] = powers
    after = {str(p.relative_to(ROOT)): digest(p) for p in [path, path.with_suffix('.json')]}
    assert before == after
    return result, spectra


def main():
    if (OUT / 'paired_report.json').exists():
        raise FileExistsError('Existing paired report must not be overwritten')
    records, spectra = {}, {}
    for name, path in INPUTS.items():
        records[name], spectra[name] = load_recording(name, path)
    ratios = {}
    for band in BANDS:
        ratios[band] = {}
        for axis in AXES + ['xyz_sum']:
            base = records['standstill']['band_power_g2'][band][axis]
            operating = records['operating25']['band_power_g2'][band][axis]
            ratio = operating / base if base > 0 else None
            excess = operating - base
            ratios[band][axis] = {
                'operating_to_standstill_power_ratio': ratio,
                'operating_to_standstill_power_db': float(10 * np.log10(ratio)) if ratio and ratio > 0 else None,
                'excess_power_g2': excess,
                'conditional_excess_snr_db': float(10 * np.log10(excess / base)) if base > 0 and excess > 0 else None,
            }
    report = {
        'purpose': 'paired_pilot_diagnostics_only_no_training_release',
        'source_script_sha256': digest(Path(__file__)),
        'fft_implementation_sha256': digest(ROOT / 'src/fft_pilot.py'),
        'diagnostic_bands_hz': BANDS,
        'band_definition': 'Diagnostic summaries chosen for broad comparison, not experimentally validated useful bands or acceptance criteria.',
        'spectral_method': 'Each recording: 512-sample symmetric Hann, 256-sample hop, per-segment mean removed, one-sided PSD, arithmetic mean over full segments; trapezoidal integration with linearly interpolated common exact band endpoints.',
        'vector_definition': 'sqrt(sum(axis population variance)); no mean removed from magnitude before forming vector. magnitude_ac_rms_g is separately std(norm(xyz)).',
        'time_sections': 'Non-overlapping 5-second host-relative intervals; own axis mean removed within each section. Rates use first/last host completion; no hardware sensor timestamps.',
        'records': records, 'band_comparison': ratios,
        'conditional_snr_assumptions': [
            'Stationary and unchanged background between separate standstill and operating recordings.',
            'Additive, uncorrelated vibration and background; identical mechanical transfer and sensor response.',
            'Only positive operating-minus-standstill power is converted to SNR; this is an assumption-dependent estimate, not an independently measured fan SNR.',
        ],
        'limitations': [
            'One standstill and one operating run; no repeatability or statistical confidence established.',
            'Host-observed FIFO throughput estimates frequency axis; nominal ODR 200 Hz is not measured conversion timing.',
            'No gap/overrun flags do not prove exact zero lost sensor samples.',
            'No tachometer reference: spectral peaks must not be assigned to shaft speed or blade passage.',
            'Both diagnostic bands retain substantial near-Nyquist content; alias absence and useful bandwidth are not proven.',
            'Changed mount details are not inferred from axis means; user confirms unchanged mounting.',
            'No new models, scaling, thresholds or final measurement parameters are released by this analysis.',
        ],
    }
    (OUT / 'paired_report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    labels = {'standstill': 'Stillstand', 'operating25': 'Betrieb, 25 % PWM'}
    colors = {'standstill': '#35648a', 'operating25': '#c96322'}
    fig, axes = plt.subplots(2, 2, figsize=(11.7, 8.3), constrained_layout=True)
    for axis, ax in zip(AXES, axes.flat):
        for name in INPUTS:
            s = spectra[name][spectra[name].axis == axis]
            ax.semilogy(s.frequency_hz, np.maximum(s.mean_psd_g2_per_hz, 1e-15),
                        label=labels[name], color=colors[name], alpha=.9)
        ax.set(xlabel='Frequenz / Hz (FIFO-Durchsatz)', ylabel='PSD / g² Hz⁻¹', title=axis[0].upper() + '-Achse', xlim=(0, 105))
        ax.grid(alpha=.25)
    for name in INPUTS:
        sections = records[name]['five_second_sections']
        axes[1, 1].plot([s['start_seconds'] + 2.5 for s in sections],
                        [s['vector_ac_rms_g'] * 1000 for s in sections], 'o-', label=labels[name], color=colors[name])
    axes[1, 1].set(xlabel='Zeit im jeweiligen Versuch / s', ylabel='Vektor-AC-RMS / mg',
                   title='Separate 5-s-Abschnitte', xticks=np.arange(0, 31, 5))
    axes[1, 1].grid(alpha=.25)
    axes[0, 0].legend(fontsize=9)
    axes[1, 1].legend(fontsize=9)
    fig.suptitle('Kontrolliertes Pilotpaar: Stillstand und 25 % PWM\nADXL345 am Lüfterrahmen; 200 Hz Soll-ODR, ±2 g; je 30 s; keine Drehzahlmessung', fontsize=12)
    fig.savefig(OUT / 'paired_comparison.png', dpi=180)
    fig.savefig(OUT / 'paired_comparison.pdf')
    plt.close(fig)
    rows = ['# Kontrolliertes Pilotpaar vom 09.09.2026', '',
            'Die beiden neu erhobenen Pilotaufnahmen werden getrennt von Training, Validierung und unabhängigen Tests ausgewertet. Die Montage am Lüfterrahmen und der sichtbare gleichmäßige Betrieb wurden vom Nutzer bestätigt. 25 % bezeichnet den Softwaretastgrad; eine Drehzahl wurde nicht gemessen.', '',
            '| Kennwert | Stillstand | Betrieb bei 25 % |', '|---|---:|---:|']
    for label, getter, fmt in [
        ('Wertezahl', lambda r: r['timing']['samples'], '.0f'),
        ('Beobachteter FIFO-Durchsatz / Hz', lambda r: r['timing']['host_observed_fifo_rate_hz'], '.3f'),
        ('Größtes Hostintervall / ms', lambda r: r['timing']['host_interval_max_ms'], '.3f'),
        ('Vektor-AC-RMS / g', lambda r: r['statistics']['vector_ac_rms_g'], '.6f'),
        ('AC-RMS des Betrags / g', lambda r: r['statistics']['magnitude_ac_rms_g'], '.6f'),
    ]:
        rows.append(f'| {label} | {getter(records["standstill"]):{fmt}} | {getter(records["operating25"]):{fmt}} |')
    rows.extend(['', 'In beiden Dateien sind Lücken-, Überlauf- und Sättigungsflags durchgängig falsch. Die Sampleindizes sind vollständig und monoton. Die FIFO-Tiefe ist maximal eins. Dies ist ein positiver Erfassungsbefund, kein Nachweis einer exakt bestimmten Zahl physikalischer Abtastungen oder einer kalibrierten Frequenzachse.', '',
                 '| Achse | AC-RMS Stillstand / g | AC-RMS Betrieb / g | Mittelwert Stillstand / g | Mittelwert Betrieb / g |', '|---|---:|---:|---:|---:|'])
    for a in AXES:
        s, o = [records[n]['statistics']['axes'][a] for n in INPUTS]
        rows.append(f'| {a[0].upper()} | {s["ac_rms_g"]:.6f} | {o["ac_rms_g"]:.6f} | {s["mean_g"]:.6f} | {o["mean_g"]:.6f} |')
    rows.extend(['', 'PSD: 512 Werte pro symmetrischem Hann-Fenster, 256 Werte Vorschub, Mittelwertentfernung je Segment, einseitige Leistungsdichte und arithmetische Mittelung der vollständigen Segmente. Die Bandintegration verwendet lineare Interpolation an gemeinsamen exakten Bandgrenzen und die Trapezregel. Die Diagnosebänder 1–90 Hz und 5–80 Hz dienen der breiten Gegenüberstellung; sie sind keine nachgewiesenen Nutzbänder oder vorgegebenen Akzeptanzgrenzen.', '',
                 '| Diagnoseband | Größe | Leistung Stillstand / g² | Leistung Betrieb / g² | Betrieb/Stillstand / dB | Bedingter Überschuss-SNR / dB |', '|---|---|---:|---:|---:|---:|'])
    for band in BANDS:
        for axis in AXES + ['xyz_sum']:
            s, o = [records[n]['band_power_g2'][band][axis] for n in INPUTS]
            comp = ratios[band][axis]
            snr = comp['conditional_excess_snr_db']
            snrstr = f'{snr:.2f}' if snr is not None else 'nicht positiv / nicht definiert'
            rows.append(f'| {BANDS[band][0]:g}–{BANDS[band][1]:g} Hz | {axis} | {s:.8g} | {o:.8g} | {comp["operating_to_standstill_power_db"]:.2f} | {snrstr} |')
    rows.extend(['', 'Betrieb/Stillstand bezeichnet 10 log10(P_Betrieb/P_Stillstand). Der nur bei positivem Überschuss angegebene SNR-Schätzwert lautet 10 log10((P_Betrieb−P_Stillstand)/P_Stillstand). Er setzt einen stationären unveränderten Hintergrund, additive unkorrelierte Beiträge und eine gleiche mechanische Übertragung voraus. Das getrennte Pilotpaar belegt diese Annahmen nicht. Der Schätzwert ist deshalb kein unabhängig gemessener Lüfter-SNR.', '',
                 '| Zustand | 5-s-Abschnitt / s | Werte | FIFO-Durchsatz / Hz | Vektor-AC-RMS / g |', '|---|---:|---:|---:|---:|'])
    for name in INPUTS:
        for s in records[name]['five_second_sections']:
            rows.append(f'| {labels[name]} | {s["start_seconds"]}–{s["stop_seconds"]} | {s["samples"]} | {s["host_observed_fifo_rate_hz"]:.3f} | {s["vector_ac_rms_g"]:.6f} |')
    rows.extend(['', 'Die Spektren und Abschnittswerte sind in `paired_comparison.png` und `.pdf` dargestellt. Vollständige Kennwerte einschließlich Minima/Maxima, Achsenmittelwerten, Qualitätsflags und Datei-Hashes stehen in `paired_report.json`. Die jeweiligen Einzel-FFT-Berichte liegen in neuen Unterverzeichnissen; ihre generischen Einschränkungen beziehen sich auf die Einzelaufnahme. Erst dieser Paarbericht führt den kontrollierten Zustand und die bedingte Hintergrundsubtraktion zusammen.', '',
                 'Die kleine Leistungszunahme im Betrieb liefert einen messbaren Unterschied dieser beiden Dateien. Sie trägt allein keine belastbare allgemeine Trennung des Lüfternutzsignals vom Hintergrund: Es fehlen Wiederholungen, Unsicherheitsschätzung und eine Drehzahlreferenz. Größte Spektralbins werden keiner Drehzahl oder Blattfolge zugeordnet. Energie nahe der halben Abtastrate belegt weder Aliasfreiheit noch ein geeignetes Nutzband. Modelle und Schwellen werden aus dieser Analyse nicht freigegeben.', ''])
    (OUT / 'paired_report.md').write_text('\n'.join(rows))
    print(json.dumps({'band_comparison': ratios,
                      'sections': {name: records[name]['five_second_sections'] for name in INPUTS}}, indent=2))


if __name__ == '__main__':
    main()
