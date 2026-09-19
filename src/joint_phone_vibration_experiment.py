"""One live sensor stream, identical windows, three concurrent method workers.

No fan control, no GUI, no recalibration. Chat cues are not physical onset times.
CPU and memory metrics belong to the shared process, not individual methods.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import threading
import time

import numpy as np

import common_comparison as common
from live_pipeline import BufferedAcquisition, ProcessMetrics, Sample
from phone_vibration_experiment import mark, pwm_readback, read_number, utc
from replay_phone_pilot import phase_of, assign_ranks


METHODS = ('tflite_autoencoder', 'isolation_forest', 'rms')
LABELS = {'tflite_autoencoder': 'Autoencoder', 'isolation_forest': 'Isolation Forest', 'rms': 'RMS'}


def evaluate_shared_window(raw, functions, scaler, thresholds, executor, *, invalid=False):
    """Every worker gets an immutable copy of exactly the same raw values."""
    shared = np.array(raw, dtype=np.float64, order='C', copy=True)
    shared.flags.writeable = False
    digest = hashlib.sha256(shared.tobytes()).hexdigest()
    barrier = threading.Barrier(len(METHODS))
    dispatch_ns = time.monotonic_ns()

    def evaluate(method):
        values = shared.copy()
        values.flags.writeable = False
        barrier.wait(timeout=10)
        started = time.monotonic_ns()
        score = prediction = None
        error = ''
        try:
            if invalid:
                raise ValueError('Ungueltiges Sensorfenster')
            score, prediction = common.classify_raw(values, scaler, functions[method], thresholds[method])
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
        finished = time.monotonic_ns()
        return dict(method=method, input_sha256=digest, dispatch_ns=dispatch_ns,
                    worker_start_ns=started, decision_ns=finished,
                    processing_ms=(finished-started)/1e6, dispatch_to_decision_ms=(finished-dispatch_ns)/1e6,
                    score=score, threshold=thresholds[method], prediction=prediction, error=error)

    pending = [executor.submit(evaluate, method) for method in METHODS]
    # Output order is not a latency ranking. Compare window indices for onset ordering.
    return [future.result() for future in pending]


def capture(plan_directory, output, seconds):
    from adxl345 import connect, read_fresh_sample, reset_fifo, sensor_configuration
    source, output = Path(plan_directory).resolve(), Path(output).resolve()
    plan = common.read_json(source/'plan.json')
    directory = source/'bundle'
    if common.sha256(directory/'bundle.json') != plan['bundle_sha256']:
        raise ValueError('Eingefrorenes Buendel veraendert.')
    bundle = common.load_bundle(directory)
    before = pwm_readback()
    if before['enable'] != 1 or not math.isclose(before['percent'], plan['pwm_percent']):
        raise ValueError('PWM entspricht nicht dem bisherigen Versuchsplan.')
    output.mkdir(parents=True, exist_ok=False)
    for original, name in [(Path(__file__), 'capture_source.py'), (source/'plan.json', 'source_plan.json'),
                           (source/'protocol.md', 'source_protocol.md'), (directory/'bundle.json', 'bundle.json'),
                           (Path(common.__file__), 'common_comparison_source.py')]:
        shutil.copy2(original, output/name)
    joint_plan = dict(plan, mode='joint_live_same_windows', methods=list(METHODS),
                      events_per_joint_run=1, resource_scope='combined_process_all_methods',
                      source_plan_sha256=common.sha256(source/'plan.json'))
    common.write_json(output/'plan.json', joint_plan)
    (output/'protocol.md').write_text(
        '# Gemeinsamer Live-Anrufversuch\n\n'
        'Ein Sensorstream, jedes Fenster identisch an Autoencoder, Isolation Forest und RMS. '
        'Drei Threads werden je Fenster mit einer Barriere freigegeben; Scheduler und Laufzeiten unterscheiden sich. '
        'Fenstergrenzen, Eingabehash, Dispatch-, Start- und Entscheidungszeiten werden protokolliert. '
        'Gleiche erste Alarmfenster sind Gleichstand auf Fensteraufloesung.\n\n'
        'Unveraenderte Modelle/Schwellen und 75 % PWM aus dem bisherigen Plan. '
        'Mindestens 30 s Ruhe vor Freigabe; ein Anruf, Ziel etwa 5 s Vibration; danach mindestens 15 s Ruhe. '
        'Chat-Marker sind keine gemessenen physischen Anfangs-/Endzeiten. '
        'Finaler Handyaufbau weiterhin unbestaetigt; explorativer Pilot, keine allgemeine Erkennungsrate.\n\n'
        'CPU/RAM gelten fuer den gesamten gemeinsamen Prozess. Berechnungszeiten im konkurrierenden Betrieb '
        'sind kein isolierter Modellbenchmark. Keine Live-GUI; Diagramme/Screenshots erst nach Aufnahme.\n', encoding='utf-8')
    stop = threading.Event()
    previous = {s: signal.signal(s, lambda *_: stop.set()) for s in (signal.SIGINT, signal.SIGTERM)}
    metadata = dict(method='joint', methods_active=list(METHODS), purpose='exploratory_joint_phone_pilot',
        started_utc=utc(), status='starting', gui_enabled=False, requested_seconds=seconds,
        execution_mode='single_sensor_three_threads_per_window_barrier', resource_scope='combined_process',
        physical_onset_verified=False, setup_confirmed=plan['setup_confirmed'],
        pwm_before=before, thresholds=bundle['thresholds'], bundle_sha256=plan['bundle_sha256'],
        source_plan_sha256=common.sha256(source/'plan.json'), provenance=common.provenance(), warmup_windows=20)
    bus = acquisition = executor = None
    try:
        functions, runtimes = {}, {}
        for method in METHODS:
            functions[method], runtimes[method] = common.scorer(method, bundle, directory, runtime='litert', threads=1)
        metadata['runtimes'] = runtimes
        thresholds = {m: bundle['thresholds'][m]['value'] for m in METHODS}
        executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix='joint-method')
        warmup = np.load(directory/'validation_raw.npy', mmap_mode='r')
        for i in range(20):
            evaluated = evaluate_shared_window(warmup[i % len(warmup)], functions, bundle['scaler'], thresholds, executor)
            if any(row['error'] for row in evaluated):
                raise ValueError('Warmup fehlgeschlagen: '+repr(evaluated))
        bus = connect(odr_hz=bundle['sampling_rate_hz'], range_g=2, fifo=True)
        metadata['sensor'] = sensor_configuration(bus)
        reset_fifo(bus)
        start = time.monotonic_ns()
        metadata['start_monotonic_ns'] = start
        metadata['status'] = 'recording'
        (output/'cues.jsonl').touch(exist_ok=False)
        common.write_json(output/'started.json', metadata)

        def read(event):
            if time.monotonic_ns()-start >= seconds*1e9:
                return None
            sample = read_fresh_sample(bus, stop_event=event)
            if sample is None:
                return None
            return Sample(sample.xyz_g, sample.monotonic_ns, time.time_ns(), sample.gap,
                          sample.overrun, sample.saturated, {'sensor_sample_index': sample.sample_index})

        metrics = ProcessMetrics()
        acquisition = BufferedAcquisition(read, output/'raw.csv', window_size=bundle['window_size'],
                                          capacity=4, stop_event=stop).start()
        decisions_fields = ['window', 'window_start_ns', 'window_complete_ns', 'elapsed_s', 'method',
            'input_sha256', 'dispatch_ns', 'worker_start_ns', 'decision_ns', 'processing_ms',
            'dispatch_to_decision_ms', 'score', 'threshold', 'prediction', 'error', 'window_to_decision_ms']
        resource_fields = ['window', 'elapsed_s', 'batch_ms', 'process_cpu_percent_one_core',
            'process_rss_bytes', 'process_lifetime_peak_rss_bytes', 'temperature_c', 'cpu_frequency_khz', 'windows_dropped']
        with (output/'decisions.csv').open('x', newline='', buffering=1) as handle, \
                (output/'resources.csv').open('x', newline='', buffering=1) as resources:
            writer = csv.DictWriter(handle, fieldnames=decisions_fields); writer.writeheader()
            resource_writer = csv.DictWriter(resources, fieldnames=resource_fields); resource_writer.writeheader()
            while not stop.is_set():
                window = acquisition.get(timeout=.1)
                if window is None:
                    if acquisition.done.is_set():
                        break
                    continue
                batch_started = time.monotonic_ns()
                results = evaluate_shared_window(window.values, functions, bundle['scaler'], thresholds, executor,
                    invalid=bool(window.gap_count or window.overrun_count or window.saturated_count))
                for row in results:
                    writer.writerow(dict(row, window=window.index, window_start_ns=window.first_sample_ns,
                        window_complete_ns=window.complete_ns, elapsed_s=(row['decision_ns']-start)/1e9,
                        window_to_decision_ms=(row['decision_ns']-window.complete_ns)/1e6))
                finished = time.monotonic_ns()
                resource_writer.writerow(dict(window=window.index, elapsed_s=(finished-start)/1e9,
                    batch_ms=(finished-batch_started)/1e6, **metrics.sample(),
                    temperature_c=read_number('/sys/class/thermal/thermal_zone0/temp',1000),
                    cpu_frequency_khz=read_number('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq'),
                    windows_dropped=acquisition.snapshot()['windows_dropped']))
            for file in (handle,resources):
                file.flush(); os.fsync(file.fileno())
        metadata['status'] = 'stopped' if stop.is_set() else 'completed'
    except BaseException as exc:
        metadata.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        cleanup_errors = []
        for name, operation in [('acquisition', lambda: acquisition.stop() if acquisition else None),
                                ('workers', lambda: executor.shutdown(wait=True) if executor else None),
                                ('sensor', lambda: bus.close() if bus else None)]:
            try:
                operation()
            except Exception as exc:
                cleanup_errors.append(f'{name}: {type(exc).__name__}: {exc}')
        if acquisition:
            metadata['acquisition'] = acquisition.snapshot()
        try:
            metadata['pwm_after'] = pwm_readback()
        except Exception as exc:
            metadata['pwm_after'] = None
            cleanup_errors.append(f'PWM readback: {exc}')
        for s, handler in previous.items():
            signal.signal(s, handler)
        metadata['finished_utc'] = utc(); metadata['cleanup_errors'] = cleanup_errors
        if cleanup_errors and metadata['status'] != 'failed':
            metadata['status'] = 'cleanup_failed'
        metadata['file_sha256'] = {p.name: common.sha256(p) for p in output.iterdir() if p.is_file()}
        common.write_json(output/'run.json', metadata)
    return output


def summarize_joint(rows, cues):
    grouped = {}
    for row in rows:
        grouped.setdefault(int(row['window']), []).append(row)
    for index, group in grouped.items():
        if len(group) != 3 or set(r['method'] for r in group) != set(METHODS):
            raise ValueError(f'Incomplete method group in window {index}')
        for field in ('input_sha256', 'window_start_ns', 'window_complete_ns', 'dispatch_ns'):
            if len({r[field] for r in group}) != 1:
                raise ValueError(f'Methods received different {field}, window {index}')
    starts = [c['monotonic_ns'] for c in cues if c['event']=='call_requested']
    ends = [c['monotonic_ns'] for c in cues if c['event']=='end_reported']
    entries = {}
    for method in METHODS:
        selected = [r for r in rows if r['method']==method]
        valid = [r for r in selected if r['prediction'] in ('0','1') and not r['error']]
        entry = dict(windows=len(selected), invalid_windows=len(selected)-len(valid),
            alarm_windows=sum(r['prediction']=='1' for r in valid), first_alarm_window_between_cues=None)
        if len(starts)==len(ends)==1 and starts[0]<ends[0]:
            entry['phases'] = {}
            for phase in ('pre_cue','between_cues','post_cue','straddling'):
                phase_rows = [r for r in valid if phase_of(r,starts[0],ends[0])==phase]
                alarms = [r for r in phase_rows if r['prediction']=='1']
                entry['phases'][phase] = dict(valid_windows=len(phase_rows),alarm_windows=len(alarms))
                if phase=='between_cues' and alarms:
                    entry['first_alarm_window_between_cues'] = min(int(r['window']) for r in alarms)
        entries[method] = entry
    assign_ranks(entries)
    return dict(shared_windows=len(grouped), shared_input_verified=True, methods=entries,
                true_detection_delay_ms=None, reason='No independent physical onset reference')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    record=sub.add_parser('record');record.add_argument('--plan',required=True);record.add_argument('--output',required=True)
    record.add_argument('--seconds',type=float,default=600)
    marker=sub.add_parser('mark');marker.add_argument('--run',required=True)
    marker.add_argument('--event',choices=('call_requested','end_reported','note'),required=True);marker.add_argument('--note',default='')
    summary=sub.add_parser('summary');summary.add_argument('--run',required=True)
    args=parser.parse_args()
    if args.command=='record':
        if not math.isfinite(args.seconds) or not 0<args.seconds<=600:
            parser.error('Duration must be between 0 and 600 s.')
        print(capture(args.plan,args.output,args.seconds))
    elif args.command=='mark':
        if args.event=='call_requested':
            meta=common.read_json(Path(args.run)/'started.json')
            if time.monotonic_ns()-meta['start_monotonic_ns'] < 30e9:
                parser.error('At least 30 s lead-in required.')
        print(json.dumps(mark(args.run,args.event,1,args.note)))
    else:
        run=Path(args.run)
        with (run/'decisions.csv').open() as handle:
            rows=list(csv.DictReader(handle))
        cues=[json.loads(line) for line in (run/'cues.jsonl').read_text().splitlines()]
        result=summarize_joint(rows,cues)
        print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
