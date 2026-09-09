"""Announced 25-% pilot; stdin confirmation gates capture after 30 s settling.

Leaves last PWM setting unchanged on close. Uses existing FanPWM + FIFO recorder.
Run only for the explicitly announced bench trial, not as a background service.
"""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import signal
import subprocess
import sys
import time

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / 'src'))
from fan_pwm import FanPWM
from adxl345 import connect
from collect_real_data import record

out = PROJECT / 'results/hardware_confirmation_20260909'
stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
path = PROJECT / f'data/controlled_20260909/operating25_{stamp}.csv'
journal = out / f'operating25_{stamp}_fan.jsonl'
session = out / f'operating25_{stamp}_session.json'
report = {'phase': 'operating_pilot_25_percent', 'requested_utc': datetime.now(timezone.utc).isoformat(),
          'csv': str(path.relative_to(PROJECT)), 'fan_journal': str(journal.relative_to(PROJECT)),
          'status': 'preflight', 'mounting_id': 'fan_frame_corner_adxl345_gpio18_v1',
          'user_readiness': 'Ja, bereit', 'rpm_measured': None,
          'output_on_exit': 'leave_last_setting_unchanged'}
for executable in ['soffice.bin', 'libreoffice']:
    check = subprocess.run(['pgrep', '-x', executable], capture_output=True, text=True, timeout=5)
    if check.returncode != 1:
        raise RuntimeError('Document renderer active or process check failed')
holders = subprocess.run(['fuser', '/dev/i2c-1', '/dev/gpiochip0', '/dev/gpiomem0'], capture_output=True, text=True, timeout=5)
if holders.returncode != 1 or holders.stdout.strip() or holders.stderr.strip():
    raise RuntimeError('Device holder or unclear device preflight')

def interrupt(*args):
    raise KeyboardInterrupt('Recording interrupted')
signal.signal(signal.SIGTERM, interrupt)
try:
    with FanPWM(journal_path=journal) as fan:
        report['fan_before'] = fan.verify(0)
        report['fan_command_result'] = fan.set_percent(25)
        report['setting_applied_utc'] = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()
        print(json.dumps({'event': '25_percent_applied', 'utc': report['setting_applied_utc'],
                          'setting': report['fan_command_result']['pwm_configuration'], 'settling_seconds': 30}), flush=True)
        time.sleep(30)
        report['minimum_settling_elapsed_s'] = time.monotonic() - start
        report['fan_after_settling'] = fan.verify(25)
        print('SETTLED_WAITING_FOR_VISUAL_RUNNING_CONFIRMATION_AND_CAPTURE_ANNOUNCEMENT', flush=True)
        confirmation = json.loads(sys.stdin.readline())
        if confirmation.get('fan_observed_running') is not True:
            raise RuntimeError('No positive running observation; capture not started')
        report['operator_confirmation'] = confirmation
        report['operator_confirmation_received_utc'] = datetime.now(timezone.utc).isoformat()
        with connect(odr_hz=200, range_g=2, fifo=True) as bus:
            report['fan_before_capture'] = fan.verify(25)
            metadata = {'purpose': 'pilot', 'mounting': 'ADXL345 with intended I2C wiring attached to a corner of ARCTIC P12 Pro PST frame; fan control GPIO18',
                        'mounting_id': report['mounting_id'], 'hardware_confirmation_source': 'results/hardware_confirmation_20260909/user_confirmation_and_backup.json',
                        'fan_pwm_setpoint_percent': 25.0, 'fan_pwm_source': 'agent_hardware_pwm_command_with_readback_and_pinmux_verification',
                        'fan_control_journal': report['fan_journal'], 'rpm_measured': None, 'rpm_method': None, 'rpm_source': 'not_measured',
                        'physical_state_source': 'operator_visual_running_observation', 'operator_confirmation': confirmation,
                        'settling_seconds_before_capture': time.monotonic() - start, 'detection_controls_fan': False}
            print(json.dumps({'event': 'capture_start', 'utc': datetime.now(timezone.utc).isoformat(), 'seconds': 30, 'pwm_percent': 25, 'csv': report['csv']}), flush=True)
            data = record(bus, 30, 200, output_path=path, label=0, state='normal_operating_25_percent_pilot', metadata=metadata)
            report['capture_report'] = data.attrs['report']
        report['fan_after_capture'] = fan.verify(25)
        report['status'] = report['capture_report']['status']
except BaseException as exc:
    report.update(status='error', error=f'{type(exc).__name__}: {exc}')
    raise
finally:
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    with session.open('x') as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
print(json.dumps({'session': str(session.relative_to(PROJECT)), 'status': report['status'], 'summary': report['capture_report']['summary']}, ensure_ascii=False), flush=True)
