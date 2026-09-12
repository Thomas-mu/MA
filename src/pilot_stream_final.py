"""Frozen v4 streaming/replay bridge. No GPIO/PWM or hardware imports.

The source owns sensor lifecycle and supplies original Float64 XYZ rows. All raw
rows are retained before inference; the bounded queue drops decisions, not raw.
Only [180,300) is evaluated, partitioned from its first sample (not from t=0).
"""
from __future__ import annotations
import csv
import json
import os
from pathlib import Path
import queue
import threading
import time

import numpy as np
import pandas as pd
import independent_normal_test as frozen_test
import pilot_method_comparison as pilot
from live_pipeline import ProcessMetrics


class WindowAssembler:
    def __init__(self, command_ns):
        if type(command_ns) is not int:
            raise ValueError('Integer PWM command timestamp required')
        self.command_ns = command_ns
        self.pending = []
        self.previous_host = None
        self.first_predecessor = None
        self.samples = 0
        self.selected = 0
        self.windows = 0

    def push(self, row):
        row = dict(row)
        host, index = row['host_monotonic_ns'], row['sample_index']
        if type(host) is not int or type(index) is not int or index != self.samples:
            raise ValueError('Nonintegral timestamp or discontinuous sample index')
        if self.previous_host is not None and host <= self.previous_host:
            raise ValueError('Nonmonotonic host time: source rejected')
        relative = host - self.command_ns
        predecessor = self.previous_host
        self.previous_host = host
        self.samples += 1
        if not 180_000_000_000 <= relative < 300_000_000_000:
            return None
        if not self.pending:
            self.first_predecessor = predecessor
        self.pending.append(row)
        self.selected += 1
        if len(self.pending) != 128:
            return None
        frame = pd.DataFrame(self.pending)
        # Use the frozen kernel, including its F-order Float64 centering/flags.
        window = frozen_test.build_windows(frame, self.command_ns)[0][0]
        meta = window['metadata']
        meta.update(window_index_in_recording=self.windows,
                    source_start_index=self.pending[0]['sample_index'],
                    source_end_index_exclusive=self.pending[-1]['sample_index'] + 1)
        if self.first_predecessor is not None and frame.host_monotonic_ns.iloc[0] - self.first_predecessor > 160_000_000:
            if 'host_interval_over_160ms' not in meta['quality_reasons']:
                meta['quality_reasons'].append('host_interval_over_160ms')
            meta['quality_valid'] = False
            window['ac_float32'] = None
        self.windows += 1
        self.pending.clear()
        return window

    def summary(self):
        return dict(raw_xyz=self.samples, selected_xyz=self.selected,
                    complete_windows=self.windows, trailing_selected_xyz=len(self.pending))


from pilot_runtime_final import FrozenEngine


def run_stream(rows, command_ns, engine, output, *, capacity=4, paced=False,
               stop_event=None, source_mode='offline_replay'):
    """Source iteration on producer thread; no actuation. New output only.

    Unpaced replay is correctness/throughput work, not real-time sensor evidence.
    A sensor source must be cooperative, save partial raw rows, and own safe stop.
    """
    if capacity < 1 or source_mode not in ('offline_replay', 'sensor_live'):
        raise ValueError('Invalid queue capacity/source mode')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    stop = stop_event if stop_event is not None else threading.Event()
    done, metrics_done = threading.Event(), threading.Event()
    pending = queue.Queue(maxsize=capacity)
    assembler = WindowAssembler(command_ns)
    stats = dict(windows_dropped=0, queue_high_watermark=0, source_mode=source_mode,
                 paced_replay=paced, physical_lost_samples=None, source_error=None,
                 raw_write_and_assembly_in_sensor_thread=True,
                 decision_interval_seconds=[180,300], warmup_invocations=20 if engine.warmup_ns is not None else 0)
    resource_path = output/"resources.csv"
    metrics = ProcessMetrics()

    def monitor():
        with resource_path.open('x', newline='') as handle:
            writer=None
            while True:
                sample=dict(monotonic_ns=time.monotonic_ns(), queue_pending_windows=pending.qsize(), **metrics.sample())
                if writer is None:
                    writer=csv.DictWriter(handle, fieldnames=list(sample));writer.writeheader()
                writer.writerow(sample);handle.flush()
                if metrics_done.wait(.1):break
            os.fsync(handle.fileno())

    def produce():
        first_host, replay_origin = None, None
        try:
            with (output/'raw.csv').open('x', newline='') as raw, (output/'events.jsonl').open('x') as events:
                writer = None
                try:
                    for row in rows:
                        if stop.is_set():
                            stats['source_error'] = 'Interrupted source; partial raw preserved'
                            break
                        row = dict(row)
                        host = row['host_monotonic_ns']
                        if first_host is None:
                            first_host, replay_origin = host, time.monotonic_ns()
                        if paced:
                            delay = (replay_origin + host-first_host-time.monotonic_ns())/1e9
                            if delay > 0 and stop.wait(delay):
                                stats['source_error'] = 'Interrupted paced replay'
                                break
                        received_ns = time.monotonic_ns()
                        if writer is None:
                            writer = csv.DictWriter(raw, fieldnames=list(row))
                            writer.writeheader()
                        writer.writerow(row)
                        window = assembler.push(row)
                        if window is None:
                            continue
                        raw.flush()
                        # Sensor: host completion timestamp; replay: mapped arrival.
                        complete = host if source_mode == 'sensor_live' else (
                            replay_origin+host-first_host if paced else received_ns)
                        window['available_monotonic_ns'] = complete
                        window['assembly_completed_monotonic_ns'] = time.monotonic_ns()
                        try:
                            pending.put_nowait(window)
                            stats['queue_high_watermark'] = max(stats['queue_high_watermark'], pending.qsize())
                        except queue.Full:
                            stats['windows_dropped'] += 1
                            events.write(json.dumps(dict(event='decision_window_dropped_queue_full',
                                                          **window['metadata']))+'\n')
                finally:
                    raw.flush()
                    os.fsync(raw.fileno())
                    events.flush()
                    os.fsync(events.fileno())
        except BaseException as exc:
            stats['source_error'] = f'{type(exc).__name__}: {exc}'
        finally:
            if stop.is_set() and stats['source_error'] is None:
                stats['source_error'] = 'Interrupted source; partial raw preserved'
            done.set()

    producer = threading.Thread(target=produce, daemon=False)
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    producer.start()
    monitor_thread.start()
    decision_count = invalid_count = 0
    failure = None
    try:
        with (output/'decisions.jsonl').open('x') as journal:
            while not done.is_set() or not pending.empty():
                try:
                    window = pending.get(timeout=.1)
                except queue.Empty:
                    continue
                for result in engine.score(window):
                    result['complete_to_decision_ns'] = result['decision_monotonic_ns'] - window['available_monotonic_ns']
                    result['assembly_ns'] = window['assembly_completed_monotonic_ns']-window['available_monotonic_ns']
                    decision_count += 1
                    invalid_count += int(result["decision"] == "INVALID")
                    result["queue_wait_ns"] = result["dequeue_monotonic_ns"]-window["assembly_completed_monotonic_ns"]
                    result["logging_monotonic_ns"] = time.monotonic_ns()
                    journal.write(json.dumps(result, allow_nan=False)+'\n')
                journal.flush()
            os.fsync(journal.fileno())
    except BaseException as exc:
        failure = exc
        stop.set()
    finally:
        producer.join(timeout=5)
        if producer.is_alive():
            failure = failure or RuntimeError('Source did not stop cooperatively within 5s')
        metrics_done.set()
        monitor_thread.join(timeout=1)
        stats.update(assembler.summary())
        stats['decision_rows'] = decision_count
        stats['status'] = 'error' if failure or stats['source_error'] else 'completed'
        stats['processing_error'] = str(failure) if failure else None
        stats['invalid_decisions'] = invalid_count
        stats['unprocessed_windows'] = assembler.windows - stats['windows_dropped'] - decision_count//len(engine.methods)
        stats['model_load_ns'] = engine.load_ns
        stats['warmup_ns'] = engine.warmup_ns
        stats['latency_scope'] = 'complete-to-decision including assembly and queue; scorer_call includes transfer and scoring, not isolated model invoke'
        stats['model_package_sha256'] = frozen_test.sha256(engine.directory/'pilot_bundle.json')
        (output/'summary.json').write_text(json.dumps(stats,indent=2,allow_nan=False)+'\n')
    if failure:
        raise failure
    if stats['source_error']:
        raise RuntimeError(stats['source_error'])
    pilot.load_bundle(engine.directory)
    return stats
