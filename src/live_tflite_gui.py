#!/usr/bin/env python3
"""Simple Tkinter GUI for the existing profile-aware TFLite monitor.

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
    warm_up,
    iter_live_measurements, add_acquisition_arguments, acquisition_options,
    validate_acquisition_options,
)


from live_pipeline import decision_status, is_stale

PLOT_WINDOW_COUNT = 100
QUEUE_POLL_INTERVAL_MS = 50
SIMULATION_INTERVAL_SECONDS = 0.35
NORMAL_COLOR = "#18864b"
ANOMALY_COLOR = "#c62828"
IDLE_COLOR = "#59636e"
BACKGROUND_COLOR = "#f4f6f8"
PANEL_COLOR = "#ffffff"
TEXT_COLOR = "#18212b"


@dataclass(frozen=True)
class ProfileDisplayMetadata:
    profile_name: str
    profile_version: int
    sampling_rate_hz: int
    results_directory: Path


@dataclass(frozen=True)
class Measurement:
    timestamp: str
    window_index: int
    reconstruction_error: float
    threshold: float
    predicted_label: int
    inference_time_ms: float
    measured_sampling_rate_hz: float
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
        simulation_interval_seconds: float = SIMULATION_INTERVAL_SECONDS,
        acquisition_configuration: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(name="sensor-tflite-worker", daemon=False)
        self.configuration = configuration
        self.metadata = metadata
        self.output_queue = output_queue
        self.stop_event = stop_event
        self.self_test = self_test
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
        factors = (0.55, 0.72, 1.22, 0.64, 1.48)
        window_index = 0
        while not self.stop_event.is_set():
            factor = factors[window_index % len(factors)]
            window_index += 1
            error = self.configuration.threshold * factor
            prediction = int(error > self.configuration.threshold)
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
        if self.stop_event.is_set():
            return

        log_path = allocate_gui_log_path(PROJECT_ROOT / "results" / "live_runs")
        self.emit("log_path", log_path)
        self.emit("status", "Live-Messung aktiv; Rohdaten und Puffer werden protokolliert")
        with closing(iter_live_measurements(
                runtime, scaler, self.configuration, log_path, stop_event=self.stop_event,
                gui_enabled=True, **self.acquisition_configuration)) as measurements:
            for row in measurements:
                self.emit("measurement", Measurement(
                    timestamp=row["timestamp"], window_index=row["window_index"],
                    reconstruction_error=row["reconstruction_error"], threshold=row["threshold"],
                    predicted_label=row["predicted_label"], inference_time_ms=row["inference_time_ms"],
                    measured_sampling_rate_hz=row["measured_sampling_rate_hz"],
                    decision_monotonic_ns=row["decision_monotonic_ns"],
                    window_complete_monotonic_ns=row["window_complete_monotonic_ns"], details=row))


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
        acquisition_configuration: dict[str, Any] | None = None,
    ) -> None:
        self.root = root
        self.configuration = configuration
        self.metadata = metadata
        self.threshold_source = threshold_source
        self.self_test = self_test
        self.self_test_duration = self_test_duration
        self.acquisition_configuration = acquisition_configuration or {}
        self.last_decision_ns: int | None = None
        self.last_window_complete_ns: int | None = None
        self.gui_metrics_handle = None
        self.gui_metrics_writer = None
        self.last_draw_logged_ns = 0
        self.message_queue: queue.Queue[WorkerMessage] = queue.Queue(maxsize=8)
        self.stop_event = threading.Event()
        self.worker: AcquisitionWorker | None = None
        self.closing = False
        self.log_path: Path | None = None
        self.normal_seen = False
        self.anomaly_seen = False
        self.window_indices: deque[int] = deque(maxlen=PLOT_WINDOW_COUNT)
        self.reconstruction_errors: deque[float] = deque(
            maxlen=PLOT_WINDOW_COUNT
        )

        self.status_text = tk.StringVar(value="BEREIT")
        self.mse_text = tk.StringVar(value="–")
        self.threshold_text = tk.StringVar(
            value=f"{configuration.threshold:.6f}"
        )
        self.threshold_source_text = tk.StringVar(
            value=f"Quelle: {threshold_source}"
        )
        self.sampling_text = tk.StringVar(value="– Hz")
        self.inference_text = tk.StringVar(value="– ms")
        self.window_text = tk.StringVar(value="0")
        self.decision_text = tk.StringVar(value="–")
        self.latency_text = tk.StringVar(value="–")
        self.worker_status_text = tk.StringVar(value="Bereit")
        self.log_text = tk.StringVar(value="Noch kein Live-Log")

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
        self.root.title("Edge AI – Anomaly Detection")
        self.root.geometry("920x760")
        self.root.minsize(760, 650)
        self.root.configure(background=BACKGROUND_COLOR)

    def build_layout(self) -> None:
        outer = tk.Frame(self.root, bg=BACKGROUND_COLOR, padx=18, pady=14)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BACKGROUND_COLOR)
        header.pack(fill="x")
        tk.Label(
            header,
            text="EDGE AI – ANOMALY DETECTION",
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

        self.status_label = tk.Label(
            outer,
            textvariable=self.status_text,
            font=("Helvetica", 38, "bold"),
            fg="white",
            bg=IDLE_COLOR,
            height=2,
        )
        self.status_label.pack(fill="x", pady=(0, 12))

        metrics = tk.Frame(outer, bg=BACKGROUND_COLOR)
        metrics.pack(fill="x", pady=(0, 10))
        self.build_metric_panel(metrics, "MSE", self.mse_text, 0)
        self.build_metric_panel(
            metrics,
            "Threshold",
            self.threshold_text,
            1,
            detail_variable=self.threshold_source_text,
        )
        metrics.grid_columnconfigure(0, weight=1, uniform="metric")
        metrics.grid_columnconfigure(1, weight=1, uniform="metric")

        plot_panel = tk.Frame(outer, bg=PANEL_COLOR, bd=1, relief="solid")
        plot_panel.pack(fill="both", expand=True, pady=(0, 10))
        self.figure = Figure(figsize=(8.4, 3.5), dpi=100, facecolor=PANEL_COLOR)
        self.axis = self.figure.add_subplot(111)
        self.axis.set_title("Live Reconstruction Error")
        self.axis.set_xlabel("Window")
        self.axis.set_ylabel("Reconstruction Error (MSE)")
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
        self.figure.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_panel)
        self.canvas.mpl_connect("draw_event", self.record_gui_draw)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=6)

        footer = tk.Frame(outer, bg=PANEL_COLOR, bd=1, relief="solid")
        footer.pack(fill="x")
        info = tk.Frame(footer, bg=PANEL_COLOR, padx=12, pady=9)
        info.pack(side="left", fill="both", expand=True)
        self.build_info_row(info, "Sampling:", self.sampling_text, 0)
        self.build_info_row(info, "Inference:", self.inference_text, 1)
        self.build_info_row(info, "Window:", self.window_text, 2)
        self.build_info_row(info, "Worker:", self.worker_status_text, 3)
        self.build_info_row(info, "Log:", self.log_text, 4)
        self.build_info_row(info, "Entscheidung:", self.decision_text, 5)
        self.build_info_row(info, "Latenz/Puffer:", self.latency_text, 6)

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
        self.normal_seen = False
        self.anomaly_seen = False
        self.status_text.set("STARTING")
        self.status_label.configure(bg=IDLE_COLOR)
        self.mse_text.set("–")
        self.sampling_text.set("– Hz")
        self.inference_text.set("– ms")
        self.window_text.set("0")
        self.error_line.set_data([], [])
        self.axis.set_xlim(0, PLOT_WINDOW_COUNT)
        self.axis.set_ylim(0, max(self.configuration.threshold * 1.35, 1e-6))
        self.canvas.draw_idle()

    def start_measurement(self) -> None:
        if self.closing or (self.worker is not None and self.worker.is_alive()):
            return
        self.reset_display()
        self.stop_event = threading.Event()
        self.log_path = None
        self.log_text.set("Self-Test – kein Log" if self.self_test else "Wird angelegt …")
        self.worker = AcquisitionWorker(
            configuration=self.configuration,
            metadata=self.metadata,
            output_queue=self.message_queue,
            stop_event=self.stop_event,
            self_test=self.self_test,
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
            self.log_text.set(str(self.log_path.relative_to(PROJECT_ROOT)))
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
        try:
            while True:
                message = self.message_queue.get_nowait()
                if message.kind == "measurement":
                    self.update_measurement(message.payload)
        except queue.Empty:
            pass
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
        if not self.closing:
            self.root.after(QUEUE_POLL_INTERVAL_MS, self.process_queue)

    def update_measurement(self, measurement: Measurement) -> None:
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

        self.mse_text.set(f"{measurement.reconstruction_error:.6f}")
        self.threshold_text.set(f"{measurement.threshold:.6f}")
        self.sampling_text.set(
            f"{measurement.measured_sampling_rate_hz:.1f} Hz"
        )
        self.inference_text.set(f"{measurement.inference_time_ms:.3f} ms")
        self.window_text.set(str(measurement.window_index))
        self.window_indices.append(measurement.window_index)
        self.reconstruction_errors.append(measurement.reconstruction_error if math.isfinite(measurement.reconstruction_error) else float("nan"))
        self.update_plot()

    def update_plot(self) -> None:
        x_values = list(self.window_indices)
        y_values = list(self.reconstruction_errors)
        self.error_line.set_data(x_values, y_values)
        if x_values:
            left = max(0, x_values[-1] - PLOT_WINDOW_COUNT + 1)
            right = max(left + 1, x_values[-1])
            self.axis.set_xlim(left, right)
        maximum_error = max((value for value in y_values if math.isfinite(value)), default=0.0)
        upper_limit = max(
            maximum_error * 1.18,
            self.configuration.threshold * 1.35,
            1e-6,
        )
        self.axis.set_ylim(0, upper_limit)
        self.canvas.draw_idle()

    def show_worker_error(self, payload: dict[str, str]) -> None:
        self.status_text.set("ERROR")
        self.status_label.configure(bg=ANOMALY_COLOR)
        self.worker_status_text.set(payload["message"])
        print(payload["traceback"], file=sys.stderr, flush=True)

    def worker_finished(self) -> None:
        if not self.closing:
            if self.status_text.get() != "ERROR":
                self.status_text.set("STOPPED")
                self.status_label.configure(bg=IDLE_COLOR)
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
                "nicht vollständig geprüft."
            )
        if self.window_indices[-1] < PLOT_WINDOW_COUNT:
            raise AssertionError("Self-Test erzeugte nicht mindestens 100 Fenster.")
        threshold_y = float(self.threshold_line.get_ydata()[0])
        if threshold_y != self.configuration.threshold:
            raise AssertionError("Threshold-Linie stimmt nicht mit dem Profil überein.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Einfache Tkinter-/Matplotlib-Anzeige für die profilabhängige "
            "ADXL345-TFLite-Live-Anomalieerkennung."
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
            "Automatisierter GUI-Self-Test erfolgreich: NORMAL, ANOMALY, "
            "Threshold-Linie, Plot-Limit und sauberes Schließen geprüft."
        )


if __name__ == "__main__":
    main()
