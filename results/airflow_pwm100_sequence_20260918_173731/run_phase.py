"""One operator-confirmed phase at 100% PWM; reuse frozen v4 processing unchanged."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')

def utc():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))
    os.replace(temporary, path)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['normal_before', 'airflow_modified', 'normal_after'], required=True)
    args = parser.parse_args()
    plan = json.loads((BASE / 'plan.json').read_text())
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != plan['boot_id']:
        raise RuntimeError('Boot changed; do not reuse physical confirmations')
    for name, expected in plan['implementation_sha256'].items():
        if sha(name) != expected:
            raise RuntimeError(f'Implementation changed: {name}')
    release_path = BASE / f'{args.phase}_condition.json'
    condition = json.loads(release_path.read_text())
    present = args.phase == 'airflow_modified'
    if condition.get('phase') != args.phase or condition.get('plate_present') is not present:
        raise ValueError('Phase and reported plate state disagree')
    if condition.get('source') != 'explicit_user_message' or condition.get('ready') is not True:
        raise ValueError('Actual plate condition must be reported by operator')
    index = plan['phases'].index(args.phase)
    zero_ns = plan['zero_command_completed_monotonic_ns']
    if index:
        prior = json.loads((BASE / f'{plan["phases"][index-1]}_session.json').read_text())
        if prior['status'] != 'completed':
            raise ValueError('Previous phase did not complete')
        if condition['accepted_monotonic_ns'] <= prior['zero_command_completed_monotonic_ns']:
            raise ValueError('Plate change must follow prior shutdown')
        zero_ns = prior['zero_command_completed_monotonic_ns']
    path = BASE / f'{args.phase}_session.json'
    session = dict(phase=args.phase, status='preflight', started_utc=utc(),
                   plan_sha256=sha(BASE / 'plan.json'), condition=condition,
                   condition_sha256=sha(release_path), pwm_percent=100, duration_s=300,
                   evaluation_mode='offline_after_capture', condition_is_defect_truth=False)
    with path.open('x') as f:
        json.dump(session, f, indent=2)
    stop = threading.Event()
    def cancel(*_):
        stop.set()
        raise KeyboardInterrupt('Operator stop')
    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)
    from fan_pwm import FanPWM
    from adxl345 import connect, sensor_configuration
    from collect_real_data import record
    from prepare_pilot_dataset import EXPECTED_SENSOR
    from pilot_runtime_final import FrozenEngine
    from independent_normal_test import build_windows, summarize_quality
    engine = FrozenEngine(plan['frozen_bundle_directory'])
    engine.warmup()
    session['bundle_sha256'] = sha(engine.directory / 'pilot_bundle.json')
    session['thresholds'] = engine.bundle['thresholds']
    progress_done = threading.Event()
    def heartbeat():
        while not progress_done.wait(30):
            elapsed = (time.monotonic_ns()-session['command_invocation_monotonic_ns'])/1e9
            print(json.dumps(dict(phase=args.phase, elapsed_s=round(elapsed, 1), target_s=300)), flush=True)
    progress = None
    try:
        with FanPWM(journal_path=BASE / f'{args.phase}_fan.jsonl') as fan:
            fan.verify(0)
            target = max(zero_ns, condition['accepted_monotonic_ns']) + 60_000_000_000
            while time.monotonic_ns() < target:
                time.sleep(min(1, (target-time.monotonic_ns())/1e9))
            with closing(connect(odr_hz=200, range_g=2, fifo=True)) as bus:
                sensor = sensor_configuration(bus)
                if any(sensor.get(k) != v for k,v in EXPECTED_SENSOR.items()):
                    raise ValueError('Sensor configuration differs from frozen v4 model input')
                csv_path = BASE / f'{args.phase}_100pwm_300s.csv'
                session['csv'] = str(csv_path)
                session['sensor'] = sensor
                try:
                    session['command_invocation_utc'] = utc()
                    session['command_invocation_monotonic_ns'] = time.monotonic_ns()
                    session['setting_result'] = fan.set_percent(100)
                    session['status'] = 'recording'
                    save(path, session)
                    print(f'{args.phase}: recording 300 seconds at verified 100% PWM.', flush=True)
                    progress = threading.Thread(target=heartbeat, daemon=True)
                    progress.start()
                    frame = record(bus, 300, 200, output_path=csv_path,
                        label=1 if present else 0, state='airflow_modified' if present else 'normal',
                        stop_event=stop, metadata=dict(
                            phase=args.phase, purpose='exploratory_plate_sequence_pwm100',
                            fan_pwm_setpoint_percent=100, fan_pwm_frequency_hz=25000,
                            pwm_command_invocation_monotonic_ns=session['command_invocation_monotonic_ns'],
                            pwm_command_invocation_utc=session['command_invocation_utc'],
                            user_condition=condition, plate_present=present,
                            condition_is_defect_truth=False, detection_controls_fan=False,
                            measured_rpm=None, mounting_identity_verified=False,
                            model_reference_pwm_percent=75,
                            frozen_bundle_sha256=session['bundle_sha256']))
                    session['recording'] = frame.attrs['report']
                    if session['recording']['status'] != 'completed':
                        raise RuntimeError('Recording incomplete')
                    session['pwm_after_capture'] = fan.verify(100)
                finally:
                    progress_done.set()
                    session['final_readback'] = fan.stop()
                    fan.verify(0)
                    session['zero_command_completed_monotonic_ns'] = time.monotonic_ns()
                    session['zero_command_completed_utc'] = utc()
                    save(path, session)
                    print('PWM set to verified 0%; phase capture ended.', flush=True)
        windows, selection = build_windows(frame, session['command_invocation_monotonic_ns'])
        session['quality'] = summarize_quality(frame, session['command_invocation_monotonic_ns'])
        session['selection'] = selection
        rows = []
        with (BASE / f'{args.phase}_decisions.jsonl').open('x') as f:
            for window in windows:
                for row in engine.score(window):
                    row['phase'] = args.phase
                    rows.append(row)
                    f.write(json.dumps(row, allow_nan=False)+'\n')
        import numpy as np
        metrics = {}
        for method in engine.methods:
            chosen = [r for r in rows if r['method'] == method]
            valid = [r for r in chosen if r['decision'] in ('NORMAL', 'ANOMALY')]
            alarms = sum(r['decision'] == 'ANOMALY' for r in valid)
            metrics[method] = dict(total_windows=len(chosen), valid_windows=len(valid),
                invalid_windows=len(chosen)-len(valid), alarm_windows=alarms,
                alarm_fraction=alarms/len(valid) if valid else None,
                mean_score=float(np.mean([r['score'] for r in valid])) if valid else None,
                threshold=engine.bundle['thresholds'][method]['value'])
        session.update(status='completed', metrics=metrics, finished_utc=utc())
        save(path, session)
        print(json.dumps(dict(phase=args.phase, status='completed', metrics=metrics), indent=2), flush=True)
    except BaseException as exc:
        session.update(status='error', error=f'{type(exc).__name__}: {exc}', finished_utc=utc())
        save(path, session)
        raise
    finally:
        progress_done.set()
        if progress is not None:
            progress.join(timeout=1)

if __name__ == '__main__':
    main()
