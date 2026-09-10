"""Announced S1, two50% pilots, final0%; agent stdin gates each new phase.

Uses unchanged project recorder and hardware PWM backend. No training or edits
to existing documents/data. Host timestamps do not measure shaft RPM.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from fan_pwm import FanPWM
from adxl345 import connect
from collect_real_data import record


def utc():
    return datetime.now(timezone.utc).isoformat()


def gate(expected):
    message = json.loads(sys.stdin.readline())
    if message.get('action') != expected:
        raise ValueError(f'Expected an announced phase: {expected}')
    return message


def main():
    confirmation = json.loads((OUT / 'standstill_confirmation.json').read_text())
    if confirmation.get('fan_observed_fully_stopped') is not True:
        raise ValueError('No confirmed full standstill')
    holders = subprocess.run(['fuser', '/dev/i2c-1', '/dev/gpiochip0', '/dev/gpiomem0'],
                             capture_output=True, text=True, timeout=5)
    if holders.returncode != 1 or holders.stdout.strip() or holders.stderr.strip():
        raise RuntimeError('Device holder or unclear preflight')
    for name in ('soffice.bin', 'libreoffice'):
        if subprocess.run(['pgrep', '-x', name], capture_output=True).returncode != 1:
            raise RuntimeError('Document process active')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    session_path = OUT / f'measurement_sequence_{stamp}.json'
    journal = OUT / f'measurement_sequence_{stamp}_fan.jsonl'
    report = {'started_utc': utc(), 'status': 'running', 'recordings': [],
              'fan_journal': str(journal.relative_to(ROOT)), 'training': False,
              'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'standstill_confirmation': confirmation, 'final_requested_percent': 0}

    def persist():
        temporary = session_path.with_suffix('.json.tmp')
        with temporary.open('w') as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, session_path)

    def interrupted(*_):
        raise KeyboardInterrupt('Announced sequence interrupted')

    signal.signal(signal.SIGTERM, interrupted)

    with FanPWM(journal_path=journal) as fan:
        def capture(name, percent, physical_confirmation, settling=None):
            path = Path('data/controlled_20260910') / (
                name + '_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S') + '.csv')
            before = fan.verify(percent)
            metadata = {
                'purpose': 'pilot', 'mounting_id': 'fan_frame_corner_adxl345_gpio18_v1',
                'mounting': 'ADXL345 with intended I2C wiring attached to a corner of ARCTIC P12 Pro PST frame; fan control GPIO18',
                'mounting_unchanged_user_statement': True,
                'fan_pwm_setpoint_percent': float(percent),
                'fan_pwm_source': 'agent_hardware_pwm_command_with_readback_and_pinmux_verification',
                'fan_pwm_frequency_hz': 25000, 'fan_control_journal': report['fan_journal'],
                'physical_state_source': 'operator_visual_confirmation',
                'operator_confirmation': physical_confirmation,
                'settling_seconds_since_pwm_change': settling,
                'rpm_measured': None, 'rpm_method': None, 'rpm_source': 'not_measured',
                'detection_controls_fan': False,
                'sequence_role': name,
                'context': 'new day; no claim of uninterrupted background stationarity since20260909',
            }
            with connect(odr_hz=200, range_g=2, fifo=True) as bus:
                print(json.dumps({'event': 'capture_start', 'utc': utc(), 'name': name,
                                  'seconds': 30, 'pwm_percent': percent, 'csv': str(path)}), flush=True)
                df = record(bus, 30, 200, output_path=path, label=-1 if percent == 0 else 0,
                            state='controlled_standstill_post_operation' if percent == 0 else 'normal_operating_50_percent_pilot',
                            metadata=metadata)
            after = fan.verify(percent)
            item = {'csv': str(path), 'before': before, 'after': after, 'report': df.attrs['report']}
            report['recordings'].append(item)
            persist()
            print(json.dumps({'event': 'capture_completed', 'name': name,
                              'summary': item['report']['summary']}), flush=True)
            if item['report']['status'] != 'completed':
                raise RuntimeError('Pilot did not complete')
            if any(item['report']['summary'][key] for key in (
                    'overrun_flagged_samples', 'gap_flagged_samples', 'saturated_samples')):
                raise RuntimeError('Quality flag: stop sequence for inspection')

        try:
            fan.verify(0)
            capture('standstill_post_operation', 0, confirmation)
            print('WAITING_FOR_ANNOUNCED_50_PERCENT_PHASE', flush=True)
            report['operating_phase_announcement'] = gate('set_50_percent')
            report['setting50'] = fan.set_percent(50)
            start = time.monotonic()
            report['setting50_completed_utc'] = utc()
            print(json.dumps({'event': '50_percent_applied', 'utc': utc(), 'minimum_settling_seconds': 30}), flush=True)
            time.sleep(30)
            report['minimum_settling_elapsed_seconds'] = time.monotonic() - start
            report['after_settling'] = fan.verify(50)
            persist()
            print('WAITING_FOR_VISUAL_STABLE_RUNNING_CONFIRMATION', flush=True)
            running = gate('capture_50_first')
            if running.get('fan_observed_running_uniformly') is not True:
                raise ValueError('No confirmed uniform operation')
            report['running_confirmation'] = running
            capture('operating50_first', 50, running, time.monotonic() - start)
            print('WAITING_FOR_ANNOUNCED_SECOND_50_PERCENT_CAPTURE', flush=True)
            report['second_capture_announcement'] = gate('capture_50_second')
            capture('operating50_second', 50, running, time.monotonic() - start)
            report['status'] = 'completed'
        except BaseException as exc:
            report.update(status='error', error=f'{type(exc).__name__}: {exc}')
            raise
        finally:
            try:
                report['final_zero_command'] = fan.stop()
                report['final_zero_completed_utc'] = utc()
                print(json.dumps({'event': 'final_zero_applied', 'utc': utc(), 'pwm_percent': 0}), flush=True)
                time.sleep(10)
                report['final_zero_readback'] = fan.verify(0)
                report['final_mechanical_standstill'] = 'not_confirmed_after_final_shutdown'
            except BaseException as exc:
                report['final_zero_error'] = f'{type(exc).__name__}: {exc}'
                report['status'] = 'error'
            report['finished_utc'] = utc()
            persist()
    print(json.dumps({'event': 'sequence_finished', 'session': str(session_path.relative_to(ROOT)),
                      'status': report['status'], 'mechanical_standstill': report.get('final_mechanical_standstill')}), flush=True)


if __name__ == '__main__':
    main()
