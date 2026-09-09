"""Dokumentierte FFT-Pilotanalyse gespeicherter FIFO-Aufnahmen (keine Testoptimierung).

Ausgangspunkt: Mittelwertentfernung/rfft in preprocessing.calculate_features.
Hier zusätzlich Hann-Fenster, korrekte einseitige Amplituden-/PSD-Skalierung,
Zeit-/Verlustprüfung, dreiachsige Auswertung und vollständige Provenienz.
"""
import argparse
import hashlib
import json
from numbers import Integral
from pathlib import Path

import numpy as np
import pandas as pd

from collect_real_data import provenance


def _integer_column(dataframe, name):
    """Recorder-Ganzzahlen ohne Umweg über Float und dessen Rundung lesen."""
    values = dataframe[name]
    if not values.str.fullmatch(r'[0-9]+').all():
        raise ValueError(f'{name} muss nichtnegative ganze Zahlen enthalten')
    try:
        integers = [int(value) for value in values]
        if any(value > np.iinfo(np.int64).max for value in integers):
            raise ValueError('außerhalb des int64-Bereichs')
        return np.asarray(integers, dtype=np.int64)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f'Ungültige Ganzzahlen in {name}') from exc


def _validate_recording(dataframe, meta, nperseg):
    """Alle FFT-Eingaben prüfen, bevor Auswertungsdateien angelegt werden."""
    if isinstance(nperseg, bool) or not isinstance(nperseg, Integral) or nperseg < 4:
        raise ValueError('Segmentlänge muss eine ganze Zahl von mindestens vier sein')
    if len(dataframe) < nperseg:
        raise ValueError('Zu wenige Samples für die Segmentlänge')
    required = {'x_g', 'y_g', 'z_g', 'host_monotonic_ns', 'sample_index',
                'gap', 'overrun', 'saturated'}
    missing = required.difference(dataframe.columns)
    if missing:
        raise ValueError(f'Fehlende Erfassungsspalten: {sorted(missing)}')
    for flag in ['gap', 'overrun', 'saturated']:
        # Der Recorder schreibt boolesche CSV-Werte. Nur bekannte False-Werte
        # zulassen: leer/unbekannt darf nicht als fehlender Fehler gelten.
        if not dataframe[flag].str.lower().isin(['false', '0']).all():
            raise ValueError(f'FFT wegen fehlender/unzulässiger Qualitätsflags gesperrt: {flag}')
    summary = meta.get('summary')
    samples = summary.get('samples') if isinstance(summary, dict) else None
    if type(samples) is not int or samples != len(dataframe):
        raise ValueError('Manifest-Samplezahl fehlt oder stimmt nicht mit CSV überein')
    odr = meta['sensor'].get('odr_hz')
    if isinstance(odr, bool) or not isinstance(odr, (int, float)) or not np.isfinite(odr) or odr <= 0:
        raise ValueError('Sensor-ODR muss endlich und positiv sein')
    indices = _integer_column(dataframe, 'sample_index')
    if not np.array_equal(indices, np.arange(len(dataframe), dtype=np.int64)):
        raise ValueError('Samplefolge muss bei null beginnen und lückenlos sein')
    times = _integer_column(dataframe, 'host_monotonic_ns')
    intervals = np.diff(times)
    if (intervals <= 0).any():
        raise ValueError('Nicht monotone Hostzeit')
    if int(intervals.max()) / 1e9 >= 32 / odr:
        raise ValueError('Hostlücke größer als FIFO-Kapazität')
    xyz = dataframe[['x_g', 'y_g', 'z_g']].to_numpy(dtype=np.float64)
    if not np.isfinite(xyz).all():
        raise ValueError('Alle XYZ-Werte müssen endlich sein, auch im Segmentrest')
    fs = (len(dataframe) - 1) * 1e9 / (int(times[-1]) - int(times[0]))
    return xyz, odr, fs


def spectrum(values, fs):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or len(values) < 4 or not np.isfinite(values).all() or not np.isfinite(fs) or fs <= 0:
        raise ValueError('FFT benötigt mindestens vier endliche Werte und positive Rate')
    w = np.hanning(len(values))
    transformed = np.fft.rfft((values - np.mean(values)) * w)
    amplitude = np.abs(transformed) / w.sum()
    psd = np.abs(transformed)**2 / (fs * np.sum(w*w))
    end = -1 if len(values) % 2 == 0 else None
    amplitude[1:end] *= 2
    psd[1:end] *= 2
    return np.fft.rfftfreq(len(values), d=1/fs), amplitude, psd


def analyze(path, output, nperseg=512):
    path, output = Path(path), Path(output)
    sidecar = path.with_suffix('.json')
    meta = json.loads(sidecar.read_text())
    if meta.get('purpose') != 'pilot':
        raise ValueError('Nur ausdrücklich als pilot deklarierte Daten; keine Testdaten zur Parameterwahl')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if meta.get('csv_sha256') != digest:
        raise ValueError('CSV-Hash stimmt nicht mit Erfassungsmanifest überein')
    if meta.get('status') != 'completed':
        raise ValueError('Nur vollständig abgeschlossene Aufnahmen für diese Pilot-FFT')
    if not isinstance(meta.get('sensor'), dict) or meta['sensor'].get('acquisition_mode') != 'fifo_stream':
        raise ValueError('Kein dokumentierter FIFO-Frischwertnachweis')
    # Keine automatische Float-/NA-Konvertierung für Integer und Qualitätsflags.
    df = pd.read_csv(path, dtype=str, keep_default_na=False, skip_blank_lines=False)
    xyz, odr, fs = _validate_recording(df, meta, nperseg)
    nperseg = int(nperseg)
    # Sensorwerte sind FIFO-geordnet. Fs ist eine Host-Durchsatzschätzung des
    # Sensor-Taktes; die ungleichmäßigen Host-Lesezeiten werden nicht interpoliert.
    output.mkdir(parents=True, exist_ok=False)
    spectra = []
    axes = {}
    for column, axis in enumerate(['x_g', 'y_g', 'z_g']):
        values = xyz[:, column]
        results = [spectrum(values[i:i+nperseg], fs)
                   for i in range(0, len(values)-nperseg+1, nperseg//2)]
        f = results[0][0]
        amplitude = np.mean([s[1] for s in results], axis=0)
        psd = np.mean([s[2] for s in results], axis=0)
        peak = 1 + int(np.argmax(psd[1:]))
        axes[axis] = dict(mean_g=float(values.mean()), ac_rms_g=float(values.std()),
                          largest_psd_bin_hz=float(f[peak]),
                          mean_amplitude_at_peak_g=float(amplitude[peak]),
                          psd_high_band_fraction=float(psd[f >= .8*fs/2].sum()/psd.sum()) if psd.sum() > 0 else None,
                          segments=len(results))
        spectra.append(pd.DataFrame(dict(axis=axis, frequency_hz=f, mean_amplitude_g=amplitude, mean_psd_g2_per_hz=psd)))
    all_spectra = pd.concat(spectra, ignore_index=True)
    all_spectra.to_csv(output/'spectra.csv', index=False)
    report = dict(input=str(path.resolve()), csv_sha256=digest,
                  metadata_sha256=hashlib.sha256(sidecar.read_bytes()).hexdigest(),
                  code=provenance(), purpose='pilot_only', state=meta.get('state'),
                  configured_odr_hz=odr, host_observed_fifo_rate_hz=fs,
                  segment_samples=nperseg, overlap_samples=nperseg//2,
                  segment_seconds=nperseg/fs, frequency_bin_spacing_hz=fs/nperseg,
                  window='symmetric Hann', detrend='remove each segment mean',
                  amplitude='abs(rfft)/sum(window); double positive bins except Nyquist',
                  psd='abs(rfft)^2/(fs*sum(window^2)); one-sided; arithmetic segment mean',
                  axes=axes, snr_db=None,
                  limitations=[
                      'State/mounting may be unconfirmed: no physical attribution of peaks.',
                      'Frequency axis uses observed FIFO throughput, assuming stable sensor clock and no undetected loss; no hardware sample timestamps.',
                      'No verified useful bandwidth, anti-alias margin or SNR from this recording alone.',
                      'High-band power is diagnostic, not proof of absence/presence of aliasing.',
                      'No reference noise recording: SNR remains unmeasured.',
                      'No changes to models, thresholds or final parameters based on test data.',
                  ])
    (output/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 5))
    for axis, group in all_spectra.groupby('axis'):
        ax.semilogy(group.frequency_hz, np.maximum(group.mean_psd_g2_per_hz, 1e-16), label=axis)
    ax.set(xlabel='Frequenz / Hz (aus FIFO-Durchsatz geschätzt)', ylabel='Leistungsdichte / g²/Hz',
           title=f'Pilotanalyse: {meta.get("state", "unbestätigt")}\nHann, {nperseg} Samples; Nutzband/SNR noch nicht bestätigt')
    ax.legend()
    ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(output/'fft_pilot.png', dpi=160)
    plt.close(fig)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--segment-samples', type=int, default=512)
    args = p.parse_args()
    report = analyze(args.input, args.output, args.segment_samples)
    print(json.dumps({k: report[k] for k in ['host_observed_fifo_rate_hz', 'frequency_bin_spacing_hz', 'snr_db', 'axes']}, indent=2))


if __name__ == '__main__':
    main()
