"""Expliziter Hardwaretest ohne Lüftersteuerung, keine automatische pytest-Suite.

Aufruf aus Repository: .venv/bin/python tests/manual_sensor_checks.py --output <neu>
Absichtlich 250 ms Lesepause zur Überlaufprüfung; separate Daten, Zustand unbestätigt.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import adxl345 as a
import collect_real_data as c


def registers():
    with a.SMBus(1) as bus:
        return {hex(r): hex(bus.read_byte_data(0x53, r)) for r in [0, 0x2c, 0x2d, 0x2e, 0x31, 0x38]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    before = registers()
    report = {'code': c.provenance(), 'registers_before': before,
              'state': 'unconfirmed', 'fan_control_used': False}
    with a.connect(odr_hz=200) as bus:
        time.sleep(.25)  # Vorlauf absichtlich über FIFO-Kapazität.
        a.reset_fifo(bus)
        sample = a.read_fresh_sample(bus)
        report['first_after_reset'] = asdict(sample)
        original = c.read_fresh_sample
        calls = 0
        def delayed(*ar, **kw):
            nonlocal calls
            calls += 1
            if calls == 129:
                time.sleep(.25)
            return original(*ar, **kw)
        c.read_fresh_sample = delayed
        try:
            df = c.record(bus, 3, 200, output_path=args.output/'intentional_overflow.csv',
                          state='technical_intentional_reader_pause',
                          metadata={'purpose': 'pilot', 'injected_reader_pause_ms': 250})
        finally:
            c.read_fresh_sample = original
        report['overflow_summary'] = df.attrs['report']['summary']
    stop_path = args.output/'sigterm.csv'
    process = subprocess.Popen([sys.executable, 'src/collect_real_data.py', '--seconds', '60',
                                '--output', str(stop_path), '--state', 'technical_sigterm_probe'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'Erfassungsprozess vor SIGTERM beendet: {process.communicate()}')
            if stop_path.exists() and stop_path.stat().st_size > 1000:
                break
            time.sleep(.05)
        else:
            raise TimeoutError('Erfassungsprozess hat kein Rohdatenjournal geschrieben')
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=10)
        report['sigterm_process'] = {'returncode': process.returncode, 'stdout': stdout, 'stderr': stderr}
        report['sigterm_metadata'] = json.loads(stop_path.with_suffix('.json').read_text())
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
    report['registers_after'] = registers()
    report['checks'] = {
        'reset_clears_prerun_overflow': not sample.gap and not sample.overrun,
        'deliberate_overflow_detected': report['overflow_summary']['overrun_flagged_samples'] > 0,
        'sigterm_preserves_partial_data': report['sigterm_metadata']['summary']['samples'] > 0 and report['sigterm_metadata']['status'] == 'interrupted',
        'original_registers_restored': report['registers_before'] == report['registers_after'],
    }
    (args.output/'checks.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(report['checks'], indent=2))
    if not all(report['checks'].values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
