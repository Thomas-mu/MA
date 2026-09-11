"""Two initial or one closing30-s references; no positive PWM commands."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

from pilot_common import ROOT, BASE, MOUNTING_ID, mounting_metadata, persist, require_standstill, utc
sys.path.insert(0, str(ROOT / 'src'))
from adxl345 import connect
from collect_real_data import record
from fan_pwm import FanPWM


def emit(event, **details):
    print(json.dumps({'event': event, 'utc': utc(), **details}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('before', 'after'), required=True)
    phase = parser.parse_args().phase
    confirmation = require_standstill(phase)
    if phase == 'after':
        operation = json.loads((BASE / 'session.json').read_text())
        if operation['final_readback']['pwm_configuration']['configured_duty_percent'] != 0:
            raise ValueError('Operating session has not verified zero')
        if datetime.fromisoformat(confirmation['recorded_utc']) <= datetime.fromisoformat(operation['zero_command_completed_utc']):
            raise ValueError('Closing standstill confirmation must follow final shutdown')
    holders = subprocess.run(['fuser', '-v', '/dev/i2c-1', '/dev/gpiochip0', '/dev/gpiomem0'], capture_output=True, text=True, timeout=5)
    if holders.returncode != 1 or holders.stdout or holders.stderr:
        raise RuntimeError('Device access in use or unclear')
    session_path = BASE / f'{phase}_session.json'
    journal = BASE / f'{phase}_fan.jsonl'
    if journal.exists() or session_path.exists():
        raise FileExistsError('Existing phase must not be overwritten')
    with session_path.open('x') as handle:
        handle.write('{}\n')
    session = {'started_utc': utc(), 'status': 'running', 'phase': phase, 'mounting_id': MOUNTING_ID,
               'recordings': [], 'operator_confirmation': confirmation,
               'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'common_sha256': hashlib.sha256((BASE / 'pilot_common.py').read_bytes()).hexdigest(),
               'fan_journal': str(journal.relative_to(ROOT)), 'training': False, 'induced_anomalies': False}

    def interrupt(*_):
        raise KeyboardInterrupt('Reference capture interrupted')

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    failure = None
    with FanPWM(journal_path=journal) as fan:
        try:
            session['initial_readback'] = fan.verify(0)
            persist(session_path, session)
            for repeat in range(1, (2 if phase == 'before' else 1) + 1):
                before = fan.verify(0)
                stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
                path = Path('data') / BASE.name / f'standstill_{phase}_r{repeat}_{stamp}.csv'
                metadata = {**mounting_metadata(), 'purpose': 'pilot', 'sequence_id': BASE.name,
                            'sequence_phase': f'standstill_{phase}', 'phase_repeat': repeat,
                            'fan_pwm_setpoint_percent': 0.0, 'fan_pwm_frequency_hz': 25000,
                            'fan_12v_supply_connected_user_confirmed': True,
                            'fan_pwm_source': 'verified_existing_zero_hardware_pwm',
                            'fan_control_journal': session['fan_journal'],
                            'physical_state_source': 'explicit_operator_full_standstill_confirmation',
                            'operator_confirmation': confirmation,
                            'rpm_measured': None, 'rpm_method': None, 'rpm_source': 'not_measured',
                            'detection_controls_fan': False, 'induced_anomaly': False}
                with connect(odr_hz=200, range_g=2, fifo=True) as bus:
                    emit('capture_start', phase=phase, repeat=repeat, seconds=30, pwm_percent=0, csv=str(path))
                    df = record(bus, 30, 200, output_path=path, label=-1,
                                state=f'controlled_standstill_{phase}_new_mount_pilot', metadata=metadata)
                after = fan.verify(0)
                session['recordings'].append({'csv': str(path), 'repeat': repeat, 'before': before,
                                               'after': after, 'report': df.attrs['report']})
                persist(session_path, session)
                emit('capture_completed', phase=phase, repeat=repeat, summary=df.attrs['report']['summary'])
                if df.attrs['report']['status'] != 'completed':
                    raise RuntimeError('Reference incomplete')
                if phase == 'before' and repeat == 1:
                    time.sleep(5)
            session['status'] = 'completed'
            session['final_readback'] = fan.verify(0)
        except BaseException as exc:
            failure = exc
            session.update(status='error', error=f'{type(exc).__name__}: {exc}')
            try:
                session['error_zero_command'] = fan.stop()
                session['final_readback'] = fan.verify(0)
            except BaseException as stop_error:
                session['zero_error'] = f'{type(stop_error).__name__}: {stop_error}'
        finally:
            session['finished_utc'] = utc()
            persist(session_path, session)
    emit('phase_finished', phase=phase, status=session['status'], session=str(session_path.relative_to(ROOT)))
    if failure:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
