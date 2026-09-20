"""Ten operator-cued calls in one persistent recording at fixed 75% / 25 kHz.

Only raw acquisition runs during the experiment. Frozen methods are compared
afterwards on identical saved windows. No call cue is a physical onset label.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import common_comparison as common
from fan_pwm import FanPWM
from live_pipeline import BufferedAcquisition, Sample

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'profiles/standlauf_pwm75_200hz'
TRIALS = 10
NORMAL_SECONDS = 30
WARMUP_SECONDS = 30


def timestamp():
    return dict(monotonic_ns=time.monotonic_ns(), utc_ns=time.time_ns(),
                local_timestamp=datetime.now(ZoneInfo('Europe/Berlin')).isoformat(),
                utc=datetime.now(timezone.utc).isoformat())


def atomic_status(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, allow_nan=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@contextmanager
def control_lock(run):
    with (Path(run) / 'control.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def read_cues(run):
    with (Path(run) / 'cues.jsonl').open(encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]


def append_cue(run, record):
    with (Path(run) / 'cues.jsonl').open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def validate_cues(cues):
    """Reject duplicates, reversed pairs, interleaving and trial gaps."""
    completed, pending = 0, None
    last = -1
    for cue in cues:
        if cue['monotonic_ns'] <= last:
            raise ValueError('Markerzeit muss streng monoton sein.')
        last = cue['monotonic_ns']
        if cue['event'] == 'call_requested':
            if pending is not None or cue['number'] != completed + 1 or completed >= TRIALS:
                raise ValueError('Unzulässige Anrufreihenfolge.')
            pending = cue['number']
        elif cue['event'] == 'end_reported':
            if pending is None or cue['number'] != pending:
                raise ValueError('Rückmeldung ohne passende Aufforderung.')
            completed, pending = pending, None
        else:
            raise ValueError('Unbekanntes Ereignis.')
    return completed, pending


def prepare(output):
    output = Path(output).resolve()
    bundle = common.load_bundle(PROFILE / 'comparison_bundle')
    if (bundle['profile_name'], bundle['sampling_rate_hz'], bundle['window_size'], bundle['step_size']) != (
            'standlauf_pwm75_200hz', 200, 128, 128):
        raise ValueError('Vorgesehenes eingefrorenes 75%-Profil stimmt nicht überein.')
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(PROFILE / 'comparison_bundle', output / 'bundle')
    shutil.copy2(PROFILE / 'profile.json', output / 'source_profile.json')
    (output / 'source').mkdir()
    for name in ('phone_series_experiment.py', 'analyze_phone_series.py',
                 'common_comparison.py', 'fan_pwm.py', 'live_pipeline.py', 'adxl345.py'):
        shutil.copy2(ROOT / 'src' / name, output / 'source' / name)
    plan = dict(schema_version=1, created=timestamp(), trials=TRIALS,
                phone='Google Pixel 9a', setup='Position, Orientierung und Befestigungen unverändert laut Auftrag',
                profile_name=bundle['profile_name'], source_profile=str(PROFILE / 'profile.json'),
                bundle_sha256=common.sha256(output / 'bundle/bundle.json'),
                artifact_sha256=bundle['artifact_sha256'], thresholds=bundle['thresholds'],
                sampling_rate_hz=200, window_size=128, step_size=128,
                pwm=dict(percent=75, frequency_hz=25000, period_ns=40000, duty_cycle_ns=30000,
                         enable=1, gpio_bcm=18, hold_all_phases=True, change_after_start=False),
                warmup_seconds=WARMUP_SECONDS, normal_seconds=NORMAL_SECONDS,
                warmup_source='30 s initial run-in rule: docs/versuchsplan_kontrolliert_20260909.md; separate 30 s normal lead-in from existing phone plan',
                mechanical_stability_measured=False,
                acquisition_mode='one_raw_sensor_process_then_shared_offline_windows',
                maximum_duration_seconds=None, timestamp_basis='host_monotonic_ns; Europe/Berlin wall clock additionally',
                physical_onset_measured=False, fixed_call_duration_seconds=None,
                model_training_or_threshold_changes=False,
                pwm_verification_interval_seconds=5, final_output_policy='leave_75_percent_unchanged',
                source_sha256={p.name: common.sha256(p) for p in (output / 'source').iterdir()},
                provenance=common.provenance())
    common.write_json(output / 'plan.json', plan)
    from analyze_phone_series import RULES
    common.write_json(output / 'analysis_rules.json', {'rules': RULES})
    (output / 'cues.jsonl').touch(exist_ok=False)
    (output / 'protocol.md').write_text(
        '# Smartphone-Messreihe: Versuch 1 bis 10\n\n'
        'Google Pixel 9a; unveränderte Positionen, Orientierung und Befestigungen. '
        'Das bestehende Profil standlauf_pwm75_200hz einschließlich aller Modelle, '
        'Standardisierung, 128/128-Fenster und Schwellen bleibt eingefroren.\n\n'
        f'75 % PWM bei 25 kHz werden vor der Aufnahme gesetzt und rückgelesen. '
        f'Einlaufzeit {WARMUP_SECONDS} s, danach mindestens 30 s Normalbetrieb. '
        'Alle Rohdaten einschließlich Einlauf werden gespeichert. Zehn Anrufe mit jeweils '
        'Aufforderung und Rückmeldung; mindestens 30 s Ruhe nach jeder Rückmeldung. '
        'Nach Versuch 10 automatischer kontrollierter Stopp nach mindestens 30 s Nachlauf. '
        'Kein 600-s-Limit. Ein Stop-Befehl oder SIGTERM beendet kontrolliert. '
        'Die PWM wird in keinem Abschnitt und auch beim Aufnahmestopp geändert.\n\n'
        'Marker verwenden lokale Pi-Zeit und dieselbe monotone Zeitbasis wie die Aufnahme. '
        'Sie begrenzen Suchbereiche und messen keinen Vibrationsbeginn oder kein Vibrationsende. '
        'Die Dauer eines Anrufs wird nicht vorgegeben. Die vorab gespeicherten Regeln stehen '
        'in analysis_rules.json. Methodenvergleich und separater Rechenzeitbenchmark folgen '
        'nach Abschluss; es entstehen keine gemessenen Live-Ausgabezeiten.\n', encoding='utf-8')
    return output


def status(run, *, now_ns=None):
    run = Path(run)
    result = common.read_json(run / 'status.json')
    now_ns = time.monotonic_ns() if now_ns is None else now_ns
    result['heartbeat_age_seconds'] = (now_ns - result['heartbeat_monotonic_ns']) / 1e9
    result['healthy'] = (result['state'] == 'recording' and 0 <= result['heartbeat_age_seconds'] <= 5
                         and result.get('last_sample_age_seconds', 999) + result['heartbeat_age_seconds'] <= 2
                         and not (run / 'run.json').exists() and not (run / 'stop.request.json').exists())
    try:
        os.kill(result['pid'], 0)
    except (ProcessLookupError, PermissionError):
        result['healthy'] = False
    return result


def mark(run, event, number, note=''):
    run = Path(run)
    with control_lock(run):
        current = status(run)
        if not current['healthy']:
            raise ValueError('Keine frische, laufende Aufnahme für diesen Marker.')
        plan = common.read_json(run / 'plan.json')
        cues = read_cues(run)
        completed, pending = validate_cues(cues)
        record = dict(event=event, number=number, note=note, physical_onset_verified=False, **timestamp())
        if event == 'call_requested':
            earliest = (cues[-1]['monotonic_ns'] + int(plan['normal_seconds'] * 1e9)) if cues else (
                current['normal_start_monotonic_ns'] + int(plan['normal_seconds'] * 1e9))
            if pending is not None or number != completed + 1 or number > TRIALS:
                raise ValueError('Anrufnummer oder ausstehende Rückmeldung widerspricht der Serie.')
            if record['monotonic_ns'] < earliest or current['last_sample_monotonic_ns'] < earliest:
                raise ValueError('Die mindestens 30 Sekunden Normalphase sind noch nicht erfasst.')
        elif event == 'end_reported':
            if number != pending:
                raise ValueError('Rückmeldung passt nicht zur offenen Aufforderung.')
        else:
            raise ValueError('Unbekannter Marker.')
        validate_cues(cues + [record])
        append_cue(run, record)
    return record


def request_stop(run, note='Vom Nutzer gewünschter kontrollierter Abbruch'):
    run = Path(run)
    with control_lock(run):
        if (run / 'run.json').exists():
            raise ValueError('Aufnahme bereits beendet.')
        if (run / 'stop.request.json').exists():
            return dict(stop_requested=True, already_requested=True)
        common.write_json(run / 'stop.request.json', dict(note=note, **timestamp()))
    return dict(stop_requested=True)


def capture(run, *, sensor_module=None, fan_factory=FanPWM):
    run = Path(run).resolve()
    with (run / 'recording.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Für diesen Ordner läuft bereits eine Aufnahme.') from exc
        return _capture_owned(run, sensor_module=sensor_module, fan_factory=fan_factory)


def _capture_owned(run, *, sensor_module=None, fan_factory=FanPWM):
    if sensor_module is None:
        import adxl345 as sensor_module
    run = Path(run).resolve()
    plan = common.read_json(run / 'plan.json')
    if (run / 'stop.request.json').exists():
        raise ValueError('Diese Serie wurde bereits vor dem Start abgebrochen.')
    if (run / 'started.json').exists() or (run / 'run.json').exists() or (run / 'config.json').exists():
        raise FileExistsError('Eine vorbereitete Serie darf nur einmal gestartet werden.')
    if common.sha256(run / 'bundle/bundle.json') != plan['bundle_sha256']:
        raise ValueError('Vorbereitetes Modellbündel verändert.')
    bundle = common.load_bundle(run / 'bundle')
    for name, digest in plan['source_sha256'].items():
        if common.sha256(run / 'source' / name) != digest:
            raise ValueError('Eingefrorener Quellcode verändert: ' + name)
    stop = threading.Event()
    previous = {s: signal.signal(s, lambda *_: stop.set()) for s in (signal.SIGINT, signal.SIGTERM)}
    report = dict(status='starting', pid=os.getpid(), start=timestamp(), live_inference=False)
    acquisition = bus = None
    try:
        with fan_factory(journal_path=run / 'fan.jsonl') as fan:
            # Sensor ownership is acquired before changing PWM; no competing reader.
            bus = sensor_module.connect(odr_hz=bundle['sampling_rate_hz'], range_g=2, fifo=True)
            report['pwm_before'] = fan.read_state()
            fan.set_percent(75)
            readback = fan.verify(75)
            configured = timestamp()
            config = dict(plan, pwm_readback=readback, pwm_set_and_verified=configured,
                          sensor=sensor_module.sensor_configuration(bus))
            common.write_json(run / 'config.json', config)
            sensor_module.reset_fifo(bus)
            start = time.monotonic_ns()
            normal_start = start + int(plan['warmup_seconds'] * 1e9)
            report.update(start_monotonic_ns=start, normal_start_monotonic_ns=normal_start,
                          pwm_initial_readback=readback, sensor=config['sensor'])
            common.write_json(run / 'started.json', report)

            def read(event):
                sample = sensor_module.read_fresh_sample(bus, stop_event=event)
                if sample is None:
                    return None
                return Sample(sample.xyz_g, sample.monotonic_ns, time.time_ns(),
                              sample.gap, sample.overrun, sample.saturated,
                              {'sensor_sample_index': sample.sample_index})

            acquisition = BufferedAcquisition(read, run / 'raw.csv', window_size=bundle['window_size'],
                                              capacity=8, stop_event=stop).start()
            next_verify = next_status = next_sync = 0
            report['status'] = 'recording'
            try:
                while not stop.is_set():
                    acquisition.get(timeout=.1)  # Raw windows consumed without model load.
                    now = time.monotonic_ns()
                    if stop.is_set():
                        break
                    if acquisition.done.is_set():
                        if acquisition.error:
                            raise RuntimeError(str(acquisition.error))
                        raise RuntimeError('Sensorstream unerwartet beendet.')
                    if now >= next_verify:
                        report['pwm_latest_readback'] = fan.verify(75)
                        report['pwm_latest_verified_monotonic_ns'] = now
                        next_verify = now + int(5e9)
                    if now >= next_status:
                        snapshot = acquisition.snapshot()
                        last = snapshot['last_sample_host_monotonic_ns']
                        age = (now - last) / 1e9 if last else (now - start) / 1e9
                        if age > 2:
                            raise RuntimeError('Seit mehr als zwei Sekunden keine Sensordaten.')
                        with control_lock(run):
                            cues = read_cues(run)
                            completed, pending = validate_cues(cues)
                            if (run / 'stop.request.json').exists():
                                report['stop_reason'] = 'operator_request'
                                stop.set()
                            elif completed == TRIALS and last and last >= cues[-1]['monotonic_ns'] + int(plan['normal_seconds'] * 1e9):
                                report['stop_reason'] = 'ten_trials_and_postrun_complete'
                                stop.set()
                            current = dict(state='stopping' if stop.is_set() else 'recording', pid=os.getpid(),
                                heartbeat_monotonic_ns=now, start_monotonic_ns=start,
                                normal_start_monotonic_ns=normal_start, completed_trials=completed,
                                pending_trial=pending, last_sample_monotonic_ns=last,
                                last_sample_age_seconds=age, acquisition=snapshot,
                                pwm_readback=report['pwm_latest_readback'],
                                pwm_verified_monotonic_ns=report['pwm_latest_verified_monotonic_ns'])
                            atomic_status(run / 'status.json', current)
                        next_status = now + int(.5e9)
                    if now >= next_sync:
                        with (run / 'raw.csv').open('r') as raw:
                            os.fsync(raw.fileno())
                        next_sync = now + int(5e9)
                report['status'] = ('completed' if report.get('stop_reason') == 'ten_trials_and_postrun_complete'
                                    else 'aborted')
                report.setdefault('stop_reason', 'signal')
            finally:
                with control_lock(run):
                    atomic_status(run / 'status.json', dict(state='stopping', pid=os.getpid(),
                                                          heartbeat_monotonic_ns=time.monotonic_ns()))
                acquisition.stop()
                report['acquisition'] = acquisition.snapshot()
                report['pwm_final_readback'] = fan.verify(75)
                if acquisition.error:
                    raise RuntimeError(f'Erfassungsfehler beim Stopp: {acquisition.error}')
    except BaseException as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        cleanup_errors = []
        for name, close in [('acquisition', lambda: acquisition.stop() if acquisition else None),
                            ('sensor', lambda: bus.close() if bus and not (acquisition and acquisition.thread.is_alive()) else None)]:
            try:
                close()
            except Exception as exc:
                cleanup_errors.append(f'{name}: {exc}')
        if acquisition:
            report['acquisition'] = acquisition.snapshot()
        for s, handler in previous.items():
            signal.signal(s, handler)
        report.update(finished=timestamp(), end_monotonic_ns=time.monotonic_ns(), cleanup_errors=cleanup_errors)
        if cleanup_errors:
            report['status'] = 'failed'
        with control_lock(run):
            atomic_status(run / 'status.json', dict(state=report['status'], pid=os.getpid(),
                                                  heartbeat_monotonic_ns=time.monotonic_ns()))
            report['file_sha256'] = {str(p.relative_to(run)): common.sha256(p) for p in run.rglob('*')
                                     if p.is_file() and p.name not in ('status.json', 'control.lock', 'recording.lock')}
            common.write_json(run / 'run.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--output', required=True)
    for name in ('record', 'status', 'stop', 'mark'):
        p = sub.add_parser(name); p.add_argument('--run', required=True)
        if name in ('mark', 'stop'):
            p.add_argument('--note', default='')
        if name == 'mark':
            p.add_argument('--event', choices=('call_requested', 'end_reported'), required=True)
            p.add_argument('--number', type=int, choices=range(1, TRIALS + 1), required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        print(prepare(args.output))
    else:
        if args.command == 'record': result = capture(args.run)
        elif args.command == 'status': result = status(args.run)
        elif args.command == 'stop': result = request_stop(args.run, args.note)
        else: result = mark(args.run, args.event, args.number, args.note)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
