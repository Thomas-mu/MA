import json
from pathlib import Path
import struct
import sys
import threading
import time
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import adxl345 as a
import collect_real_data as c


class Bus:
    def __init__(self, entries=(1,), raw=(0, 0, 256), source=0):
        self.regs = {0: 0xE5}
        self.entries = list(entries)
        self.raw, self.source, self.bursts = raw, source, 0
    def write_byte_data(self, addr, reg, value):
        self.regs[reg] = value
    def read_byte_data(self, addr, reg):
        if reg == a.REGISTER_FIFO_STATUS:
            return self.entries.pop(0) if len(self.entries) > 1 else self.entries[0]
        if reg == a.REGISTER_INT_SOURCE:
            return self.source
        return self.regs.get(reg, 0)
    def read_i2c_block_data(self, *args):
        self.bursts += 1
        return list(struct.pack('<hhh', *self.raw))


def configured(**kwargs):
    bus = Bus(**kwargs)
    a.configure_sensor(bus)
    return bus


def test_no_500_hz_and_readback():
    with pytest.raises(ValueError, match='keine ODR'):
        a.configure_sensor(Bus(), odr_hz=500)
    bus = configured()
    assert bus.regs[0x2c] == 0x0b
    assert bus.regs[0x31] == 0x08
    assert bus.regs[0x38] >> 6 == 2


def test_no_burst_without_fifo_entry_and_equal_values_are_fresh():
    bus = configured(entries=[0, 0, 1, 1])
    first, second = a.read_fresh_sample(bus), a.read_fresh_sample(bus)
    assert first.xyz_g == second.xyz_g
    assert second.sample_index == first.sample_index + 1
    assert second.monotonic_ns > first.monotonic_ns
    assert bus.bursts == 2


def test_overflow_saturation_signed_and_stop():
    bus = configured(entries=[32], raw=(-512, 511, -10), source=1)
    s = a.read_fresh_sample(bus)
    assert s.overrun and s.gap and s.saturated
    assert s.xyz_g[0] < 0
    stop = threading.Event()
    stop.set()
    assert a.read_fresh_sample(bus, stop_event=stop) is None
    assert bus.bursts == 1


def test_timeout_and_invalid_fifo():
    bus = configured(entries=[0])
    with pytest.raises(TimeoutError):
        a.read_fresh_sample(bus, timeout_s=.003)
    assert not bus.bursts
    with pytest.raises(IOError, match='FIFO'):
        a.read_fresh_sample(configured(entries=[33]))


def test_range_and_bus_rate_reject_before_open():
    with patch.object(a, 'configured_i2c_clock_hz', return_value=100000), patch.object(a, 'SMBus') as smbus:
        with pytest.raises(ValueError, match='I²C'):
            a.connect(odr_hz=400)
        smbus.assert_not_called()


def test_wrong_device_id_does_not_write_even_during_cleanup():
    bus = Bus()
    bus.regs[0] = 0
    with patch.object(a, 'configured_i2c_clock_hz', return_value=100000), \
         patch.object(a, 'SMBus', return_value=bus), \
         patch.object(bus, 'close', create=True) as close, \
         patch.object(bus, 'write_byte_data') as write:
        with pytest.raises(RuntimeError, match='Gerätekennung'):
            a.connect()
        close.assert_called_once()
        write.assert_not_called()


@pytest.mark.parametrize('failure', [KeyboardInterrupt(), OSError('sensor disconnected')])
def test_partial_record_survives_interrupt_or_error(tmp_path, failure):
    bus = configured()
    s = a.FreshSample((0., 0., 1.), time.monotonic_ns(), 0, 0., 1, False, False, False, 1000)
    path = tmp_path / 'capture.csv'
    with patch.object(c, 'read_fresh_sample', side_effect=[s, failure]), patch.object(c, 'provenance', return_value={}):
        with pytest.raises(type(failure)):
            c.record(bus, 1, 200, output_path=path)
    assert len(path.read_text().splitlines()) == 2
    meta = json.loads(path.with_suffix('.json').read_text())
    assert meta['summary']['samples'] == 1
    assert meta['status'] in ('interrupted', 'error')
    assert meta['label'] == -1
    with pytest.raises(FileExistsError):
        c.record(bus, 1, 200, output_path=path)


def test_rate_mismatch_has_no_output(tmp_path):
    with pytest.raises(ValueError, match='implizite'):
        c.record(configured(), 1, 500, output_path=tmp_path/'bad.csv')
    assert not list(tmp_path.iterdir())
