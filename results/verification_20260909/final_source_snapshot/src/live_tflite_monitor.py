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
import importlib.metadata
import json
import os
import re
import platform
import signal
import subprocess
import threading
from contextlib import closing, contextmanager
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

try:
    from live_pipeline import BufferedAcquisition, Sample, ProcessMetrics, decision_status, summarize_decisions
except ModuleNotFoundError:
    from src.live_pipeline import BufferedAcquisition, Sample, ProcessMetrics, decision_status, summarize_decisions


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "models" / "clean_comparison" / "autoencoder_float32.tflite"
SCALER_PATH = PROJECT_ROOT / "models" / "clean_comparison" / "scaler.joblib"
THRESHOLD_PATH = PROJECT_ROOT / "results" / "clean_tensorflow_threshold.json"
DEFAULT_LOG_PATH = PROJECT_ROOT / "results" / "live_runs" / "live_tflite_log.csv"
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
    "status", "error", "threshold_source", "runtime_backend",
    "window_start_timestamp", "window_complete_monotonic_ns", "decision_monotonic_ns",
    "queue_wait_ms", "preprocessing_time_ms", "decision_latency_ms", "window_formation_time_ms",
    "total_window_pipeline_time_ms", "queue_pending_windows", "windows_dropped",
    "gap_count", "overrun_count", "saturated_count", "process_cpu_percent_one_core",
    "process_rss_bytes", "process_lifetime_peak_rss_bytes",
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
    threshold_source: str = "PROFILE/P99"
    profile_sampling_rate_hz: float = 500.0


@dataclass
class LiveSummary:
    window_count: int = 0
    normal_count: int = 0
    invalid_count: int = 0
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
        if decision_status(predicted_label, reconstruction_error, 0) == "ERROR":
            self.invalid_count += 1
            return
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
        valid_count = self.window_count - self.invalid_count
        return total / valid_count if valid_count else None


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
            threshold_source="CLEAN/P99",
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
    if threshold_document.get("percentile") != 99:
        raise ValueError("Profilthreshold ist nicht P99-kalibriert.")
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
        default_log_path=DEFAULT_LOG_PATH.with_name(f"{profile_name}_live_tflite_log.csv"),
        profile_sampling_rate_hz=float(metadata["sampling_rate_hz"]),
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
    try:
        from ai_edge_litert.interpreter import Interpreter
        backend = f"ai_edge_litert.Interpreter {importlib.metadata.version('ai-edge-litert')} num_threads=1"
    except ImportError:
        import tensorflow as tf
        Interpreter = tf.lite.Interpreter
        backend = f"tensorflow.lite.Interpreter {tf.__version__} num_threads=1"
    interpreter = Interpreter(model_path=str(model_path), num_threads=1)
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
        backend=backend,
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
    if not np.all(np.isfinite(scaled_window)):
        raise ValueError("Modelleingabe enthält NaN/Inf.")
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("Threshold muss endlich und nichtnegativ sein.")
    model_input = scaled_window[np.newaxis, ...]

    start_ns = time.perf_counter_ns()
    runtime.interpreter.set_tensor(runtime.input_index, model_input)
    runtime.interpreter.invoke()
    reconstruction = np.asarray(
        runtime.interpreter.get_tensor(runtime.output_index)[0], dtype=np.float32
    )
    if reconstruction.shape != WINDOW_SHAPE or not np.all(np.isfinite(reconstruction)):
        raise ValueError("Modellausgabe hat ungültige Form oder enthält NaN/Inf.")
    reconstruction_error = float(
        np.mean(
            np.square(scaled_window - reconstruction),
            dtype=np.float64,
        )
    )
    if not np.isfinite(reconstruction_error):
        raise ValueError("Rekonstruktionsfehler ist nicht endlich; keine NORMAL-Entscheidung.")
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


def collect_window(*args: Any, **kwargs: Any) -> tuple[np.ndarray, float]:
    raise RuntimeError(
        "Software-Polling wurde stillgelegt: iter_live_measurements nutzt neue "
        "FIFO-Sensorwerte und speichert Empfangszeitstempel."
    )


@contextmanager
def cooperative_shutdown(stop_event: threading.Event):
    """SIGTERM/SIGINT: Reader stoppen; finally sichert Rohdaten und Manifest."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = {}
    def request_stop(signum: int, frame: Any) -> None:
        stop_event.set()
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, request_stop)
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def add_acquisition_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sensor-odr", type=float, default=200, help="Explizite ADXL345-ODR in Hz; Standard 200 (keine 500-Hz-Softwareabfrage).")
    parser.add_argument("--sensor-range", type=int, choices=(2, 4, 8, 16), default=2)
    parser.add_argument("--buffer-windows", type=int, default=4)
    parser.add_argument("--allow-sampling-mismatch", action="store_true", help="Nur Entwicklung: Legacy-Profil trotz abweichender Sensor-ODR anwenden; kein finaler P99-Vergleich.")
    parser.add_argument("--fan-pwm-setpoint", type=float, default=None, help="Extern vorgegebene PWM in Prozent dokumentieren; verändert keine Hardware.")
    parser.add_argument("--measured-rpm", type=float, default=None, help="Unabhängig gemessene Drehzahl, niemals aus PWM berechnet.")
    parser.add_argument("--rpm-source", default=None, help="Messverfahren/Quelle der angegebenen Drehzahl.")


def acquisition_options(arguments: argparse.Namespace) -> dict[str, Any]:
    return {name: getattr(arguments, name) for name in
            ("sensor_odr", "sensor_range", "buffer_windows", "allow_sampling_mismatch",
             "fan_pwm_setpoint", "measured_rpm", "rpm_source")}


def validate_acquisition_options(configuration: LiveConfiguration, *, sensor_odr: float,
                                 sensor_range: int, buffer_windows: int,
                                 allow_sampling_mismatch: bool, fan_pwm_setpoint: float | None,
                                 measured_rpm: float | None, rpm_source: str | None) -> None:
    if not np.isfinite(sensor_odr) or sensor_odr <= 0 or buffer_windows < 1:
        raise ValueError("Sensor-ODR und Pufferkapazität müssen positiv sein.")
    if sensor_range not in (2, 4, 8, 16):
        raise ValueError("Ungültiger Messbereich")
    if sensor_odr != configuration.profile_sampling_rate_hz and not allow_sampling_mismatch:
        raise ValueError(f"Sensor-ODR {sensor_odr:g} Hz != Profil {configuration.profile_sampling_rate_hz:g} Hz. "
                         "Neue kompatible Kalibrierung erforderlich; --allow-sampling-mismatch nur für Entwicklung.")
    if fan_pwm_setpoint is not None and (not np.isfinite(fan_pwm_setpoint) or not 0 <= fan_pwm_setpoint <= 100):
        raise ValueError("PWM-Vorgabe muss zwischen 0 und 100 liegen")
    if measured_rpm is not None and (not np.isfinite(measured_rpm) or measured_rpm < 0 or not rpm_source):
        raise ValueError("Drehzahl benötigt endlichen nichtnegativen Wert und --rpm-source")


def run_provenance(configuration: LiveConfiguration, runtime: TFLiteRuntime,
                   options: dict[str, Any], *, gui_enabled: bool, mode: str) -> dict[str, Any]:
    def git(*args: str) -> str:
        result = subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else "unavailable"
    paths = {"model": configuration.model_path, "scaler": configuration.scaler_path,
             "threshold": configuration.threshold_path}
    if configuration.profile_name:
        paths["profile"] = configuration.model_path.parent.parent / "profile.json"
    return {"schema_version": 1, "started_utc": datetime.now().astimezone().isoformat(),
            "status": "running", "mode": mode, "gui_enabled": gui_enabled,
            "host": platform.node(), "platform": platform.platform(), "python": sys.version,
            "python_executable": sys.executable, "command": sys.argv,
            "package_versions": {name: importlib.metadata.version(name) for name in ("numpy", "scikit-learn", "joblib", "psutil")},
            "git_commit": git("rev-parse", "HEAD"),
            "git_status": git("status", "--short"),
            "source_sha256": {str(p.relative_to(PROJECT_ROOT)): sha256_file(p)
                              for p in sorted((PROJECT_ROOT / "src").glob("*.py"))},
            "artifacts": {key: {"path": str(path), "sha256": sha256_file(path)} for key, path in paths.items()},
            "profile_name": configuration.profile_name,
            "profile_sampling_rate_hz": configuration.profile_sampling_rate_hz,
            "effective_threshold": configuration.threshold, "threshold_source": configuration.threshold_source,
            "sampling_mismatch": options["sensor_odr"] != configuration.profile_sampling_rate_hz,
            "final_p99_comparison_eligible": False,
            "scope": "Live-Entwicklung; unabhängige Zustandslabels und Vergleich aller Methoden separat erforderlich",
            "runtime_backend": runtime.backend, "configuration": options,
            "rpm_note": "Unabhängige Benutzermessung; keine Tachosensor-Erfassung" if options["measured_rpm"] is not None else "Nicht gemessen",
            "latency_definition": "host completion last sample -> score/classification available; incl queue + scaling + TFLite + score",
            "cpu_definition": "all process threads incl acquisition/preprocessing/libraries/GUI; 100 percent = one core; sampled between decisions",
            "memory_definition": "RSS at decision; lifetime peak is Linux ru_maxrss including initialization/warmup",
            "warmup_inferences_excluded": WARMUP_INFERENCES,
            "sampling_rate_field_definition": "measured_sampling_rate_hz = (N-1)/host read-completion span; FIFO bursts affect this value, not an independent ODR measurement",
            "sensor_loss_count_note": "gap/overrun events are evidence; exact lost sensor sample count is unknown; queue-dropped windows counted exactly"}


def iter_live_measurements(runtime: TFLiteRuntime, scaler: Any, configuration: LiveConfiguration,
                           output_path: Path, *, stop_event: threading.Event | None = None,
                           max_windows: int | None = None, gui_enabled: bool = False,
                           mode: str = "development_monitor", sensor_odr: float = 200,
                           sensor_range: int = 2, buffer_windows: int = 4,
                           allow_sampling_mismatch: bool = False,
                           fan_pwm_setpoint: float | None = None,
                           measured_rpm: float | None = None, rpm_source: str | None = None,
                           before_acquisition: Callable[[], Any] | None = None):
    options = dict(sensor_odr=sensor_odr, sensor_range=sensor_range, buffer_windows=buffer_windows,
                   allow_sampling_mismatch=allow_sampling_mismatch, fan_pwm_setpoint=fan_pwm_setpoint,
                   measured_rpm=measured_rpm, rpm_source=rpm_source)
    validate_acquisition_options(configuration, **options)
    stop = stop_event or threading.Event()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = output_path.with_suffix(".run.json")
    raw_path = output_path.with_suffix(".raw.csv")
    for path in (output_path, manifest_path, raw_path, raw_path.with_suffix(".events.jsonl")):
        if path.exists():
            raise FileExistsError(f"Ergebnis wird nicht überschrieben: {path}")
    manifest = run_provenance(configuration, runtime, options, gui_enabled=gui_enabled, mode=mode)
    with manifest_path.open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    bus = None
    acquisition = None
    processed = 0
    invalid = 0
    metrics = ProcessMetrics()
    try:
        connect_sensor, _ = load_sensor_access()
        try:
            from adxl345 import read_fresh_sample, sensor_configuration, reset_fifo
        except ModuleNotFoundError:
            from src.adxl345 import read_fresh_sample, sensor_configuration, reset_fifo
        bus = connect_sensor(odr_hz=sensor_odr, range_g=sensor_range, fifo=True)
        manifest["sensor"] = sensor_configuration(bus)
        def read(stop: threading.Event) -> Sample | None:
            sample = read_fresh_sample(bus, stop_event=stop)
            if sample is None:
                return None
            return Sample(sample.xyz_g, sample.monotonic_ns, time.time_ns(), sample.gap,
                          sample.overrun, sample.saturated,
                          {key: getattr(sample, key) for key in ("sample_index", "sensor_time_estimate_s", "fifo_depth", "read_duration_ns")})
        acquisition = BufferedAcquisition(read, raw_path, capacity=buffer_windows, stop_event=stop,
                                          max_samples=max_windows * WINDOW_SIZE if max_windows else None)
        with output_path.open("x", encoding="utf-8", newline="", buffering=1) as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            try:
                if before_acquisition is not None:
                    before_acquisition()
                reset_fifo(bus)
                acquisition.start()
                while not stop.is_set() and (not acquisition.done.is_set() or not acquisition.queue.empty()):
                    window = acquisition.get()
                    if window is None:
                        continue
                    start_ns = time.monotonic_ns()
                    error_message = ""
                    fatal = False
                    score, prediction, inference_ms, preprocessing_ms = float("nan"), -1, 0.0, 0.0
                    try:
                        if window.gap_count or window.overrun_count or window.saturated_count:
                            raise ValueError("Sensorfenster mit Lücke, Overrun oder Sättigung; Entscheidung ungültig")
                        scaled = scale_window(window.values, scaler)
                        preprocessing_ms = (time.monotonic_ns() - start_ns) / 1e6
                        score, prediction, inference_ms = infer_window(runtime, scaled, configuration.threshold)
                    except Exception as error:
                        error_message = f"{type(error).__name__}: {error}"
                        invalid += 1
                        fatal = not (window.gap_count or window.overrun_count or window.saturated_count)
                    decision_ns = time.monotonic_ns()
                    snapshot = acquisition.snapshot()
                    row = {"timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                           "window_index": window.index, "reconstruction_error": score,
                           "threshold": configuration.threshold, "threshold_source": configuration.threshold_source,
                           "predicted_label": prediction, "status": decision_status(prediction, score, configuration.threshold),
                           "error": error_message, "runtime_backend": runtime.backend,
                           "inference_time_ms": inference_ms, "measured_sampling_rate_hz": window.sampling_rate_hz,
                           "window_start_timestamp": datetime.fromtimestamp(window.first_utc_ns / 1e9).astimezone().isoformat(timespec="milliseconds"),
                           "window_complete_monotonic_ns": window.complete_ns, "decision_monotonic_ns": decision_ns,
                           "queue_wait_ms": (start_ns - window.complete_ns) / 1e6,
                           "preprocessing_time_ms": preprocessing_ms,
                           "decision_latency_ms": (decision_ns - window.complete_ns) / 1e6,
                           "window_formation_time_ms": (window.complete_ns - window.first_sample_ns) / 1e6,
                           "total_window_pipeline_time_ms": (decision_ns - window.first_sample_ns) / 1e6,
                           "queue_pending_windows": snapshot["queue_pending_windows"], "windows_dropped": snapshot["windows_dropped"],
                           "gap_count": window.gap_count, "overrun_count": window.overrun_count,
                           "saturated_count": window.saturated_count, **metrics.sample()}
                    writer.writerow(row)
                    handle.flush()
                    processed += 1
                    yield row
                    if fatal:
                        raise RuntimeError(error_message)
                if acquisition.error is not None:
                    raise RuntimeError(f"Sensorerfassung fehlgeschlagen: {acquisition.error}") from acquisition.error
                manifest["status"] = "stopped" if stop.is_set() else "completed"
            finally:
                handle.flush()
                os.fsync(handle.fileno())
    except (KeyboardInterrupt, GeneratorExit):
        manifest["status"] = "stopped"
        raise
    except BaseException as error:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        cleanup_errors = []
        if acquisition is not None:
            try:
                acquisition.stop()
            except BaseException as error:
                cleanup_errors.append(f"acquisition_stop: {type(error).__name__}: {error}")
        if bus is not None:
            try:
                bus.close()
            except BaseException as error:
                cleanup_errors.append(f"sensor_close: {type(error).__name__}: {error}")
        if acquisition is not None and acquisition.error is not None:
            manifest["status"] = "failed"
        if cleanup_errors:
            manifest["status"] = "failed"
            manifest["cleanup_errors"] = cleanup_errors
        manifest["ended_utc"] = datetime.now().astimezone().isoformat()
        manifest["decisions_logged"] = processed
        manifest["invalid_windows"] = invalid
        manifest["acquisition"] = acquisition.snapshot() if acquisition else None
        manifest["process_final"] = metrics.sample()
        if acquisition is not None and output_path.exists():
            try:
                manifest["latency_summary"] = summarize_decisions(output_path, acquisition.snapshot(), WINDOW_SIZE)
            except Exception as error:
                manifest["latency_summary_error"] = f"{type(error).__name__}: {error}"
        temporary = manifest_path.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(manifest_path)
        if cleanup_errors:
            raise RuntimeError("; ".join(cleanup_errors))


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
    print(f"ERROR/ungültig: {summary.invalid_count}")
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


def run_live_monitor(runtime: TFLiteRuntime, scaler: Any, output_path: Path,
                     max_windows: int | None, configuration: LiveConfiguration,
                     **options: Any) -> None:
    stop = threading.Event()
    summary = LiveSummary()
    try:
        with cooperative_shutdown(stop), closing(iter_live_measurements(
                runtime, scaler, configuration, output_path, stop_event=stop,
                max_windows=max_windows, **options)) as measurements:
            for row in measurements:
                summary.add(row["reconstruction_error"], row["predicted_label"],
                            row["inference_time_ms"], row["measured_sampling_rate_hz"])
                print(f"Window {row['window_index']:04d} | {row['status']} | "
                      f"MSE {row['reconstruction_error']:.6f} | "
                      f"Latenz {row['decision_latency_ms']:.3f} ms | "
                      f"Queue {row['queue_pending_windows']} | verworfen {row['windows_dropped']}", flush=True)
    finally:
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
        help="Nach dieser Zahl erfasster Fenster beenden; Pufferverluste werden separat gezählt.",
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
    add_acquisition_arguments(parser)
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
        configuration,
        **acquisition_options(arguments),
    )


if __name__ == "__main__":
    main()
