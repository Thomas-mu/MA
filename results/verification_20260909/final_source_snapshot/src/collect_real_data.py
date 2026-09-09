"""Journalisierte FIFO-Aufnahmen; keine automatische Zustands- oder RPM-Annahme."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
import platform
from pathlib import Path
import signal
import subprocess
import sys
import time

import pandas as pd

from adxl345 import connect, read_fresh_sample, sensor_configuration, reset_fifo

SAMPLE_RATE_HZ = 200
OUTPUT_DIRECTORY = Path('data/acquisition')
FIELDS = ['timestamp_s', 'signal', 'x_g', 'y_g', 'z_g', 'label', 'anomaly_type',
          'source', 'sample_index', 'host_monotonic_ns', 'sensor_time_estimate_s',
          'fifo_depth', 'overrun', 'gap', 'saturated', 'read_duration_ns']


def provenance():
    root = Path(__file__).resolve().parents[1]
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
    return {
        'git_commit': git('rev-parse', 'HEAD'), 'git_status': git('status', '--porcelain'),
        'command': sys.argv, 'python_executable': sys.executable,
        'python_version': sys.version, 'platform': platform.platform(),
        'packages': {name: importlib.metadata.version(name) for name in ['numpy', 'pandas', 'smbus2']},
        'source_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted((root / 'src').glob('*.py'))},
    }


def recording_summary(dataframe, odr_hz):
    n = len(dataframe)
    if not n:
        return {'samples': 0, 'observed_host_rate_hz': None}
    dt = dataframe.host_monotonic_ns.diff().dropna() / 1e9
    xyz = dataframe[['x_g', 'y_g', 'z_g']]
    return {
        'samples': n,
        'observed_host_rate_hz': ((n - 1) * 1e9 / (int(dataframe.host_monotonic_ns.iloc[-1]) -
                                  int(dataframe.host_monotonic_ns.iloc[0]))) if n > 1 else None,
        'host_interval_p50_ms': float(dt.median() * 1000) if len(dt) else None,
        'host_interval_p99_ms': float(dt.quantile(.99) * 1000) if len(dt) else None,
        'host_interval_max_ms': float(dt.max() * 1000) if len(dt) else None,
        'host_intervals_over_2_periods': int((dt > 2 / odr_hz).sum()),
        'nonmonotonic_host_intervals': int((dt <= 0).sum()),
        'fifo_depth_max': int(dataframe.fifo_depth.max()),
        'overrun_flagged_samples': int(dataframe.overrun.sum()),
        'gap_flagged_samples': int(dataframe.gap.sum()),
        'saturated_samples': int(dataframe.saturated.sum()),
        'consecutive_equal_xyz_fraction': float((xyz.diff().iloc[1:] == 0).all(axis=1).mean()) if n > 1 else None,
        'lost_samples_exact': None,
        'limits': 'FIFO flags detect possible loss, not exact counts; host intervals are not sensor conversion intervals.',
    }


def record(bus, duration_seconds, sample_rate_hz, *, output_path=None, label=-1,
           state='unconfirmed', metadata=None, stop_event=None):
    """Schreibt jeden gelesenen Wert sofort ins Journal, auch unvollständige Fenster.

    SIGINT/Fehler werden nach dem Sichern weitergereicht. Auch alte Aufrufer ohne
    output_path erhalten ein neues Journal statt ausschließlich flüchtigen RAM.
    """
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError('Aufnahmedauer muss endlich und positiv sein')
    config = sensor_configuration(bus)
    if sample_rate_hz != config['odr_hz']:
        raise ValueError(f'Angeforderte {sample_rate_hz} Hz passen nicht zur konfigurierten '
                         f"Sensor-ODR {config['odr_hz']} Hz; keine implizite Neuabtastung.")
    if label not in (-1, 0, 1):
        raise ValueError('label muss -1 (unbestätigt), 0 oder 1 sein')
    path = Path(output_path) if output_path else OUTPUT_DIRECTORY / (
        datetime.now().strftime('recording_%Y%m%d_%H%M%S_%f.csv'))
    path.parent.mkdir(parents=True, exist_ok=True)
    sidecar = path.with_suffix('.json')
    if path.exists() or sidecar.exists():
        raise FileExistsError(f'Aufnahme wird nicht überschrieben: {path}')
    report = dict(metadata or {})
    report.update(schema_version=1, recording_id=path.stem, path=str(path),
                  started_at_utc=datetime.now(timezone.utc).isoformat(),
                  configured_duration_seconds=duration_seconds, label=label, state=state,
                  sensor=config, code=provenance(), status='recording',
                  timestamp_note='timestamp_s is relative host read completion; sensor_time_estimate_s is nominal only')
    with sidecar.open('x') as f:
        json.dump(report, f, indent=2, allow_nan=False)
    rows = []
    start = time.monotonic_ns()
    last_flush = start
    error = None
    try:
        with path.open('x', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            reset_fifo(bus)
            start = time.monotonic_ns()
            try:
                while (time.monotonic_ns() - start) / 1e9 < duration_seconds:
                    s = read_fresh_sample(bus, stop_event=stop_event)
                    if s is None:
                        report['status'] = 'stopped'
                        break
                    x, y, z = s.xyz_g
                    row = dict(timestamp_s=(s.monotonic_ns - start) / 1e9,
                               signal=math.sqrt(x*x + y*y + z*z), x_g=x, y_g=y, z_g=z,
                               label=label, anomaly_type=state, source='real_fifo',
                               sample_index=s.sample_index, host_monotonic_ns=s.monotonic_ns,
                               sensor_time_estimate_s=s.sensor_time_estimate_s,
                               fifo_depth=s.fifo_depth, overrun=s.overrun, gap=s.gap,
                               saturated=s.saturated, read_duration_ns=s.read_duration_ns)
                    writer.writerow(row)
                    rows.append(row)
                    if s.monotonic_ns - last_flush >= 1_000_000_000:
                        f.flush()
                        last_flush = s.monotonic_ns
                else:
                    report['status'] = 'completed'
            finally:
                f.flush()
                os.fsync(f.fileno())
    except BaseException as exc:
        error = exc
        report.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'error',
                      error=f'{type(exc).__name__}: {exc}')
    finally:
        df = pd.DataFrame(rows, columns=FIELDS)
        report.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),
                      summary=recording_summary(df, sample_rate_hz))
        if path.exists():
            report['csv_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        tmp = sidecar.with_suffix('.json.tmp')
        with tmp.open('x') as f:
            json.dump(report, f, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, sidecar)
    if error is not None:
        raise error
    df.attrs.update(recording_path=str(path), metadata_path=str(sidecar), report=report)
    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--odr', type=int, default=200)
    parser.add_argument('--range-g', type=int, choices=[2, 4, 8, 16], default=2)
    parser.add_argument('--label', choices=['unknown', 'normal', 'anomaly'], default='unknown')
    parser.add_argument('--state', '--anomaly-type', dest='state', default='unconfirmed')
    parser.add_argument('--purpose', choices=['pilot', 'training', 'validation', 'test'], default='pilot')
    parser.add_argument('--mounting', default='not_documented')
    parser.add_argument('--fan-pwm-setpoint', type=float, help='Dokumentierte externe Vorgabe in Prozent; steuert keinen GPIO')
    parser.add_argument('--rpm-measured', type=float, help='Unabhängig gemessene Drehzahl, niemals aus PWM berechnet')
    parser.add_argument('--rpm-method', default=None)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.fan_pwm_setpoint is not None and not (0 <= args.fan_pwm_setpoint <= 100):
        parser.error('PWM muss zwischen 0 und 100 Prozent liegen')
    if args.rpm_measured is not None and (not math.isfinite(args.rpm_measured) or args.rpm_measured < 0 or not args.rpm_method):
        parser.error('Drehzahl muss endlich/nichtnegativ sein; --rpm-method erforderlich')
    if args.purpose != 'pilot' and (args.label == 'unknown' or args.state == 'unconfirmed' or args.mounting == 'not_documented'):
        parser.error('Für Training/Validierung/Test sind --label, --state und --mounting erforderlich')
    def stop(*_):
        raise KeyboardInterrupt('Stopp-Signal empfangen')
    signal.signal(signal.SIGTERM, stop)
    metadata = dict(purpose=args.purpose, mounting=args.mounting,
                    fan_pwm_setpoint_percent=args.fan_pwm_setpoint,
                    fan_pwm_source='operator_documented_external_setting' if args.fan_pwm_setpoint is not None else 'unknown',
                    rpm_measured=args.rpm_measured, rpm_method=args.rpm_method,
                    rpm_source='operator_supplied_measurement' if args.rpm_measured is not None else 'not_measured',
                    detection_controls_fan=False)
    try:
        with connect(odr_hz=args.odr, range_g=args.range_g) as bus:
            df = record(bus, args.seconds, args.odr, output_path=args.output,
                        label={'unknown': -1, 'normal': 0, 'anomaly': 1}[args.label],
                        state=args.state, metadata=metadata)
        print(json.dumps({'path': df.attrs['recording_path'], 'summary': df.attrs['report']['summary']}, indent=2))
    except KeyboardInterrupt:
        print('Aufnahme abgebrochen; gelesene Werte und Abbruchstatus im CSV/JSON-Journal gesichert.')
        raise SystemExit(130)


if __name__ == '__main__':
    main()
