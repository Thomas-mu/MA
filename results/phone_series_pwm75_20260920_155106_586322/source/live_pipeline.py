"""Begrenzte Live-Erfassung, Rohdatensicherung und Prozessmetriken.

Keine Hardwareimporte: der Aufrufer liefert einen Reader für neue Sensorwerte.
Host-Zeitstempel sind Empfangszeiten, keine vom Sensor gemessenen Samplezeiten.
"""
from __future__ import annotations

import csv
import json
import os
import queue
import resource
import sqlite3
import tempfile
import math
import threading
import time
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import psutil


@dataclass(frozen=True)
class Sample:
    xyz_g: tuple[float, float, float]
    monotonic_ns: int
    utc_ns: int
    gap: bool = False
    overrun: bool = False
    saturated: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Window:
    index: int
    values: np.ndarray
    first_sample_ns: int
    complete_ns: int
    first_utc_ns: int
    last_utc_ns: int
    gap_count: int
    overrun_count: int
    saturated_count: int

    @property
    def sampling_rate_hz(self) -> float:
        duration = (self.complete_ns - self.first_sample_ns) / 1e9
        return (len(self.values) - 1) / duration if duration > 0 else float("nan")


class BufferedAcquisition:
    """Reader und Rohdatenschreiber laufen unabhängig von Inferenz/GUI.

    Bei voller Queue wird das neueste komplette Fenster verworfen (drop-newest).
    Seine Rohwerte bleiben gespeichert. Kein blockierendes Backpressure auf I²C.
    Stop: begonnener Reader beendet sich kooperativ; Teilfenster bleiben im CSV.
    """

    def __init__(self, read_sample: Callable[[threading.Event], Sample | None],
                 raw_path: Path, *, window_size: int = 128, capacity: int = 4,
                 stop_event: threading.Event | None = None,
                 max_samples: int | None = None) -> None:
        if window_size < 2 or capacity < 1:
            raise ValueError("window_size >= 2 und capacity >= 1 erforderlich")
        self.read_sample = read_sample
        self.raw_path = Path(raw_path)
        self.event_path = self.raw_path.with_suffix(".events.jsonl")
        self.window_size = window_size
        self.queue: queue.Queue[Window] = queue.Queue(maxsize=capacity)
        self.stop_event = stop_event or threading.Event()
        self.max_samples = max_samples
        self.done = threading.Event()
        self.error: BaseException | None = None
        self.stats = {"samples_captured": 0, "windows_formed": 0,
                      "windows_dropped": 0, "samples_in_dropped_windows": 0,
                      "gap_events": 0, "overrun_events": 0,
                      "saturated_samples": 0, "queue_high_watermark": 0,
                      "partial_samples_saved": 0,
                      "first_sample_host_monotonic_ns": None, "last_sample_host_monotonic_ns": None}
        self.thread = threading.Thread(target=self._run, name="adxl345-acquisition", daemon=False)

    def start(self) -> "BufferedAcquisition":
        self.raw_path.parent.mkdir(parents=True, exist_ok=True)
        self.thread.start()
        return self

    def _run(self) -> None:
        pending: list[Sample] = []
        try:
            with self.raw_path.open("x", newline="", encoding="utf-8", buffering=1) as raw, \
                    self.event_path.open("x", encoding="utf-8", buffering=1) as events:
                writer = csv.writer(raw)
                writer.writerow(["sample_index", "window_index", "host_monotonic_ns", "host_utc_ns",
                                 "x_g", "y_g", "z_g", "gap", "overrun", "saturated", "diagnostics_json"])
                try:
                    while not self.stop_event.is_set():
                        if self.max_samples is not None and self.stats["samples_captured"] >= self.max_samples:
                            break
                        sample = self.read_sample(self.stop_event)
                        if sample is None:
                            break
                        if self.stats["first_sample_host_monotonic_ns"] is None:
                            self.stats["first_sample_host_monotonic_ns"] = sample.monotonic_ns
                        self.stats["last_sample_host_monotonic_ns"] = sample.monotonic_ns
                        self.stats["samples_captured"] += 1
                        self.stats["gap_events"] += int(sample.gap)
                        self.stats["overrun_events"] += int(sample.overrun)
                        self.stats["saturated_samples"] += int(sample.saturated)
                        writer.writerow([self.stats["samples_captured"], self.stats["windows_formed"] + 1,
                                         sample.monotonic_ns, sample.utc_ns, *sample.xyz_g,
                                         int(sample.gap), int(sample.overrun), int(sample.saturated),
                                         json.dumps(sample.diagnostics, separators=(",", ":"))])
                        pending.append(sample)
                        if len(pending) < self.window_size:
                            continue
                        self.stats["windows_formed"] += 1
                        window = Window(self.stats["windows_formed"], np.array([s.xyz_g for s in pending]),
                                        pending[0].monotonic_ns, pending[-1].monotonic_ns,
                                        pending[0].utc_ns, pending[-1].utc_ns,
                                        sum(s.gap for s in pending), sum(s.overrun for s in pending),
                                        sum(s.saturated for s in pending))
                        pending.clear()
                        raw.flush()
                        try:
                            self.queue.put_nowait(window)
                            self.stats["queue_high_watermark"] = max(self.stats["queue_high_watermark"], self.queue.qsize())
                        except queue.Full:
                            self.stats["windows_dropped"] += 1
                            self.stats["samples_in_dropped_windows"] += self.window_size
                            events.write(json.dumps({"event": "decision_window_dropped_queue_full",
                                                     "window_index": window.index,
                                                     "complete_monotonic_ns": window.complete_ns}) + "\n")
                finally:
                    self.stats["partial_samples_saved"] = len(pending)
                    raw.flush()
                    os.fsync(raw.fileno())
                    events.flush()
                    os.fsync(events.fileno())
        except BaseException as error:
            self.error = error
        finally:
            self.done.set()

    def get(self, timeout: float = 0.1) -> Window | None:
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            if self.done.is_set() and self.error is not None:
                raise RuntimeError(f"Erfassung fehlgeschlagen: {self.error}") from self.error
            return None

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread.ident is not None:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                raise RuntimeError("Sensor-Reader beendet sich nicht innerhalb von 5 s")

    def snapshot(self) -> dict[str, Any]:
        return {**self.stats, "queue_capacity_windows": self.queue.maxsize,
                "queue_pending_windows": self.queue.qsize(), "drop_policy": "drop_newest",
                "acquisition_error": str(self.error) if self.error else None}


class ProcessMetrics:
    """CPU: alle Threads/100 % = ein Kern; RSS: gesamter Prozess inkl. Bibliotheken."""

    def __init__(self) -> None:
        self.process = psutil.Process()
        self.last_wall = time.monotonic()
        cpu = self.process.cpu_times()
        self.last_cpu = cpu.user + cpu.system

    def sample(self) -> dict[str, float | int]:
        now = time.monotonic()
        cpu = self.process.cpu_times()
        total = cpu.user + cpu.system
        wall = now - self.last_wall
        utilization = 100 * (total - self.last_cpu) / wall if wall > 0 else 0.0
        self.last_wall, self.last_cpu = now, total
        return {"process_cpu_percent_one_core": utilization,
                "process_rss_bytes": self.process.memory_info().rss,
                "process_lifetime_peak_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)}


def decision_status(label: int, score: float, threshold: float) -> str:
    if label not in (0, 1) or not np.isfinite(score) or not np.isfinite(threshold) or threshold < 0:
        return "ERROR"
    return "ANOMALY" if label else "NORMAL"


def is_stale(decision_ns: int | None, *, now_ns: int | None = None, limit_seconds: float = 1.0) -> bool:
    return decision_ns is None or ((time.monotonic_ns() if now_ns is None else now_ns) - decision_ns) > limit_seconds * 1e9


def summarize_decisions(csv_path: Path, acquisition: dict[str, Any], window_size: int = 128) -> dict[str, Any]:
    """Exaktes P99 aus Entscheidungs-CSV nach Stop; diskbasiert statt endloser RAM-Liste.

    Empfangsrate ist eine Host-Diagnose. Sie bestätigt keine physische Sensor-ODR
    und ebenso wenig die wissenschaftliche H2 mit allen weiteren Bedingungen.
    """
    count = acquisition["samples_captured"]
    first = acquisition["first_sample_host_monotonic_ns"]
    last = acquisition["last_sample_host_monotonic_ns"]
    observed_hz = (count - 1) * 1e9 / (last - first) if count > 1 and last > first else None
    deadline_ms = window_size / observed_hz * 1000 if observed_hz else None
    valid_count = invalid_count = missed = total = 0
    latency_sum = 0.0
    max_latency = None
    p99 = None
    with tempfile.TemporaryDirectory(prefix=".live-summary-", dir=csv_path.parent) as directory:
        with closing(sqlite3.connect(str(Path(directory) / "latencies.sqlite"))) as database:
            database.execute("PRAGMA cache_size=-2048")
            database.execute("PRAGMA temp_store=FILE")
            database.execute("CREATE TABLE latency (ms REAL)")
            with csv_path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    total += 1
                    value = float(row["decision_latency_ms"])
                    if row["status"] not in ("NORMAL", "ANOMALY") or not math.isfinite(value):
                        invalid_count += 1
                        continue
                    valid_count += 1
                    latency_sum += value
                    max_latency = max(value, max_latency) if max_latency is not None else value
                    missed += int(deadline_ms is not None and value >= deadline_ms)
                    database.execute("INSERT INTO latency VALUES (?)", (value,))
            if valid_count:
                database.execute("CREATE INDEX latency_order ON latency(ms)")
                position = (valid_count - 1) * .99
                low, high = math.floor(position), math.ceil(position)
                left = database.execute("SELECT ms FROM latency ORDER BY ms LIMIT 1 OFFSET ?", (low,)).fetchone()[0]
                right = database.execute("SELECT ms FROM latency ORDER BY ms LIMIT 1 OFFSET ?", (high,)).fetchone()[0]
                p99 = left + (right - left) * (position - low)
    return {"observed_host_delivery_rate_hz": observed_hz,
            "empirical_window_step_budget_ms": deadline_ms, "window_step_samples": window_size,
            "valid_decisions": valid_count, "invalid_decisions": invalid_count,
            "decisions_logged": total, "valid_decision_latency_p99_ms": p99,
            "valid_decision_latency_mean_ms": latency_sum / valid_count if valid_count else None,
            "valid_decision_latency_max_ms": max_latency,
            "deadline_misses_valid_decisions": missed,
            "deadline_miss_fraction_valid_decisions": missed / valid_count if valid_count else None,
            "complete_windows_without_valid_decision": acquisition["windows_formed"] - valid_count,
            "all_complete_windows_have_valid_decisions": acquisition["windows_formed"] == valid_count and valid_count > 0,
            "latency_p99_below_empirical_budget": p99 < deadline_ms if p99 is not None and deadline_ms is not None else None,
            "h2_confirmed": False,
            "interpretation": "Technische Latenzdiagnose; Empfangsrate keine bestätigte Sensor-ODR; verworfene/ungültige/fehlende Entscheidungen separat, kein H2-Nachweis"}
