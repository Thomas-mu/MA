from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
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
