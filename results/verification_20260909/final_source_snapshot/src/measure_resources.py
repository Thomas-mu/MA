"""Benchmark clean TensorFlow and Isolation Forest inference on Raspberry Pi.

Each model is measured in a fresh subprocess. The primary latency observation
is one scaled (128, 3) window through model inference, score calculation and
the already frozen threshold decision. Model loading is measured separately.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

os.environ.setdefault("MPLCONFIGDIR", "/tmp/masterarbeit-matplotlib-cache")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import psutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "clean_comparison" / "X_test.npy"
RESULT_DIRECTORY = PROJECT_ROOT / "results"
FIGURE_DIRECTORY = PROJECT_ROOT / "figures"

SUMMARY_CSV_PATH = RESULT_DIRECTORY / "resource_comparison.csv"
DETAILS_JSON_PATH = RESULT_DIRECTORY / "resource_comparison_details.json"
TIMINGS_CSV_PATH = RESULT_DIRECTORY / "resource_inference_timings.csv"

FIGURE_PATHS = {
    "latency": FIGURE_DIRECTORY / "clean_resource_inference_time.png",
    "size": FIGURE_DIRECTORY / "clean_resource_model_size.png",
    "ram": FIGURE_DIRECTORY / "clean_resource_ram.png",
    "distribution": FIGURE_DIRECTORY / "clean_resource_latency_distribution.png",
}

MODEL_CONFIG = {
    "tensorflow_autoencoder": {
        "display_name": "TensorFlow Autoencoder",
        "model_path": (
            PROJECT_ROOT / "models" / "clean_comparison" / "autoencoder.keras"
        ),
        "threshold_path": (
            RESULT_DIRECTORY / "clean_tensorflow_threshold.json"
        ),
        "predictions_path": (
            RESULT_DIRECTORY / "clean_tensorflow_test_predictions.csv"
        ),
        "prediction_score_column": "reconstruction_error",
    },
    "isolation_forest": {
        "display_name": "Isolation Forest",
        "model_path": (
            PROJECT_ROOT
            / "models"
            / "clean_comparison"
            / "isolation_forest.joblib"
        ),
        "threshold_path": (
            RESULT_DIRECTORY / "clean_isolation_forest_threshold.json"
        ),
        "predictions_path": (
            RESULT_DIRECTORY / "clean_isolation_forest_predictions.csv"
        ),
        "prediction_score_column": "anomaly_score",
    },
}

EXPECTED_TEST_SHAPE = (702, 128, 3)
WARMUP_INFERENCES = 50
REPETITIONS = 5
SAMPLE_RATE_HZ = 500
WINDOW_SIZE = 128
WINDOW_CREATION_TIME_MS = WINDOW_SIZE / SAMPLE_RATE_HZ * 1000
RESOURCE_SAMPLE_INTERVAL_SECONDS = 0.01
BYTES_PER_MIB = 1024**2
BYTES_PER_KIB = 1024


def relative_path(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rss_mb(process: psutil.Process) -> float:
    return float(process.memory_info().rss / BYTES_PER_MIB)


def cpu_seconds(process: psutil.Process) -> float:
    times = process.cpu_times()
    return float(times.user + times.system)


class ResourceSampler:
    """Sample process RSS and CPU percentage during timed inference."""

    def __init__(
        self,
        process: psutil.Process,
        interval_seconds: float,
    ) -> None:
        self.process = process
        self.interval_seconds = interval_seconds
        self.rss_samples_mb: list[float] = []
        self.cpu_samples_percent: list[float] = []
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _sample(self) -> None:
        self.rss_samples_mb.append(rss_mb(self.process))
        self.cpu_samples_percent.append(
            float(self.process.cpu_percent(interval=None))
        )

    def _run(self) -> None:
        self._sample()
        while not self._stop_event.wait(self.interval_seconds):
            self._sample()

    def start(self) -> None:
        self.process.cpu_percent(interval=None)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join()
        self._sample()


def load_threshold(path: Path) -> float:
    with path.open(encoding="utf-8") as file:
        report = json.load(file)
    return float(report["threshold"])


def load_tensorflow_model(
    path: Path,
) -> tuple[object, str, Callable[[np.ndarray], tuple[float, int]]]:
    import tensorflow as tf

    model = tf.keras.models.load_model(path, compile=False)

    def infer(window: np.ndarray) -> tuple[float, int]:
        reconstruction = model(window[np.newaxis, ...], training=False).numpy()[0]
        score = float(
            np.mean(
                np.square(window - reconstruction),
                dtype=np.float64,
            )
        )
        return score, 0

    return model, tf.__version__, infer


def import_tensorflow_framework() -> str:
    import tensorflow as tf

    return tf.__version__


def load_isolation_forest_model(
    path: Path,
) -> tuple[object, str, Callable[[np.ndarray], tuple[float, int]]]:
    import joblib
    import sklearn

    model = joblib.load(path)

    def infer(window: np.ndarray) -> tuple[float, int]:
        flattened = window.reshape(1, 128 * 3)
        score = float(-model.score_samples(flattened)[0])
        return score, 0

    return model, sklearn.__version__, infer


def import_isolation_forest_framework() -> str:
    import joblib  # noqa: F401 - import cost is intentionally measured
    import sklearn
    from sklearn.ensemble import IsolationForest  # noqa: F401

    return sklearn.__version__


def percentile_summary(values_ms: np.ndarray) -> dict[str, float]:
    mean_ms = float(np.mean(values_ms))
    return {
        "mean_inference_ms": mean_ms,
        "median_inference_ms": float(np.median(values_ms)),
        "std_inference_ms": float(np.std(values_ms, ddof=0)),
        "min_inference_ms": float(np.min(values_ms)),
        "max_inference_ms": float(np.max(values_ms)),
        "p95_inference_ms": float(np.percentile(values_ms, 95)),
        "p99_inference_ms": float(np.percentile(values_ms, 99)),
        "windows_per_second": float(1000 / mean_ms),
        "realtime_factor": float(WINDOW_CREATION_TIME_MS / mean_ms),
    }


def benchmark_worker(model_key: str, output_path: Path) -> None:
    config = MODEL_CONFIG[model_key]
    model_path = config["model_path"]
    threshold_path = config["threshold_path"]
    process = psutil.Process(os.getpid())

    features = np.load(DATA_PATH, allow_pickle=False)
    if features.shape != EXPECTED_TEST_SHAPE:
        raise ValueError(
            f"Erwartete Testform {EXPECTED_TEST_SHAPE}, erhalten {features.shape}"
        )
    if features.dtype != np.float32:
        features = features.astype(np.float32)
    threshold = load_threshold(threshold_path)

    rss_before_framework_import_mb = rss_mb(process)
    framework_start_ns = time.perf_counter_ns()
    if model_key == "tensorflow_autoencoder":
        framework_version = import_tensorflow_framework()
        loader = load_tensorflow_model
    else:
        framework_version = import_isolation_forest_framework()
        loader = load_isolation_forest_model
    framework_import_time_ms = (
        time.perf_counter_ns() - framework_start_ns
    ) / 1_000_000
    rss_before_model_load_mb = rss_mb(process)

    load_start_ns = time.perf_counter_ns()
    model, loaded_framework_version, inference_without_decision = loader(model_path)
    model_load_time_ms = (
        time.perf_counter_ns() - load_start_ns
    ) / 1_000_000
    if loaded_framework_version != framework_version:
        raise RuntimeError("Inkonsistente Framework-Version während Modellladung.")
    rss_after_model_load_mb = rss_mb(process)

    def inference_with_decision(window: np.ndarray) -> tuple[float, int]:
        score, _ = inference_without_decision(window)
        prediction = int(score > threshold)
        return score, prediction

    for warmup_index in range(WARMUP_INFERENCES):
        inference_with_decision(features[warmup_index % len(features)])

    gc.collect()
    sampler = ResourceSampler(process, RESOURCE_SAMPLE_INTERVAL_SECONDS)
    timing_records: list[dict[str, float | int | str]] = []
    cpu_before = cpu_seconds(process)
    benchmark_start_ns = time.perf_counter_ns()
    sampler.start()

    for repetition in range(1, REPETITIONS + 1):
        for window_index, window in enumerate(features):
            start_ns = time.perf_counter_ns()
            score, prediction = inference_with_decision(window)
            elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            timing_records.append(
                {
                    "model_key": model_key,
                    "model": config["display_name"],
                    "repetition": repetition,
                    "window_index": window_index,
                    "inference_ms": elapsed_ms,
                    "anomaly_score": score,
                    "predicted_label": prediction,
                }
            )

    sampler.stop()
    benchmark_end_ns = time.perf_counter_ns()
    cpu_after = cpu_seconds(process)
    wall_time_seconds = (benchmark_end_ns - benchmark_start_ns) / 1_000_000_000
    rss_after_inference_mb = rss_mb(process)

    inference_values = np.asarray(
        [record["inference_ms"] for record in timing_records],
        dtype=np.float64,
    )
    summary = percentile_summary(inference_values)
    summary.update(
        {
            "model_key": model_key,
            "model": config["display_name"],
            "model_path": relative_path(model_path),
            "threshold_path": relative_path(threshold_path),
            "threshold": threshold,
            "test_windows": int(len(features)),
            "warmup_inferences": WARMUP_INFERENCES,
            "repetitions": REPETITIONS,
            "measured_inferences": int(len(timing_records)),
            "framework_version": framework_version,
            "framework_import_time_ms": float(framework_import_time_ms),
            "load_time_ms": float(model_load_time_ms),
            "model_size_bytes": int(model_path.stat().st_size),
            "model_size_kb": float(model_path.stat().st_size / BYTES_PER_KIB),
            "model_size_mb": float(model_path.stat().st_size / BYTES_PER_MIB),
            "rss_before_framework_import_mb": rss_before_framework_import_mb,
            "rss_before_load_mb": rss_before_model_load_mb,
            "rss_after_load_mb": rss_after_model_load_mb,
            "framework_import_ram_delta_mb": (
                rss_before_model_load_mb - rss_before_framework_import_mb
            ),
            "model_load_ram_delta_mb": (
                rss_after_model_load_mb - rss_before_model_load_mb
            ),
            "runtime_total_ram_delta_mb": (
                rss_after_model_load_mb - rss_before_framework_import_mb
            ),
            "mean_rss_during_inference_mb": float(
                np.mean(sampler.rss_samples_mb)
            ),
            "peak_rss_mb": float(max(sampler.rss_samples_mb)),
            "rss_after_inference_mb": rss_after_inference_mb,
            "mean_cpu_percent": float(
                (cpu_after - cpu_before) / wall_time_seconds * 100
            ),
            "max_cpu_percent": float(max(sampler.cpu_samples_percent)),
            "resource_sample_count": int(len(sampler.rss_samples_mb)),
            "resource_sample_interval_ms": (
                RESOURCE_SAMPLE_INTERVAL_SECONDS * 1000
            ),
            "benchmark_wall_time_seconds": float(wall_time_seconds),
            "window_creation_time_ms": WINDOW_CREATION_TIME_MS,
            "latencies_exceeding_window_creation_time": int(
                np.count_nonzero(inference_values > WINDOW_CREATION_TIME_MS)
            ),
        }
    )

    repetition_summaries: list[dict[str, float | int]] = []
    for repetition in range(1, REPETITIONS + 1):
        mask = np.fromiter(
            (
                record["repetition"] == repetition
                for record in timing_records
            ),
            dtype=bool,
            count=len(timing_records),
        )
        values = inference_values[mask]
        repetition_summaries.append(
            {
                "repetition": repetition,
                **percentile_summary(values),
            }
        )

    predictions_by_repetition: dict[str, list[int]] = {}
    for repetition in range(1, REPETITIONS + 1):
        predictions_by_repetition[str(repetition)] = [
            int(record["predicted_label"])
            for record in timing_records
            if record["repetition"] == repetition
        ]

    worker_report = {
        "summary": summary,
        "repetition_summaries": repetition_summaries,
        "predictions_by_repetition": predictions_by_repetition,
        "timing_records": timing_records,
    }
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(worker_report, file)

    # Explicitly release references before the worker process exits.
    del model
    del features
    gc.collect()


def read_expected_predictions(path: Path) -> tuple[list[int], list[float]]:
    predictions: list[int] = []
    scores: list[float] = []
    score_column = next(
        config["prediction_score_column"]
        for config in MODEL_CONFIG.values()
        if config["predictions_path"] == path
    )
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            predictions.append(int(row["predicted_label"]))
            scores.append(float(row[score_column]))
    return predictions, scores


def validate_worker_decisions(
    model_key: str,
    worker_report: dict[str, object],
) -> dict[str, float | int | bool]:
    config = MODEL_CONFIG[model_key]
    expected_predictions, expected_scores = read_expected_predictions(
        config["predictions_path"]
    )
    repeated_predictions = worker_report["predictions_by_repetition"]
    if len(expected_predictions) != EXPECTED_TEST_SHAPE[0]:
        raise ValueError("Gespeicherte Clean-Predictions haben falsche Länge.")

    for repetition in range(1, REPETITIONS + 1):
        measured = repeated_predictions[str(repetition)]
        if measured != expected_predictions:
            mismatches = sum(
                first != second
                for first, second in zip(measured, expected_predictions)
            )
            raise RuntimeError(
                f"{model_key}: {mismatches} Benchmark-Entscheidungen weichen "
                "von der Clean-Evaluation ab."
            )

    first_repetition_scores = [
        float(record["anomaly_score"])
        for record in worker_report["timing_records"]
        if record["repetition"] == 1
    ]
    score_difference = np.abs(
        np.asarray(first_repetition_scores) - np.asarray(expected_scores)
    )
    return {
        "all_repetitions_match_saved_predictions": True,
        "expected_window_count": len(expected_predictions),
        "maximum_absolute_score_difference": float(np.max(score_difference)),
    }


def package_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def read_device_model() -> str | None:
    for path in (
        Path("/proc/device-tree/model"),
        Path("/sys/firmware/devicetree/base/model"),
    ):
        if path.exists():
            return path.read_bytes().rstrip(b"\0").decode(errors="replace")
    return None


def read_os_name() -> str:
    os_release_path = Path("/etc/os-release")
    if not os_release_path.exists():
        return platform.platform()
    values: dict[str, str] = {}
    for line in os_release_path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    return values.get("PRETTY_NAME", platform.platform())


def read_cpu_information() -> dict[str, object]:
    fields: dict[str, str] = {}
    try:
        completed = subprocess.run(
            ["lscpu"],
            check=True,
            capture_output=True,
            text=True,
        )
        for line in completed.stdout.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip()] = value.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    frequency = psutil.cpu_freq()
    return {
        "model_name": fields.get("Model name", platform.processor() or None),
        "vendor_id": fields.get("Vendor ID"),
        "architecture": platform.machine(),
        "logical_cores": psutil.cpu_count(logical=True),
        "physical_cores": psutil.cpu_count(logical=False),
        "current_frequency_mhz": (
            float(frequency.current) if frequency is not None else None
        ),
        "minimum_frequency_mhz": (
            float(frequency.min) if frequency is not None else None
        ),
        "maximum_frequency_mhz": (
            float(frequency.max) if frequency is not None else None
        ),
    }


def read_temperatures() -> dict[str, list[float]]:
    temperatures: dict[str, list[float]] = {}
    try:
        for name, entries in psutil.sensors_temperatures().items():
            temperatures[name] = [float(entry.current) for entry in entries]
    except (AttributeError, OSError):
        pass
    return temperatures


def collect_system_information() -> dict[str, object]:
    virtual_memory = psutil.virtual_memory()
    return {
        "device_model": read_device_model(),
        "cpu": read_cpu_information(),
        "architecture": platform.machine(),
        "total_ram_bytes": int(virtual_memory.total),
        "total_ram_gib": float(virtual_memory.total / 1024**3),
        "operating_system": read_os_name(),
        "kernel": platform.release(),
        "python_version": platform.python_version(),
        "tensorflow_version": package_version("tensorflow"),
        "numpy_version": package_version("numpy"),
        "scikit_learn_version": package_version("scikit-learn"),
        "psutil_version": package_version("psutil"),
    }


def output_paths() -> list[Path]:
    return [
        SUMMARY_CSV_PATH,
        DETAILS_JSON_PATH,
        TIMINGS_CSV_PATH,
        *FIGURE_PATHS.values(),
    ]


def ensure_outputs_do_not_exist() -> None:
    existing = [relative_path(path) for path in output_paths() if path.exists()]
    if existing:
        raise FileExistsError(
            "Benchmark-Ausgaben existieren bereits und werden nicht "
            "überschrieben: " + ", ".join(existing)
        )


def run_worker_process(model_key: str, temporary_directory: Path) -> dict[str, object]:
    worker_output = temporary_directory / f"{model_key}.json"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        model_key,
        "--worker-output",
        str(worker_output),
    ]
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = "42"
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Benchmark-Worker {model_key} fehlgeschlagen.\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    with worker_output.open(encoding="utf-8") as file:
        report = json.load(file)
    report["worker_stdout"] = completed.stdout
    report["worker_stderr"] = completed.stderr
    return report


def write_summary_csv(worker_reports: dict[str, dict[str, object]]) -> None:
    fieldnames = [
        "model",
        "model_size_kb",
        "load_time_ms",
        "mean_inference_ms",
        "median_inference_ms",
        "std_inference_ms",
        "min_inference_ms",
        "max_inference_ms",
        "p95_inference_ms",
        "p99_inference_ms",
        "windows_per_second",
        "realtime_factor",
        "rss_before_load_mb",
        "rss_after_load_mb",
        "model_load_ram_delta_mb",
        "peak_rss_mb",
        "mean_cpu_percent",
        "max_cpu_percent",
    ]
    with SUMMARY_CSV_PATH.open("x", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for model_key in MODEL_CONFIG:
            summary = worker_reports[model_key]["summary"]
            writer.writerow({field: summary[field] for field in fieldnames})


def write_timings_csv(worker_reports: dict[str, dict[str, object]]) -> None:
    fieldnames = [
        "model_key",
        "model",
        "repetition",
        "window_index",
        "inference_ms",
        "anomaly_score",
        "predicted_label",
    ]
    with TIMINGS_CSV_PATH.open("x", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for model_key in MODEL_CONFIG:
            writer.writerows(worker_reports[model_key]["timing_records"])


def create_figures(worker_reports: dict[str, dict[str, object]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    model_keys = list(MODEL_CONFIG)
    labels = [MODEL_CONFIG[key]["display_name"] for key in model_keys]
    colors = ["tab:blue", "tab:orange"]

    def annotated_bar(
        values: list[float],
        ylabel: str,
        title: str,
        output_path: Path,
        *,
        logarithmic: bool = False,
    ) -> None:
        figure, axis = plt.subplots(figsize=(9, 6))
        bars = axis.bar(labels, values, color=colors)
        if logarithmic:
            axis.set_yscale("log")
        axis.set_ylabel(ylabel)
        axis.set_title(title)
        axis.grid(axis="y", alpha=0.25)
        for bar, value in zip(bars, values):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                value,
                f"{value:.3f}",
                ha="center",
                va="bottom",
            )
        figure.tight_layout()
        figure.savefig(output_path, dpi=250)
        plt.close(figure)

    annotated_bar(
        [
            float(worker_reports[key]["summary"]["mean_inference_ms"])
            for key in model_keys
        ],
        "Mittlere End-to-End-Inferenzzeit (ms)",
        "Clean Edge-Benchmark: Einzelinferenz",
        FIGURE_PATHS["latency"],
    )
    annotated_bar(
        [
            float(worker_reports[key]["summary"]["model_size_kb"])
            for key in model_keys
        ],
        "Modellgröße (KiB, logarithmische Skala)",
        "Clean Edge-Benchmark: Modellgröße",
        FIGURE_PATHS["size"],
        logarithmic=True,
    )

    positions = np.arange(len(model_keys))
    width = 0.25
    figure, axis = plt.subplots(figsize=(10, 6))
    before = [
        float(worker_reports[key]["summary"]["rss_before_load_mb"])
        for key in model_keys
    ]
    after = [
        float(worker_reports[key]["summary"]["rss_after_load_mb"])
        for key in model_keys
    ]
    peak = [
        float(worker_reports[key]["summary"]["peak_rss_mb"])
        for key in model_keys
    ]
    axis.bar(positions - width, before, width, label="Vor Modellladen")
    axis.bar(positions, after, width, label="Nach Modellladen")
    axis.bar(positions + width, peak, width, label="Peak während Inferenz")
    axis.set_xticks(positions, labels)
    axis.set_ylabel("Prozess-RSS (MiB)")
    axis.set_title("Clean Edge-Benchmark: Prozessspeicher")
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(FIGURE_PATHS["ram"], dpi=250)
    plt.close(figure)

    timing_values = [
        [
            float(record["inference_ms"])
            for record in worker_reports[key]["timing_records"]
        ]
        for key in model_keys
    ]
    figure, axis = plt.subplots(figsize=(10, 6))
    axis.boxplot(timing_values, tick_labels=labels, showfliers=True)
    axis.set_yscale("log")
    axis.set_ylabel("End-to-End-Inferenzzeit (ms, logarithmische Skala)")
    axis.set_title("Clean Edge-Benchmark: Latenzverteilung")
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(FIGURE_PATHS["distribution"], dpi=250)
    plt.close(figure)


def run_benchmark() -> None:
    ensure_outputs_do_not_exist()
    required_paths = [DATA_PATH]
    for config in MODEL_CONFIG.values():
        required_paths.extend(
            [
                config["model_path"],
                config["threshold_path"],
                config["predictions_path"],
            ]
        )
    missing = [relative_path(path) for path in required_paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Fehlende Benchmark-Eingaben: " + ", ".join(missing))

    features = np.load(DATA_PATH, mmap_mode="r", allow_pickle=False)
    if features.shape != EXPECTED_TEST_SHAPE:
        raise ValueError(f"Unerwartete Clean-Testform: {features.shape}")
    del features

    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    FIGURE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    system_information = collect_system_information()
    temperature_before = read_temperatures()
    worker_reports: dict[str, dict[str, object]] = {}

    with tempfile.TemporaryDirectory(prefix="edge-benchmark-") as temp_directory:
        temporary_directory = Path(temp_directory)
        for model_key in MODEL_CONFIG:
            print(f"Starte separaten Worker: {MODEL_CONFIG[model_key]['display_name']}")
            report = run_worker_process(model_key, temporary_directory)
            report["decision_validation"] = validate_worker_decisions(
                model_key, report
            )
            worker_reports[model_key] = report
            summary = report["summary"]
            print(
                f"  Mean={summary['mean_inference_ms']:.6f} ms, "
                f"P95={summary['p95_inference_ms']:.6f} ms, "
                f"Peak RSS={summary['peak_rss_mb']:.2f} MiB"
            )

    temperature_after = read_temperatures()
    write_summary_csv(worker_reports)
    write_timings_csv(worker_reports)
    create_figures(worker_reports)

    details_models: dict[str, object] = {}
    for model_key, report in worker_reports.items():
        details_models[model_key] = {
            "summary": report["summary"],
            "repetition_summaries": report["repetition_summaries"],
            "decision_validation": report["decision_validation"],
            "worker_stdout": report["worker_stdout"],
            "worker_stderr": report["worker_stderr"],
        }

    tensorflow_size = float(
        worker_reports["tensorflow_autoencoder"]["summary"]["model_size_bytes"]
    )
    isolation_size = float(
        worker_reports["isolation_forest"]["summary"]["model_size_bytes"]
    )
    details = {
        "benchmark": {
            "description": (
                "End-to-end single-window inference including score and frozen "
                "threshold decision, excluding model/framework load and warm-up."
            ),
            "execution_order": list(MODEL_CONFIG),
            "separate_process_per_model": True,
            "test_data_path": relative_path(DATA_PATH),
            "test_data_sha256": sha256(DATA_PATH),
            "test_shape": list(EXPECTED_TEST_SHAPE),
            "window_size": WINDOW_SIZE,
            "sampling_rate_hz": SAMPLE_RATE_HZ,
            "window_creation_time_ms": WINDOW_CREATION_TIME_MS,
            "warmup_inferences_per_model": WARMUP_INFERENCES,
            "repetitions": REPETITIONS,
            "measured_inferences_per_model": (
                EXPECTED_TEST_SHAPE[0] * REPETITIONS
            ),
            "timing_clock": "time.perf_counter_ns",
            "resource_sample_interval_ms": (
                RESOURCE_SAMPLE_INTERVAL_SECONDS * 1000
            ),
            "model_load_definition": (
                "Model deserialization after framework import; compile=False "
                "for TensorFlow inference."
            ),
            "cpu_percent_definition": (
                "Mean is process CPU-time divided by benchmark wall-time; "
                "100% corresponds approximately to one fully occupied core. "
                "Maximum is the largest 10 ms psutil process sample and may "
                "exceed 100% on a multicore system."
            ),
            "rss_definition": (
                "rss_before_load is measured after framework import and test "
                "array loading; runtime_total_ram_delta also includes framework "
                "import. Peak RSS is sampled every 10 ms during inference."
            ),
            "limitations": [
                "Model and framework load times are single cold-process observations.",
                "Operating-system scheduling and background load were not controlled.",
                "RSS peaks shorter than the 10 ms sampling interval may be missed.",
                "CPU monitoring adds small and comparable overhead to both workers.",
                "Five repetitions run consecutively after one warm-up and one load.",
            ],
        },
        "system": system_information,
        "temperature_before": temperature_before,
        "temperature_after": temperature_after,
        "input_artifacts": {
            model_key: {
                "model_path": relative_path(config["model_path"]),
                "model_sha256": sha256(config["model_path"]),
                "threshold_path": relative_path(config["threshold_path"]),
                "threshold_sha256": sha256(config["threshold_path"]),
            }
            for model_key, config in MODEL_CONFIG.items()
        },
        "models": details_models,
        "model_size_ratio_isolation_forest_to_tensorflow": (
            isolation_size / tensorflow_size
        ),
        "artifacts": {
            "summary_csv": relative_path(SUMMARY_CSV_PATH),
            "details_json": relative_path(DETAILS_JSON_PATH),
            "timings_csv": relative_path(TIMINGS_CSV_PATH),
            "figures": [relative_path(path) for path in FIGURE_PATHS.values()],
        },
    }
    with DETAILS_JSON_PATH.open("x", encoding="utf-8") as file:
        json.dump(details, file, indent=2, ensure_ascii=False)

    print("\nRessourcenbenchmark abgeschlossen.")
    print(f"Zusammenfassung: {relative_path(SUMMARY_CSV_PATH)}")
    print(f"Details: {relative_path(DETAILS_JSON_PATH)}")
    print(f"Einzeltimings: {relative_path(TIMINGS_CSV_PATH)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--worker",
        choices=sorted(MODEL_CONFIG),
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--worker-output",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.worker is not None:
        if args.worker_output is None:
            raise ValueError("--worker-output wird im Worker-Modus benötigt.")
        benchmark_worker(args.worker, args.worker_output)
    else:
        run_benchmark()


if __name__ == "__main__":
    main()
