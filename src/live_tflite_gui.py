#!/usr/bin/env python3
"""Tkinter GUI for parallel Autoencoder and Isolation-Forest monitoring.

The acquisition worker reuses the validated sensor, scaling, inference and
logging schema from ``live_tflite_monitor.py``.  Tkinter and Matplotlib are
updated exclusively by the main thread.  This module contains no actuator
integration.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import queue
import signal
from contextlib import closing
import sys
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass, replace, field
from datetime import datetime
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/masterarbeit_matplotlib")

import tkinter as tk
from tkinter import ttk

import joblib
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = Path(__file__).resolve().parent
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

from live_tflite_monitor import (  # noqa: E402
    CSV_FIELDS,
    LiveConfiguration,
    collect_window,
    infer_window,
    load_scaler,
    load_sensor_access,
    load_tflite_runtime,
    resolve_live_configuration,
    scale_window,
    sha256_file,
    warm_up,
    iter_live_measurements, add_acquisition_arguments, acquisition_options,
    validate_acquisition_options,
)


from live_pipeline import decision_status, is_stale

PLOT_WINDOW_COUNT = 100
RANKING_EVENT_COUNT = 20
QUEUE_POLL_INTERVAL_MS = 50
SIMULATION_INTERVAL_SECONDS = 0.35
NORMAL_COLOR = "#18864b"
ANOMALY_COLOR = "#c62828"
IDLE_COLOR = "#59636e"
BACKGROUND_COLOR = "#f4f6f8"
PANEL_COLOR = "#ffffff"
TEXT_COLOR = "#18212b"
ANOMALY_EVENT_RESET_NORMAL_WINDOWS = 2
ANOMALY_METHOD_LABELS = {
    "autoencoder": "Autoencoder",
    "isolation_forest": "Isolation Forest",
    "rms": "RMS",
}
ANOMALY_EVENT_FIELDS = (
    "event_id",
    "method",
    "method_label",
    "result",
    "detection_timestamp",
    "detection_window",
    "first_alarm_timestamp",
    "first_alarm_window",
    "delay_windows_from_first",
    "delay_ms_from_first",
    "detection_rank",
    "is_fastest",
    "first_methods",
)


class AnomalyEventTracker:
    """Group model alarms into events and compare their first alarm windows.

    There is no external ground-truth trigger in the live GUI.  Consequently,
    delays are deliberately measured from the earliest model alarm, not from an
    assumed physical fault onset.  Two consecutive all-normal windows close an
    event so that one brief normal window does not split delayed detections.
    """

    def __init__(self, methods: tuple[str, ...]) -> None:
        if not methods or any(method not in ANOMALY_METHOD_LABELS for method in methods):
            raise ValueError("Unbekannte oder leere Methodenliste für Alarmvergleich.")
        self.methods = methods
        self.event_id = 0
        self.active = False
        self.normal_windows = 0
        self.first_alarm_timestamp = ""
        self.first_alarm_window = 0
        self.first_alarm_monotonic_ns = 0
        self.first_methods: tuple[str, ...] = ()
        self.detected_methods: set[str] = set()
        self.detection_delays: dict[str, int] = {}

    def update(
        self,
        *,
        timestamp: str,
        window_index: int,
        decision_monotonic_ns: int,
        labels: dict[str, int | None],
    ) -> list[dict[str, Any]]:
        valid_labels = {
            method: labels.get(method)
            for method in self.methods
            if labels.get(method) in (0, 1)
        }
        anomaly_methods = tuple(
            method for method in self.methods if valid_labels.get(method) == 1
        )
        rows: list[dict[str, Any]] = []

        if not self.active:
            if not anomaly_methods:
                return rows
            self.event_id += 1
            self.active = True
            self.normal_windows = 0
            self.first_alarm_timestamp = timestamp
            self.first_alarm_window = int(window_index)
            self.first_alarm_monotonic_ns = int(decision_monotonic_ns)
            self.first_methods = anomaly_methods
            self.detected_methods = set()
            self.detection_delays = {}

        if anomaly_methods:
            self.normal_windows = 0
            for method in anomaly_methods:
                if method in self.detected_methods:
                    continue
                delay_windows = int(window_index) - self.first_alarm_window
                delay_ms = max(
                    0.0,
                    (int(decision_monotonic_ns) - self.first_alarm_monotonic_ns)
                    / 1e6,
                )
                detection_rank = 1 + len(
                    {
                        previous_delay
                        for previous_delay in self.detection_delays.values()
                        if previous_delay < delay_windows
                    }
                )
                rows.append(
                    self._row(
                        method=method,
                        result="DETECTED",
                        detection_timestamp=timestamp,
                        detection_window=int(window_index),
                        delay_windows=delay_windows,
                        delay_ms=delay_ms,
                        detection_rank=detection_rank,
                        is_fastest=delay_windows == 0,
                    )
                )
                self.detected_methods.add(method)
                self.detection_delays[method] = delay_windows
        elif len(valid_labels) == len(self.methods):
            self.normal_windows += 1
            if self.normal_windows >= ANOMALY_EVENT_RESET_NORMAL_WINDOWS:
                rows.extend(self._close_event())
        return rows

    def finish(self) -> list[dict[str, Any]]:
        """Close a running event and report methods that never detected it."""
        return self._close_event() if self.active else []

    def _close_event(self) -> list[dict[str, Any]]:
        rows = [
            self._row(
                method=method,
                result="NOT_DETECTED",
                detection_timestamp="",
                detection_window="",
                delay_windows="",
                delay_ms="",
                detection_rank="",
                is_fastest=False,
            )
            for method in self.methods
            if method not in self.detected_methods
        ]
        self.active = False
        self.normal_windows = 0
        return rows

    def _row(
        self,
        *,
        method: str,
        result: str,
        detection_timestamp: str,
        detection_window: int | str,
        delay_windows: int | str,
        delay_ms: float | str,
        detection_rank: int | str,
        is_fastest: bool,
    ) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "method": method,
            "method_label": ANOMALY_METHOD_LABELS[method],
            "result": result,
            "detection_timestamp": detection_timestamp,
            "detection_window": detection_window,
            "first_alarm_timestamp": self.first_alarm_timestamp,
            "first_alarm_window": self.first_alarm_window,
            "delay_windows_from_first": delay_windows,
            "delay_ms_from_first": delay_ms,
            "detection_rank": detection_rank,
            "is_fastest": int(is_fastest),
            "first_methods": "+".join(self.first_methods),
        }


@dataclass(frozen=True)
class ProfileDisplayMetadata:
    profile_name: str
    profile_version: int
    sampling_rate_hz: int
    results_directory: Path


@dataclass(frozen=True)
class IsolationForestConfiguration:
    bundle_directory: Path
    model_path: Path
    threshold: float
    rms_threshold: float
    runtime: str
    rms_runtime: str
    scaler_mean: tuple[float, float, float]
    scaler_scale: tuple[float, float, float]
    provenance: dict[str, Any]


@dataclass(frozen=True)
class Measurement:
    timestamp: str
    window_index: int
    reconstruction_error: float
    threshold: float
    predicted_label: int
    inference_time_ms: float
    measured_sampling_rate_hz: float
    isolation_forest_score: float | None = None
    isolation_forest_threshold: float | None = None
    isolation_forest_predicted_label: int | None = None
    isolation_forest_inference_time_ms: float | None = None
    rms_score: float | None = None
    rms_threshold: float | None = None
    rms_predicted_label: int | None = None
    rms_inference_time_ms: float | None = None
    decision_monotonic_ns: int = 0
    window_complete_monotonic_ns: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def csv_row(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "window_index": self.window_index,
            "reconstruction_error": self.reconstruction_error,
            "threshold": self.threshold,
            "predicted_label": self.predicted_label,
            "inference_time_ms": self.inference_time_ms,
            "measured_sampling_rate_hz": self.measured_sampling_rate_hz,
            "isolation_forest_score": self.isolation_forest_score,
            "isolation_forest_threshold": self.isolation_forest_threshold,
            "isolation_forest_predicted_label": self.isolation_forest_predicted_label,
            "isolation_forest_inference_time_ms": self.isolation_forest_inference_time_ms,
            "rms_score": self.rms_score,
            "rms_threshold": self.rms_threshold,
            "rms_predicted_label": self.rms_predicted_label,
            "rms_inference_time_ms": self.rms_inference_time_ms,
        }


@dataclass(frozen=True)
class WorkerMessage:
    kind: str
    payload: Any = None


def measurement_display_status(measurement: Measurement, *, now_ns: int | None = None,
                               limit_seconds: float = 1.0) -> str:
    status = decision_status(measurement.predicted_label, measurement.reconstruction_error, measurement.threshold)
    if status == "ERROR":
        return status
    # Eine gerade berechnete Entscheidung kann sich auf längst alte Daten beziehen.
    if (is_stale(measurement.window_complete_monotonic_ns, now_ns=now_ns, limit_seconds=limit_seconds)
            or is_stale(measurement.decision_monotonic_ns, now_ns=now_ns, limit_seconds=limit_seconds)):
        return "STALE / VERALTET"
    return status


def isolation_forest_display_status(
    measurement: Measurement,
    *,
    now_ns: int | None = None,
    limit_seconds: float = 1.0,
) -> str:
    if (
        measurement.isolation_forest_score is None
        or measurement.isolation_forest_threshold is None
        or measurement.isolation_forest_predicted_label is None
    ):
        return "ERROR"
    status = decision_status(
        measurement.isolation_forest_predicted_label,
        measurement.isolation_forest_score,
        measurement.isolation_forest_threshold,
    )
    if status == "ERROR":
        return status
    if (
        is_stale(measurement.window_complete_monotonic_ns, now_ns=now_ns, limit_seconds=limit_seconds)
        or is_stale(measurement.decision_monotonic_ns, now_ns=now_ns, limit_seconds=limit_seconds)
    ):
        return "STALE / VERALTET"
    return status


def rms_display_status(
    measurement: Measurement,
    *,
    now_ns: int | None = None,
    limit_seconds: float = 1.0,
) -> str:
    if (
        measurement.rms_score is None
        or measurement.rms_threshold is None
        or measurement.rms_predicted_label is None
    ):
        return "ERROR"
    status = decision_status(
        measurement.rms_predicted_label,
        measurement.rms_score,
        measurement.rms_threshold,
    )
    if status == "ERROR":
        return status
    if (
        is_stale(measurement.window_complete_monotonic_ns, now_ns=now_ns, limit_seconds=limit_seconds)
        or is_stale(measurement.decision_monotonic_ns, now_ns=now_ns, limit_seconds=limit_seconds)
    ):
        return "STALE / VERALTET"
    return status


def read_profile_display_metadata(
    configuration: LiveConfiguration,
) -> ProfileDisplayMetadata:
    if configuration.profile_name is None:
        raise ValueError("Die GUI benötigt zwingend ein Setup-Profil.")
    profile_root = configuration.model_path.parent.parent
    metadata_path = profile_root / "profile.json"
    with metadata_path.open(encoding="utf-8") as handle:
        metadata = json.load(handle)
    if metadata.get("profile_name") != configuration.profile_name:
        raise ValueError("Inkonsistenter Profilname in profile.json.")
    if metadata.get("status") != "ready":
        raise ValueError("Die GUI akzeptiert nur Profile mit Status 'ready'.")
    sampling_rate_hz = int(metadata.get("sampling_rate_hz", -1))
    if sampling_rate_hz <= 0:
        raise ValueError(f"Ungültige Profil-Samplingrate: {sampling_rate_hz}")
    return ProfileDisplayMetadata(
        profile_name=configuration.profile_name,
        profile_version=int(metadata.get("profile_version", 0)),
        sampling_rate_hz=sampling_rate_hz,
        results_directory=profile_root / "results",
    )


def resolve_isolation_forest_configuration(
    configuration: LiveConfiguration,
) -> IsolationForestConfiguration | None:
    """Load the profile-bound IF bundle when one is installed beside the profile."""
    profile_root = configuration.model_path.parent.parent
    bundle_directory = profile_root / "comparison_bundle"
    bundle_path = bundle_directory / "bundle.json"
    if not bundle_path.is_file():
        return None
    with bundle_path.open(encoding="utf-8") as handle:
        bundle = json.load(handle)
    if bundle.get("profile_name") != configuration.profile_name:
        raise ValueError("Isolation-Forest-Bündel gehört zu einem anderen Profil.")
    if int(bundle.get("sampling_rate_hz", -1)) != int(configuration.profile_sampling_rate_hz):
        raise ValueError("Isolation-Forest-Bündel und Profil haben verschiedene Samplingraten.")
    if int(bundle.get("window_size", -1)) != 128:
        raise ValueError("Isolation-Forest-Bündel erwartet nicht 128 Samples pro Fenster.")
    model_path = bundle_directory / "isolation_forest.joblib"
    expected_hash = bundle.get("artifact_sha256", {}).get("isolation_forest.joblib")
    if not model_path.is_file() or not expected_hash or sha256_file(model_path) != expected_hash:
        raise ValueError("Isolation-Forest-Modell fehlt oder stimmt nicht mit dem Bündel überein.")
    threshold = float(bundle.get("thresholds", {}).get("isolation_forest", {}).get("value", float("nan")))
    if not math.isfinite(threshold) or threshold < 0:
        raise ValueError("Isolation-Forest-Bündel enthält keinen gültigen Threshold.")
    rms_threshold = float(bundle.get("thresholds", {}).get("rms", {}).get("value", float("nan")))
    if not math.isfinite(rms_threshold) or rms_threshold < 0:
        raise ValueError("Vergleichsbündel enthält keinen gültigen RMS-Threshold.")
    scaler = bundle.get("scaler", {})
    mean = tuple(float(value) for value in scaler.get("mean", []))
    scale = tuple(float(value) for value in scaler.get("scale", []))
    if len(mean) != 3 or len(scale) != 3 or not all(math.isfinite(value) for value in (*mean, *scale)):
        raise ValueError("Isolation-Forest-Bündel enthält keine gültige Skalierung.")
    return IsolationForestConfiguration(
        bundle_directory=bundle_directory,
        model_path=model_path,
        threshold=threshold,
        rms_threshold=rms_threshold,
        runtime="scikit-learn IsolationForest.score_samples",
        rms_runtime="NumPy RMS auf standardisiertem 128×3-Fenster",
        scaler_mean=mean,
        scaler_scale=scale,
        provenance={
            "bundle_path": str(bundle_path),
            "bundle_sha256": sha256_file(bundle_path),
            "model_path": str(model_path),
            "model_sha256": expected_hash,
            "threshold_source": "P99_NORMAL_VALIDATION",
            "rms_threshold": rms_threshold,
            "measurement_chain_status": bundle.get("measurement_chain_status"),
        },
    )


def load_isolation_forest_scorer(
    configuration: IsolationForestConfiguration,
    scaler: Any,
) -> Any:
    if not np.allclose(np.asarray(scaler.mean_), configuration.scaler_mean, rtol=0, atol=1e-12):
        raise ValueError("Isolation Forest und Autoencoder verwenden verschiedene Scaler-Mittelwerte.")
    if not np.allclose(np.asarray(scaler.scale_), configuration.scaler_scale, rtol=0, atol=1e-12):
        raise ValueError("Isolation Forest und Autoencoder verwenden verschiedene Scaler-Skalierungen.")
    model = joblib.load(configuration.model_path)
    if int(getattr(model, "n_features_in_", -1)) != 128 * 3:
        raise ValueError("Isolation Forest erwartet nicht 128×3 Eingabewerte.")

    def score(scaled_window: np.ndarray) -> float:
        if scaled_window.shape != (128, 3) or not np.isfinite(scaled_window).all():
            raise ValueError("Isolation Forest benötigt ein endliches 128×3-Fenster.")
        return float(-model.score_samples(scaled_window.reshape(1, -1))[0])

    # Initialisiert den sklearn-Pfad vor Beginn der zeitkritischen Erfassung.
    score(np.zeros((128, 3), dtype=np.float32))
    return score


def allocate_gui_log_path(results_directory: Path) -> Path:
    results_directory.mkdir(parents=True, exist_ok=True)
    base_id = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    for suffix in range(10_000):
        run_id = base_id if suffix == 0 else f"{base_id}_{suffix:03d}"
        path = results_directory / f"live_tflite_gui_{run_id}.csv"
        if not path.exists():
            return path
    raise RuntimeError("Kein freier GUI-Logdateiname verfügbar.")


class AcquisitionWorker(threading.Thread):
    """Own sensor/model resources and publish immutable GUI measurements."""

    def __init__(
        self,
        *,
        configuration: LiveConfiguration,
        metadata: ProfileDisplayMetadata,
        output_queue: queue.Queue[WorkerMessage],
        stop_event: threading.Event,
        self_test: bool,
        isolation_forest_configuration: IsolationForestConfiguration | None = None,
        simulation_interval_seconds: float = SIMULATION_INTERVAL_SECONDS,
        acquisition_configuration: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(name="sensor-tflite-worker", daemon=False)
        self.configuration = configuration
        self.metadata = metadata
        self.output_queue = output_queue
        self.stop_event = stop_event
        self.self_test = self_test
        self.isolation_forest_configuration = isolation_forest_configuration
        self.simulation_interval_seconds = simulation_interval_seconds
        self.acquisition_configuration = acquisition_configuration or {}
        self.gui_messages_dropped = 0
        # Genau vier Kontrollarten, unabhängig von der begrenzten Messwertqueue.
        # Pro Art wird der letzte Zustand bis zur Abholung aufbewahrt.
        self.control_messages: dict[str, WorkerMessage] = {}
        self.control_lock = threading.Lock()

    def emit(self, kind: str, payload: Any = None) -> None:
        message = WorkerMessage(kind, payload)
        if kind != "measurement":
            if kind not in ("status", "log_path", "error", "finished"):
                raise ValueError(f"Unbekannte GUI-Kontrollnachricht: {kind}")
            with self.control_lock:
                self.control_messages[kind] = message
            return
        try:
            self.output_queue.put_nowait(message)
        except queue.Full:
            # GUI-Verzögerung darf den Inferenz-Worker nicht blockieren.
            try:
                self.output_queue.get_nowait()
                self.gui_messages_dropped += 1
            except queue.Empty:
                pass
            self.output_queue.put_nowait(message)

    def take_control_messages(self) -> list[WorkerMessage]:
        with self.control_lock:
            messages = list(self.control_messages.values())
            self.control_messages.clear()
        return messages

    def run(self) -> None:
        try:
            if self.self_test:
                self.run_simulation()
            else:
                self.run_live_inference()
        except Exception as error:
            self.emit(
                "error",
                {
                    "message": f"{type(error).__name__}: {error}",
                    "traceback": traceback.format_exc(),
                },
            )
        finally:
            self.emit("finished")

    def run_simulation(self) -> None:
        self.emit("status", "Self-Test: simulierte Live-Werte")
        # Jede Methode alarmiert in einem anderen Fenster. Dadurch prüft der
        # GUI-Self-Test nicht nur rote Statusfelder, sondern auch den zeitlichen
        # Erkennungsvergleich und dessen Verzögerungsanzeige.
        factors = (
            (0.55, 0.55, 0.55),
            (1.22, 0.75, 0.80),
            (0.70, 1.22, 0.85),
            (0.75, 0.80, 1.22),
            (0.64, 0.64, 0.64),
            (0.55, 0.55, 0.55),
            (0.75, 1.22, 0.80),
            (0.70, 0.75, 1.22),
            (1.22, 0.80, 0.85),
            (0.64, 0.64, 0.64),
            (0.55, 0.55, 0.55),
            (0.75, 0.80, 1.22),
            (1.22, 0.75, 0.85),
            (0.70, 1.22, 0.80),
            (0.64, 0.64, 0.64),
            (0.55, 0.55, 0.55),
        )
        window_index = 0
        while not self.stop_event.is_set():
            ae_factor, if_factor, rms_factor = factors[window_index % len(factors)]
            window_index += 1
            error = self.configuration.threshold * ae_factor
            prediction = int(error > self.configuration.threshold)
            if_threshold = (
                self.isolation_forest_configuration.threshold
                if self.isolation_forest_configuration is not None else None
            )
            if_score = if_threshold * if_factor if if_threshold is not None else None
            if_prediction = (
                int(if_score > if_threshold)
                if if_score is not None and if_threshold is not None else None
            )
            rms_threshold = (
                self.isolation_forest_configuration.rms_threshold
                if self.isolation_forest_configuration is not None else None
            )
            rms_score = rms_threshold * rms_factor if rms_threshold is not None else None
            rms_prediction = (
                int(rms_score > rms_threshold)
                if rms_score is not None and rms_threshold is not None else None
            )
            sampling_rate = self.metadata.sampling_rate_hz + (
                ((window_index % 5) - 2) * 0.08
            )
            inference_time = 0.16 + (window_index % 4) * 0.015
            simulated_complete_ns = time.monotonic_ns()
            self.emit(
                "measurement",
                Measurement(
                    timestamp=datetime.now()
                    .astimezone()
                    .isoformat(timespec="milliseconds"),
                    window_index=window_index,
                    reconstruction_error=error,
                    threshold=self.configuration.threshold,
                    predicted_label=prediction,
                    inference_time_ms=inference_time,
                    measured_sampling_rate_hz=sampling_rate,
                    isolation_forest_score=if_score,
                    isolation_forest_threshold=if_threshold,
                    isolation_forest_predicted_label=if_prediction,
                    isolation_forest_inference_time_ms=(
                        0.28 + (window_index % 3) * 0.02
                        if if_threshold is not None else None
                    ),
                    rms_score=rms_score,
                    rms_threshold=rms_threshold,
                    rms_predicted_label=rms_prediction,
                    rms_inference_time_ms=(
                        0.02 + (window_index % 2) * 0.005
                        if rms_threshold is not None else None
                    ),
                    decision_monotonic_ns=simulated_complete_ns,
                    window_complete_monotonic_ns=simulated_complete_ns,
                ),
            )
            if self.stop_event.wait(self.simulation_interval_seconds):
                break

    def run_live_inference(self) -> None:
        self.emit("status", "Modell und Scaler werden geladen …")
        scaler = load_scaler(self.configuration.scaler_path)
        runtime = load_tflite_runtime(self.configuration.model_path)
        warm_up(runtime, self.configuration.threshold)
        if_scorer = None
        if_threshold = None
        if_runtime = None
        if_provenance = None
        rms_scorer = None
        rms_threshold = None
        rms_runtime = None
        rms_provenance = None
        if self.isolation_forest_configuration is not None:
            if_scorer = load_isolation_forest_scorer(
                self.isolation_forest_configuration, scaler
            )
            if_threshold = self.isolation_forest_configuration.threshold
            if_runtime = self.isolation_forest_configuration.runtime
            if_provenance = self.isolation_forest_configuration.provenance
            rms_threshold = self.isolation_forest_configuration.rms_threshold
            rms_runtime = self.isolation_forest_configuration.rms_runtime
            rms_provenance = {
                **self.isolation_forest_configuration.provenance,
                "method": "rms",
            }

            def rms_scorer(scaled_window: np.ndarray) -> float:
                if scaled_window.shape != (128, 3) or not np.isfinite(scaled_window).all():
                    raise ValueError("RMS benötigt ein endliches 128×3-Fenster.")
                return float(
                    np.sqrt(np.mean(np.square(scaled_window), dtype=np.float64))
                )

            rms_scorer(np.zeros((128, 3), dtype=np.float32))
        if self.stop_event.is_set():
            return

        log_path = allocate_gui_log_path(PROJECT_ROOT / "results" / "live_runs")
        anomaly_log_path = log_path.with_suffix(".anomalies.csv")
        self.emit("log_path", log_path)
        self.emit(
            "status",
            "Live-Messung aktiv: Autoencoder + Isolation Forest + RMS; Rohdaten werden protokolliert"
            if if_scorer is not None
            else "Live-Messung aktiv: Autoencoder; Isolation Forest nicht konfiguriert",
        )
        compared_methods = (
            ("autoencoder", "isolation_forest", "rms")
            if if_scorer is not None else ("autoencoder",)
        )
        event_tracker = AnomalyEventTracker(compared_methods)
        with anomaly_log_path.open(
            "x", encoding="utf-8", newline="", buffering=1
        ) as anomaly_handle, closing(iter_live_measurements(
            runtime, scaler, self.configuration, log_path, stop_event=self.stop_event,
            gui_enabled=True, isolation_forest_scorer=if_scorer,
            isolation_forest_threshold=if_threshold,
            isolation_forest_runtime=if_runtime,
            isolation_forest_provenance=if_provenance,
            rms_scorer=rms_scorer,
            rms_threshold=rms_threshold,
            rms_runtime=rms_runtime,
            rms_provenance=rms_provenance,
            **self.acquisition_configuration,
        )) as measurements:
            anomaly_writer = csv.DictWriter(
                anomaly_handle, fieldnames=ANOMALY_EVENT_FIELDS
            )
            anomaly_writer.writeheader()
            try:
                for row in measurements:
                    event_rows = event_tracker.update(
                        timestamp=row["timestamp"],
                        window_index=row["window_index"],
                        decision_monotonic_ns=row["decision_monotonic_ns"],
                        labels={
                            "autoencoder": row["predicted_label"],
                            "isolation_forest": row["isolation_forest_predicted_label"],
                            "rms": row["rms_predicted_label"],
                        },
                    )
                    if event_rows:
                        anomaly_writer.writerows(event_rows)
                    self.emit("measurement", Measurement(
                        timestamp=row["timestamp"], window_index=row["window_index"],
                        reconstruction_error=row["reconstruction_error"], threshold=row["threshold"],
                        predicted_label=row["predicted_label"], inference_time_ms=row["inference_time_ms"],
                        measured_sampling_rate_hz=row["measured_sampling_rate_hz"],
                        isolation_forest_score=(
                            row["isolation_forest_score"] if if_scorer is not None else None
                        ),
                        isolation_forest_threshold=if_threshold,
                        isolation_forest_predicted_label=(
                            row["isolation_forest_predicted_label"] if if_scorer is not None else None
                        ),
                        isolation_forest_inference_time_ms=(
                            row["isolation_forest_inference_time_ms"] if if_scorer is not None else None
                        ),
                        rms_score=row["rms_score"] if rms_scorer is not None else None,
                        rms_threshold=rms_threshold,
                        rms_predicted_label=(
                            row["rms_predicted_label"] if rms_scorer is not None else None
                        ),
                        rms_inference_time_ms=(
                            row["rms_inference_time_ms"] if rms_scorer is not None else None
                        ),
                        decision_monotonic_ns=row["decision_monotonic_ns"],
                        window_complete_monotonic_ns=row["window_complete_monotonic_ns"], details=row))
            finally:
                remaining_rows = event_tracker.finish()
                if remaining_rows:
                    anomaly_writer.writerows(remaining_rows)
                anomaly_handle.flush()
                os.fsync(anomaly_handle.fileno())


class LiveTFLiteApplication:
    def __init__(
        self,
        root: tk.Tk,
        configuration: LiveConfiguration,
        metadata: ProfileDisplayMetadata,
        *,
        threshold_source: str,
        self_test: bool,
        self_test_duration: float | None,
        isolation_forest_configuration: IsolationForestConfiguration | None = None,
        acquisition_configuration: dict[str, Any] | None = None,
    ) -> None:
        self.root = root
        self.configuration = configuration
        self.metadata = metadata
        self.threshold_source = threshold_source
        self.self_test = self_test
        self.self_test_duration = self_test_duration
        self.isolation_forest_configuration = isolation_forest_configuration
        self.acquisition_configuration = acquisition_configuration or {}
        self.last_decision_ns: int | None = None
        self.last_window_complete_ns: int | None = None
        self.gui_metrics_handle = None
        self.gui_metrics_writer = None
        self.last_draw_logged_ns = 0
        # Der automatisierte Darstellungs-Self-Test prüft 100 Historienpunkte
        # in kurzer Zeit. Der echte Livebetrieb behält bewusst die enge
        # Acht-Nachrichten-Grenze, damit Anzeigeverzug nie die Erfassung staut.
        queue_size = 128 if self_test and self_test_duration is not None else 8
        self.message_queue: queue.Queue[WorkerMessage] = queue.Queue(
            maxsize=queue_size
        )
        self.stop_event = threading.Event()
        self.worker: AcquisitionWorker | None = None
        self.closing = False
        self.log_path: Path | None = None
        self.anomaly_log_path: Path | None = None
        self.normal_seen = False
        self.anomaly_seen = False
        self.window_indices: deque[int] = deque(maxlen=PLOT_WINDOW_COUNT)
        self.reconstruction_errors: deque[float] = deque(
            maxlen=PLOT_WINDOW_COUNT
        )
        self.isolation_forest_scores: deque[float] = deque(maxlen=PLOT_WINDOW_COUNT)
        self.rms_scores: deque[float] = deque(maxlen=PLOT_WINDOW_COUNT)
        self.autoencoder_anomaly_states: deque[float] = deque(maxlen=PLOT_WINDOW_COUNT)
        self.isolation_forest_anomaly_states: deque[float] = deque(maxlen=PLOT_WINDOW_COUNT)
        self.rms_anomaly_states: deque[float] = deque(maxlen=PLOT_WINDOW_COUNT)
        self.fastest_alarm_windows: dict[str, deque[int]] = {
            method: deque(maxlen=PLOT_WINDOW_COUNT)
            for method in ANOMALY_METHOD_LABELS
        }
        self.detection_rankings: dict[str, deque[tuple[int, float]]] = {
            method: deque(maxlen=RANKING_EVENT_COUNT)
            for method in ANOMALY_METHOD_LABELS
        }
        compared_methods = (
            ("autoencoder", "isolation_forest", "rms")
            if isolation_forest_configuration is not None else ("autoencoder",)
        )
        self.anomaly_event_tracker = AnomalyEventTracker(compared_methods)
        self.latest_event_detections: dict[str, dict[str, Any]] = {}

        self.status_text = tk.StringVar(value="BEREIT")
        self.isolation_forest_status_text = tk.StringVar(
            value="BEREIT" if isolation_forest_configuration is not None else "NICHT KONFIGURIERT"
        )
        self.rms_status_text = tk.StringVar(
            value="BEREIT" if isolation_forest_configuration is not None else "NICHT KONFIGURIERT"
        )
        self.mse_text = tk.StringVar(value="–")
        self.threshold_text = tk.StringVar(
            value=f"{configuration.threshold:.6f}"
        )
        self.threshold_source_text = tk.StringVar(
            value=f"Threshold: {configuration.threshold:.6f} | Quelle: {threshold_source}"
        )
        self.isolation_forest_score_text = tk.StringVar(value="–")
        self.isolation_forest_threshold_text = tk.StringVar(
            value=(
                f"Threshold: {isolation_forest_configuration.threshold:.6f} | Quelle: PROFILE / P99"
                if isolation_forest_configuration is not None
                else "Kein profilgebundenes Vergleichsbündel"
            )
        )
        self.rms_score_text = tk.StringVar(value="–")
        self.rms_threshold_text = tk.StringVar(
            value=(
                f"Threshold: {isolation_forest_configuration.rms_threshold:.6f} | Quelle: PROFILE / P99"
                if isolation_forest_configuration is not None
                else "Kein profilgebundenes Vergleichsbündel"
            )
        )
        self.sampling_text = tk.StringVar(value="– Hz")
        self.inference_text = tk.StringVar(value="AE – ms | IF – ms | RMS – ms")
        self.window_text = tk.StringVar(value="0")
        self.decision_text = tk.StringVar(value="–")
        self.latency_text = tk.StringVar(value="–")
        self.worker_status_text = tk.StringVar(value="Bereit")
        self.log_text = tk.StringVar(value="Noch kein Live-Log")
        self.anomaly_log_text = tk.StringVar(value="Noch kein Alarmprotokoll")
        self.anomaly_comparison_text = tk.StringVar(
            value="Noch keine Anomalie erkannt"
        )

        self.configure_window()
        self.build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self.close_application)
        self.root.after(QUEUE_POLL_INTERVAL_MS, self.process_queue)
        self.root.after(150, self.start_measurement)
        if self_test and self_test_duration is not None:
            self.root.after(
                max(1, int(self_test_duration * 1000)),
                self.close_application,
            )

    def configure_window(self) -> None:
        self.root.title("Edge AI – Autoencoder + Isolation Forest + RMS")
        self.root.geometry("1380x960")
        self.root.minsize(1050, 760)
        self.root.configure(background=BACKGROUND_COLOR)

    def build_layout(self) -> None:
        outer = tk.Frame(self.root, bg=BACKGROUND_COLOR, padx=18, pady=14)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BACKGROUND_COLOR)
        header.pack(fill="x")
        tk.Label(
            header,
            text="EDGE AI – LIVE ANOMALY DETECTION",
            font=("Helvetica", 21, "bold"),
            fg=TEXT_COLOR,
            bg=BACKGROUND_COLOR,
        ).pack(anchor="w")
        tk.Label(
            header,
            text=(
                f"Profil: {self.metadata.profile_name} "
                f"(Version {self.metadata.profile_version})"
            ),
            font=("Helvetica", 12),
            fg="#4c5967",
            bg=BACKGROUND_COLOR,
        ).pack(anchor="w", pady=(3, 12))

        status_area = tk.Frame(outer, bg=BACKGROUND_COLOR)
        status_area.pack(fill="x", pady=(0, 12))
        status_area.grid_columnconfigure(0, weight=1, uniform="status")
        status_area.grid_columnconfigure(1, weight=1, uniform="status")
        status_area.grid_columnconfigure(2, weight=1, uniform="status")
        autoencoder_status = tk.Frame(status_area, bg=BACKGROUND_COLOR)
        autoencoder_status.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        isolation_status = tk.Frame(status_area, bg=BACKGROUND_COLOR)
        isolation_status.grid(row=0, column=1, sticky="nsew", padx=5)
        rms_status = tk.Frame(status_area, bg=BACKGROUND_COLOR)
        rms_status.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        tk.Label(
            autoencoder_status, text="AUTOENCODER", font=("Helvetica", 11, "bold"),
            fg=TEXT_COLOR, bg=BACKGROUND_COLOR,
        ).pack(anchor="w")
        tk.Label(
            isolation_status, text="ISOLATION FOREST", font=("Helvetica", 11, "bold"),
            fg=TEXT_COLOR, bg=BACKGROUND_COLOR,
        ).pack(anchor="w")
        tk.Label(
            rms_status, text="KLASSISCHES RMS", font=("Helvetica", 11, "bold"),
            fg=TEXT_COLOR, bg=BACKGROUND_COLOR,
        ).pack(anchor="w")
        self.status_label = tk.Label(
            autoencoder_status,
            textvariable=self.status_text,
            font=("Helvetica", 22, "bold"),
            fg="white",
            bg=IDLE_COLOR,
            height=2,
        )
        self.status_label.pack(fill="x")
        self.isolation_forest_status_label = tk.Label(
            isolation_status,
            textvariable=self.isolation_forest_status_text,
            font=("Helvetica", 22, "bold"),
            fg="white",
            bg=IDLE_COLOR,
            height=2,
        )
        self.isolation_forest_status_label.pack(fill="x")
        self.rms_status_label = tk.Label(
            rms_status,
            textvariable=self.rms_status_text,
            font=("Helvetica", 22, "bold"),
            fg="white",
            bg=IDLE_COLOR,
            height=2,
        )
        self.rms_status_label.pack(fill="x")

        metrics = tk.Frame(outer, bg=BACKGROUND_COLOR)
        metrics.pack(fill="x", pady=(0, 10))
        self.build_metric_panel(
            metrics, "Autoencoder – Reconstruction Error (MSE)", self.mse_text, 0,
            detail_variable=self.threshold_source_text,
        )
        self.build_metric_panel(
            metrics,
            "Isolation Forest – Anomaly Score",
            self.isolation_forest_score_text,
            1,
            detail_variable=self.isolation_forest_threshold_text,
        )
        self.build_metric_panel(
            metrics,
            "Klassische Methode – RMS",
            self.rms_score_text,
            2,
            detail_variable=self.rms_threshold_text,
        )
        metrics.grid_columnconfigure(0, weight=1, uniform="metric")
        metrics.grid_columnconfigure(1, weight=1, uniform="metric")
        metrics.grid_columnconfigure(2, weight=1, uniform="metric")

        plot_blocks = tk.Frame(outer, bg=BACKGROUND_COLOR)
        plot_blocks.pack(fill="both", expand=True, pady=(0, 10))
        plot_blocks.grid_rowconfigure(0, weight=1)
        plot_blocks.grid_columnconfigure(0, weight=2, uniform="plot")
        plot_blocks.grid_columnconfigure(1, weight=1, uniform="plot")

        plot_panel = tk.Frame(plot_blocks, bg=PANEL_COLOR, bd=1, relief="solid")
        plot_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.figure = Figure(figsize=(8.2, 6.5), dpi=100, facecolor=PANEL_COLOR)
        self.axis = self.figure.add_subplot(311)
        self.axis.set_title("Autoencoder – Live Reconstruction Error")
        self.axis.set_ylabel("MSE")
        self.axis.grid(alpha=0.25)
        (self.error_line,) = self.axis.plot(
            [], [], color="#1565c0", linewidth=1.5, marker="o", markersize=2.8
        )
        self.threshold_line = self.axis.axhline(
            self.configuration.threshold,
            color=ANOMALY_COLOR,
            linestyle="--",
            linewidth=1.2,
            label=f"Threshold {self.configuration.threshold:.6f}",
        )
        self.axis.legend(loc="upper right")
        self.axis.set_xlim(0, PLOT_WINDOW_COUNT)
        self.axis.set_ylim(
            0,
            max(self.configuration.threshold * 1.35, 1e-6),
        )
        self.isolation_forest_axis = self.figure.add_subplot(312, sharex=self.axis)
        self.isolation_forest_axis.set_title("Isolation Forest – Live Anomaly Score")
        self.isolation_forest_axis.set_ylabel("IF Score")
        self.isolation_forest_axis.grid(alpha=0.25)
        (self.isolation_forest_line,) = self.isolation_forest_axis.plot(
            [], [], color="#7b1fa2", linewidth=1.5, marker="o", markersize=2.8
        )
        if_threshold = (
            self.isolation_forest_configuration.threshold
            if self.isolation_forest_configuration is not None else 0.0
        )
        self.isolation_forest_threshold_line = self.isolation_forest_axis.axhline(
            if_threshold,
            color=ANOMALY_COLOR,
            linestyle="--",
            linewidth=1.2,
            label=f"Threshold {if_threshold:.6f}",
        )
        self.isolation_forest_threshold_line.set_visible(
            self.isolation_forest_configuration is not None
        )
        self.isolation_forest_axis.set_xlim(0, PLOT_WINDOW_COUNT)
        self.isolation_forest_axis.set_ylim(0, max(if_threshold * 1.35, 1e-6))
        if self.isolation_forest_configuration is not None:
            self.isolation_forest_axis.legend(loc="upper right")
        self.rms_axis = self.figure.add_subplot(313, sharex=self.axis)
        self.rms_axis.set_title("Klassische Methode – Live RMS")
        self.rms_axis.set_xlabel("Window")
        self.rms_axis.set_ylabel("RMS")
        self.rms_axis.grid(alpha=0.25)
        (self.rms_line,) = self.rms_axis.plot(
            [], [], color="#ef6c00", linewidth=1.5, marker="o", markersize=2.8
        )
        rms_threshold = (
            self.isolation_forest_configuration.rms_threshold
            if self.isolation_forest_configuration is not None else 0.0
        )
        self.rms_threshold_line = self.rms_axis.axhline(
            rms_threshold,
            color=ANOMALY_COLOR,
            linestyle="--",
            linewidth=1.2,
            label=f"Threshold {rms_threshold:.6f}",
        )
        self.rms_threshold_line.set_visible(
            self.isolation_forest_configuration is not None
        )
        self.rms_axis.set_xlim(0, PLOT_WINDOW_COUNT)
        self.rms_axis.set_ylim(0, max(rms_threshold * 1.35, 1e-6))
        if self.isolation_forest_configuration is not None:
            self.rms_axis.legend(loc="upper right")
        self.figure.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_panel)
        self.canvas.mpl_connect("draw_event", self.record_gui_draw)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=6)

        detection_panel = tk.Frame(
            plot_blocks, bg=PANEL_COLOR, bd=1, relief="solid"
        )
        detection_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        tk.Label(
            detection_panel,
            text="ANOMALIE-ERKENNUNG IM VERGLEICH",
            font=("Helvetica", 12, "bold"),
            fg=TEXT_COLOR,
            bg=PANEL_COLOR,
        ).pack(anchor="w", padx=10, pady=(8, 0))
        tk.Label(
            detection_panel,
            text=(
                "Oben: Alarmzustand je Fenster (★ = erster Alarm) | "
                "unten: Platzierung je Ereignis"
            ),
            font=("Helvetica", 9),
            fg="#65717e",
            bg=PANEL_COLOR,
        ).pack(anchor="w", padx=10)
        tk.Label(
            detection_panel,
            textvariable=self.anomaly_comparison_text,
            font=("Helvetica", 9, "bold"),
            fg=TEXT_COLOR,
            bg=PANEL_COLOR,
            justify="left",
            wraplength=350,
        ).pack(anchor="w", fill="x", padx=10, pady=(5, 0))
        self.detection_figure = Figure(
            figsize=(4.0, 7.0), dpi=100, facecolor=PANEL_COLOR
        )
        self.detection_axes = [
            self.detection_figure.add_subplot(411),
            self.detection_figure.add_subplot(412),
            self.detection_figure.add_subplot(413),
        ]
        detection_specs = (
            ("Autoencoder", "#1565c0"),
            ("Isolation Forest", "#7b1fa2"),
            ("RMS", "#ef6c00"),
        )
        self.anomaly_state_lines = []
        self.fastest_alarm_lines = []
        for index, (axis, (title, color)) in enumerate(
            zip(self.detection_axes, detection_specs)
        ):
            axis.set_title(title, fontsize=9)
            axis.set_yticks((0, 1), labels=("NORMAL", "ANOMALY"), fontsize=7)
            axis.set_ylim(-0.15, 1.2)
            axis.set_xlim(0, PLOT_WINDOW_COUNT)
            axis.grid(alpha=0.25)
            (state_line,) = axis.plot(
                [], [], color=color, linewidth=1.5, marker="o", markersize=2.5,
                drawstyle="steps-post",
            )
            (fastest_line,) = axis.plot(
                [], [], linestyle="none", marker="*", markersize=11,
                color=ANOMALY_COLOR, markeredgecolor="#7f0000",
            )
            self.anomaly_state_lines.append(state_line)
            self.fastest_alarm_lines.append(fastest_line)
            if index < 2:
                axis.tick_params(labelbottom=False)
        self.detection_axes[-1].set_xlabel("Window")
        self.ranking_axis = self.detection_figure.add_subplot(414)
        self.ranking_axis.set_title(
            "Erkennungsreihenfolge pro Ereignis", fontsize=9
        )
        self.ranking_axis.set_xlabel("Ereignisnummer")
        self.ranking_axis.set_yticks(
            (1, 2, 3, 4),
            labels=("1. zuerst", "2.", "3.", "nicht erkannt"),
            fontsize=7,
        )
        self.ranking_axis.set_ylim(4.5, 0.5)
        self.ranking_axis.set_xlim(0.5, RANKING_EVENT_COUNT + 0.5)
        self.ranking_axis.grid(alpha=0.25)
        ranking_specs = (
            ("autoencoder", "#1565c0", "o", -0.18),
            ("isolation_forest", "#7b1fa2", "s", 0.0),
            ("rms", "#ef6c00", "^", 0.18),
        )
        self.ranking_lines: dict[str, Any] = {}
        self.ranking_x_offsets: dict[str, float] = {}
        for method, color, marker, x_offset in ranking_specs:
            (ranking_line,) = self.ranking_axis.plot(
                [], [], linestyle="none", marker=marker, markersize=6,
                color=color, label=ANOMALY_METHOD_LABELS[method],
            )
            self.ranking_lines[method] = ranking_line
            self.ranking_x_offsets[method] = x_offset
        self.ranking_axis.legend(loc="upper right", fontsize=7)
        self.detection_figure.tight_layout()
        self.detection_canvas = FigureCanvasTkAgg(
            self.detection_figure, master=detection_panel
        )
        self.detection_canvas.draw()
        self.detection_canvas.get_tk_widget().pack(
            fill="both", expand=True, padx=8, pady=6
        )

        footer = tk.Frame(outer, bg=PANEL_COLOR, bd=1, relief="solid")
        footer.pack(fill="x")
        info = tk.Frame(footer, bg=PANEL_COLOR, padx=12, pady=9)
        info.pack(side="left", fill="both", expand=True)
        self.build_info_row(info, "Sampling:", self.sampling_text, 0)
        self.build_info_row(info, "Inference:", self.inference_text, 1)
        self.build_info_row(info, "Window:", self.window_text, 2)
        self.build_info_row(info, "Worker:", self.worker_status_text, 3)
        self.build_info_row(info, "Log:", self.log_text, 4)
        self.build_info_row(info, "Alarmprotokoll:", self.anomaly_log_text, 5)
        self.build_info_row(info, "Entscheidung:", self.decision_text, 6)
        self.build_info_row(info, "Latenz/Puffer:", self.latency_text, 7)

        controls = tk.Frame(footer, bg=PANEL_COLOR, padx=12, pady=9)
        controls.pack(side="right", fill="y")
        self.start_button = ttk.Button(
            controls, text="Start", command=self.start_measurement
        )
        self.start_button.pack(fill="x", pady=(0, 5))
        self.stop_button = ttk.Button(
            controls, text="Stop", command=self.stop_measurement
        )
        self.stop_button.pack(fill="x", pady=(0, 5))
        ttk.Button(
            controls, text="Exit", command=self.close_application
        ).pack(fill="x")

    def build_metric_panel(
        self,
        parent: tk.Widget,
        title: str,
        variable: tk.StringVar,
        column: int,
        detail_variable: tk.StringVar | None = None,
    ) -> None:
        panel = tk.Frame(parent, bg=PANEL_COLOR, bd=1, relief="solid", padx=14, pady=8)
        panel.grid(row=0, column=column, sticky="nsew", padx=(0, 5) if column == 0 else (5, 0))
        tk.Label(
            panel,
            text=title,
            font=("Helvetica", 11),
            fg="#65717e",
            bg=PANEL_COLOR,
        ).pack(anchor="w")
        tk.Label(
            panel,
            textvariable=variable,
            font=("Helvetica", 22, "bold"),
            fg=TEXT_COLOR,
            bg=PANEL_COLOR,
        ).pack(anchor="w")
        if detail_variable is not None:
            tk.Label(
                panel,
                textvariable=detail_variable,
                font=("Helvetica", 10),
                fg="#65717e",
                bg=PANEL_COLOR,
            ).pack(anchor="w")

    def build_info_row(
        self,
        parent: tk.Widget,
        label: str,
        variable: tk.StringVar,
        row: int,
    ) -> None:
        tk.Label(
            parent,
            text=label,
            font=("Helvetica", 10, "bold"),
            fg=TEXT_COLOR,
            bg=PANEL_COLOR,
        ).grid(row=row, column=0, sticky="w", padx=(0, 8))
        tk.Label(
            parent,
            textvariable=variable,
            font=("Helvetica", 10),
            fg="#4c5967",
            bg=PANEL_COLOR,
            anchor="w",
        ).grid(row=row, column=1, sticky="w")

    def reset_display(self) -> None:
        self.last_decision_ns = None
        self.last_window_complete_ns = None
        self.close_gui_metrics()
        self.decision_text.set("–")
        self.latency_text.set("–")
        self.window_indices.clear()
        self.reconstruction_errors.clear()
        self.isolation_forest_scores.clear()
        self.rms_scores.clear()
        self.autoencoder_anomaly_states.clear()
        self.isolation_forest_anomaly_states.clear()
        self.rms_anomaly_states.clear()
        for windows in self.fastest_alarm_windows.values():
            windows.clear()
        for rankings in self.detection_rankings.values():
            rankings.clear()
        compared_methods = (
            ("autoencoder", "isolation_forest", "rms")
            if self.isolation_forest_configuration is not None else ("autoencoder",)
        )
        self.anomaly_event_tracker = AnomalyEventTracker(compared_methods)
        self.latest_event_detections.clear()
        self.anomaly_comparison_text.set("Noch keine Anomalie erkannt")
        self.normal_seen = False
        self.anomaly_seen = False
        self.status_text.set("STARTING")
        self.status_label.configure(bg=IDLE_COLOR)
        self.isolation_forest_status_text.set(
            "STARTING" if self.isolation_forest_configuration is not None else "NICHT KONFIGURIERT"
        )
        self.isolation_forest_status_label.configure(bg=IDLE_COLOR)
        self.rms_status_text.set(
            "STARTING" if self.isolation_forest_configuration is not None else "NICHT KONFIGURIERT"
        )
        self.rms_status_label.configure(bg=IDLE_COLOR)
        self.mse_text.set("–")
        self.isolation_forest_score_text.set("–")
        self.rms_score_text.set("–")
        self.sampling_text.set("– Hz")
        self.inference_text.set("AE – ms | IF – ms | RMS – ms")
        self.window_text.set("0")
        self.error_line.set_data([], [])
        self.isolation_forest_line.set_data([], [])
        self.rms_line.set_data([], [])
        for state_line, fastest_line in zip(
            self.anomaly_state_lines, self.fastest_alarm_lines
        ):
            state_line.set_data([], [])
            fastest_line.set_data([], [])
        for ranking_line in self.ranking_lines.values():
            ranking_line.set_data([], [])
        self.axis.set_xlim(0, PLOT_WINDOW_COUNT)
        self.axis.set_ylim(0, max(self.configuration.threshold * 1.35, 1e-6))
        self.isolation_forest_axis.set_xlim(0, PLOT_WINDOW_COUNT)
        if_threshold = (
            self.isolation_forest_configuration.threshold
            if self.isolation_forest_configuration is not None else 0.0
        )
        self.isolation_forest_axis.set_ylim(0, max(if_threshold * 1.35, 1e-6))
        self.rms_axis.set_xlim(0, PLOT_WINDOW_COUNT)
        rms_threshold = (
            self.isolation_forest_configuration.rms_threshold
            if self.isolation_forest_configuration is not None else 0.0
        )
        self.rms_axis.set_ylim(0, max(rms_threshold * 1.35, 1e-6))
        for detection_axis in self.detection_axes:
            detection_axis.set_xlim(0, PLOT_WINDOW_COUNT)
        self.ranking_axis.set_xlim(0.5, RANKING_EVENT_COUNT + 0.5)
        self.canvas.draw_idle()
        self.detection_canvas.draw_idle()

    def start_measurement(self) -> None:
        if self.closing or (self.worker is not None and self.worker.is_alive()):
            return
        self.reset_display()
        self.stop_event = threading.Event()
        self.log_path = None
        self.anomaly_log_path = None
        self.log_text.set("Self-Test – kein Log" if self.self_test else "Wird angelegt …")
        self.anomaly_log_text.set(
            "Self-Test – kein Log" if self.self_test else "Wird angelegt …"
        )
        self.worker = AcquisitionWorker(
            configuration=self.configuration,
            metadata=self.metadata,
            output_queue=self.message_queue,
            stop_event=self.stop_event,
            self_test=self.self_test,
            isolation_forest_configuration=self.isolation_forest_configuration,
            acquisition_configuration=self.acquisition_configuration,
            simulation_interval_seconds=(
                0.01
                if self.self_test and self.self_test_duration is not None
                else SIMULATION_INTERVAL_SECONDS
            ),
        )
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.worker.start()

    def stop_measurement(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            self.worker_status_text.set("Stop wird angefordert …")
            self.stop_event.set()

    def handle_control_message(self, message: WorkerMessage) -> None:
        if message.kind == "status":
            self.worker_status_text.set(str(message.payload))
        elif message.kind == "log_path":
            self.log_path = Path(message.payload)
            self.anomaly_log_path = self.log_path.with_suffix(".anomalies.csv")
            self.log_text.set(str(self.log_path.relative_to(PROJECT_ROOT)))
            self.anomaly_log_text.set(
                str(self.anomaly_log_path.relative_to(PROJECT_ROOT))
            )
            gui_path = self.log_path.with_suffix(".gui.csv")
            self.gui_metrics_handle = gui_path.open("x", encoding="utf-8", newline="", buffering=1)
            self.gui_metrics_writer = csv.DictWriter(self.gui_metrics_handle, fieldnames=[
                "window_index", "window_complete_monotonic_ns", "decision_monotonic_ns",
                "draw_completed_monotonic_ns", "decision_to_gui_draw_ms", "window_to_gui_draw_ms",
                "gui_messages_dropped"])
            self.gui_metrics_writer.writeheader()
        elif message.kind == "error":
            self.show_worker_error(message.payload)
        elif message.kind == "finished":
            self.worker_finished()

    def process_queue(self) -> None:
        controls = self.worker.take_control_messages() if self.worker is not None else []
        # Logdatei muss vor den Messwerten geöffnet sein; Fehler/Ende danach,
        # damit nachträglich gelieferte Messwerte keinen Fehlerzustand überdecken.
        for message in controls:
            if message.kind not in ("error", "finished"):
                self.handle_control_message(message)
        measurements_updated = False
        try:
            while True:
                message = self.message_queue.get_nowait()
                if message.kind == "measurement":
                    self.update_measurement(message.payload, redraw=False)
                    measurements_updated = True
        except queue.Empty:
            pass
        if measurements_updated:
            self.update_plot()
        for message in controls:
            if message.kind in ("error", "finished"):
                self.handle_control_message(message)

        limit_seconds = max(1.0, 3 * 128 / self.acquisition_configuration.get("sensor_odr", 200))
        if (not self.closing and self.worker is not None and self.worker.is_alive()
                and self.last_decision_ns is not None
                and self.status_text.get() not in ("ERROR", "STOPPED")
                and (is_stale(self.last_window_complete_ns, limit_seconds=limit_seconds)
                     or is_stale(self.last_decision_ns, limit_seconds=limit_seconds))):
            self.status_text.set("STALE / VERALTET")
            self.status_label.configure(bg=IDLE_COLOR)
            if getattr(self, "isolation_forest_configuration", None) is not None:
                self.isolation_forest_status_text.set("STALE / VERALTET")
                self.isolation_forest_status_label.configure(bg=IDLE_COLOR)
                self.rms_status_text.set("STALE / VERALTET")
                self.rms_status_label.configure(bg=IDLE_COLOR)
        if not self.closing:
            self.root.after(QUEUE_POLL_INTERVAL_MS, self.process_queue)

    def update_measurement(
        self, measurement: Measurement, *, redraw: bool = True
    ) -> None:
        self.last_decision_ns = measurement.decision_monotonic_ns
        self.last_window_complete_ns = measurement.window_complete_monotonic_ns
        self.decision_text.set(measurement.timestamp)
        details = measurement.details
        self.latency_text.set(f"{details.get('decision_latency_ms', 0):.3f} ms | "
                              f"Queue {details.get('queue_pending_windows', 0)} | "
                              f"verworfen {details.get('windows_dropped', 0)}")
        status = measurement_display_status(measurement, limit_seconds=max(
            1.0, 3 * 128 / self.acquisition_configuration.get("sensor_odr", 200)))
        if status == "ERROR":
            self.status_text.set("ERROR")
            self.status_label.configure(bg=ANOMALY_COLOR)
            self.worker_status_text.set(details.get("error", "Ungültige Entscheidung"))
        elif status == "STALE / VERALTET":
            self.status_text.set(status)
            self.status_label.configure(bg=IDLE_COLOR)
        elif measurement.predicted_label:
            self.status_text.set("ANOMALY")
            self.status_label.configure(bg=ANOMALY_COLOR)
            self.anomaly_seen = True
        else:
            self.status_text.set("NORMAL")
            self.status_label.configure(bg=NORMAL_COLOR)
            self.normal_seen = True

        if getattr(self, "isolation_forest_configuration", None) is not None:
            if_status = isolation_forest_display_status(
                measurement,
                limit_seconds=max(
                    1.0, 3 * 128 / self.acquisition_configuration.get("sensor_odr", 200)
                ),
            )
            self.isolation_forest_status_text.set(if_status)
            if if_status == "NORMAL":
                self.isolation_forest_status_label.configure(bg=NORMAL_COLOR)
            elif if_status == "ANOMALY":
                self.isolation_forest_status_label.configure(bg=ANOMALY_COLOR)
            elif if_status == "ERROR":
                self.isolation_forest_status_label.configure(bg=ANOMALY_COLOR)
                self.worker_status_text.set(
                    details.get("error", "Ungültige Isolation-Forest-Entscheidung")
                )
            else:
                self.isolation_forest_status_label.configure(bg=IDLE_COLOR)

            rms_status = rms_display_status(
                measurement,
                limit_seconds=max(
                    1.0, 3 * 128 / self.acquisition_configuration.get("sensor_odr", 200)
                ),
            )
            self.rms_status_text.set(rms_status)
            if rms_status == "NORMAL":
                self.rms_status_label.configure(bg=NORMAL_COLOR)
            elif rms_status == "ANOMALY":
                self.rms_status_label.configure(bg=ANOMALY_COLOR)
            elif rms_status == "ERROR":
                self.rms_status_label.configure(bg=ANOMALY_COLOR)
                self.worker_status_text.set(
                    details.get("error", "Ungültige RMS-Entscheidung")
                )
            else:
                self.rms_status_label.configure(bg=IDLE_COLOR)

        self.mse_text.set(f"{measurement.reconstruction_error:.6f}")
        self.threshold_text.set(f"{measurement.threshold:.6f}")
        if measurement.isolation_forest_score is not None:
            self.isolation_forest_score_text.set(
                f"{measurement.isolation_forest_score:.6f}"
            )
        if measurement.rms_score is not None:
            self.rms_score_text.set(f"{measurement.rms_score:.6f}")
        self.sampling_text.set(
            f"{measurement.measured_sampling_rate_hz:.1f} Hz"
        )
        if_time = measurement.isolation_forest_inference_time_ms
        rms_time = measurement.rms_inference_time_ms
        if_text = f"{if_time:.3f}" if if_time is not None else "–"
        rms_text = f"{rms_time:.3f}" if rms_time is not None else "–"
        self.inference_text.set(
            f"AE {measurement.inference_time_ms:.3f} ms | "
            f"IF {if_text} ms | RMS {rms_text} ms"
        )
        self.window_text.set(str(measurement.window_index))
        self.window_indices.append(measurement.window_index)
        self.reconstruction_errors.append(measurement.reconstruction_error if math.isfinite(measurement.reconstruction_error) else float("nan"))
        if measurement.isolation_forest_score is not None:
            self.isolation_forest_scores.append(
                measurement.isolation_forest_score
                if math.isfinite(measurement.isolation_forest_score)
                else float("nan")
            )
        if measurement.rms_score is not None:
            self.rms_scores.append(
                measurement.rms_score
                if math.isfinite(measurement.rms_score)
                else float("nan")
            )
        self.autoencoder_anomaly_states.append(
            float(measurement.predicted_label)
            if measurement.predicted_label in (0, 1) else float("nan")
        )
        self.isolation_forest_anomaly_states.append(
            float(measurement.isolation_forest_predicted_label)
            if measurement.isolation_forest_predicted_label in (0, 1)
            else float("nan")
        )
        self.rms_anomaly_states.append(
            float(measurement.rms_predicted_label)
            if measurement.rms_predicted_label in (0, 1) else float("nan")
        )
        event_rows = self.anomaly_event_tracker.update(
            timestamp=measurement.timestamp,
            window_index=measurement.window_index,
            decision_monotonic_ns=measurement.decision_monotonic_ns,
            labels={
                "autoencoder": measurement.predicted_label,
                "isolation_forest": measurement.isolation_forest_predicted_label,
                "rms": measurement.rms_predicted_label,
            },
        )
        if event_rows:
            self.update_anomaly_comparison(event_rows)
        if redraw:
            self.update_plot()

    def update_anomaly_comparison(
        self, event_rows: list[dict[str, Any]]
    ) -> None:
        newest_event_id = int(event_rows[-1]["event_id"])
        current_event_id = (
            int(next(iter(self.latest_event_detections.values()))["event_id"])
            if self.latest_event_detections else None
        )
        if newest_event_id != current_event_id:
            self.latest_event_detections.clear()
        for row in event_rows:
            method = str(row["method"])
            self.latest_event_detections[method] = row
            ranking_value = (
                float(row["detection_rank"])
                if row["result"] == "DETECTED" else 4.0
            )
            self.detection_rankings[method].append(
                (int(row["event_id"]), ranking_value)
            )
            if row["result"] == "DETECTED" and int(row["is_fastest"]) == 1:
                self.fastest_alarm_windows[method].append(
                    int(row["detection_window"])
                )

        first_row = next(iter(self.latest_event_detections.values()))
        first_methods = [
            ANOMALY_METHOD_LABELS[method]
            for method in str(first_row["first_methods"]).split("+")
            if method
        ]
        parts = [
            f"Ereignis {newest_event_id}: zuerst "
            f"{', '.join(first_methods)} in Fenster {first_row['first_alarm_window']}"
        ]
        for method in self.anomaly_event_tracker.methods:
            row = self.latest_event_detections.get(method)
            label = ANOMALY_METHOD_LABELS[method]
            if row is None:
                parts.append(f"{label}: wartet")
            elif row["result"] == "NOT_DETECTED":
                parts.append(f"{label}: nicht erkannt")
            elif int(row["delay_windows_from_first"]) == 0:
                parts.append(f"{label}: Platz 1")
            else:
                parts.append(
                    f"{label}: Platz {int(row['detection_rank'])}, "
                    f"+{int(row['delay_windows_from_first'])} Fenster "
                    f"/ +{float(row['delay_ms_from_first']):.0f} ms"
                )
        self.anomaly_comparison_text.set(" | ".join(parts))

    def update_plot(self) -> None:
        x_values = list(self.window_indices)
        y_values = list(self.reconstruction_errors)
        if_values = list(self.isolation_forest_scores)
        rms_values = list(self.rms_scores)
        anomaly_states = (
            list(self.autoencoder_anomaly_states),
            list(self.isolation_forest_anomaly_states),
            list(self.rms_anomaly_states),
        )
        self.error_line.set_data(x_values, y_values)
        self.isolation_forest_line.set_data(
            x_values[-len(if_values):] if if_values else [], if_values
        )
        self.rms_line.set_data(
            x_values[-len(rms_values):] if rms_values else [], rms_values
        )
        for method, state_line, fastest_line, states in zip(
            ANOMALY_METHOD_LABELS,
            self.anomaly_state_lines,
            self.fastest_alarm_lines,
            anomaly_states,
        ):
            state_x = x_values[-len(states):] if states else []
            state_line.set_data(state_x, states)
            fastest_windows = list(self.fastest_alarm_windows[method])
            fastest_line.set_data(fastest_windows, [1.0] * len(fastest_windows))
        ranked_event_ids: list[int] = []
        for method, ranking_line in self.ranking_lines.items():
            rankings = list(self.detection_rankings[method])
            event_ids = [event_id for event_id, _ in rankings]
            ranks = [rank for _, rank in rankings]
            ranked_event_ids.extend(event_ids)
            x_offset = self.ranking_x_offsets[method]
            ranking_line.set_data(
                [event_id + x_offset for event_id in event_ids], ranks
            )
        if ranked_event_ids:
            ranking_right = max(3.5, max(ranked_event_ids) + 0.5)
            ranking_left = max(0.5, ranking_right - RANKING_EVENT_COUNT)
            self.ranking_axis.set_xlim(ranking_left, ranking_right)
        if x_values:
            left = max(0, x_values[-1] - PLOT_WINDOW_COUNT + 1)
            right = max(left + 1, x_values[-1])
            self.axis.set_xlim(left, right)
            self.isolation_forest_axis.set_xlim(left, right)
            self.rms_axis.set_xlim(left, right)
            for detection_axis in self.detection_axes:
                detection_axis.set_xlim(left, right)
        maximum_error = max((value for value in y_values if math.isfinite(value)), default=0.0)
        upper_limit = max(
            maximum_error * 1.18,
            self.configuration.threshold * 1.35,
            1e-6,
        )
        self.axis.set_ylim(0, upper_limit)
        if_threshold = (
            self.isolation_forest_configuration.threshold
            if self.isolation_forest_configuration is not None else 0.0
        )
        maximum_if_score = max(
            (value for value in if_values if math.isfinite(value)), default=0.0
        )
        self.isolation_forest_axis.set_ylim(
            0, max(maximum_if_score * 1.18, if_threshold * 1.35, 1e-6)
        )
        rms_threshold = (
            self.isolation_forest_configuration.rms_threshold
            if self.isolation_forest_configuration is not None else 0.0
        )
        maximum_rms_score = max(
            (value for value in rms_values if math.isfinite(value)), default=0.0
        )
        self.rms_axis.set_ylim(
            0, max(maximum_rms_score * 1.18, rms_threshold * 1.35, 1e-6)
        )
        self.canvas.draw_idle()
        self.detection_canvas.draw_idle()

    def show_worker_error(self, payload: dict[str, str]) -> None:
        self.status_text.set("ERROR")
        self.status_label.configure(bg=ANOMALY_COLOR)
        if getattr(self, "isolation_forest_configuration", None) is not None:
            self.isolation_forest_status_text.set("ERROR")
            self.isolation_forest_status_label.configure(bg=ANOMALY_COLOR)
            self.rms_status_text.set("ERROR")
            self.rms_status_label.configure(bg=ANOMALY_COLOR)
        self.worker_status_text.set(payload["message"])
        print(payload["traceback"], file=sys.stderr, flush=True)

    def worker_finished(self) -> None:
        if not self.closing:
            if self.status_text.get() != "ERROR":
                self.status_text.set("STOPPED")
                self.status_label.configure(bg=IDLE_COLOR)
            if getattr(self, "isolation_forest_configuration", None) is not None:
                if self.isolation_forest_status_text.get() != "ERROR":
                    self.isolation_forest_status_text.set("STOPPED")
                    self.isolation_forest_status_label.configure(bg=IDLE_COLOR)
                if self.rms_status_text.get() != "ERROR":
                    self.rms_status_text.set("STOPPED")
                    self.rms_status_label.configure(bg=IDLE_COLOR)
            self.worker_status_text.set("Gestoppt")
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.close_gui_metrics()

    def close_application(self) -> None:
        if self.closing:
            return
        self.closing = True
        self.stop_event.set()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")
        self.worker_status_text.set("GUI wird geschlossen …")
        self.wait_for_worker_and_close()

    def wait_for_worker_and_close(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            self.root.after(50, self.wait_for_worker_and_close)
            return
        self.close_gui_metrics()
        self.root.destroy()

    def record_gui_draw(self, event: Any) -> None:
        if (self.gui_metrics_writer is None or self.last_decision_ns is None
                or self.last_decision_ns == self.last_draw_logged_ns):
            return
        draw_ns = time.monotonic_ns()
        self.gui_metrics_writer.writerow({
            "window_index": self.window_text.get(), "decision_monotonic_ns": self.last_decision_ns,
            "window_complete_monotonic_ns": self.last_window_complete_ns,
            "draw_completed_monotonic_ns": draw_ns,
            "decision_to_gui_draw_ms": (draw_ns - self.last_decision_ns) / 1e6,
            "window_to_gui_draw_ms": (draw_ns - self.last_window_complete_ns) / 1e6 if self.last_window_complete_ns is not None else None,
            "gui_messages_dropped": self.worker.gui_messages_dropped if self.worker else 0})
        self.gui_metrics_handle.flush()
        self.last_draw_logged_ns = self.last_decision_ns

    def close_gui_metrics(self) -> None:
        if self.gui_metrics_handle is not None:
            self.gui_metrics_handle.flush()
            os.fsync(self.gui_metrics_handle.fileno())
            self.gui_metrics_handle.close()
        self.gui_metrics_handle = None
        self.gui_metrics_writer = None

    def validate_automated_self_test(self) -> None:
        if not self.normal_seen or not self.anomaly_seen:
            raise AssertionError(
                "Self-Test hat NORMAL und ANOMALY nicht beide dargestellt."
            )
        if len(self.window_indices) != PLOT_WINDOW_COUNT:
            raise AssertionError(
                "Automatisierter Self-Test hat die 100-Punkte-Plot-Historie "
                f"nicht vollständig geprüft: {len(self.window_indices)} Punkte."
            )
        if self.window_indices[-1] < PLOT_WINDOW_COUNT:
            raise AssertionError("Self-Test erzeugte nicht mindestens 100 Fenster.")
        if not all(
            len(values) == PLOT_WINDOW_COUNT
            for values in (
                self.autoencoder_anomaly_states,
                self.isolation_forest_anomaly_states,
                self.rms_anomaly_states,
            )
        ):
            raise AssertionError(
                "Self-Test hat den Anomalie-Zeitvergleich nicht vollständig gefüllt."
            )
        if not all(self.fastest_alarm_windows.values()):
            raise AssertionError(
                "Self-Test hat nicht jede Methode als ersten Alarm markiert."
            )
        if not all(self.detection_rankings.values()):
            raise AssertionError(
                "Self-Test hat den nummerierten Erkennungsgraphen nicht gefüllt."
            )
        observed_ranks = {
            int(rank)
            for rankings in self.detection_rankings.values()
            for _, rank in rankings
        }
        if not {1, 2, 3}.issubset(observed_ranks):
            raise AssertionError(
                "Self-Test hat die Plätze 1, 2 und 3 nicht dargestellt."
            )
        if "zuerst" not in self.anomaly_comparison_text.get():
            raise AssertionError("Anomalievergleich zeigt keine schnellste Methode.")
        threshold_y = float(self.threshold_line.get_ydata()[0])
        if threshold_y != self.configuration.threshold:
            raise AssertionError("Threshold-Linie stimmt nicht mit dem Profil überein.")
        if self.isolation_forest_configuration is not None:
            if_threshold_y = float(self.isolation_forest_threshold_line.get_ydata()[0])
            if if_threshold_y != self.isolation_forest_configuration.threshold:
                raise AssertionError(
                    "Isolation-Forest-Threshold-Linie stimmt nicht mit dem Bündel überein."
                )
            rms_threshold_y = float(self.rms_threshold_line.get_ydata()[0])
            if rms_threshold_y != self.isolation_forest_configuration.rms_threshold:
                raise AssertionError(
                    "RMS-Threshold-Linie stimmt nicht mit dem Bündel überein."
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Tkinter-/Matplotlib-Anzeige für parallele profilabhängige "
            "Autoencoder-, Isolation-Forest- und RMS-Live-Anomalieerkennung."
        )
    )
    parser.add_argument(
        "--profile",
        required=True,
        help="Freigegebenes Setup-Profil, z.B. home_v001.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help=(
            "Temporärer Threshold für diese GUI-Laufzeit; ohne Angabe wird "
            "der validierte P99-Threshold aus dem Profil verwendet."
        ),
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="GUI mit simulierten NORMAL-/ANOMALY-Werten ohne Sensor und Log testen.",
    )
    parser.add_argument(
        "--self-test-duration",
        type=float,
        default=None,
        help=(
            "Self-Test nach dieser Zeit automatisch schließen; für automatisierte "
            "GUI-Prüfungen."
        ),
    )
    add_acquisition_arguments(parser)
    arguments = parser.parse_args()
    if arguments.threshold is not None and (
        not math.isfinite(arguments.threshold) or arguments.threshold < 0
    ):
        parser.error("--threshold muss eine endliche, nichtnegative Zahl sein.")
    if arguments.self_test_duration is not None:
        if not arguments.self_test:
            parser.error("--self-test-duration ist nur mit --self-test zulässig.")
        if arguments.self_test_duration <= 0:
            parser.error("--self-test-duration muss positiv sein.")
    return arguments


def main() -> None:
    # Select the interactive backend only when actually starting this GUI.
    import matplotlib
    matplotlib.use("TkAgg")

    arguments = parse_args()
    configuration = resolve_live_configuration(arguments.profile)
    metadata = read_profile_display_metadata(configuration)
    isolation_forest_configuration = resolve_isolation_forest_configuration(
        configuration
    )
    threshold_source = "PROFILE / P99"
    if arguments.threshold is not None:
        configuration = replace(configuration, threshold=arguments.threshold, threshold_source="MANUAL")
        threshold_source = "MANUAL"
    if not arguments.self_test:
        validate_acquisition_options(configuration, **acquisition_options(arguments))
    root = tk.Tk()
    application = LiveTFLiteApplication(
        root,
        configuration,
        metadata,
        threshold_source=threshold_source,
        self_test=arguments.self_test,
        self_test_duration=arguments.self_test_duration,
        isolation_forest_configuration=isolation_forest_configuration,
        acquisition_configuration=acquisition_options(arguments),
    )
    previous = {signum: signal.signal(signum, lambda signum, frame: application.close_application())
                for signum in (signal.SIGINT, signal.SIGTERM)}
    try:
        root.mainloop()
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    if arguments.self_test and arguments.self_test_duration is not None:
        application.validate_automated_self_test()
        print(
            "Automatisierter GUI-Self-Test erfolgreich: Autoencoder und "
            "Isolation Forest sowie RMS, NORMAL, ANOMALY, Threshold-Linien, Plot-Limit, "
            "Anomalie-Zeitvergleich, nummerierten Erkennungsgraphen und sauberes "
            "Schließen geprüft."
        )


if __name__ == "__main__":
    main()
