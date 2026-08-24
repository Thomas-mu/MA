#!/usr/bin/env python3
"""Profile-aware TFLite anomaly detection with latched fan shutdown.

The script reuses the validated profile/model/sensor helpers from
``live_tflite_monitor.py`` and the existing GPIO18 ``FanController`` from
``live_monitor.py``.  Dry-run and self-test modes never instantiate the fan
controller and therefore never write a GPIO or PWM state.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/masterarbeit_matplotlib")

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = Path(__file__).resolve().parent
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

from live_tflite_monitor import (  # noqa: E402
    AXIS_COUNT,
    WINDOW_SIZE,
    LiveConfiguration,
    LiveSummary,
    TFLiteRuntime,
    collect_window,
    display_path,
    infer_window,
    load_scaler,
    load_sensor_access,
    load_tflite_runtime,
    resolve_live_configuration,
    scale_window,
    warm_up,
)


DEFAULT_STARTUP_GRACE_SECONDS = 3.0
DEFAULT_CONSECUTIVE_ANOMALIES = 3

CSV_FIELDS = [
    "timestamp",
    "window_start_timestamp",
    "window_index",
    "reconstruction_error",
    "threshold",
    "predicted_label",
    "anomaly_counter",
    "consecutive_anomalies_required",
    "confirmed_anomaly",
    "startup_grace_active",
    "inference_time_ms",
    "window_formation_time_ms",
    "total_window_pipeline_time_ms",
    "measured_sampling_rate_hz",
    "fan_action",
    "dry_run",
]


@dataclass(frozen=True)
class ProfileRuntimeMetadata:
    profile_root: Path
    results_directory: Path
    profile_version: int
    sampling_rate_hz: int
    window_size: int
    step_size: int
    axes: tuple[str, ...]


@dataclass(frozen=True)
class SafetyTransition:
    anomaly_counter: int
    confirmed_now: bool


@dataclass
class AnomalyConfirmationState:
    required_consecutive: int
    anomaly_counter: int = 0
    confirmation_latched: bool = False
    first_anomaly_timestamp: str | None = None
    first_anomaly_monotonic: float | None = None
    first_anomaly_window_start_timestamp: str | None = None
    first_anomaly_window_start_monotonic: float | None = None
    first_anomaly_window_index: int | None = None

    def __post_init__(self) -> None:
        if self.required_consecutive < 2:
            raise ValueError(
                "Mindestens zwei aufeinanderfolgende Anomalien sind erforderlich."
            )

    def reset_unconfirmed_sequence(self) -> None:
        if self.confirmation_latched:
            return
        self.anomaly_counter = 0
        self.first_anomaly_timestamp = None
        self.first_anomaly_monotonic = None
        self.first_anomaly_window_start_timestamp = None
        self.first_anomaly_window_start_monotonic = None
        self.first_anomaly_window_index = None

    def observe(
        self,
        *,
        predicted_anomaly: bool,
        armed: bool,
        window_index: int,
        detection_timestamp: str,
        detection_monotonic: float,
        window_start_timestamp: str,
        window_start_monotonic: float,
    ) -> SafetyTransition:
        if self.confirmation_latched:
            return SafetyTransition(self.anomaly_counter, False)

        if not armed:
            self.reset_unconfirmed_sequence()
            return SafetyTransition(0, False)

        if not predicted_anomaly:
            self.reset_unconfirmed_sequence()
            return SafetyTransition(0, False)

        if self.anomaly_counter == 0:
            self.first_anomaly_timestamp = detection_timestamp
            self.first_anomaly_monotonic = detection_monotonic
            self.first_anomaly_window_start_timestamp = window_start_timestamp
            self.first_anomaly_window_start_monotonic = window_start_monotonic
            self.first_anomaly_window_index = window_index

        self.anomaly_counter += 1
        confirmed_now = self.anomaly_counter >= self.required_consecutive
        if confirmed_now:
            self.anomaly_counter = self.required_consecutive
            self.confirmation_latched = True
        return SafetyTransition(self.anomaly_counter, confirmed_now)


@dataclass
class ExistingFanActuator:
    """Thin safety wrapper around the existing ``FanController`` instance."""

    controller: Any
    gpio_bcm: int
    run_description: str
    stop_description: str
    backend_description: str
    stop_attempted: bool = False
    stop_succeeded: bool = False

    def stop_once(self) -> None:
        if self.stop_attempted:
            raise RuntimeError("Der Lüfter-Stop wurde bereits ausgelöst.")
        self.stop_attempted = True
        self.controller.set_state(False)
        if not self.controller.enabled or self.controller.is_running:
            raise RuntimeError(
                "Die vorhandene Lüftersteuerung konnte STOP nicht bestätigen."
            )
        self.stop_succeeded = True


def load_existing_fan_actuator() -> ExistingFanActuator:
    """Instantiate the already established hardware implementation.

    ``load_sensor_access`` first exposes Debian's system packages to the
    TensorFlow virtual environment.  This makes the existing smbus2/RPi.GPIO
    imports available without installing or reimplementing hardware access.
    Instantiation with ``default_on=True`` is intentionally restricted to the
    explicitly selected real-hardware mode.
    """

    load_sensor_access()
    from live_monitor import (
        FAN_PIN,
        FAN_RUN_PERCENT,
        FAN_STOP_PERCENT,
        FanController,
    )

    if (int(FAN_PIN), int(FAN_RUN_PERCENT), int(FAN_STOP_PERCENT)) != (
        18,
        100,
        0,
    ):
        raise RuntimeError(
            "Die vorhandene Lüfter-Hardwaresemantik hat sich geändert; "
            "erwartet werden BCM18, RUN=100% und STOP=0%."
        )

    controller = FanController(pin=FAN_PIN, default_on=True)
    if not controller.enabled or not controller.is_running:
        raise RuntimeError(
            "Die vorhandene GPIO18-Lüftersteuerung konnte RUN nicht bestätigen."
        )
    return ExistingFanActuator(
        controller=controller,
        gpio_bcm=int(FAN_PIN),
        run_description=f"GPIO HIGH / PWM {FAN_RUN_PERCENT}%",
        stop_description=f"GPIO LOW / PWM {FAN_STOP_PERCENT}%",
        backend_description=(
            "existing FanController: pinctrl -> HardwarePWM -> RPi.GPIO fallback"
        ),
    )


def initialize_fan_actuator(
    dry_run: bool,
    factory: Callable[[], ExistingFanActuator] | None = None,
) -> ExistingFanActuator | None:
    if dry_run:
        return None
    actuator_factory = factory or load_existing_fan_actuator
    return actuator_factory()


def read_profile_runtime_metadata(
    configuration: LiveConfiguration,
) -> tuple[dict[str, Any], ProfileRuntimeMetadata]:
    if configuration.profile_name is None:
        raise ValueError("Die Lüftersteuerung benötigt zwingend ein Setup-Profil.")
    profile_root = configuration.model_path.parent.parent
    metadata_path = profile_root / "profile.json"
    with metadata_path.open(encoding="utf-8") as handle:
        metadata = json.load(handle)
    if metadata.get("profile_name") != configuration.profile_name:
        raise ValueError("Inkonsistenter Profilname in profile.json.")
    if metadata.get("status") != "ready":
        raise ValueError("Nur ein Profil mit Status 'ready' darf verwendet werden.")

    window_size = int(metadata.get("window_size", -1))
    step_size = int(metadata.get("step_size", -1))
    axes = tuple(str(value) for value in metadata.get("axes", []))
    sampling_rate_hz = int(metadata.get("sampling_rate_hz", -1))
    if window_size != WINDOW_SIZE or step_size != WINDOW_SIZE:
        raise ValueError(
            f"Profil benötigt window_size=step_size={WINDOW_SIZE}; "
            f"erhalten: {window_size}/{step_size}."
        )
    if axes != ("x_g", "y_g", "z_g") or len(axes) != AXIS_COUNT:
        raise ValueError(f"Ungültige Profilachsen: {axes!r}")
    if sampling_rate_hz <= 0:
        raise ValueError(f"Ungültige Profil-Samplingrate: {sampling_rate_hz}")

    runtime_metadata = ProfileRuntimeMetadata(
        profile_root=profile_root,
        results_directory=profile_root / "results",
        profile_version=int(metadata.get("profile_version", 0)),
        sampling_rate_hz=sampling_rate_hz,
        window_size=window_size,
        step_size=step_size,
        axes=axes,
    )
    return metadata, runtime_metadata


def allocate_run_paths(
    results_directory: Path,
) -> tuple[str, Path, Path]:
    results_directory.mkdir(parents=True, exist_ok=True)
    base_run_id = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    for suffix in range(10_000):
        run_id = base_run_id if suffix == 0 else f"{base_run_id}_{suffix:03d}"
        csv_path = results_directory / f"fan_control_live_{run_id}.csv"
        event_path = results_directory / f"fan_shutdown_event_{run_id}.json"
        if not csv_path.exists() and not event_path.exists():
            return run_id, csv_path, event_path
    raise RuntimeError("Keine freien Ergebnisdateinamen für den Lauf gefunden.")


def write_event_json(path: Path, document: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def build_shutdown_event(
    *,
    configuration: LiveConfiguration,
    profile_metadata: dict[str, Any],
    runtime_metadata: ProfileRuntimeMetadata,
    state: AnomalyConfirmationState,
    window_index: int,
    confirmed_timestamp: str,
    confirmed_monotonic: float,
    action_started_timestamp: str,
    action_started_monotonic: float,
    action_completed_timestamp: str,
    action_duration_ms: float,
    hardware_stop_executed: bool,
    fan_action: str,
    stop_error: str | None,
    dry_run: bool,
    inference_time_ms: float,
    window_formation_time_ms: float,
    total_window_pipeline_time_ms: float,
    confirming_sampling_rate_hz: float,
    consecutive_sampling_rates_hz: list[float],
) -> dict[str, Any]:
    if (
        state.first_anomaly_monotonic is None
        or state.first_anomaly_window_start_monotonic is None
        or state.first_anomaly_window_index is None
    ):
        raise RuntimeError("Zeitbasis der bestätigten Anomalie fehlt.")

    first_to_confirmation_ms = (
        confirmed_monotonic - state.first_anomaly_monotonic
    ) * 1000.0
    reaction_time_ms = (
        action_started_monotonic - state.first_anomaly_monotonic
    ) * 1000.0
    total_software_reaction_time_ms = (
        action_started_monotonic - state.first_anomaly_window_start_monotonic
    ) * 1000.0
    return {
        "event_type": (
            "dry_run_shutdown_decision"
            if dry_run
            else ("fan_shutdown" if hardware_stop_executed else "fan_shutdown_failed")
        ),
        "profile": configuration.profile_name,
        "profile_version": runtime_metadata.profile_version,
        "threshold": configuration.threshold,
        "threshold_source": display_path(configuration.threshold_path),
        "consecutive_anomalies_required": state.required_consecutive,
        "first_anomaly_window_index": state.first_anomaly_window_index,
        "confirmed_anomaly_window_index": window_index,
        "number_of_windows_from_first_anomaly_to_confirmation": (
            window_index - state.first_anomaly_window_index + 1
        ),
        "first_anomaly_window_start_timestamp": (
            state.first_anomaly_window_start_timestamp
        ),
        "first_anomaly_timestamp": state.first_anomaly_timestamp,
        "confirmed_anomaly_timestamp": confirmed_timestamp,
        "stop_command_timestamp": action_started_timestamp if not dry_run else None,
        "dry_run_stop_decision_timestamp": (
            action_started_timestamp if dry_run else None
        ),
        "action_completed_timestamp": action_completed_timestamp,
        "first_anomaly_to_confirmation_ms": first_to_confirmation_ms,
        "reaction_time_ms": reaction_time_ms,
        "reaction_time_basis": (
            "first anomaly classification to hardware stop command"
            if hardware_stop_executed
            else "first anomaly classification to dry-run stop decision"
        ),
        "total_software_reaction_time_ms": total_software_reaction_time_ms,
        "total_software_reaction_time_basis": (
            "start of first anomalous sensor window to stop command/decision"
        ),
        "stop_command_duration_ms": action_duration_ms,
        "confirming_window_inference_time_ms": inference_time_ms,
        "confirming_window_formation_time_ms": window_formation_time_ms,
        "confirming_window_pipeline_time_ms": total_window_pipeline_time_ms,
        "sampling_rate": {
            "configured_hz": runtime_metadata.sampling_rate_hz,
            "confirming_window_measured_hz": confirming_sampling_rate_hz,
            "confirmation_sequence_mean_measured_hz": float(
                np.mean(consecutive_sampling_rates_hz)
            ),
        },
        "model": "Float32 TFLite convolutional autoencoder",
        "scaler": display_path(configuration.scaler_path),
        "tflite_model": display_path(configuration.model_path),
        "profile_metadata": display_path(runtime_metadata.profile_root / "profile.json"),
        "model_sha256": profile_metadata["autoencoder"]["tflite_model_sha256"],
        "scaler_sha256": profile_metadata["scaler"]["sha256"],
        "threshold_sha256": profile_metadata["threshold"]["sha256"],
        "fan_gpio_bcm": 18,
        "fan_run_state": "GPIO HIGH / PWM 100%",
        "fan_stop_state": "GPIO LOW / PWM 0%",
        "fan_action": fan_action,
        "hardware_stop_executed": hardware_stop_executed,
        "stop_error": stop_error,
        "dry_run": dry_run,
        "automatic_restart_implemented": False,
    }


def print_configuration(
    configuration: LiveConfiguration,
    metadata: ProfileRuntimeMetadata,
    arguments: argparse.Namespace,
    runtime: TFLiteRuntime,
) -> None:
    print(f"Profil: {configuration.profile_name} (Version {metadata.profile_version})")
    print(f"Modell: {display_path(configuration.model_path)}")
    print(f"Scaler: {display_path(configuration.scaler_path)}")
    print(f"Threshold-Datei: {display_path(configuration.threshold_path)}")
    print(f"Geladener Profil-Threshold: {configuration.threshold:.16f}")
    print(
        f"TFLite: Input {runtime.input_shape} {runtime.input_dtype.name} | "
        f"Output {runtime.output_shape} {runtime.output_dtype.name}"
    )
    print(f"Samplingrate aus Profil: {metadata.sampling_rate_hz} Hz")
    print(f"Startup Grace: {arguments.startup_grace:.3f} s")
    print(
        "Anomaliebestätigung: "
        f"{arguments.consecutive_anomalies} aufeinanderfolgende Fenster"
    )
    print("Lüfter: BCM GPIO18 | RUN=HIGH/100% | STOP=LOW/0%")
    if arguments.dry_run:
        print("DRY RUN: GPIO-/PWM-Controller wird nicht initialisiert.")
    else:
        print("REALER HARDWAREMODUS: vorhandener FanController wird verwendet.")


def print_run_summary(
    summary: LiveSummary,
    csv_path: Path,
    event_path: Path | None,
    interrupted: bool,
    dry_run: bool,
) -> None:
    print("\nFan-Control-Monitor beendet.")
    print(f"CSV: {display_path(csv_path)}")
    print(f"Fenster: {summary.window_count}")
    print(f"NORMAL: {summary.normal_count}")
    print(f"ANOMALY: {summary.anomaly_count}")
    print(f"Bestätigtes Ereignis: {'ja' if event_path else 'nein'}")
    if event_path is not None:
        print(f"Event-JSON: {display_path(event_path)}")
    print(f"Ctrl+C: {'ja' if interrupted else 'nein'}")
    if dry_run:
        print("Dry-Run bestätigt: kein GPIO-/PWM-Controller wurde erzeugt.")
    else:
        print(
            "GPIO-Zustand wurde beim Beenden bewusst nicht durch Cleanup oder "
            "Restart verändert."
        )


def run_fan_control(
    *,
    arguments: argparse.Namespace,
    configuration: LiveConfiguration,
    profile_metadata: dict[str, Any],
    runtime_metadata: ProfileRuntimeMetadata,
    scaler: Any,
    runtime: TFLiteRuntime,
) -> None:
    _, csv_path, planned_event_path = allocate_run_paths(
        runtime_metadata.results_directory
    )
    connect_sensor, read_sensor = load_sensor_access()
    summary = LiveSummary()
    state = AnomalyConfirmationState(arguments.consecutive_anomalies)
    event_path: Path | None = None
    interrupted = False
    consecutive_sampling_rates_hz: list[float] = []
    bus = connect_sensor()

    try:
        with csv_path.open("x", encoding="utf-8", newline="", buffering=1) as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            handle.flush()

            actuator = initialize_fan_actuator(arguments.dry_run)
            if actuator is not None:
                print(
                    f"Vorhandene Lüftersteuerung aktiv: BCM GPIO{actuator.gpio_bcm}; "
                    f"RUN={actuator.run_description}; STOP={actuator.stop_description}."
                )

            run_start_monotonic = time.perf_counter()
            monitoring_announced = arguments.startup_grace == 0
            if monitoring_announced:
                print("Monitoring aktiv.")
            else:
                print(
                    "Startup Grace aktiv; Messung und Logging laufen, "
                    "Abschaltung ist deaktiviert."
                )
            print(f"Log: {display_path(csv_path)}")
            print("Beenden mit Ctrl+C.\n")

            try:
                while (
                    arguments.max_windows is None
                    or summary.window_count < arguments.max_windows
                ):
                    window_index = summary.window_count + 1
                    window_start_wall = datetime.now().astimezone()
                    window_start_timestamp = window_start_wall.isoformat(
                        timespec="milliseconds"
                    )
                    window_start_monotonic = time.perf_counter()
                    collection_start_ns = time.perf_counter_ns()
                    raw_window, measured_sampling_rate_hz = collect_window(
                        bus,
                        read_sensor,
                        sample_rate_hz=runtime_metadata.sampling_rate_hz,
                    )
                    collection_end_ns = time.perf_counter_ns()
                    scaled_window = scale_window(raw_window, scaler)
                    (
                        reconstruction_error,
                        predicted_label,
                        inference_time_ms,
                    ) = infer_window(runtime, scaled_window, configuration.threshold)
                    decision_monotonic = time.perf_counter()
                    decision_wall = datetime.now().astimezone()
                    timestamp = decision_wall.isoformat(timespec="milliseconds")
                    window_formation_time_ms = (
                        collection_end_ns - collection_start_ns
                    ) / 1e6
                    total_window_pipeline_time_ms = (
                        time.perf_counter_ns() - collection_start_ns
                    ) / 1e6

                    grace_active = (
                        window_start_monotonic - run_start_monotonic
                    ) < arguments.startup_grace
                    if not grace_active and not monitoring_announced:
                        print("Monitoring aktiv.")
                        monitoring_announced = True

                    transition = state.observe(
                        predicted_anomaly=bool(predicted_label),
                        armed=not grace_active,
                        window_index=window_index,
                        detection_timestamp=timestamp,
                        detection_monotonic=decision_monotonic,
                        window_start_timestamp=window_start_timestamp,
                        window_start_monotonic=window_start_monotonic,
                    )
                    if grace_active or not predicted_label:
                        consecutive_sampling_rates_hz.clear()
                    else:
                        consecutive_sampling_rates_hz.append(
                            measured_sampling_rate_hz
                        )

                    fan_action = (
                        "startup_shutdown_suppressed"
                        if grace_active and predicted_label
                        else "none"
                    )
                    stop_error: str | None = None
                    shutdown_event: dict[str, Any] | None = None
                    if transition.confirmed_now:
                        print("\n*** CONFIRMED ANOMALY ***", flush=True)
                        action_started_wall = datetime.now().astimezone()
                        action_started_timestamp = action_started_wall.isoformat(
                            timespec="milliseconds"
                        )
                        action_started_monotonic = time.perf_counter()
                        action_start_ns = time.perf_counter_ns()
                        hardware_stop_executed = False
                        if arguments.dry_run:
                            fan_action = "dry_run_fan_stop_would_execute"
                            print(
                                "DRY RUN: Lüfter würde jetzt gestoppt werden.",
                                flush=True,
                            )
                        else:
                            fan_action = "fan_stop_command_sent"
                            print("Lüfter wird gestoppt.", flush=True)
                            try:
                                if actuator is None:
                                    raise RuntimeError(
                                        "Realer Modus besitzt keinen FanController."
                                    )
                                actuator.stop_once()
                                hardware_stop_executed = True
                            except Exception as error:
                                fan_action = "fan_stop_command_failed"
                                stop_error = f"{type(error).__name__}: {error}"
                        action_duration_ms = (
                            time.perf_counter_ns() - action_start_ns
                        ) / 1e6
                        action_completed_timestamp = (
                            datetime.now()
                            .astimezone()
                            .isoformat(timespec="milliseconds")
                        )
                        shutdown_event = build_shutdown_event(
                            configuration=configuration,
                            profile_metadata=profile_metadata,
                            runtime_metadata=runtime_metadata,
                            state=state,
                            window_index=window_index,
                            confirmed_timestamp=timestamp,
                            confirmed_monotonic=decision_monotonic,
                            action_started_timestamp=action_started_timestamp,
                            action_started_monotonic=action_started_monotonic,
                            action_completed_timestamp=action_completed_timestamp,
                            action_duration_ms=action_duration_ms,
                            hardware_stop_executed=hardware_stop_executed,
                            fan_action=fan_action,
                            stop_error=stop_error,
                            dry_run=arguments.dry_run,
                            inference_time_ms=inference_time_ms,
                            window_formation_time_ms=window_formation_time_ms,
                            total_window_pipeline_time_ms=(
                                total_window_pipeline_time_ms
                            ),
                            confirming_sampling_rate_hz=(
                                measured_sampling_rate_hz
                            ),
                            consecutive_sampling_rates_hz=(
                                consecutive_sampling_rates_hz
                            ),
                        )

                    writer.writerow(
                        {
                            "timestamp": timestamp,
                            "window_start_timestamp": window_start_timestamp,
                            "window_index": window_index,
                            "reconstruction_error": reconstruction_error,
                            "threshold": configuration.threshold,
                            "predicted_label": predicted_label,
                            "anomaly_counter": transition.anomaly_counter,
                            "consecutive_anomalies_required": (
                                arguments.consecutive_anomalies
                            ),
                            "confirmed_anomaly": int(transition.confirmed_now),
                            "startup_grace_active": int(grace_active),
                            "inference_time_ms": inference_time_ms,
                            "window_formation_time_ms": window_formation_time_ms,
                            "total_window_pipeline_time_ms": (
                                total_window_pipeline_time_ms
                            ),
                            "measured_sampling_rate_hz": (
                                measured_sampling_rate_hz
                            ),
                            "fan_action": fan_action,
                            "dry_run": int(arguments.dry_run),
                        }
                    )
                    handle.flush()
                    summary.add(
                        reconstruction_error,
                        predicted_label,
                        inference_time_ms,
                        measured_sampling_rate_hz,
                    )

                    status = "ANOMALY" if predicted_label else "NORMAL"
                    if grace_active:
                        print(
                            f"STARTUP | {decision_wall:%H:%M:%S} | "
                            f"Window {window_index:04d} | "
                            f"MSE {reconstruction_error:.6f} | {status} | "
                            "Abschaltung noch deaktiviert",
                            flush=True,
                        )
                    else:
                        print(
                            f"{decision_wall:%H:%M:%S} | "
                            f"Window {window_index:04d} | "
                            f"MSE {reconstruction_error:.6f} | {status} | "
                            f"anomaly_count {transition.anomaly_counter}/"
                            f"{arguments.consecutive_anomalies}",
                            flush=True,
                        )

                    if shutdown_event is not None:
                        write_event_json(planned_event_path, shutdown_event)
                        event_path = planned_event_path
                        if arguments.dry_run:
                            print("SIMULATED SYSTEM STOPPED DUE TO ANOMALY")
                        elif shutdown_event["hardware_stop_executed"]:
                            print("SYSTEM STOPPED DUE TO ANOMALY")
                        else:
                            print("CRITICAL: FAN STOP COMMAND FAILED")
                        if stop_error is not None:
                            raise RuntimeError(stop_error)
                        break
            except KeyboardInterrupt:
                interrupted = True
                print(
                    "\nCtrl+C empfangen; CSV und I²C werden geschlossen. "
                    "Der GPIO-Zustand wird nicht verändert."
                )
    finally:
        bus.close()
        print_run_summary(
            summary,
            csv_path,
            event_path,
            interrupted,
            arguments.dry_run,
        )


def simulate_sequence(
    labels: list[int],
    *,
    required: int = DEFAULT_CONSECUTIVE_ANOMALIES,
    armed: bool = True,
) -> dict[str, Any]:
    state = AnomalyConfirmationState(required)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    confirmation_indices: list[int] = []
    counters: list[int] = []
    for index, label in enumerate(labels, start=1):
        detection = base + timedelta(seconds=index * 0.256)
        transition = state.observe(
            predicted_anomaly=bool(label),
            armed=armed,
            window_index=index,
            detection_timestamp=detection.isoformat(),
            detection_monotonic=index * 0.256,
            window_start_timestamp=(detection - timedelta(seconds=0.256)).isoformat(),
            window_start_monotonic=(index - 1) * 0.256,
        )
        counters.append(transition.anomaly_counter)
        if transition.confirmed_now:
            confirmation_indices.append(index)
    return {
        "labels": labels,
        "counters": counters,
        "confirmation_indices": confirmation_indices,
        "confirmation_count": len(confirmation_indices),
        "latched": state.confirmation_latched,
    }


def run_synthetic_safety_tests() -> dict[str, Any]:
    cases = {
        "normal_normal_anomaly_normal": simulate_sequence([0, 0, 1, 0]),
        "anomaly_anomaly_normal": simulate_sequence([1, 1, 0]),
        "three_anomalies": simulate_sequence([1, 1, 1]),
        "ten_anomalies": simulate_sequence([1] * 10),
        "startup_anomalies_suppressed": simulate_sequence(
            [1, 1, 1, 1], armed=False
        ),
    }
    assert cases["normal_normal_anomaly_normal"]["confirmation_count"] == 0
    assert cases["normal_normal_anomaly_normal"]["counters"] == [0, 0, 1, 0]
    assert cases["anomaly_anomaly_normal"]["confirmation_count"] == 0
    assert cases["anomaly_anomaly_normal"]["counters"] == [1, 2, 0]
    assert cases["three_anomalies"]["confirmation_indices"] == [3]
    assert cases["ten_anomalies"]["confirmation_indices"] == [3]
    assert cases["startup_anomalies_suppressed"]["confirmation_count"] == 0
    assert cases["startup_anomalies_suppressed"]["counters"] == [0, 0, 0, 0]

    factory_called = False

    def forbidden_factory() -> ExistingFanActuator:
        nonlocal factory_called
        factory_called = True
        raise AssertionError("Dry-Run darf keine Hardwarefactory aufrufen.")

    assert initialize_fan_actuator(True, forbidden_factory) is None
    assert not factory_called
    return cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Profilabhängige ADXL345/TFLite-Anomalieerkennung mit bestätigtem, "
            "verriegeltem Lüfter-Stop über die vorhandene GPIO18-Steuerung."
        )
    )
    parser.add_argument(
        "--profile",
        required=True,
        help="Freigegebenes Setup-Profil, z.B. home.",
    )
    parser.add_argument(
        "--startup-grace",
        type=float,
        default=DEFAULT_STARTUP_GRACE_SECONDS,
        help=(
            "Startphase ohne Abschaltung in Sekunden "
            f"(Standard: {DEFAULT_STARTUP_GRACE_SECONDS:g})."
        ),
    )
    parser.add_argument(
        "--consecutive-anomalies",
        type=int,
        default=DEFAULT_CONSECUTIVE_ANOMALIES,
        help=(
            "Erforderliche aufeinanderfolgende ANOMALY-Fenster "
            f"(Standard: {DEFAULT_CONSECUTIVE_ANOMALIES})."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Sensor und Modell live ausführen, aber keinen GPIO-/PWM-Controller "
            "initialisieren und keine Lüfteraktion ausführen."
        ),
    )
    parser.add_argument(
        "--max-windows",
        type=int,
        default=None,
        help="Nach dieser Fensterzahl sicher beenden (Standard: bis Ctrl+C/Stop).",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help=(
            "Profil, Modell und Sicherheitssequenzen prüfen; kein Sensor, GPIO "
            "oder Logging."
        ),
    )
    arguments = parser.parse_args()
    if arguments.startup_grace < 0:
        parser.error("--startup-grace darf nicht negativ sein.")
    if arguments.consecutive_anomalies < 2:
        parser.error("--consecutive-anomalies muss mindestens 2 sein.")
    if arguments.max_windows is not None and arguments.max_windows <= 0:
        parser.error("--max-windows muss positiv sein.")
    return arguments


def main() -> None:
    arguments = parse_args()
    configuration = resolve_live_configuration(arguments.profile)
    profile_metadata, runtime_metadata = read_profile_runtime_metadata(
        configuration
    )
    scaler = load_scaler(configuration.scaler_path)
    runtime = load_tflite_runtime(configuration.model_path)
    warm_up(runtime, configuration.threshold)
    print_configuration(configuration, runtime_metadata, arguments, runtime)

    if arguments.self_test:
        cases = run_synthetic_safety_tests()
        print(json.dumps(cases, indent=2, ensure_ascii=False))
        print(
            "Self-Test erfolgreich: kein Sensorzugriff, kein GPIO/PWM und "
            "keine Logdatei."
        )
        return

    run_fan_control(
        arguments=arguments,
        configuration=configuration,
        profile_metadata=profile_metadata,
        runtime_metadata=runtime_metadata,
        scaler=scaler,
        runtime=runtime,
    )


if __name__ == "__main__":
    main()
