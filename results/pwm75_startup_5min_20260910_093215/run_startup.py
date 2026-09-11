"""One announced300-s startup recording with no chat-response deadline."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from adxl345 import connect
from collect_real_data import record, provenance
from fan_pwm import FanPWM


def utc():
    return datetime.now(timezone.utc).isoformat()


def emit(event, **fields):
    print(json.dumps({'event': event, 'utc': utc(), **fields}, ensure_ascii=False), flush=True)


def persist(path, obj):
    tmp = path.with_suffix('.json.tmp')
    with tmp.open('x', encoding='utf-8') as handle:
        json.dump(obj, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def main():
    confirmation_path = BASE / 'prestart_standstill_confirmation.json'
    confirmation = json.loads(confirmation_path.read_text())
    if (confirmation.get('fan_observed_fully_stopped') is not True or
            confirmation.get('mounting_unchanged') is not True or not confirmation.get('operator_answer')):
        raise ValueError('Fresh visual full standstill confirmation required')
    holders = subprocess.run(['fuser', '-v', '/dev/i2c-1', '/dev/gpiochip0', '/dev/gpiomem0'],
                             capture_output=True, text=True, timeout=5)
    if holders.returncode != 1 or holders.stdout or holders.stderr:
        raise RuntimeError('Device access in use or unclear')
    session_path, journal = BASE / 'session.json', BASE / 'fan.jsonl'
    if session_path.exists() or journal.exists():
        raise FileExistsError('Existing attempt must not be overwritten or restarted')
    with session_path.open('x') as handle:
        handle.write('{}\n')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    csv_path = Path('data') / BASE.name / f'normal75_startup300s_{stamp}.csv'
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    session = {
        'started_utc': utc(), 'status': 'preflight', 'csv': str(csv_path),
        'fan_journal': str(journal.relative_to(ROOT)), 'requested_duration_s': 300,
        'intentional_settling_delay_s': 0, 'no_chat_response_deadline': True,
        'prestart_standstill_confirmation': confirmation,
        'prestart_confirmation_sha256': hashlib.sha256(confirmation_path.read_bytes()).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'models_trained': False, 'induced_anomalies': False,
        'final_mechanical_state': 'not_yet_confirmed_after_shutdown',
    }
    persist(session_path, session)
    started, done = threading.Event(), threading.Event()
    command_clock = {}

    def progress():
        while not started.wait(.1):
            if done.is_set():
                return
        while not done.wait(30):
            emit('recording_progress', elapsed_since_command_completion_s=
                 (time.monotonic_ns() - command_clock['completed_ns']) / 1e9,
                 requested_duration_s=300, message='Time progress only; no physical-state or sample-count inference')

    heartbeat = threading.Thread(target=progress, daemon=True)
    heartbeat.start()

    def interrupted(*_):
        raise KeyboardInterrupt('Startup recording interrupted; attempt announced return to zero')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    failure = None
    with FanPWM(journal_path=journal) as fan:
        try:
            session['initial_readback'] = fan.verify(0)
            with connect(odr_hz=200, range_g=2, fifo=True) as bus:
                # Prepare provenance/cache and metadata while the fan remains at zero.
                session['prepared_provenance'] = provenance()
                metadata = {
                    'purpose': 'pilot', 'sequence_id': BASE.name,
                    'measurement_design': 'one uninterrupted300-s intended normal startup; no pre-record settling',
                    'mounting': 'ADXL345 with intended I2C wiring attached to a corner of ARCTIC P12 Pro PST frame; GPIO18 fan control',
                    'mounting_id': 'fan_frame_corner_adxl345_gpio18_v1',
                    'mounting_unchanged_user_instruction': True,
                    'fan_pwm_setpoint_percent': 75.0, 'fan_pwm_frequency_hz': 25000,
                    'fan_pwm_source': 'announced_existing_hardware_pwm_command_with_readback',
                    'fan_control_journal': session['fan_journal'],
                    'physical_state_source': 'prestart_standstill_confirmed; subsequent_running_observation_reported_separately',
                    'standstill_confirmation': confirmation, 'operator_running_confirmation_at_capture': None,
                    'intentional_settling_delay_s': 0, 'no_chat_response_deadline': True,
                    'rpm_measured': None, 'rpm_method': None, 'rpm_source': 'not_measured',
                    'detection_controls_fan': False, 'induced_anomaly': False,
                }
                persist(session_path, session)
                session['command_invocation_utc'] = utc()
                session['command_invocation_monotonic_ns'] = time.monotonic_ns()
                session['setting_result'] = fan.set_percent(75)
                command_clock['completed_ns'] = time.monotonic_ns()
                session['command_completed_monotonic_ns'] = command_clock['completed_ns']
                session['command_completed_utc'] = utc()
                metadata.update(
                    pwm_command_invocation_monotonic_ns=session['command_invocation_monotonic_ns'],
                    pwm_command_completed_monotonic_ns=session['command_completed_monotonic_ns'],
                    pwm_command_invocation_utc=session['command_invocation_utc'],
                    pwm_command_completed_utc=session['command_completed_utc'])
                session['record_invoked_monotonic_ns'] = time.monotonic_ns()
                session['status'] = 'recording'
                started.set()
                emit('75_percent_applied_recording_now', pwm_percent=75, frequency_hz=25000,
                     duration_s=300, command_completed_utc=session['command_completed_utc'], csv=str(csv_path))
                # No intentional delay or additional journal fsync between command and recorder.
                df = record(bus, 300, 200, output_path=csv_path, label=-1,
                            state='intended_normal75_startup_pilot_running_observation_pending', metadata=metadata)
                done.set()
                session['recording'] = df.attrs['report']
                session['after_capture'] = fan.verify(75)
                if len(df):
                    first, last = int(df.host_monotonic_ns.iloc[0]), int(df.host_monotonic_ns.iloc[-1])
                    session['timing'] = {
                        'first_xyz_monotonic_ns': first, 'last_xyz_monotonic_ns': last,
                        'first_xyz_after_command_invocation_s': (first - session['command_invocation_monotonic_ns']) / 1e9,
                        'first_xyz_after_command_completion_s': (first - session['command_completed_monotonic_ns']) / 1e9,
                        'first_xyz_after_record_invocation_s': (first - session['record_invoked_monotonic_ns']) / 1e9,
                        'last_xyz_after_command_completion_s': (last - session['command_completed_monotonic_ns']) / 1e9,
                        'first_to_last_xyz_s': (last - first) / 1e9,
                        'electrical_waveform_or_rotor_start_measured': False,
                    }
                session['status'] = 'completed' if session['recording']['status'] == 'completed' else 'incomplete'
                emit('capture_completed', status=session['status'], summary=session['recording']['summary'],
                     timing=session.get('timing'))
        except BaseException as exc:
            failure = exc
            session.update(status='error', error=f'{type(exc).__name__}: {exc}')
            emit('capture_error', error=session['error'])
        finally:
            done.set()
            heartbeat.join(timeout=1)
            try:
                emit('returning_to_announced_zero', pwm_percent=0)
                session['zero_command_result'] = fan.stop()
                session['zero_command_completed_utc'] = utc()
                time.sleep(10)
                session['final_readback'] = fan.verify(0)
                session['runout_wait_s'] = 10
                emit('zero_verified_after_runout', pwm_percent=0,
                     mechanical_state='requires_new_visual_confirmation')
            except BaseException as exc:
                session['shutdown_error'] = f'{type(exc).__name__}: {exc}'
                session['status'] = 'shutdown_error'
                failure = failure or exc
            session['finished_utc'] = utc()
            persist(session_path, session)
    emit('session_finished', status=session['status'], session=str(session_path.relative_to(ROOT)))
    if failure:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
