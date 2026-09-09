#!/usr/bin/env python3
"""Convert and evaluate the clean Keras autoencoder as Float32 TFLite.

The script deliberately keeps conversion, numerical validation, classification
evaluation and the resource benchmark in one reproducible Phase-5 workflow.
All public artifacts are created exclusively: an existing result is never
overwritten.  The resource benchmark itself runs in a fresh subprocess.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "masterarbeit_matplotlib")
)

import numpy as np
import psutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIRECTORY = PROJECT_ROOT / "models" / "clean_comparison"
DATA_DIRECTORY = PROJECT_ROOT / "data" / "clean_comparison"
RESULT_DIRECTORY = PROJECT_ROOT / "results"
FIGURE_DIRECTORY = PROJECT_ROOT / "figures"

KERAS_MODEL_PATH = MODEL_DIRECTORY / "autoencoder.keras"
TFLITE_MODEL_PATH = MODEL_DIRECTORY / "autoencoder_float32.tflite"
ISOLATION_FOREST_MODEL_PATH = MODEL_DIRECTORY / "isolation_forest.joblib"
X_TEST_PATH = DATA_DIRECTORY / "X_test.npy"
Y_TEST_PATH = DATA_DIRECTORY / "y_test.npy"
THRESHOLD_PATH = RESULT_DIRECTORY / "clean_tensorflow_threshold.json"
KERAS_METRICS_PATH = RESULT_DIRECTORY / "clean_tensorflow_test_metrics.json"
KERAS_PREDICTIONS_PATH = RESULT_DIRECTORY / "clean_tensorflow_test_predictions.csv"
ISOLATION_FOREST_METRICS_PATH = (
    RESULT_DIRECTORY / "clean_isolation_forest_metrics.json"
)
PHASE4_RESOURCE_DETAILS_PATH = RESULT_DIRECTORY / "resource_comparison_details.json"

TFLITE_TEST_METRICS_PATH = RESULT_DIRECTORY / "tflite_test_metrics.json"
TFLITE_RESOURCE_METRICS_PATH = RESULT_DIRECTORY / "tflite_resource_metrics.json"
EDGE_COMPARISON_PATH = RESULT_DIRECTORY / "edge_model_comparison.csv"
TFLITE_TIMINGS_PATH = RESULT_DIRECTORY / "tflite_inference_timings.csv"
TFLITE_PREDICTIONS_PATH = RESULT_DIRECTORY / "tflite_test_predictions.csv"

CONSISTENCY_FIGURE_PATH = (
    FIGURE_DIRECTORY / "clean_tflite_reconstruction_consistency.png"
)
METRICS_FIGURE_PATH = FIGURE_DIRECTORY / "clean_edge_model_metrics.png"
LATENCY_FIGURE_PATH = FIGURE_DIRECTORY / "clean_edge_model_latency.png"
RESOURCES_FIGURE_PATH = FIGURE_DIRECTORY / "clean_edge_model_resources.png"

EXPECTED_TEST_SHAPE = (702, 128, 3)
EXPECTED_LABEL_SHAPE = (702,)
EXPECTED_TFLITE_SHAPE = (1, 128, 3)
WARMUP_INFERENCES = 50
REPETITIONS = 5
WINDOW_SIZE = 128
SAMPLING_RATE_HZ = 500
WINDOW_CREATION_TIME_MS = WINDOW_SIZE / SAMPLING_RATE_HZ * 1000.0
RESOURCE_SAMPLE_INTERVAL_SECONDS = 0.010


def relative_path(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def package_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def output_paths() -> list[Path]:
    return [
        TFLITE_MODEL_PATH,
        TFLITE_TEST_METRICS_PATH,
        TFLITE_RESOURCE_METRICS_PATH,
        EDGE_COMPARISON_PATH,
        TFLITE_TIMINGS_PATH,
        TFLITE_PREDICTIONS_PATH,
        CONSISTENCY_FIGURE_PATH,
        METRICS_FIGURE_PATH,
        LATENCY_FIGURE_PATH,
        RESOURCES_FIGURE_PATH,
    ]


def ensure_outputs_do_not_exist() -> None:
    existing = [relative_path(path) for path in output_paths() if path.exists()]
    if existing:
        raise FileExistsError(
            "Phase-5-Ausgaben existieren bereits und werden nicht überschrieben: "
            + ", ".join(existing)
        )


def write_bytes_exclusive(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)


def write_text_exclusive(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(content)


def validate_inputs() -> tuple[np.ndarray, np.ndarray, float]:
    required_paths = [
        KERAS_MODEL_PATH,
        ISOLATION_FOREST_MODEL_PATH,
        X_TEST_PATH,
        Y_TEST_PATH,
        THRESHOLD_PATH,
        KERAS_METRICS_PATH,
        KERAS_PREDICTIONS_PATH,
        ISOLATION_FOREST_METRICS_PATH,
        PHASE4_RESOURCE_DETAILS_PATH,
    ]
    missing = [relative_path(path) for path in required_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Fehlende Eingaben: " + ", ".join(missing))

    x_test = np.load(X_TEST_PATH)
    y_test = np.asarray(np.load(Y_TEST_PATH), dtype=np.int64)
    if x_test.shape != EXPECTED_TEST_SHAPE:
        raise ValueError(
            f"X_test hat Shape {x_test.shape}, erwartet ist {EXPECTED_TEST_SHAPE}."
        )
    if y_test.shape != EXPECTED_LABEL_SHAPE:
        raise ValueError(
            f"y_test hat Shape {y_test.shape}, erwartet ist {EXPECTED_LABEL_SHAPE}."
        )
    if not np.all(np.isfinite(x_test)):
        raise ValueError("X_test enthält nicht-endliche Werte.")
    if set(np.unique(y_test).tolist()) - {0, 1}:
        raise ValueError("y_test enthält andere Labels als 0 und 1.")

    threshold_document = read_json(THRESHOLD_PATH)
    threshold = float(threshold_document["threshold"])
    if threshold_document.get("test_labels_used_for_threshold_selection") is not False:
        raise ValueError("Der gespeicherte Threshold ist nicht als test-unabhängig markiert.")
    return x_test, y_test, threshold


def normalize_shape(shape: Any) -> list[int | None]:
    return [None if value is None else int(value) for value in tuple(shape)]


def convert_to_float32_tflite(keras_model: Any) -> tuple[bytes, dict[str, Any]]:
    import tensorflow as tf

    keras_input_shape = normalize_shape(keras_model.input_shape)
    keras_output_shape = normalize_shape(keras_model.output_shape)
    if keras_input_shape[-2:] != [128, 3] or keras_output_shape[-2:] != [128, 3]:
        raise ValueError(
            "Das Keras-Modell besitzt nicht die erwartete (128, 3)-Schnittstelle: "
            f"Input={keras_input_shape}, Output={keras_output_shape}."
        )

    converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
    converter.optimizations = []
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
    tflite_bytes = converter.convert()
    if not tflite_bytes:
        raise RuntimeError("Die TFLite-Konvertierung lieferte kein Modell.")

    conversion = {
        "source_format": "Keras v3 .keras",
        "target_format": "TensorFlow Lite FlatBuffer",
        "converter_api": "tf.lite.TFLiteConverter.from_keras_model",
        "numeric_format": "Float32",
        "quantization": False,
        "optimizations": [],
        "supported_ops": ["TFLITE_BUILTINS"],
        "keras_input_shape": keras_input_shape,
        "keras_output_shape": keras_output_shape,
        "edge_inference_batch_shape": list(EXPECTED_TFLITE_SHAPE),
        "tensorflow_version": tf.__version__,
    }
    return tflite_bytes, conversion


def create_interpreter(tflite_model_path: Path) -> tuple[Any, dict[str, Any]]:
    import tensorflow as tf

    interpreter = tf.lite.Interpreter(model_path=str(tflite_model_path))
    interpreter.allocate_tensors()
    inputs = interpreter.get_input_details()
    outputs = interpreter.get_output_details()
    if len(inputs) != 1 or len(outputs) != 1:
        raise ValueError(
            f"Erwartet wird je ein TFLite-Input/-Output, erhalten: {len(inputs)}/{len(outputs)}."
        )

    input_detail = inputs[0]
    output_detail = outputs[0]
    input_shape = tuple(int(value) for value in input_detail["shape"])
    output_shape = tuple(int(value) for value in output_detail["shape"])
    input_dtype = np.dtype(input_detail["dtype"])
    output_dtype = np.dtype(output_detail["dtype"])
    if input_shape != EXPECTED_TFLITE_SHAPE:
        raise ValueError(f"TFLite-Input-Shape ist {input_shape}, erwartet {EXPECTED_TFLITE_SHAPE}.")
    if output_shape != EXPECTED_TFLITE_SHAPE:
        raise ValueError(
            f"TFLite-Output-Shape ist {output_shape}, erwartet {EXPECTED_TFLITE_SHAPE}."
        )
    if input_dtype != np.dtype(np.float32) or output_dtype != np.dtype(np.float32):
        raise TypeError(
            f"Float32 erwartet, erhalten Input={input_dtype.name}, Output={output_dtype.name}."
        )

    interface = {
        "input_name": str(input_detail["name"]),
        "input_index": int(input_detail["index"]),
        "input_shape": list(input_shape),
        "input_shape_signature": [
            int(value) for value in input_detail.get("shape_signature", input_detail["shape"])
        ],
        "input_dtype": input_dtype.name,
        "input_quantization_scale": float(input_detail["quantization"][0]),
        "input_quantization_zero_point": int(input_detail["quantization"][1]),
        "output_name": str(output_detail["name"]),
        "output_index": int(output_detail["index"]),
        "output_shape": list(output_shape),
        "output_shape_signature": [
            int(value)
            for value in output_detail.get("shape_signature", output_detail["shape"])
        ],
        "output_dtype": output_dtype.name,
        "output_quantization_scale": float(output_detail["quantization"][0]),
        "output_quantization_zero_point": int(output_detail["quantization"][1]),
    }
    return interpreter, interface


def invoke_tflite(interpreter: Any, interface: dict[str, Any], window: np.ndarray) -> np.ndarray:
    input_window = np.asarray(window[np.newaxis, ...], dtype=np.float32)
    interpreter.set_tensor(interface["input_index"], input_window)
    interpreter.invoke()
    return np.asarray(interpreter.get_tensor(interface["output_index"])[0])


def calculate_classification_metrics(
    y_true: np.ndarray, y_predicted: np.ndarray
) -> dict[str, float | int]:
    tn = int(np.count_nonzero((y_true == 0) & (y_predicted == 0)))
    fp = int(np.count_nonzero((y_true == 0) & (y_predicted == 1)))
    fn = int(np.count_nonzero((y_true == 1) & (y_predicted == 0)))
    tp = int(np.count_nonzero((y_true == 1) & (y_predicted == 1)))

    def divide(numerator: float, denominator: float) -> float:
        return float(numerator / denominator) if denominator else 0.0

    accuracy = divide(tp + tn, tn + fp + fn + tp)
    precision = divide(tp, tp + fp)
    recall = divide(tp, tp + fn)
    specificity = divide(tn, tn + fp)
    false_positive_rate = divide(fp, fp + tn)
    false_negative_rate = divide(fn, fn + tp)
    f1 = divide(2.0 * precision * recall, precision + recall)
    return {
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "sensitivity": recall,
        "f1": f1,
        "specificity": specificity,
        "false_positive_rate": false_positive_rate,
        "false_negative_rate": false_negative_rate,
    }


def load_saved_keras_predictions() -> tuple[np.ndarray, np.ndarray]:
    labels: list[int] = []
    scores: list[float] = []
    with KERAS_PREDICTIONS_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            labels.append(int(row["predicted_label"]))
            scores.append(float(row["reconstruction_error"]))
    if len(labels) != EXPECTED_TEST_SHAPE[0]:
        raise ValueError("Die gespeicherten Keras-Vorhersagen enthalten nicht 702 Zeilen.")
    return np.asarray(labels, dtype=np.int64), np.asarray(scores, dtype=np.float64)


def evaluate_numerical_consistency(
    keras_model: Any,
    tflite_model_path: Path,
    x_test: np.ndarray,
    y_test: np.ndarray,
    threshold: float,
) -> tuple[dict[str, Any], list[dict[str, Any]], np.ndarray]:
    interpreter, interface = create_interpreter(tflite_model_path)
    keras_reconstructions = np.empty(EXPECTED_TEST_SHAPE, dtype=np.float32)
    tflite_reconstructions = np.empty(EXPECTED_TEST_SHAPE, dtype=np.float32)

    for index, window in enumerate(x_test):
        keras_output = keras_model(
            np.asarray(window[np.newaxis, ...], dtype=np.float32), training=False
        ).numpy()[0]
        keras_reconstructions[index] = np.asarray(keras_output, dtype=np.float32)
        tflite_reconstructions[index] = invoke_tflite(interpreter, interface, window)

    # Keep the exact Phase-3/4 score arithmetic: subtract and square in
    # Float32, then perform only the mean reduction with Float64 accumulation.
    keras_errors = np.mean(
        np.square(x_test - keras_reconstructions), axis=(1, 2), dtype=np.float64
    )
    tflite_errors = np.mean(
        np.square(x_test - tflite_reconstructions), axis=(1, 2), dtype=np.float64
    )
    reconstruction_differences = np.abs(
        keras_reconstructions.astype(np.float64)
        - tflite_reconstructions.astype(np.float64)
    )
    error_differences = np.abs(keras_errors - tflite_errors)
    keras_predictions = (keras_errors > threshold).astype(np.int64)
    tflite_predictions = (tflite_errors > threshold).astype(np.int64)
    saved_predictions, saved_scores = load_saved_keras_predictions()

    if not np.array_equal(keras_predictions, saved_predictions):
        mismatch_count = int(np.count_nonzero(keras_predictions != saved_predictions))
        raise ValueError(
            f"Neu berechnete Keras-Entscheidungen weichen in {mismatch_count} Fenstern ab."
        )
    maximum_saved_score_difference = float(np.max(np.abs(keras_errors - saved_scores)))
    if maximum_saved_score_difference > 1e-12:
        raise ValueError(
            "Neu berechnete Keras-Scores stimmen nicht exakt mit Phase 3 überein: "
            f"maximale Abweichung={maximum_saved_score_difference:.3e}."
        )

    prediction_rows: list[dict[str, Any]] = []
    for index in range(EXPECTED_TEST_SHAPE[0]):
        prediction_rows.append(
            {
                "window_index": index,
                "true_label": int(y_test[index]),
                "tflite_predicted_label": int(tflite_predictions[index]),
                "keras_predicted_label": int(keras_predictions[index]),
                "tflite_reconstruction_error": float(tflite_errors[index]),
                "keras_reconstruction_error": float(keras_errors[index]),
                "absolute_error_difference": float(error_differences[index]),
                "threshold": threshold,
            }
        )

    consistency = {
        "compared_test_windows": int(x_test.shape[0]),
        "compared_reconstruction_values": int(reconstruction_differences.size),
        "maximum_absolute_reconstruction_difference": float(
            np.max(reconstruction_differences)
        ),
        "mean_absolute_reconstruction_difference": float(
            np.mean(reconstruction_differences)
        ),
        "maximum_absolute_reconstruction_error_difference": float(
            np.max(error_differences)
        ),
        "mean_absolute_reconstruction_error_difference": float(
            np.mean(error_differences)
        ),
        "keras_vs_tflite_prediction_disagreements": int(
            np.count_nonzero(keras_predictions != tflite_predictions)
        ),
        "keras_reference_validation": {
            "predictions_match_saved_phase3_predictions": True,
            "maximum_absolute_score_difference": maximum_saved_score_difference,
        },
    }
    return consistency, prediction_rows, tflite_errors


def percentile_summary(values_ms: np.ndarray) -> dict[str, float]:
    return {
        "mean_inference_ms": float(np.mean(values_ms)),
        "median_inference_ms": float(np.median(values_ms)),
        "std_inference_ms": float(np.std(values_ms)),
        "min_inference_ms": float(np.min(values_ms)),
        "max_inference_ms": float(np.max(values_ms)),
        "p95_inference_ms": float(np.percentile(values_ms, 95)),
        "p99_inference_ms": float(np.percentile(values_ms, 99)),
        "windows_per_second": float(1000.0 / np.mean(values_ms)),
        "realtime_factor": float(WINDOW_CREATION_TIME_MS / np.mean(values_ms)),
    }


def rss_mib(process: psutil.Process) -> float:
    return float(process.memory_info().rss / (1024.0**2))


def cpu_seconds(process: psutil.Process) -> float:
    cpu_times = process.cpu_times()
    return float(cpu_times.user + cpu_times.system)


class ResourceSampler:
    def __init__(self, process: psutil.Process) -> None:
        self.process = process
        self.rss_samples_mib: list[float] = []
        self.cpu_samples_percent: list[float] = []
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.rss_samples_mib.append(rss_mib(self.process))
                self.cpu_samples_percent.append(
                    float(self.process.cpu_percent(interval=None))
                )
            except (psutil.Error, ProcessLookupError):
                break
            self.stop_event.wait(RESOURCE_SAMPLE_INTERVAL_SECONDS)

    def start(self) -> None:
        self.process.cpu_percent(interval=None)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=2.0)
        try:
            self.rss_samples_mib.append(rss_mib(self.process))
        except (psutil.Error, ProcessLookupError):
            pass


def tflite_benchmark_worker(
    model_path: Path, output_path: Path, threshold: float
) -> None:
    if output_path.exists():
        raise FileExistsError(f"Worker-Ausgabe existiert bereits: {output_path}")

    process = psutil.Process(os.getpid())
    x_test = np.load(X_TEST_PATH)
    if x_test.shape != EXPECTED_TEST_SHAPE:
        raise ValueError(f"Unerwartete Test-Shape im Worker: {x_test.shape}")
    rss_before_framework_import = rss_mib(process)

    import_start_ns = time.perf_counter_ns()
    import tensorflow as tf

    framework_import_time_ms = (time.perf_counter_ns() - import_start_ns) / 1e6
    rss_before_load = rss_mib(process)

    load_start_ns = time.perf_counter_ns()
    interpreter, interface = create_interpreter(model_path)
    load_time_ms = (time.perf_counter_ns() - load_start_ns) / 1e6
    rss_after_load = rss_mib(process)

    def infer(window: np.ndarray) -> tuple[float, int]:
        reconstruction = invoke_tflite(interpreter, interface, window)
        score = float(
            np.mean(np.square(window - reconstruction), dtype=np.float64)
        )
        return score, int(score > threshold)

    for warmup_index in range(WARMUP_INFERENCES):
        infer(x_test[warmup_index % len(x_test)])

    sampler = ResourceSampler(process)
    timing_rows: list[dict[str, Any]] = []
    cpu_start = cpu_seconds(process)
    benchmark_start_ns = time.perf_counter_ns()
    sampler.start()
    try:
        for repetition in range(1, REPETITIONS + 1):
            for window_index, window in enumerate(x_test):
                inference_start_ns = time.perf_counter_ns()
                score, prediction = infer(window)
                inference_ns = time.perf_counter_ns() - inference_start_ns
                timing_rows.append(
                    {
                        "model_key": "tflite_float32_autoencoder",
                        "model": "TensorFlow Lite Float32 Autoencoder",
                        "repetition": repetition,
                        "window_index": window_index,
                        "inference_ms": inference_ns / 1e6,
                        "reconstruction_error": score,
                        "predicted_label": prediction,
                    }
                )
    finally:
        sampler.stop()
    benchmark_end_ns = time.perf_counter_ns()
    cpu_end = cpu_seconds(process)

    benchmark_wall_time_seconds = (benchmark_end_ns - benchmark_start_ns) / 1e9
    mean_cpu_percent = (
        (cpu_end - cpu_start) / benchmark_wall_time_seconds * 100.0
        if benchmark_wall_time_seconds
        else 0.0
    )
    latencies = np.asarray(
        [row["inference_ms"] for row in timing_rows], dtype=np.float64
    )
    summary: dict[str, Any] = percentile_summary(latencies)
    summary.update(
        {
            "model_key": "tflite_float32_autoencoder",
            "model": "TensorFlow Lite Float32 Autoencoder",
            "model_path": relative_path(TFLITE_MODEL_PATH),
            "threshold_path": relative_path(THRESHOLD_PATH),
            "threshold": threshold,
            "test_windows": EXPECTED_TEST_SHAPE[0],
            "warmup_inferences": WARMUP_INFERENCES,
            "repetitions": REPETITIONS,
            "measured_inferences": len(timing_rows),
            "runtime_backend": "tensorflow.lite.Interpreter",
            "framework_version": tf.__version__,
            "framework_import_time_ms": framework_import_time_ms,
            "load_time_ms": load_time_ms,
            "model_size_bytes": model_path.stat().st_size,
            "model_size_kb": model_path.stat().st_size / 1024.0,
            "model_size_mb": model_path.stat().st_size / (1024.0**2),
            "rss_before_framework_import_mb": rss_before_framework_import,
            "rss_before_load_mb": rss_before_load,
            "rss_after_load_mb": rss_after_load,
            "framework_import_ram_delta_mb": (
                rss_before_load - rss_before_framework_import
            ),
            "model_load_ram_delta_mb": rss_after_load - rss_before_load,
            "runtime_total_ram_delta_mb": (
                rss_after_load - rss_before_framework_import
            ),
            "mean_rss_during_inference_mb": float(
                np.mean(sampler.rss_samples_mib)
                if sampler.rss_samples_mib
                else rss_after_load
            ),
            "peak_rss_mb": float(
                max(sampler.rss_samples_mib)
                if sampler.rss_samples_mib
                else rss_after_load
            ),
            "rss_after_inference_mb": rss_mib(process),
            "mean_cpu_percent": mean_cpu_percent,
            "max_cpu_percent": float(
                max(sampler.cpu_samples_percent)
                if sampler.cpu_samples_percent
                else 0.0
            ),
            "resource_sample_count": len(sampler.rss_samples_mib),
            "resource_sample_interval_ms": (
                RESOURCE_SAMPLE_INTERVAL_SECONDS * 1000.0
            ),
            "benchmark_wall_time_seconds": benchmark_wall_time_seconds,
            "window_creation_time_ms": WINDOW_CREATION_TIME_MS,
            "latencies_exceeding_window_creation_time": int(
                np.count_nonzero(latencies > WINDOW_CREATION_TIME_MS)
            ),
            "interpreter_interface": interface,
        }
    )

    repetition_summaries: list[dict[str, Any]] = []
    for repetition in range(1, REPETITIONS + 1):
        repetition_values = np.asarray(
            [
                row["inference_ms"]
                for row in timing_rows
                if row["repetition"] == repetition
            ],
            dtype=np.float64,
        )
        repetition_summary: dict[str, Any] = {"repetition": repetition}
        repetition_summary.update(percentile_summary(repetition_values))
        repetition_summaries.append(repetition_summary)

    report = {
        "summary": summary,
        "repetition_summaries": repetition_summaries,
        "timings": timing_rows,
    }
    with output_path.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)


def run_benchmark_worker(
    temporary_model_path: Path, temporary_directory: Path, threshold: float
) -> tuple[dict[str, Any], str, str]:
    worker_output_path = temporary_directory / "tflite_worker_report.json"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--benchmark-worker",
        "--model-path",
        str(temporary_model_path),
        "--output-path",
        str(worker_output_path),
        "--threshold",
        repr(threshold),
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Der TFLite-Benchmark-Worker ist fehlgeschlagen.\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    report = read_json(worker_output_path)
    return report, completed.stdout, completed.stderr


def validate_worker_results(
    worker_report: dict[str, Any], prediction_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    expected_predictions = [
        int(row["tflite_predicted_label"]) for row in prediction_rows
    ]
    expected_scores = np.asarray(
        [row["tflite_reconstruction_error"] for row in prediction_rows],
        dtype=np.float64,
    )
    timing_rows = worker_report["timings"]
    if len(timing_rows) != REPETITIONS * EXPECTED_TEST_SHAPE[0]:
        raise ValueError("Der Worker lieferte nicht 5 × 702 Einzelmessungen.")

    maximum_score_difference = 0.0
    for repetition in range(1, REPETITIONS + 1):
        rows = [row for row in timing_rows if row["repetition"] == repetition]
        if len(rows) != EXPECTED_TEST_SHAPE[0]:
            raise ValueError(f"Wiederholung {repetition} ist unvollständig.")
        indices = [int(row["window_index"]) for row in rows]
        if indices != list(range(EXPECTED_TEST_SHAPE[0])):
            raise ValueError(f"Wiederholung {repetition} hat eine falsche Reihenfolge.")
        predictions = [int(row["predicted_label"]) for row in rows]
        if predictions != expected_predictions:
            mismatch_count = sum(
                first != second
                for first, second in zip(predictions, expected_predictions)
            )
            diagnostic_samples = [
                {
                    "window_index": int(rows[index]["window_index"]),
                    "worker_score": float(rows[index]["reconstruction_error"]),
                    "worker_prediction": int(rows[index]["predicted_label"]),
                    "evaluation_score": float(expected_scores[index]),
                    "evaluation_prediction": int(expected_predictions[index]),
                }
                for index in range(min(5, len(rows)))
            ]
            raise ValueError(
                f"Worker-Wiederholung {repetition}: {mismatch_count} Entscheidungen "
                f"abweichend; Threshold={worker_report['summary']['threshold']}; "
                f"Beispiele={diagnostic_samples}."
            )
        measured_scores = np.asarray(
            [row["reconstruction_error"] for row in rows], dtype=np.float64
        )
        maximum_score_difference = max(
            maximum_score_difference,
            float(np.max(np.abs(measured_scores - expected_scores))),
        )

    return {
        "all_repetitions_match_evaluation_predictions": True,
        "expected_window_count": EXPECTED_TEST_SHAPE[0],
        "maximum_absolute_score_difference": maximum_score_difference,
    }


def read_device_model() -> str | None:
    path = Path("/proc/device-tree/model")
    if not path.is_file():
        return None
    return path.read_bytes().decode("utf-8", errors="replace").rstrip("\x00\n")


def read_os_name() -> str:
    path = Path("/etc/os-release")
    if path.is_file():
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value.strip().strip('"')
        if "PRETTY_NAME" in values:
            return values["PRETTY_NAME"]
    return platform.platform()


def read_cpu_model() -> str | None:
    path = Path("/proc/cpuinfo")
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lower().startswith("model name") and ":" in line:
            return line.split(":", 1)[1].strip()
    return None


def read_temperatures() -> dict[str, list[float]]:
    try:
        return {
            group: [float(entry.current) for entry in entries]
            for group, entries in psutil.sensors_temperatures().items()
        }
    except (AttributeError, OSError):
        return {}


def collect_system_information() -> dict[str, Any]:
    frequency = psutil.cpu_freq()
    cpu_model = read_cpu_model()
    if cpu_model is None:
        try:
            cpu_model = read_json(PHASE4_RESOURCE_DETAILS_PATH)["system"]["cpu"][
                "model_name"
            ]
        except (FileNotFoundError, KeyError, TypeError):
            pass
    return {
        "device_model": read_device_model(),
        "cpu_model": cpu_model,
        "architecture": platform.machine(),
        "logical_cores": psutil.cpu_count(logical=True),
        "physical_cores": psutil.cpu_count(logical=False),
        "current_frequency_mhz": float(frequency.current) if frequency else None,
        "total_ram_bytes": int(psutil.virtual_memory().total),
        "total_ram_gib": float(psutil.virtual_memory().total / (1024.0**3)),
        "operating_system": read_os_name(),
        "kernel": platform.release(),
        "python_version": platform.python_version(),
        "tensorflow_version": package_version("tensorflow"),
        "keras_version": package_version("keras"),
        "numpy_version": np.__version__,
        "scikit_learn_version": package_version("scikit-learn"),
        "psutil_version": psutil.__version__,
        "standalone_ai_edge_litert_installed": package_version("ai-edge-litert")
        is not None,
        "standalone_tflite_runtime_installed": package_version("tflite-runtime")
        is not None,
    }


def build_edge_comparison_rows(
    tflite_metrics: dict[str, Any], tflite_resource: dict[str, Any]
) -> list[dict[str, Any]]:
    keras_metrics = read_json(KERAS_METRICS_PATH)["metrics"]
    isolation_metrics = read_json(ISOLATION_FOREST_METRICS_PATH)["metrics"]
    phase4_models = read_json(PHASE4_RESOURCE_DETAILS_PATH)["models"]
    keras_resource = phase4_models["tensorflow_autoencoder"]["summary"]
    isolation_resource = phase4_models["isolation_forest"]["summary"]

    configurations = [
        ("Keras TensorFlow Autoencoder", keras_metrics, keras_resource),
        ("TensorFlow Lite Float32 Autoencoder", tflite_metrics, tflite_resource),
        ("Isolation Forest", isolation_metrics, isolation_resource),
    ]
    rows: list[dict[str, Any]] = []
    for model_name, metrics, resources in configurations:
        rows.append(
            {
                "model": model_name,
                "accuracy": metrics["accuracy"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "specificity": metrics["specificity"],
                "false_positive_rate": metrics["false_positive_rate"],
                "false_negative_rate": metrics["false_negative_rate"],
                "tn": metrics["tn"],
                "fp": metrics["fp"],
                "fn": metrics["fn"],
                "tp": metrics["tp"],
                "model_size_bytes": resources["model_size_bytes"],
                "model_size_kb": resources["model_size_kb"],
                "load_time_ms": resources["load_time_ms"],
                "mean_inference_ms": resources["mean_inference_ms"],
                "median_inference_ms": resources["median_inference_ms"],
                "std_inference_ms": resources["std_inference_ms"],
                "p95_inference_ms": resources["p95_inference_ms"],
                "p99_inference_ms": resources["p99_inference_ms"],
                "max_inference_ms": resources["max_inference_ms"],
                "windows_per_second": resources["windows_per_second"],
                "realtime_factor": resources["realtime_factor"],
                "peak_rss_mb": resources["peak_rss_mb"],
                "mean_cpu_percent": resources["mean_cpu_percent"],
                "max_cpu_percent": resources["max_cpu_percent"],
            }
        )
    return rows


def dictionaries_to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        raise ValueError("Leere CSV-Ausgabe ist nicht erlaubt.")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def create_figures(
    temporary_directory: Path,
    comparison_rows: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
) -> dict[Path, bytes]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [
        "Keras\nAutoencoder",
        "TFLite Float32\nAutoencoder",
        "Isolation\nForest",
    ]
    colors = ["#1f77b4", "#2ca02c", "#ff7f0e"]
    figure_bytes: dict[Path, bytes] = {}

    keras_errors = np.asarray(
        [row["keras_reconstruction_error"] for row in prediction_rows]
    )
    tflite_errors = np.asarray(
        [row["tflite_reconstruction_error"] for row in prediction_rows]
    )
    true_labels = np.asarray([row["true_label"] for row in prediction_rows])
    figure, axis = plt.subplots(figsize=(8, 6))
    for label_value, name, color in ((0, "Normal", "#1f77b4"), (1, "Anomalie", "#d62728")):
        mask = true_labels == label_value
        axis.scatter(
            keras_errors[mask],
            tflite_errors[mask],
            s=18,
            alpha=0.65,
            label=name,
            color=color,
        )
    lower = float(min(np.min(keras_errors), np.min(tflite_errors)))
    upper = float(max(np.max(keras_errors), np.max(tflite_errors)))
    axis.plot([lower, upper], [lower, upper], "k--", linewidth=1.2, label="Identität")
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlabel("Keras Reconstruction MSE")
    axis.set_ylabel("TFLite Float32 Reconstruction MSE")
    axis.set_title("Numerische Konsistenz: Keras vs. TFLite Float32")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    temp_path = temporary_directory / CONSISTENCY_FIGURE_PATH.name
    figure.savefig(temp_path, dpi=300, bbox_inches="tight")
    plt.close(figure)
    figure_bytes[CONSISTENCY_FIGURE_PATH] = temp_path.read_bytes()

    metric_names = ["accuracy", "precision", "recall", "f1"]
    metric_labels = ["Accuracy", "Precision", "Recall", "F1"]
    x_positions = np.arange(len(metric_names))
    width = 0.25
    figure, axis = plt.subplots(figsize=(10, 6))
    for model_index, (label, color, row) in enumerate(
        zip(labels, colors, comparison_rows)
    ):
        offset = (model_index - 1) * width
        axis.bar(
            x_positions + offset,
            [float(row[name]) for name in metric_names],
            width,
            label=label,
            color=color,
        )
    axis.set_xticks(x_positions, metric_labels)
    axis.set_ylim(0.95, 1.002)
    axis.set_ylabel("Metrikwert")
    axis.set_title("Clean-Testmetriken der Edge-Modelle")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(loc="center left", bbox_to_anchor=(1.01, 0.5))
    figure.tight_layout()
    temp_path = temporary_directory / METRICS_FIGURE_PATH.name
    figure.savefig(temp_path, dpi=300, bbox_inches="tight")
    plt.close(figure)
    figure_bytes[METRICS_FIGURE_PATH] = temp_path.read_bytes()

    figure, axis = plt.subplots(figsize=(9, 6))
    x_positions = np.arange(len(labels))
    width = 0.36
    mean_values = [float(row["mean_inference_ms"]) for row in comparison_rows]
    p95_values = [float(row["p95_inference_ms"]) for row in comparison_rows]
    axis.bar(x_positions - width / 2, mean_values, width, label="Mittelwert")
    mean_bars = axis.containers[-1]
    axis.bar(x_positions + width / 2, p95_values, width, label="P95")
    p95_bars = axis.containers[-1]
    axis.axhline(
        WINDOW_CREATION_TIME_MS,
        color="#d62728",
        linestyle="--",
        linewidth=1.4,
        label="Fensterentstehung 256 ms",
    )
    axis.set_yscale("log")
    axis.set_ylim(min(mean_values + p95_values) * 0.45, 400.0)
    axis.set_xticks(x_positions, labels)
    axis.set_ylabel("End-to-End-Inferenzzeit (ms, logarithmisch)")
    axis.set_title("Einzelinferenz: Mittelwert und P95")
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    for bars, values in ((mean_bars, mean_values), (p95_bars, p95_values)):
        for bar, value in zip(bars, values):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                value * 1.12,
                f"{value:.3f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    figure.tight_layout()
    temp_path = temporary_directory / LATENCY_FIGURE_PATH.name
    figure.savefig(temp_path, dpi=300, bbox_inches="tight")
    plt.close(figure)
    figure_bytes[LATENCY_FIGURE_PATH] = temp_path.read_bytes()

    figure, axes = plt.subplots(1, 3, figsize=(15, 5.5))
    resource_fields = [
        ("model_size_kb", "Modellgröße (KiB, log)", True),
        ("peak_rss_mb", "Peak-RSS (MiB)", False),
        ("mean_cpu_percent", "Mittlere Prozess-CPU (%)", False),
    ]
    for axis, (field, ylabel, logarithmic) in zip(axes, resource_fields):
        values = [float(row[field]) for row in comparison_rows]
        bars = axis.bar(labels, values, color=colors)
        if logarithmic:
            axis.set_yscale("log")
        axis.set_ylabel(ylabel)
        axis.grid(axis="y", alpha=0.25)
        for bar, value in zip(bars, values):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                value,
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    figure.suptitle("Ressourcenvergleich der Edge-Modelle")
    figure.tight_layout()
    temp_path = temporary_directory / RESOURCES_FIGURE_PATH.name
    figure.savefig(temp_path, dpi=300, bbox_inches="tight")
    plt.close(figure)
    figure_bytes[RESOURCES_FIGURE_PATH] = temp_path.read_bytes()

    return figure_bytes


def run_phase5() -> None:
    ensure_outputs_do_not_exist()
    x_test, y_test, threshold = validate_inputs()
    system_information = collect_system_information()
    temperature_before = read_temperatures()

    import tensorflow as tf

    keras_model = tf.keras.models.load_model(KERAS_MODEL_PATH, compile=False)

    with tempfile.TemporaryDirectory(prefix="phase5_tflite_", dir="/tmp") as temp_name:
        temporary_directory = Path(temp_name)
        tflite_bytes, conversion = convert_to_float32_tflite(keras_model)
        temporary_model_path = temporary_directory / TFLITE_MODEL_PATH.name
        temporary_model_path.write_bytes(tflite_bytes)
        _, interface = create_interpreter(temporary_model_path)

        consistency, prediction_rows, tflite_errors = evaluate_numerical_consistency(
            keras_model,
            temporary_model_path,
            x_test,
            y_test,
            threshold,
        )
        tflite_predictions = np.asarray(
            [row["tflite_predicted_label"] for row in prediction_rows],
            dtype=np.int64,
        )
        tflite_metrics = calculate_classification_metrics(y_test, tflite_predictions)
        keras_reference_metrics = read_json(KERAS_METRICS_PATH)["metrics"]

        print("Starte separaten TFLite-Ressourcenbenchmark ...", flush=True)
        worker_report, worker_stdout, worker_stderr = run_benchmark_worker(
            temporary_model_path, temporary_directory, threshold
        )
        decision_validation = validate_worker_results(worker_report, prediction_rows)
        resource_summary = worker_report["summary"]

        comparison_rows = build_edge_comparison_rows(
            tflite_metrics, resource_summary
        )
        figure_bytes = create_figures(
            temporary_directory, comparison_rows, prediction_rows
        )

        model_size_bytes = len(tflite_bytes)
        test_metrics_document = {
            "experiment": "clean_comparison_phase5_float32_tflite_20260823",
            "model": "TensorFlow Lite Float32 Autoencoder",
            "source_model_path": relative_path(KERAS_MODEL_PATH),
            "tflite_model_path": relative_path(TFLITE_MODEL_PATH),
            "source_model_sha256": sha256_file(KERAS_MODEL_PATH),
            "tflite_model_sha256": sha256_bytes(tflite_bytes),
            "source_model_size_bytes": KERAS_MODEL_PATH.stat().st_size,
            "source_model_size_kb": KERAS_MODEL_PATH.stat().st_size / 1024.0,
            "tflite_model_size_bytes": model_size_bytes,
            "tflite_model_size_kb": model_size_bytes / 1024.0,
            "tflite_model_size_mb": model_size_bytes / (1024.0**2),
            "conversion": conversion,
            "interface": interface,
            "test_data_path": relative_path(X_TEST_PATH),
            "test_labels_path": relative_path(Y_TEST_PATH),
            "test_data_sha256": sha256_file(X_TEST_PATH),
            "test_labels_sha256": sha256_file(Y_TEST_PATH),
            "test_shape": list(x_test.shape),
            "test_window_count": int(x_test.shape[0]),
            "normal_test_windows": int(np.count_nonzero(y_test == 0)),
            "anomaly_test_windows": int(np.count_nonzero(y_test == 1)),
            "threshold": threshold,
            "threshold_path": relative_path(THRESHOLD_PATH),
            "threshold_sha256": sha256_file(THRESHOLD_PATH),
            "threshold_source": "Existing clean Keras validation threshold",
            "test_labels_used_for_threshold_selection": False,
            "decision_rule": {
                "normal": "reconstruction_error <= threshold",
                "anomaly": "reconstruction_error > threshold",
            },
            "numerical_consistency": consistency,
            "metrics": tflite_metrics,
            "confusion_matrix": {
                key: tflite_metrics[key] for key in ("tn", "fp", "fn", "tp")
            },
            "keras_reference_metrics": keras_reference_metrics,
            "metric_deltas_tflite_minus_keras": {
                key: float(tflite_metrics[key] - keras_reference_metrics[key])
                for key in (
                    "accuracy",
                    "precision",
                    "recall",
                    "f1",
                    "specificity",
                    "false_positive_rate",
                    "false_negative_rate",
                )
            },
            "tflite_reconstruction_error": {
                "mean": float(np.mean(tflite_errors)),
                "median": float(np.median(tflite_errors)),
                "minimum": float(np.min(tflite_errors)),
                "maximum": float(np.max(tflite_errors)),
            },
        }

        resource_metrics_document = {
            "experiment": "clean_comparison_phase5_float32_tflite_20260823",
            "model": "TensorFlow Lite Float32 Autoencoder",
            "summary": resource_summary,
            "repetition_summaries": worker_report["repetition_summaries"],
            "decision_validation": decision_validation,
            "benchmark": {
                "description": (
                    "End-to-end single-window TFLite inference including Float32 "
                    "input conversion, reconstruction retrieval, MSE and frozen "
                    "threshold decision; model/framework load and warm-up excluded."
                ),
                "separate_process": True,
                "test_shape": list(x_test.shape),
                "warmup_inferences": WARMUP_INFERENCES,
                "repetitions": REPETITIONS,
                "measured_inferences": REPETITIONS * len(x_test),
                "timing_clock": "time.perf_counter_ns",
                "resource_sample_interval_ms": (
                    RESOURCE_SAMPLE_INTERVAL_SECONDS * 1000.0
                ),
                "window_creation_time_ms": WINDOW_CREATION_TIME_MS,
                "model_load_definition": (
                    "tf.lite.Interpreter construction plus allocate_tensors after "
                    "the TensorFlow framework import."
                ),
                "rss_definition": (
                    "rss_before_load is measured after loading X_test and importing "
                    "TensorFlow. Peak RSS is sampled every 10 ms during inference."
                ),
                "cpu_percent_definition": (
                    "Mean is process CPU-time divided by inference benchmark wall-time; "
                    "100% is approximately one fully occupied core. Maximum is the "
                    "largest 10 ms psutil sample and may exceed 100% on four cores."
                ),
                "runtime_limitation": (
                    "No standalone ai-edge-litert or tflite-runtime package was "
                    "installed. The available tensorflow.lite.Interpreter therefore "
                    "requires the full TensorFlow import, which is included in process "
                    "RSS but excluded from model deserialization time."
                ),
                "comparison_limitation": (
                    "Keras and Isolation Forest values are the validated Phase-4 "
                    "measurements; TFLite was measured later with the same method and "
                    "platform, not simultaneously."
                ),
                "other_limitations": [
                    "Operating-system scheduling and background load were not controlled.",
                    "RSS peaks shorter than 10 ms may be missed.",
                    "CPU monitoring adds small overhead.",
                    "Five repetitions run consecutively after one warm-up and one load.",
                ],
            },
            "system": system_information,
            "temperature_before": temperature_before,
            "temperature_after": read_temperatures(),
            "input_artifacts": {
                "tflite_model_path": relative_path(TFLITE_MODEL_PATH),
                "tflite_model_sha256": sha256_bytes(tflite_bytes),
                "x_test_sha256": sha256_file(X_TEST_PATH),
                "threshold_sha256": sha256_file(THRESHOLD_PATH),
            },
            "worker_stdout": worker_stdout,
            "worker_stderr": worker_stderr,
        }

        test_metrics_text = json.dumps(
            test_metrics_document, indent=2, ensure_ascii=False
        ) + "\n"
        resource_metrics_text = json.dumps(
            resource_metrics_document, indent=2, ensure_ascii=False
        ) + "\n"
        comparison_csv_text = dictionaries_to_csv(comparison_rows)
        timings_csv_text = dictionaries_to_csv(worker_report["timings"])
        predictions_csv_text = dictionaries_to_csv(prediction_rows)

        # Commit only after conversion, evaluation, benchmark and figures succeeded.
        write_bytes_exclusive(TFLITE_MODEL_PATH, tflite_bytes)
        write_text_exclusive(TFLITE_TEST_METRICS_PATH, test_metrics_text)
        write_text_exclusive(TFLITE_RESOURCE_METRICS_PATH, resource_metrics_text)
        write_text_exclusive(EDGE_COMPARISON_PATH, comparison_csv_text)
        write_text_exclusive(TFLITE_TIMINGS_PATH, timings_csv_text)
        write_text_exclusive(TFLITE_PREDICTIONS_PATH, predictions_csv_text)
        for final_path, content in figure_bytes.items():
            write_bytes_exclusive(final_path, content)

    print("Phase 5 abgeschlossen.")
    print(
        f"TFLite: {model_size_bytes / 1024.0:.3f} KiB, "
        f"Accuracy={tflite_metrics['accuracy']:.6f}, "
        f"Mean={resource_summary['mean_inference_ms']:.6f} ms, "
        f"P95={resource_summary['p95_inference_ms']:.6f} ms"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert the existing clean Keras autoencoder to unquantized Float32 "
            "TensorFlow Lite, validate it and benchmark single-window inference."
        )
    )
    parser.add_argument("--benchmark-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--model-path", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--output-path", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--threshold", type=float, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    if arguments.benchmark_worker:
        if (
            arguments.model_path is None
            or arguments.output_path is None
            or arguments.threshold is None
        ):
            raise ValueError("Worker-Modus benötigt Modell, Ausgabe und Threshold.")
        tflite_benchmark_worker(
            arguments.model_path, arguments.output_path, arguments.threshold
        )
        return
    if any(
        value is not None
        for value in (
            arguments.model_path,
            arguments.output_path,
            arguments.threshold,
        )
    ):
        raise ValueError("Worker-Argumente sind nur mit --benchmark-worker erlaubt.")
    run_phase5()


if __name__ == "__main__":
    main()
