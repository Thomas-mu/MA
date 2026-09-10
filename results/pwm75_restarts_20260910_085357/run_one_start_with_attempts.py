"""One confirmed restart with explicit attempt IDs; original capture/timing unchanged.

Run only after the agent has announced 75%, the timed capture and automatic
return to0%. A new visual standstill confirmation is required for every start.
No controller remains waiting across conversation turns at zero output.
"""
import argparse
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
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from adxl345 import connect
from collect_real_data import record
from fan_pwm import FanPWM

SETTLING_S = 60
RECORD_S = 30


def utc():
    return datetime.now(timezone.utc).isoformat()


def emit(event, **fields):
    print(json.dumps({'event': event, 'utc': utc(), **fields}, ensure_ascii=False), flush=True)


def persist(path, obj):
    temporary = path.with_suffix('.json.tmp')
    with temporary.open('x', encoding='utf-8') as handle:
        json.dump(obj, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def require_free_devices():
    result = subprocess.run(['fuser', '-v', '/dev/i2c-1', '/dev/gpiochip0', '/dev/gpiomem0'],
                            capture_output=True, text=True, timeout=5)
    if result.returncode != 1 or result.stdout.strip() or result.stderr.strip():
        raise RuntimeError('Sensor/GPIO use found or process check unclear')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trial', type=int, required=True, choices=(1, 2, 3))
    parser.add_argument('--attempt', type=int, default=1)
    args = parser.parse_args()
    trial = args.trial
    if args.attempt < 1:
        raise ValueError('Attempt must be positive')
    suffix = '' if args.attempt == 1 else f'_attempt{args.attempt}'
    confirmation_path = BASE / f'standstill_before_start_{trial}{suffix}.json'
    confirmation = json.loads(confirmation_path.read_text())
    if (confirmation.get('trial') != trial or
            confirmation.get('fan_observed_fully_stopped') is not True or
            confirmation.get('mounting_unchanged') is not True or
            not confirmation.get('operator_answer')):
        raise ValueError('New positive visual standstill confirmation required')
    if trial > 1:
        previous_paths = [BASE / f'start_{trial - 1}.json'] + sorted(BASE.glob(f'start_{trial - 1}_attempt*.json'))
        completed_previous = [json.loads(path.read_text()) for path in previous_paths if path.exists() and json.loads(path.read_text()).get('status') == 'completed']
        if len(completed_previous) != 1:
            raise ValueError('Exactly one completed preceding trial required')
        previous = completed_previous[0]
        if previous.get('status') != 'completed' or previous['final_readback']['pwm_configuration']['configured_duty_percent'] != 0:
            raise ValueError('Previous trial must be completed and zero verified')
        if datetime.fromisoformat(confirmation['recorded_utc']) <= datetime.fromisoformat(previous['finished_utc']):
            raise ValueError('Standstill observation must follow previous trial')
    running_path = BASE / f'running_start_{trial}{suffix}.json'
    session_path = BASE / f'start_{trial}{suffix}.json'
    if args.attempt > 1:
        prior_suffix = '' if args.attempt == 2 else f'_attempt{args.attempt - 1}'
        prior_attempt = json.loads((BASE / f'start_{trial}{prior_suffix}.json').read_text())
        if prior_attempt.get('status') != 'aborted' or 'recording' in prior_attempt:
            raise ValueError('Retry only a documented attempt aborted without a recording')
        if prior_attempt['final_readback']['pwm_configuration']['configured_duty_percent'] != 0:
            raise ValueError('Previous aborted attempt did not verify zero')
        if datetime.fromisoformat(confirmation['recorded_utc']) <= datetime.fromisoformat(prior_attempt['finished_utc']):
            raise ValueError('Fresh standstill observation after aborted attempt required')
    if running_path.exists() or session_path.exists():
        raise FileExistsError('No reuse of observations or existing trial journals')
    require_free_devices()
    with session_path.open('x') as handle:
        handle.write('{}\n')
    journal = BASE / f'start_{trial}{suffix}_fan.jsonl'
    session = {
        'trial': trial, 'attempt': args.attempt, 'started_utc': utc(), 'status': 'preflight',
        'protocol': 'confirmed full standstill ->75% ->fixed60s ->30s capture ->0%',
        'standstill_confirmation': confirmation,
        'standstill_confirmation_sha256': hashlib.sha256(confirmation_path.read_bytes()).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'fan_journal': str(journal.relative_to(ROOT)),
        'requested_settling_s': SETTLING_S, 'requested_record_s': RECORD_S,
        'training': False, 'induced_anomalies': False,
        'mechanical_state_after_shutdown': 'not_yet_visually_confirmed',
    }

    def interrupted(*_):
        raise KeyboardInterrupt('Trial interrupted; attempt requested return to zero')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    failure = None
    with FanPWM(journal_path=journal) as fan:
        try:
            session['initial_readback'] = fan.verify(0)
            # Initialise and lock the sensor before the timed fan start.
            # The existing recorder resets the FIFO at actual capture start.
            with connect(odr_hz=200, range_g=2, fifo=True) as bus:
                session['setting_result'] = fan.set_percent(75)
                set_ns = time.monotonic_ns()
                session['setting_completed_monotonic_ns'] = set_ns
                session['setting_completed_utc'] = utc()
                deadline_ns = set_ns + SETTLING_S * 1_000_000_000
                session['capture_deadline_monotonic_ns'] = deadline_ns
                session['status'] = 'settling_waiting_for_visual_running_confirmation'
                persist(session_path, session)
                emit('75_percent_applied', trial=trial, settling_s=SETTLING_S,
                     capture_after_fixed_seconds=SETTLING_S,
                     confirmation_file=str(running_path.relative_to(ROOT)))
                observation = None
                while time.monotonic_ns() < deadline_ns:
                    if running_path.exists() and observation is None:
                        observation = json.loads(running_path.read_text())
                        if (observation.get('trial') != trial or
                                observation.get('fan_observed_running_uniformly') is not True or
                                observation.get('mounting_unchanged') is not True or
                                not observation.get('operator_answer')):
                            raise ValueError('Running state not positively confirmed')
                        observed_ns = time.monotonic_ns()
                        if observed_ns >= deadline_ns:
                            raise TimeoutError('Running confirmation too late for fixed settling')
                        session['running_confirmation'] = observation
                        session['running_confirmation_received_monotonic_ns'] = observed_ns
                        session['running_confirmation_sha256'] = hashlib.sha256(running_path.read_bytes()).hexdigest()
                        persist(session_path, session)
                        emit('uniform_running_confirmed', trial=trial,
                             seconds_since_setting=(observed_ns - set_ns) / 1e9)
                    time.sleep(min(0.05, max(0, (deadline_ns - time.monotonic_ns()) / 1e9)))
                if observation is None:
                    raise TimeoutError('No visual running confirmation before fixed60-s capture deadline; no capture')
                session['before_capture'] = fan.verify(75)
                stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
                csv_path = Path('data') / BASE.name / f'operating75_start{trial}_{stamp}.csv'
                metadata = {
                    'purpose': 'pilot', 'sequence_id': BASE.name, 'restart_trial': trial, 'restart_attempt': args.attempt,
                    'repeat_design': 'separate fan start after new visually confirmed full standstill',
                    'mounting': 'ADXL345 with intended I2C wiring attached to a corner of ARCTIC P12 Pro PST frame; GPIO18 fan control',
                    'mounting_id': 'fan_frame_corner_adxl345_gpio18_v1',
                    'mounting_unchanged_user_instruction': True,
                    'fan_pwm_setpoint_percent': 75.0, 'fan_pwm_frequency_hz': 25000,
                    'fan_pwm_source': 'announced_agent_hardware_pwm_command_with_readback',
                    'fan_control_journal': session['fan_journal'],
                    'physical_state_source': 'operator_visual_confirmation_before_fixed_capture_deadline',
                    'standstill_confirmation': confirmation, 'operator_confirmation': observation,
                    'planned_settling_seconds': SETTLING_S,
                    'pwm_setting_completed_monotonic_ns': set_ns,
                    'pwm_setting_completed_utc': session['setting_completed_utc'],
                    'elapsed_since_phase_pwm_command_s': (time.monotonic_ns() - set_ns) / 1e9,
                    'rpm_measured': None, 'rpm_method': None, 'rpm_source': 'not_measured',
                    'detection_controls_fan': False, 'induced_anomaly': False,
                }
                session['record_invoked_utc'] = utc()
                session['record_invoked_monotonic_ns'] = time.monotonic_ns()
                session['status'] = 'recording'
                session['csv'] = str(csv_path)
                persist(session_path, session)
                emit('capture_start', trial=trial, seconds=RECORD_S, pwm_percent=75,
                     elapsed_since_setting_s=(time.monotonic_ns() - set_ns) / 1e9,
                     csv=str(csv_path), automatic_zero_after_capture=True)
                df = record(bus, RECORD_S, 200, output_path=csv_path, label=0,
                            state='controlled_operating75_independent_restart_pilot', metadata=metadata)
                session['recording'] = df.attrs['report']
                session['after_capture'] = fan.verify(75)
                session['actual_first_point_after_setting_s'] = (int(df.host_monotonic_ns.iloc[0]) - set_ns) / 1e9
                session['actual_last_point_after_setting_s'] = (int(df.host_monotonic_ns.iloc[-1]) - set_ns) / 1e9
                session['first_point_delay_from_planned_deadline_s'] = session['actual_first_point_after_setting_s'] - SETTLING_S
                quality = session['recording']['summary']
                session['quality_flagged'] = any(quality[k] for k in
                    ('gap_flagged_samples', 'overrun_flagged_samples', 'saturated_samples'))
                session['timing_needs_review'] = not (0 <= session['first_point_delay_from_planned_deadline_s'] <= 0.1)
                if session['recording']['status'] != 'completed':
                    raise RuntimeError('Recording not completed')
                session['status'] = 'completed'
                emit('capture_completed', trial=trial, summary=quality,
                     first_point_after_setting_s=session['actual_first_point_after_setting_s'])
        except BaseException as exc:
            failure = exc
            session.update(status='aborted', error=f'{type(exc).__name__}: {exc}')
            emit('trial_aborted', trial=trial, error=session['error'])
        finally:
            try:
                emit('returning_to_announced_zero', trial=trial, pwm_percent=0)
                session['zero_command_result'] = fan.stop()
                session['zero_command_completed_utc'] = utc()
                time.sleep(10)
                session['final_readback'] = fan.verify(0)
                session['runout_wait_s'] = 10
                emit('zero_verified_after_runout', trial=trial, pwm_percent=0,
                     mechanical_standstill='requires_new_visual_confirmation')
            except BaseException as exc:
                session['shutdown_error'] = f'{type(exc).__name__}: {exc}'
                session['status'] = 'shutdown_error'
                failure = failure or exc
            session['finished_utc'] = utc()
            persist(session_path, session)
    emit('trial_finished', trial=trial, status=session['status'], session=str(session_path.relative_to(ROOT)))
    if failure:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
