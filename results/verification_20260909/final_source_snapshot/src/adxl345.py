"""ADXL345: explizite Konfiguration und Frischwerte aus dem Hardware-FIFO.

Zeitstempel sind Host-Lesezeiten, keine vom Sensor gemessenen Zeitstempel.
Gleiche XYZ-Tupel können verschiedene, quantisierte Sensorwerte sein.
"""
from dataclasses import dataclass
import fcntl
from pathlib import Path
import struct
import time

from smbus2 import SMBus

I2C_BUS_NUMBER = 1
ADXL345_ADDRESS = 0x53
REGISTER_DEVID = 0x00
REGISTER_BW_RATE = 0x2C
REGISTER_POWER_CTL = 0x2D
REGISTER_INT_ENABLE = 0x2E
REGISTER_INT_SOURCE = 0x30
REGISTER_DATA_FORMAT = 0x31
REGISTER_DATAX0 = 0x32
REGISTER_FIFO_CTL = 0x38
REGISTER_FIFO_STATUS = 0x39
GRAVITY_SCALE_FACTOR = 0.0039
EXPECTED_DEVICE_ID = 0xE5
ODR_CODES = {25: 0x08, 50: 0x09, 100: 0x0A, 200: 0x0B, 400: 0x0C, 800: 0x0D}
RANGE_CODES = {2: 0, 4: 1, 8: 2, 16: 3}


@dataclass(frozen=True)
class FreshSample:
    xyz_g: tuple[float, float, float]
    monotonic_ns: int
    sample_index: int
    sensor_time_estimate_s: float
    fifo_depth: int
    overrun: bool
    gap: bool
    saturated: bool
    read_duration_ns: int


def configured_i2c_clock_hz(bus_number=1):
    """Device-Tree-Konfiguration; keine elektrische Messung der SCL-Frequenz."""
    for root in (Path('/sys/bus/i2c/devices'), Path('/sys/class/i2c-dev')):
        for suffix in ('of_node/clock-frequency', 'device/of_node/clock-frequency'):
            p = root / f'i2c-{bus_number}' / suffix
            if p.exists():
                return int.from_bytes(p.read_bytes(), 'big')
    return None


class SensorConnection:
    """Ein Besitzer pro Bus/Adresse; Registerzustand beim Schließen restaurieren."""
    def __init__(self, bus, lock, original):
        self.bus, self.lock, self.original = bus, lock, original
        self.closed = False

    def __getattr__(self, name):
        return getattr(self.bus, name)

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.bus.write_byte_data(ADXL345_ADDRESS, REGISTER_POWER_CTL, 0)
            self.bus.write_byte_data(ADXL345_ADDRESS, REGISTER_FIFO_CTL, 0)
            for reg, value in self.original.items():
                if reg != REGISTER_POWER_CTL:
                    self.bus.write_byte_data(ADXL345_ADDRESS, reg, value)
            self.bus.write_byte_data(ADXL345_ADDRESS, REGISTER_POWER_CTL,
                                     self.original[REGISTER_POWER_CTL])
        finally:
            try:
                self.bus.close()
            finally:
                self.lock.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def configure_sensor(bus, *, odr_hz=200, range_g=2, fifo=True):
    if odr_hz not in ODR_CODES:
        raise ValueError(f'ADXL345 besitzt keine ODR {odr_hz} Hz; erlaubt: {list(ODR_CODES)}')
    if range_g not in RANGE_CODES:
        raise ValueError('Messbereich muss 2, 4, 8 oder 16 g sein')
    if bus.read_byte_data(ADXL345_ADDRESS, REGISTER_DEVID) != EXPECTED_DEVICE_ID:
        raise RuntimeError('Unerwartete ADXL345-Gerätekennung an Adresse 0x53')
    expected = {
        REGISTER_BW_RATE: ODR_CODES[odr_hz],
        REGISTER_DATA_FORMAT: 0x08 | RANGE_CODES[range_g],
        REGISTER_INT_ENABLE: 0,
        REGISTER_FIFO_CTL: 0x80 | 16 if fifo else 0,
        REGISTER_POWER_CTL: 0x08,
    }
    bus.write_byte_data(ADXL345_ADDRESS, REGISTER_POWER_CTL, 0)
    bus.write_byte_data(ADXL345_ADDRESS, REGISTER_FIFO_CTL, 0)
    for reg, value in expected.items():
        bus.write_byte_data(ADXL345_ADDRESS, reg, value)
    readback = {reg: bus.read_byte_data(ADXL345_ADDRESS, reg) for reg in expected}
    if readback != expected:
        raise RuntimeError(f'ADXL345-Konfiguration nicht bestätigt: {readback}')
    bus._edge_config = {
        'model': 'ADXL345', 'odr_hz': odr_hz, 'range_g': range_g,
        'full_resolution': True, 'scale_g_per_lsb': GRAVITY_SCALE_FACTOR,
        'acquisition_mode': 'fifo_stream' if fifo else 'bypass',
        'register_readback': {hex(r): hex(v) for r, v in readback.items()},
        'timestamp_source': 'host_monotonic_read_completion',
        'sensor_time_estimate': 'sample_index / nominal ODR; not measured sensor time',
        'lost_samples_exact': None,
    }
    bus._edge_index = 0
    bus._edge_last_ns = None


def connect(bus_number=I2C_BUS_NUMBER, *, odr_hz=200, range_g=2, fifo=True):
    """Default 200 Hz bei 100-kHz-I²C; keine implizite 500-Hz-Erfassung."""
    if odr_hz not in ODR_CODES:
        raise ValueError(f'Keine ADXL345-ODR {odr_hz} Hz; zulässig: {list(ODR_CODES)}')
    clock = configured_i2c_clock_hz(bus_number)
    max_odr = min(800, (clock or 100000) / 500)
    if odr_hz > max_odr:
        raise ValueError(f'{odr_hz} Hz über I²C-Empfehlung ({max_odr:g} Hz; Bus {clock} Hz)')
    lock = open(f'/tmp/edge-ai-adxl345-{bus_number}-53.lock', 'a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        lock.close()
        raise RuntimeError('ADXL345 wird bereits von einem Erfassungsprozess verwendet')
    bus = None
    connection = None
    try:
        bus = SMBus(bus_number)
        # Ein fremdes Gerät darf auch im Fehler-Cleanup keine Registerwrites erhalten.
        if bus.read_byte_data(ADXL345_ADDRESS, REGISTER_DEVID) != EXPECTED_DEVICE_ID:
            raise RuntimeError('Unerwartete ADXL345-Gerätekennung an Adresse 0x53')
        regs = [REGISTER_BW_RATE, REGISTER_POWER_CTL, REGISTER_INT_ENABLE,
                REGISTER_DATA_FORMAT, REGISTER_FIFO_CTL]
        original = {r: bus.read_byte_data(ADXL345_ADDRESS, r) for r in regs}
        connection = SensorConnection(bus, lock, original)
        configure_sensor(connection, odr_hz=odr_hz, range_g=range_g, fifo=fifo)
        connection._edge_config.update(bus_number=bus_number,
                                      i2c_clock_configured_hz=clock)
        return connection
    except BaseException:
        if connection is not None:
            connection.close()
        else:
            if bus is not None:
                bus.close()
            lock.close()
        raise


def sensor_configuration(bus):
    return dict(bus._edge_config)


def reset_fifo(bus):
    """Neue Aufnahmegrenze: noch nicht erfasste Vorlaufwerte bewusst verwerfen."""
    if bus._edge_config['acquisition_mode'] != 'fifo_stream':
        raise ValueError('FIFO-Reset benötigt Stream-Modus')
    bus.write_byte_data(ADXL345_ADDRESS, REGISTER_POWER_CTL, 0)
    bus.write_byte_data(ADXL345_ADDRESS, REGISTER_FIFO_CTL, 0)
    # Alten Overrun/Data-ready-Zustand vor der neuen Aufnahmegrenze löschen.
    _read_raw(bus)
    bus.read_byte_data(ADXL345_ADDRESS, REGISTER_INT_SOURCE)
    bus.write_byte_data(ADXL345_ADDRESS, REGISTER_FIFO_CTL, 0x90)
    bus.write_byte_data(ADXL345_ADDRESS, REGISTER_POWER_CTL, 0x08)
    bus._edge_index = 0
    bus._edge_last_ns = None


def _read_raw(bus):
    data = bus.read_i2c_block_data(ADXL345_ADDRESS, REGISTER_DATAX0, 6)
    if len(data) != 6:
        raise IOError(f'Unvollständiger ADXL345-Burst: {len(data)} statt 6 Bytes')
    return struct.unpack('<hhh', bytes(data))


def read_acceleration_g(bus):
    """Kompatibilitätszugriff ohne Frischwertgarantie; neu: read_fresh_sample."""
    return tuple(v * GRAVITY_SCALE_FACTOR for v in _read_raw(bus))


def read_fresh_sample(bus, stop_event=None, timeout_s=1.0):
    """FIFO-Status belegt neues XYZ-Sample, Überlauf keine exakte Verlustzahl.

    INT_SOURCE vor Datenburst prüfen (Auslesen löscht Overrun). Voller FIFO
    ist Verlustverdacht. I²C sichert die nötigen 5 µs zwischen FIFO-Bursts.
    """
    cfg = sensor_configuration(bus)
    if cfg['acquisition_mode'] != 'fifo_stream':
        raise ValueError('Frischwerterfassung benötigt FIFO-Stream-Modus')
    if timeout_s <= 0:
        raise ValueError('timeout_s muss positiv sein')
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if stop_event is not None and stop_event.is_set():
            return None
        begin = time.monotonic_ns()
        source = bus.read_byte_data(ADXL345_ADDRESS, REGISTER_INT_SOURCE)
        count = bus.read_byte_data(ADXL345_ADDRESS, REGISTER_FIFO_STATUS) & 0x3F
        if count > 32:
            raise IOError(f'Ungültiger FIFO-Füllstand: {count}')
        if count:
            raw = _read_raw(bus)
            end = time.monotonic_ns()
            overrun = bool(source & 1) or count == 32
            late = (bus._edge_last_ns is not None and
                    (end - bus._edge_last_ns) / 1e9 > 32 / cfg['odr_hz'])
            rail = 256 * cfg['range_g']
            sample = FreshSample(
                xyz_g=tuple(v * GRAVITY_SCALE_FACTOR for v in raw),
                monotonic_ns=end, sample_index=bus._edge_index,
                sensor_time_estimate_s=bus._edge_index / cfg['odr_hz'],
                fifo_depth=count, overrun=overrun, gap=overrun or late,
                saturated=any(v <= -rail + 1 or v >= rail - 2 for v in raw),
                read_duration_ns=end - begin,
            )
            bus._edge_index += 1
            bus._edge_last_ns = end
            return sample
        delay = min(0.001, 0.2 / cfg['odr_hz'])
        if stop_event is not None:
            stop_event.wait(delay)
        else:
            time.sleep(delay)
    raise TimeoutError(f'Kein neuer ADXL345-FIFO-Wert innerhalb {timeout_s:g} s')
