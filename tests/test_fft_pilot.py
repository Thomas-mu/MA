import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import fft_pilot
from fft_pilot import spectrum


def test_hann_amplitude_and_psd_of_known_sinusoid():
    fs, n, amplitude, frequency = 200, 1000, .4, 20
    x = 1.5 + amplitude*np.sin(2*np.pi*frequency*np.arange(n)/fs)
    f, a, psd = spectrum(x, fs)
    peak = np.argmax(a)
    assert f[peak] == frequency
    assert a[peak] == pytest.approx(amplitude, rel=1e-4)
    assert psd.sum() * fs/n == pytest.approx(amplitude**2/2, rel=1e-4)
    assert a[0] < 1e-6


def test_fft_rejects_invalid_values():
    with pytest.raises(ValueError):
        spectrum([1, 2, float('nan'), 4], 200)
    with pytest.raises(ValueError):
        spectrum([1, 2, 3, 4], 0)


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    """Synthetische CSV-/Manifest-Schnittstelle; kein Sensor wird geöffnet."""
    n = 17  # Ein Schlusswert liegt außerhalb des einzigen 16-Sample-Segments.
    dataframe = pd.DataFrame(dict(
        x_g=np.sin(np.arange(n)), y_g=np.cos(np.arange(n)), z_g=np.ones(n),
        sample_index=np.arange(n),
        host_monotonic_ns=2**53 + 1 + np.arange(n, dtype=np.int64) * 5_000_001,
        gap=False, overrun=False, saturated=False,
    )).astype(str)
    manifest = dict(purpose='pilot', status='completed', state='synthetic_test_only',
                    sensor=dict(acquisition_mode='fifo_stream', odr_hz=200),
                    summary=dict(samples=n))
    monkeypatch.setattr(fft_pilot, 'provenance', lambda: {'synthetic_test_only': True})

    def run(nperseg=16):
        path = tmp_path / 'synthetic.csv'
        dataframe.to_csv(path, index=False)
        manifest['csv_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix('.json').write_text(json.dumps(manifest))
        return fft_pilot.analyze(path, tmp_path / 'analysis', nperseg=nperseg)

    return dataframe, manifest, run, tmp_path / 'analysis'


@pytest.mark.parametrize('false_value', ['False', 'false', '0'])
def test_analyze_valid_recorder_flags_and_integer_time_precision(pilot, false_value):
    dataframe, _, run, output = pilot
    dataframe[['gap', 'overrun', 'saturated']] = false_value
    report = run()
    assert report['host_observed_fifo_rate_hz'] == 1e9 / 5_000_001
    assert report['axes']['x_g']['segments'] == 1
    assert report['snr_db'] is None
    assert {p.name for p in output.iterdir()} == {'spectra.csv', 'report.json', 'fft_pilot.png'}


@pytest.mark.parametrize('flag', ['gap', 'overrun', 'saturated'])
@pytest.mark.parametrize('value', ['', 'unknown', 'True', '1', '2', '0.0'])
def test_analyze_rejects_unknown_missing_or_active_flag_before_output(pilot, flag, value):
    dataframe, _, run, output = pilot
    dataframe.loc[16, flag] = value
    with pytest.raises(ValueError, match=flag):
        run()
    assert not output.exists()


@pytest.mark.parametrize('column', ['x_g', 'y_g', 'z_g', 'host_monotonic_ns',
                                   'sample_index', 'gap', 'overrun', 'saturated'])
def test_analyze_requires_each_consumed_column(pilot, column):
    dataframe, _, run, output = pilot
    dataframe.drop(columns=column, inplace=True)
    with pytest.raises(ValueError, match=column):
        run()
    assert not output.exists()


@pytest.mark.parametrize('column', ['host_monotonic_ns', 'sample_index'])
@pytest.mark.parametrize('value', ['1.5', 'nan', 'inf', '', '-1', str(2**63)])
def test_analyze_rejects_invalid_integer_fields(pilot, column, value):
    dataframe, _, run, output = pilot
    dataframe.loc[0, column] = value
    with pytest.raises(ValueError, match=column):
        run()
    assert not output.exists()


@pytest.mark.parametrize('sequence', ['starts_at_one', 'missing_index', 'duplicate_index'])
def test_analyze_rejects_incomplete_sample_sequence(pilot, sequence):
    dataframe, _, run, output = pilot
    if sequence == 'starts_at_one':
        dataframe['sample_index'] = np.arange(1, len(dataframe) + 1).astype(str)
    elif sequence == 'missing_index':
        dataframe.loc[16, 'sample_index'] = '17'
    else:
        dataframe.loc[16, 'sample_index'] = '15'
    with pytest.raises(ValueError, match='Samplefolge'):
        run()
    assert not output.exists()


@pytest.mark.parametrize('interval', [0, -1, 160_000_000])
def test_analyze_rejects_nonmonotonic_time_and_fifo_sized_gap(pilot, interval):
    dataframe, _, run, output = pilot
    dataframe.loc[16, 'host_monotonic_ns'] = str(int(dataframe.loc[15, 'host_monotonic_ns']) + interval)
    with pytest.raises(ValueError, match='Hostzeit|Hostlücke'):
        run()
    assert not output.exists()


@pytest.mark.parametrize('value', [None, 16, 17.0, True, '17'])
def test_analyze_requires_matching_integer_manifest_sample_count(pilot, value):
    _, manifest, run, output = pilot
    manifest['summary']['samples'] = value
    with pytest.raises(ValueError, match='Samplezahl'):
        run()
    assert not output.exists()


def test_analyze_requires_manifest_summary(pilot):
    _, manifest, run, output = pilot
    del manifest['summary']
    with pytest.raises(ValueError, match='Samplezahl'):
        run()
    assert not output.exists()


@pytest.mark.parametrize('value', [None, 0, -200, float('nan'), float('inf'), True, '200'])
def test_analyze_requires_finite_positive_numeric_odr(pilot, value):
    _, manifest, run, output = pilot
    manifest['sensor']['odr_hz'] = value
    with pytest.raises(ValueError, match='ODR'):
        run()
    assert not output.exists()


@pytest.mark.parametrize('value', [0, -4, 3, 16.0, True, '16', float('nan')])
def test_analyze_requires_integer_segment_length(pilot, value):
    _, _, run, output = pilot
    with pytest.raises(ValueError, match='Segmentlänge'):
        run(nperseg=value)
    assert not output.exists()


@pytest.mark.parametrize('axis', ['x_g', 'y_g', 'z_g'])
@pytest.mark.parametrize('value', ['nan', 'inf', '-inf', ''])
def test_analyze_rejects_nonfinite_segment_remainder_before_any_output(pilot, axis, value):
    dataframe, _, run, output = pilot
    dataframe.loc[16, axis] = value
    with pytest.raises(ValueError):
        run()
    assert not output.exists()
