"""Exactly one explicitly released 300-s phase. No user prompts, retries, or phase loop."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from sequence_common import BASE, ROOT, PHASES, MOUNTING_ID, digest, persist, release_gate, utc
sys.path.insert(0, str(ROOT/'src'))
from adxl345 import connect, sensor_configuration
from collect_real_data import record, provenance
from fan_pwm import FanPWM


def emit(event, **fields):
    print(json.dumps({'event': event, 'utc': utc(), **fields}, ensure_ascii=False), flush=True)


def execute_capture(fan, bus, session, csv_path, metadata, recorder=record):
    """Single command/record path. A failed recorder still reaches the zero command."""
    failure = None
    try:
        session['command_invocation_utc'] = utc()
        session['command_invocation_monotonic_ns'] = time.monotonic_ns()
        session['setting_result'] = fan.set_percent(75)
        session['command_completed_monotonic_ns'] = time.monotonic_ns()
        session['command_completed_utc'] = utc()
        session['status'] = 'recording'
        for key in ('command_invocation_utc', 'command_invocation_monotonic_ns',
                    'command_completed_monotonic_ns', 'command_completed_utc'):
            metadata['pwm_'+key] = session[key]
        session['record_invoked_monotonic_ns'] = time.monotonic_ns()
        emit('capture_start', phase=session['phase'], pwm_percent=75, frequency_hz=25000,
             requested_seconds=300, csv=str(csv_path))
        df = recorder(bus, 300, 200, output_path=csv_path,
                      label=1 if session['phase']=='airflow_modified' else 0,
                      state=session['phase'], metadata=metadata)
        session['recording'] = df.attrs['report']
        session['after_capture_readback'] = fan.verify(75)
        if len(df):
            first, last = int(df.host_monotonic_ns.iloc[0]), int(df.host_monotonic_ns.iloc[-1])
            session['timing'] = {
                'first_xyz_monotonic_ns': first, 'last_xyz_monotonic_ns': last,
                'first_xyz_after_command_invocation_s': (first-session['command_invocation_monotonic_ns'])/1e9,
                'first_xyz_after_command_completion_s': (first-session['command_completed_monotonic_ns'])/1e9,
                'first_to_last_xyz_s': (last-first)/1e9,
                'last_xyz_after_command_invocation_s': (last-session['command_invocation_monotonic_ns'])/1e9,
                'first_xyz_utc_estimate': datetime.fromtimestamp(
                    datetime.fromisoformat(session['command_invocation_utc']).timestamp()+
                    (first-session['command_invocation_monotonic_ns'])/1e9, timezone.utc).isoformat(),
                'utc_estimate_note': 'derived from paired host UTC/monotonic command timestamps',
                'electrical_signal_and_rotor_start_measured': False}
        session['status'] = 'completed' if session['recording']['status']=='completed' else 'incomplete'
    except BaseException as exc:
        failure = exc
        session.update(status='error', error=f'{type(exc).__name__}: {exc}')
        emit('capture_error', error=session['error'])
    finally:
        emit('returning_to_zero', pwm_percent=0)
        try:
            session['zero_command_result'] = fan.stop()
            session['zero_command_completed_monotonic_ns'] = time.monotonic_ns()
            session['zero_command_completed_utc'] = utc()
            session['final_readback'] = fan.verify(0)
            emit('zero_readback_complete', pwm_percent=0, mechanical_state='not_observed')
        except BaseException as exc:
            session['shutdown_error'] = f'{type(exc).__name__}: {exc}'
            session['status'] = 'shutdown_error'
            try:
                session['actual_state_after_shutdown_error'] = fan.read_state()
            except BaseException as read_exc:
                session['actual_state_read_error'] = str(read_exc)
            failure = failure or exc
    return failure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=PHASES, required=True)
    parser.add_argument('--check-release-only', action='store_true')
    args = parser.parse_args()
    # This guard must precede imports/contexts that open a device or change PWM.
    release, previous = release_gate(args.phase)
    if args.check_release_only:
        emit('release_valid', phase=args.phase, hardware_access=False)
        return
    holders = subprocess.run(['fuser','-v','/dev/i2c-1','/dev/gpiochip0','/dev/gpiomem0'],
                             capture_output=True, text=True, timeout=5)
    if holders.returncode != 1 or holders.stdout or holders.stderr:
        raise RuntimeError('Device access in use or unclear; no start')
    path = BASE/f'{args.phase}_session.json'
    journal = BASE/f'{args.phase}_fan.jsonl'
    with path.open('x') as f:
        f.write('{}\n')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    csv_path = ROOT/'data'/BASE.name/f'{args.phase}_75pwm_300s_{stamp}.csv'
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    geometry_path = BASE/f'{args.phase}_geometry.json'
    if not geometry_path.exists():
        geometry_path = BASE/'geometry.json'
    geometry = json.loads(geometry_path.read_text())
    mounting = json.loads((BASE/'mounting.json').read_text())
    session = dict(status='preflight', started_utc=utc(), phase=args.phase,
        csv=str(csv_path.relative_to(ROOT)), requested_duration_s=300,
        fan_journal=str(journal.relative_to(ROOT)), user_release=release,
        mounting_id=MOUNTING_ID, mounting=mounting, geometry=geometry,
        geometry_source=str(geometry_path.relative_to(ROOT)), geometry_sha256=digest(geometry_path),
        planned_additional_off_s=60,
        no_response_deadline=True, automatic_restarts=False, models_trained=False,
        label_interpretation='controlled condition; not a proven defect',
        final_mechanical_state='not_observed', running_observation_requested=False,
        runner_sha256=digest(Path(__file__)), common_sha256=digest(BASE/'sequence_common.py'))
    persist(path, session)
    done = threading.Event()
    def progress():
        while not done.wait(30):
            if session.get('status') == 'recording':
                emit('recording_progress', phase=args.phase,
                     elapsed_since_command_s=(time.monotonic_ns()-session['command_invocation_monotonic_ns'])/1e9,
                     physical_running_observation=None)
    heartbeat = threading.Thread(target=progress, daemon=True)
    heartbeat.start()
    def interrupt(*_):
        raise KeyboardInterrupt('Capture interrupted; try zero; no restart')
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    failure = None
    try:
        with FanPWM(journal_path=journal) as fan:
            try:
                session['initial_readback'] = fan.verify(0)
                with connect(odr_hz=200, range_g=2, fifo=True) as bus:
                    session['sensor'] = sensor_configuration(bus)
                    session['prepared_provenance'] = provenance()
                    metadata = dict(mounting_id=MOUNTING_ID, geometry=geometry,
                        mounting=mounting, fan_orientation='upright', old_measurements_pooled=False,
                        purpose='pilot', sequence_id=BASE.name, phase=args.phase,
                        condition_label=args.phase, split='development_pilot',
                        primary_comparison_interval_s=[180,300], primary_time_origin='pwm_command_invocation',
                        settling_time_validated=False, user_release=release,
                        fan_pwm_setpoint_percent=75, fan_pwm_frequency_hz=25000,
                        fan_control_journal=session['fan_journal'], detection_controls_fan=False,
                        operator_running_confirmation=None, running_observation_requested=False,
                        rpm_measured=None, rpm_method=None,
                        condition_interpretation='controlled operating state; not a proven defect',
                        intentional_pre_record_settling_delay_s=0)
                    target = release['accepted_monotonic_ns'] + 60_000_000_000
                    session['off_timer_target_monotonic_ns'] = target
                    persist(path, session)
                    emit('off_wait', phase=args.phase, additional_seconds=60,
                         remaining_s=max(0,(target-time.monotonic_ns())/1e9), pwm_percent=0)
                    while time.monotonic_ns() < target:
                        time.sleep(max(0,min(1,(target-time.monotonic_ns())/1e9)))
                    session['precommand_zero_readback'] = fan.verify(0)
                    failure = execute_capture(fan, bus, session, csv_path, metadata)
            except BaseException as exc:
                failure = failure or exc
                session.update(status='error', error=f'{type(exc).__name__}: {exc}')
                # Covers sensor/preparation/restore failures outside execute_capture.
                if 'final_readback' not in session:
                    try:
                        session['zero_command_result'] = fan.stop()
                        session['zero_command_completed_monotonic_ns'] = time.monotonic_ns()
                        session['zero_command_completed_utc'] = utc()
                        session['final_readback'] = fan.verify(0)
                    except BaseException as stop_exc:
                        session.update(status='shutdown_error', shutdown_error=str(stop_exc))
                        try: session['actual_state_after_shutdown_error'] = fan.read_state()
                        except BaseException as read_exc: session['actual_state_read_error'] = str(read_exc)
    except BaseException as exc:
        failure = failure or exc
        session.update(status='error', preflight_or_controller_error=f'{type(exc).__name__}: {exc}')
    finally:
        done.set()
        heartbeat.join(timeout=1)
        if 'command_invocation_monotonic_ns' in session:
            session['additional_off_from_release_actual_s'] = (
                session['command_invocation_monotonic_ns']-release['accepted_monotonic_ns'])/1e9
            if previous and 'zero_command_completed_monotonic_ns' in previous:
                session['total_off_since_previous_zero_s'] = (
                    session['command_invocation_monotonic_ns']-previous['zero_command_completed_monotonic_ns'])/1e9
                session['total_off_time_source'] = 'same-boot monotonic times of this sequence'
            else:
                session['total_off_since_previous_zero_s'] = None
                session['total_off_time_source'] = 'first operating run after standstill; no continuously verified earlier full off interval'
        session['finished_utc'] = utc()
        persist(path, session)
    emit('phase_finished', phase=args.phase, status=session['status'], next_action='pause_for_user_manual_step',
         session=str(path.relative_to(ROOT)))
    if failure:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
