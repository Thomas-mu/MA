#!/usr/bin/env python3
"""Live anomaly detection with the validated Float32 TFLite autoencoder.

Phase 6 is intentionally limited to sensor acquisition, classification,
terminal output and CSV logging.  It has no actuator integration.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/masterarbeit_matplotlib")

import joblib
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "models" / "clean_comparison" / "autoencoder_float32.tflite"
SCALER_PATH = PROJECT_ROOT / "models" / "clean_comparison" / "scaler.joblib"
THRESHOLD_PATH = PROJECT_ROOT / "results" / "clean_tensorflow_threshold.json"
DEFAULT_LOG_PATH = PROJECT_ROOT / "results" / "live_tflite_log.csv"
PROFILES_DIRECTORY = PROJECT_ROOT / "profiles"
SYSTEM_DIST_PACKAGES = Path("/usr/lib/python3/dist-packages")

SAMPLE_RATE_HZ = 500
WINDOW_SIZE = 128
AXIS_COUNT = 3
WINDOW_SHAPE = (WINDOW_SIZE, AXIS_COUNT)
MODEL_TENSOR_SHAPE = (1, WINDOW_SIZE, AXIS_COUNT)
WARMUP_INFERENCES = 20
RECONSTRUCTION_ERROR_THRESHOLD = 0.2185792346784422
PROFILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

CSV_FIELDS = [
    "timestamp",
    "window_index",
    "reconstruction_error",
    "threshold",
    "predicted_label",
    "inference_time_ms",
    "measured_sampling_rate_hz",
]


@dataclass(frozen=True)
class TFLiteRuntime:
    interpreter: Any
    input_index: int
    output_index: int
    input_shape: tuple[int, ...]
    output_shape: tuple[int, ...]
    input_dtype: np.dtype[Any]
    output_dtype: np.dtype[Any]
    backend: str


@dataclass(frozen=True)
class LiveConfiguration:
    profile_name: str | None
    model_path: Path
    scaler_path: Path
    threshold_path: Path
    threshold: float
    default_log_path: Path


@dataclass
class LiveSummary:
    window_count: int = 0
    normal_count: int = 0
    anomaly_count: int = 0
    reconstruction_error_sum: float = 0.0
    inference_time_sum_ms: float = 0.0
    sampling_rate_sum_hz: float = 0.0

    def add(
        self,
        reconstruction_error: float,
        predicted_label: int,
        inference_time_ms: float,
        measured_sampling_rate_hz: float,
    ) -> None:
        self.window_count += 1
        if predicted_label == 0:
            self.normal_count += 1
        else:
            self.anomaly_count += 1
        self.reconstruction_error_sum += reconstruction_error
        self.inference_time_sum_ms += inference_time_ms
        self.sampling_rate_sum_hz += measured_sampling_rate_hz

    def mean(self, total: float) -> float | None:
        if self.window_count == 0:
            return None
        return total / self.window_count


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_output_path(
    requested_path: Path | None, default_log_path: Path = DEFAULT_LOG_PATH
) -> Path:
    if requested_path is not None:
        path = (
            requested_path
            if requested_path.is_absolute()
            else PROJECT_ROOT / requested_path
        )
        if path.exists():
            raise FileExistsError(
                f"Die Logdatei existiert bereits und wird nicht überschrieben: {path}"
            )
        return path

    if not default_log_path.exists():
        return default_log_path

    run_id = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    return default_log_path.with_name(f"live_tflite_log_{run_id}.csv")


def validate_fixed_threshold() -> float:
    with THRESHOLD_PATH.open(encoding="utf-8") as handle:
        stored_threshold = float(json.load(handle)["threshold"])
    if stored_threshold != RECONSTRUCTION_ERROR_THRESHOLD:
        raise ValueError(
            "Der fest codierte Live-Threshold stimmt nicht exakt mit dem "
            f"validierten Clean-Threshold überein: {stored_threshold!r}."
        )
    return stored_threshold


def validate_profile_name(profile_name: str) -> None:
    if not PROFILE_NAME_PATTERN.fullmatch(profile_name):
        raise ValueError(
            "Profilname muss mit einem alphanumerischen Zeichen beginnen und "
            "darf höchstens 64 Zeichen aus Buchstaben, Ziffern, '_' und '-' enthalten."
        )


def verify_profile_hash(
    path: Path, metadata: dict[str, Any], hash_key: str
) -> None:
    expected_hash = metadata.get(hash_key)
    if expected_hash is None:
        raise ValueError(f"Profilmetadaten enthalten keinen Hash {hash_key!r}.")
    actual_hash = sha256_file(path)
    if actual_hash != expected_hash:
        raise ValueError(
            f"Profilartefakt wurde seit der Freigabe verändert: {path}"
        )


def resolve_live_configuration(
    profile_name: str | None,
    profiles_directory: Path = PROFILES_DIRECTORY,
) -> LiveConfiguration:
    if profile_name is None:
        for path in (MODEL_PATH, SCALER_PATH, THRESHOLD_PATH):
            if not path.is_file():
                raise FileNotFoundError(f"Erforderliches Artefakt fehlt: {path}")
        return LiveConfiguration(
            profile_name=None,
            model_path=MODEL_PATH,
            scaler_path=SCALER_PATH,
            threshold_path=THRESHOLD_PATH,
            threshold=validate_fixed_threshold(),
            default_log_path=DEFAULT_LOG_PATH,
        )

    validate_profile_name(profile_name)
    profile_root = profiles_directory / profile_name
    metadata_path = profile_root / "profile.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Profilmetadaten fehlen: {metadata_path}")
    with metadata_path.open(encoding="utf-8") as handle:
        metadata = json.load(handle)
    if metadata.get("profile_name") != profile_name:
        raise ValueError(
            "Profilname in profile.json stimmt nicht mit --profile überein."
        )
    if metadata.get("status") != "ready":
        raise ValueError(
            f"Profil {profile_name!r} ist nicht freigegeben; "
            f"Status: {metadata.get('status')!r}."
        )

    model_path = profile_root / "models" / "autoencoder_float32.tflite"
    scaler_path = profile_root / "models" / "scaler.joblib"
    threshold_path = profile_root / "models" / "threshold.json"
    for path in (model_path, scaler_path, threshold_path):
        if not path.is_file():
            raise FileNotFoundError(f"Profilartefakt fehlt: {path}")

    with threshold_path.open(encoding="utf-8") as handle:
        threshold_document = json.load(handle)
    if not threshold_document.get("normal_validation_only", False):
        raise ValueError(
            "Profilthreshold ist nicht als ausschließlich normal-validiert markiert."
        )
    if threshold_document.get("test_or_anomaly_data_used", True):
        raise ValueError(
            "Profilthreshold weist Test- oder Anomaliedatennutzung aus."
        )
    threshold = float(
        threshold_document.get(
            "selected_threshold", threshold_document.get("threshold")
        )
    )
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError(f"Ungültiger Profilthreshold: {threshold!r}")
    stored_profile_threshold = float(
        metadata.get("threshold", {}).get("selected_threshold", np.nan)
    )
    if stored_profile_threshold != threshold:
        raise ValueError(
            "Threshold in profile.json und models/threshold.json stimmt nicht überein."
        )

    verify_profile_hash(model_path, metadata["autoencoder"], "tflite_model_sha256")
    verify_profile_hash(scaler_path, metadata["scaler"], "sha256")
    verify_profile_hash(threshold_path, metadata["threshold"], "sha256")
    return LiveConfiguration(
        profile_name=profile_name,
        model_path=model_path,
        scaler_path=scaler_path,
        threshold_path=threshold_path,
        threshold=threshold,
        default_log_path=profile_root / "results" / "live_tflite_log.csv",
    )


def load_sensor_access() -> tuple[Callable[..., Any], Callable[..., Any]]:
    """Load the existing ADXL345 module only when hardware access starts.

    TensorFlow lives in the project environment while the already installed
    Raspberry-Pi smbus2 package lives in Debian's system dist-packages.  The
    system path is appended (never prepended), so project packages keep
    precedence and no additional sensor library is installed.
    """

    if importlib.util.find_spec("smbus2") is None:
        if not SYSTEM_DIST_PACKAGES.is_dir():
            raise ModuleNotFoundError(
                "smbus2 fehlt sowohl in .venv_tf als auch in den Systempaketen."
            )
        sys.path.append(str(SYSTEM_DIST_PACKAGES))
        importlib.invalidate_caches()
    if importlib.util.find_spec("smbus2") is None:
        raise ModuleNotFoundError("Das vorhandene smbus2-Paket ist nicht importierbar.")

    try:
        from adxl345 import connect as sensor_connect
        from adxl345 import read_acceleration_g as sensor_read
    except ModuleNotFoundError as error:
        if error.name != "adxl345":
            raise
        from src.adxl345 import connect as sensor_connect
        from src.adxl345 import read_acceleration_g as sensor_read

    return sensor_connect, sensor_read


def load_scaler(scaler_path: Path = SCALER_PATH) -> Any:
    scaler = joblib.load(scaler_path)
    if type(scaler).__module__ != "sklearn.preprocessing._data" or type(
        scaler
    ).__name__ != "StandardScaler":
        raise TypeError(
            "Erwartet wird der gespeicherte sklearn StandardScaler; erhalten: "
            f"{type(scaler).__module__}.{type(scaler).__name__}."
        )
    if int(getattr(scaler, "n_features_in_", -1)) != AXIS_COUNT:
        raise ValueError(
            f"Der Scaler erwartet nicht exakt {AXIS_COUNT} XYZ-Features."
        )
    for attribute in ("mean_", "scale_"):
        values = np.asarray(getattr(scaler, attribute, []))
        if values.shape != (AXIS_COUNT,) or not np.all(np.isfinite(values)):
            raise ValueError(f"Ungültiger Scaler-Zustand: {attribute}={values!r}")
    return scaler


def load_tflite_runtime(model_path: Path = MODEL_PATH) -> TFLiteRuntime:
    import tensorflow as tf

    interpreter = tf.lite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    inputs = interpreter.get_input_details()
    outputs = interpreter.get_output_details()
    if len(inputs) != 1 or len(outputs) != 1:
        raise ValueError(
            "Der Autoencoder muss exakt einen Input und einen Output besitzen; "
            f"erhalten: {len(inputs)} Input(s), {len(outputs)} Output(s)."
        )

    input_detail = inputs[0]
    output_detail = outputs[0]
    input_shape = tuple(int(value) for value in input_detail["shape"])
    output_shape = tuple(int(value) for value in output_detail["shape"])
    input_dtype = np.dtype(input_detail["dtype"])
    output_dtype = np.dtype(output_detail["dtype"])
    if input_shape != MODEL_TENSOR_SHAPE:
        raise ValueError(
            f"TFLite-Input-Shape {input_shape}, erwartet {MODEL_TENSOR_SHAPE}."
        )
    if output_shape != MODEL_TENSOR_SHAPE:
        raise ValueError(
            f"TFLite-Output-Shape {output_shape}, erwartet {MODEL_TENSOR_SHAPE}."
        )
    if input_dtype != np.dtype(np.float32):
        raise TypeError(f"TFLite-Input ist {input_dtype.name} statt float32.")
    if output_dtype != np.dtype(np.float32):
        raise TypeError(f"TFLite-Output ist {output_dtype.name} statt float32.")
    if input_detail["quantization"] != (0.0, 0):
        raise ValueError("Der TFLite-Input ist unerwartet quantisiert.")
    if output_detail["quantization"] != (0.0, 0):
        raise ValueError("Der TFLite-Output ist unerwartet quantisiert.")

    return TFLiteRuntime(
        interpreter=interpreter,
        input_index=int(input_detail["index"]),
        output_index=int(output_detail["index"]),
        input_shape=input_shape,
        output_shape=output_shape,
        input_dtype=input_dtype,
        output_dtype=output_dtype,
        backend=f"tensorflow.lite.Interpreter {tf.__version__}",
    )


def scale_window(raw_window: np.ndarray, scaler: Any) -> np.ndarray:
    if raw_window.shape != WINDOW_SHAPE:
        raise ValueError(
            f"Live-Fenster hat Shape {raw_window.shape}, erwartet {WINDOW_SHAPE}."
        )
    # Identisch zur Clean-Datenvorbereitung: Rohachsen zuerst Float32, dann
    # (window, sample, axis) zu (-1, 3), achsenweise transformieren und
    # zurückformen.
    raw_float32 = np.asarray(raw_window, dtype=np.float32)
    scaled = scaler.transform(raw_float32.reshape(-1, AXIS_COUNT)).reshape(
        WINDOW_SHAPE
    )
    scaled_float32 = np.asarray(scaled, dtype=np.float32)
    if not np.all(np.isfinite(scaled_float32)):
        raise ValueError("Das skalierte Live-Fenster enthält nicht-endliche Werte.")
    return scaled_float32


def infer_window(
    runtime: TFLiteRuntime,
    scaled_window: np.ndarray,
    threshold: float = RECONSTRUCTION_ERROR_THRESHOLD,
) -> tuple[float, int, float]:
    if scaled_window.shape != WINDOW_SHAPE:
        raise ValueError(f"Ungültige skalierte Fensterform: {scaled_window.shape}")
    model_input = scaled_window[np.newaxis, ...]

    start_ns = time.perf_counter_ns()
    runtime.interpreter.set_tensor(runtime.input_index, model_input)
    runtime.interpreter.invoke()
    reconstruction = np.asarray(
        runtime.interpreter.get_tensor(runtime.output_index)[0], dtype=np.float32
    )
    reconstruction_error = float(
        np.mean(
            np.square(scaled_window - reconstruction),
            dtype=np.float64,
        )
    )
    predicted_label = int(reconstruction_error > threshold)
    inference_time_ms = (time.perf_counter_ns() - start_ns) / 1e6
    return reconstruction_error, predicted_label, inference_time_ms


def warm_up(
    runtime: TFLiteRuntime,
    threshold: float = RECONSTRUCTION_ERROR_THRESHOLD,
) -> None:
    artificial_window = np.zeros(WINDOW_SHAPE, dtype=np.float32)
    for _ in range(WARMUP_INFERENCES):
        infer_window(runtime, artificial_window, threshold)


def collect_window(
    bus: Any,
    read_sensor: Callable[..., tuple[float, float, float]],
    sample_rate_hz: int = SAMPLE_RATE_HZ,
) -> tuple[np.ndarray, float]:
    if sample_rate_hz <= 0:
        raise ValueError("Die Samplingrate muss positiv sein.")
    sample_period_seconds = 1.0 / sample_rate_hz
    samples = np.empty(WINDOW_SHAPE, dtype=np.float64)
    sample_timestamps = np.empty(WINDOW_SIZE, dtype=np.float64)
    next_sample_time = time.perf_counter()

    for sample_index in range(WINDOW_SIZE):
        remaining_seconds = next_sample_time - time.perf_counter()
        if remaining_seconds > 0:
            time.sleep(remaining_seconds)

        samples[sample_index] = read_sensor(bus)
        sample_timestamps[sample_index] = time.perf_counter()
        next_sample_time += sample_period_seconds

    # Finish the nominal 128 / 500 s window period before inference starts.
    remaining_seconds = next_sample_time - time.perf_counter()
    if remaining_seconds > 0:
        time.sleep(remaining_seconds)

    measured_duration = sample_timestamps[-1] - sample_timestamps[0]
    if measured_duration <= 0:
        raise RuntimeError("Die gemessene Fensterdauer ist nicht positiv.")
    measured_sampling_rate_hz = (WINDOW_SIZE - 1) / measured_duration
    return samples, float(measured_sampling_rate_hz)


def format_mean(value: float | None, unit: str, decimals: int) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{decimals}f} {unit}".rstrip()


def print_summary(summary: LiveSummary, log_path: Path) -> None:
    print("\nLive-Monitor beendet.")
    print(f"Logdatei: {display_path(log_path)}")
    print(f"Fenster: {summary.window_count}")
    print(f"NORMAL: {summary.normal_count}")
    print(f"ANOMALY: {summary.anomaly_count}")
    print(
        "Mittlerer MSE: "
        + format_mean(summary.mean(summary.reconstruction_error_sum), "", 6)
    )
    print(
        "Mittlere Inferenzzeit: "
        + format_mean(summary.mean(summary.inference_time_sum_ms), "ms", 3)
    )
    print(
        "Mittlere gemessene Samplingrate: "
        + format_mean(summary.mean(summary.sampling_rate_sum_hz), "Hz", 1)
    )


def print_runtime_information(
    runtime: TFLiteRuntime, scaler: Any, configuration: LiveConfiguration
) -> None:
    print(
        "Profil: "
        + (configuration.profile_name if configuration.profile_name else "Clean-Standard")
    )
    print(f"Modell: {display_path(configuration.model_path)}")
    print(f"Scaler: {display_path(configuration.scaler_path)}")
    print(f"Runtime: {runtime.backend}")
    print(
        f"Input: {runtime.input_shape} {runtime.input_dtype.name} | "
        f"Output: {runtime.output_shape} {runtime.output_dtype.name}"
    )
    print(f"Threshold: {configuration.threshold:.16f}")
    print(
        "Scaler mean_: "
        + np.array2string(np.asarray(scaler.mean_), precision=9, separator=", ")
    )
    print(
        "Scaler scale_: "
        + np.array2string(np.asarray(scaler.scale_), precision=9, separator=", ")
    )
    print(f"Warm-up: {WARMUP_INFERENCES} künstliche Inferenzen (nicht geloggt)")


def run_live_monitor(
    runtime: TFLiteRuntime,
    scaler: Any,
    output_path: Path,
    max_windows: int | None,
    threshold: float = RECONSTRUCTION_ERROR_THRESHOLD,
) -> None:
    connect_sensor, read_sensor = load_sensor_access()
    bus = connect_sensor()
    summary = LiveSummary()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with output_path.open("x", encoding="utf-8", newline="", buffering=1) as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            handle.flush()

            print(f"Log: {display_path(output_path)}")
            print("Live-Erfassung gestartet. Beenden mit Ctrl+C.\n")
            try:
                while max_windows is None or summary.window_count < max_windows:
                    raw_window, measured_sampling_rate_hz = collect_window(
                        bus, read_sensor
                    )
                    scaled_window = scale_window(raw_window, scaler)
                    (
                        reconstruction_error,
                        predicted_label,
                        inference_time_ms,
                    ) = infer_window(runtime, scaled_window, threshold)

                    timestamp = datetime.now().astimezone()
                    window_index = summary.window_count + 1
                    writer.writerow(
                        {
                            "timestamp": timestamp.isoformat(timespec="milliseconds"),
                            "window_index": window_index,
                            "reconstruction_error": reconstruction_error,
                            "threshold": threshold,
                            "predicted_label": predicted_label,
                            "inference_time_ms": inference_time_ms,
                            "measured_sampling_rate_hz": measured_sampling_rate_hz,
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
                    print(
                        f"{timestamp:%H:%M:%S} | Window {window_index:04d} | "
                        f"MSE {reconstruction_error:.6f} | "
                        f"Threshold {threshold:.6f} | "
                        f"{status} | inference {inference_time_ms:.3f} ms | "
                        f"fs {measured_sampling_rate_hz:.1f} Hz",
                        flush=True,
                    )
                    if predicted_label:
                        print("*** ANOMALY DETECTED ***", flush=True)
            except KeyboardInterrupt:
                print("\nCtrl+C empfangen; beende Live-Erfassung sauber ...")
    finally:
        bus.close()
        print_summary(summary, output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Nicht überlappende ADXL345-Live-Inferenz mit dem validierten "
            "Float32-TFLite-Autoencoder."
        )
    )
    parser.add_argument(
        "--profile",
        default=None,
        help=(
            "Freigegebenes Setup-Profil unter profiles/<name> laden. "
            "Ohne Option bleibt der validierte Clean-Standard aktiv."
        ),
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Modell, Scaler, Shapes und Warm-up prüfen, ohne Sensorzugriff.",
    )
    parser.add_argument(
        "--max-windows",
        type=int,
        default=None,
        help="Nach dieser Fensterzahl automatisch beenden (Standard: bis Ctrl+C).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Neue CSV-Logdatei. Standard: im Results-Verzeichnis des aktiven "
            "Modus; vorhandene Logs erhalten einen neuen Run-Identifier."
        ),
    )
    arguments = parser.parse_args()
    if arguments.max_windows is not None and arguments.max_windows <= 0:
        parser.error("--max-windows muss positiv sein.")
    if arguments.self_test and arguments.output is not None:
        parser.error("--output wird beim --self-test nicht verwendet.")
    if arguments.profile is not None:
        try:
            validate_profile_name(arguments.profile)
        except ValueError as error:
            parser.error(str(error))
    return arguments


def main() -> None:
    arguments = parse_args()
    configuration = resolve_live_configuration(arguments.profile)
    scaler = load_scaler(configuration.scaler_path)
    runtime = load_tflite_runtime(configuration.model_path)
    warm_up(runtime, configuration.threshold)
    print_runtime_information(runtime, scaler, configuration)

    if arguments.self_test:
        print("Self-Test erfolgreich; kein Sensorzugriff und keine Logdatei.")
        return

    output_path = resolve_output_path(
        arguments.output, configuration.default_log_path
    )
    run_live_monitor(
        runtime,
        scaler,
        output_path,
        arguments.max_windows,
        configuration.threshold,
    )


if __name__ == "__main__":
    main()
