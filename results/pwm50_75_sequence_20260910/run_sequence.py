"""Four announced phases, two separate 30-s pilots each, no model training.

Agent stdin gates PWM commands and physical observations. No existing data or
documents are edited. The common PWM lock remains held throughout the sequence.
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
from adxl345 import connect
from collect_real_data import record
from fan_pwm import FanPWM

PHASES = [('standstill_before', 0), ('operating50', 50),
          ('operating75', 75), ('standstill_after', 0)]


def utc():
    return datetime.now(timezone.utc).isoformat()


def emit(event, **details):
    print(json.dumps({'event': event, 'utc': utc(), **details}, ensure_ascii=False), flush=True)


def gate(action, phase):
    message = json.loads(sys.stdin.readline())
    if message.get('action') != action or message.get('phase') != phase:
        raise ValueError(f'Expected announced action {action} for {phase}')
    message['received_by_runner_utc'] = utc()
    return message


def main():
    holders = subprocess.run(['fuser', '/dev/i2c-1', '/dev/gpiochip0', '/dev/gpiomem0'],
                             capture_output=True, text=True, timeout=5)
    if holders.returncode != 1 or holders.stdout.strip() or holders.stderr.strip():
        raise RuntimeError('Device access in use or unclear')
    for name in ('soffice.bin', 'libreoffice'):
        if subprocess.run(['pgrep', '-x', name], capture_output=True).returncode != 1:
            raise RuntimeError('Document renderer active')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    session_path = OUT / f'sequence_{stamp}.json'
    with session_path.open('x') as handle:
        handle.write('{}\n')
    journal = OUT / f'sequence_{stamp}_fan.jsonl'
    report = {'started_utc': utc(), 'status': 'running', 'phases': [], 'recordings': [],
              'fan_journal': str(journal.relative_to(ROOT)), 'training': False,
              'induced_anomalies': False, 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'protocol': 'standstill_before -> 50% -> 75% -> standstill_after; two30s files per phase;5s between repeats',
              'final_requested_percent': 0, 'final_mechanical_state': 'not_yet_confirmed'}

    def persist():
        temporary = session_path.with_suffix('.json.tmp')
        with temporary.open('w') as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, session_path)

    def interrupted(*_):
        raise KeyboardInterrupt('Sequence interrupted')

    signal.signal(signal.SIGTERM, interrupted)
    with FanPWM(journal_path=journal) as fan:
        try:
            report['initial_readback'] = fan.verify(0)
            persist()
            for phase_index, (phase, percent) in enumerate(PHASES):
                phase_report = {'phase': phase, 'pwm_percent': percent, 'started_utc': utc(), 'recordings': []}
                report['phases'].append(phase_report)
                setting_start = None
                if phase_index:
                    emit('waiting_for_announced_setting', phase=phase, requested_percent=percent)
                    phase_report['setting_announcement'] = gate('set_phase', phase)
                    phase_report['setting_result'] = fan.set_percent(percent)
                    phase_report['setting_completed_utc'] = utc()
                    setting_start = time.monotonic()
                    minimum_wait = 10 if percent == 0 else 30
                    emit('setting_applied', phase=phase, pwm_percent=percent, minimum_wait_s=minimum_wait)
                    time.sleep(minimum_wait)
                    phase_report['minimum_wait_elapsed_s'] = time.monotonic() - setting_start
                phase_report['readback_before_confirmation'] = fan.verify(percent)
                persist()
                emit('waiting_for_physical_confirmation', phase=phase, pwm_percent=percent)
                confirmation = gate('capture_phase', phase)
                key = 'fan_observed_fully_stopped' if percent == 0 else 'fan_observed_running_uniformly'
                if confirmation.get(key) is not True or not confirmation.get('operator_answer'):
                    raise ValueError('Actual positive physical observation required')
                phase_report['operator_confirmation'] = confirmation
                phase_report['observation_scope'] = 'both recordings at unchanged phase setting; mounting unchanged per user instruction'
                for repeat in (1, 2):
                    before = fan.verify(percent)
                    path = Path('data/pwm50_75_sequence_20260910') / (
                        f'{phase}_r{repeat}_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S') + '.csv')
                    metadata = {
                        'purpose': 'pilot', 'sequence_id': session_path.stem,
                        'sequence_phase': phase, 'phase_repeat': repeat,
                        'mounting': 'ADXL345 with intended I2C wiring attached to a corner of ARCTIC P12 Pro PST frame; fan control GPIO18',
                        'mounting_id': 'fan_frame_corner_adxl345_gpio18_v1',
                        'mounting_unchanged_user_instruction': True,
                        'fan_pwm_setpoint_percent': float(percent), 'fan_pwm_frequency_hz': 25000,
                        'fan_pwm_source': 'agent_hardware_pwm_command_with_readback_and_pinmux_verification',
                        'fan_control_journal': report['fan_journal'],
                        'physical_state_source': 'operator_visual_confirmation_for_unchanged_phase',
                        'operator_confirmation': confirmation,
                        'elapsed_since_phase_pwm_command_s': time.monotonic() - setting_start if setting_start else None,
                        'rpm_measured': None, 'rpm_method': None, 'rpm_source': 'not_measured',
                        'detection_controls_fan': False, 'induced_anomaly': False,
                        'repeat_design': 'two files within one continuously held state, not two independent restarts',
                    }
                    with connect(odr_hz=200, range_g=2, fifo=True) as bus:
                        emit('capture_start', phase=phase, repeat=repeat, seconds=30,
                             pwm_percent=percent, csv=str(path))
                        df = record(bus, 30, 200, output_path=path, label=-1 if percent == 0 else 0,
                                    state='controlled_' + phase + '_pilot', metadata=metadata)
                    after = fan.verify(percent)
                    item = {'phase': phase, 'repeat': repeat, 'csv': str(path),
                            'before': before, 'after': after, 'report': df.attrs['report']}
                    report['recordings'].append(item)
                    phase_report['recordings'].append(str(path))
                    persist()
                    summary = item['report']['summary']
                    emit('capture_completed', phase=phase, repeat=repeat, summary=summary)
                    if item['report']['status'] != 'completed' or any(summary[k] for k in (
                            'overrun_flagged_samples', 'gap_flagged_samples', 'saturated_samples')):
                        raise RuntimeError('Incomplete capture or flagged data: inspect before continuation')
                    if repeat == 1:
                        emit('inter_recording_pause', phase=phase, seconds=5, next_repeat=2)
                        time.sleep(5)
                phase_report['finished_utc'] = utc()
                persist()
                emit('phase_completed', phase=phase)
            report['final_readback'] = fan.verify(0)
            report['final_mechanical_state'] = 'operator_confirmed_standstill_before_final_two_recordings; no subsequent setting change'
            report['status'] = 'completed'
        except BaseException as exc:
            report.update(status='error', error=f'{type(exc).__name__}: {exc}')
            try:
                report['abort_zero_command'] = fan.stop()
                report['abort_zero_utc'] = utc()
                report['final_mechanical_state'] = 'not_confirmed_after_abort_shutdown'
                emit('abort_zero_applied', pwm_percent=0)
            except BaseException as stop_error:
                report['abort_zero_error'] = f'{type(stop_error).__name__}: {stop_error}'
            raise
        finally:
            report['finished_utc'] = utc()
            persist()
    emit('sequence_finished', status=report['status'], session=str(session_path.relative_to(ROOT)),
         recordings=len(report['recordings']), pwm_percent=0, mechanical_state=report['final_mechanical_state'])


if __name__ == '__main__':
    main()
