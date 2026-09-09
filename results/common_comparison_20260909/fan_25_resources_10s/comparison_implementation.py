"""Gemeinsamer, eingefrorener RMS/IF/Float32-TFLite-Vergleich.

Bestehende Profile bleiben unverändert. Ganze Aufnahmen werden vor der
Fensterbildung zugeordnet. `calibrate` liest ausschließlich normale Train/Val-
Aufnahmen; `evaluate` besitzt absichtlich keinen Trainings- oder Schwellenpfad.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AXES = ("x_g", "y_g", "z_g")
METHODS = ("rms", "isolation_forest", "tflite_autoencoder")
IF_PARAMETERS = dict(n_estimators=200, max_samples="auto", contamination="auto",
                     max_features=1.0, bootstrap=False, n_jobs=1, random_state=42)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: dict) -> None:
    # NaN/Infinity in wissenschaftlichen Ergebnisdateien sind keine gültigen Zahlen.
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def provenance() -> dict:
    def git(*args):
        result = subprocess.run(["git", *args], cwd=ROOT, text=True,
                                capture_output=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    versions = {}
    for package in ("numpy", "scikit-learn", "joblib", "psutil", "tensorflow",
                    "ai-edge-litert", "tflite-runtime"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    model_path = Path("/proc/device-tree/model")
    return {"created_at_utc": datetime.now(timezone.utc).isoformat(),
            "command": sys.argv, "working_directory": str(Path.cwd()),
            "code_commit": git("rev-parse", "HEAD"),
            "git_status_porcelain": git("status", "--porcelain"),
            "implementation_sha256": sha256(Path(__file__)),
            "python": sys.version, "python_executable": sys.executable,
            "platform": platform.platform(), "hostname": platform.node(),
            "device_model": (model_path.read_text().strip("\x00\n")
                             if model_path.exists() else None),
            "logical_cpu_count": os.cpu_count(), "packages": versions}


def resolve_source(path: str, base: Path = ROOT) -> Path:
    candidate = Path(path)
    return candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()


def finite_score(score: float, threshold: float) -> int:
    if not math.isfinite(score) or not math.isfinite(threshold):
        raise ValueError("Ungültiger Score oder Schwellenwert: keine NORMAL-Entscheidung.")
    return int(score > threshold)


def p99(scores: np.ndarray) -> float:
    scores = np.asarray(scores, dtype=np.float64)
    if scores.ndim != 1 or len(scores) == 0 or not np.isfinite(scores).all():
        raise ValueError("P99 benötigt nichtleere, endliche normale Validierungsscores.")
    return float(np.percentile(scores, 99, method="linear"))


def load_recording(path: Path, *, label: int, state: str) -> tuple[np.ndarray, np.ndarray, dict]:
    if label not in (0, 1) or not isinstance(state, str) or not state.strip():
        raise ValueError("Jede Aufnahme benötigt ein binäres Label und einen Zustandsnamen.")
    times, samples = [], []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not {"timestamp_s", *AXES}.issubset(reader.fieldnames or []):
            raise ValueError(f"{path}: timestamp_s und {AXES} erforderlich.")
        for index, row in enumerate(reader):
            if "label" in row and float(row["label"]) != label:
                raise ValueError(f"{path}:{index + 2}: gemischtes/falsches Zustandslabel.")
            times.append(float(row["timestamp_s"]))
            samples.append([float(row[axis]) for axis in AXES])
    timestamps = np.asarray(times, dtype=np.float64)
    values = np.asarray(samples, dtype=np.float32)
    if len(values) < 2 or not np.isfinite(values).all() or not np.isfinite(timestamps).all():
        raise ValueError(f"{path}: leere, zu kurze oder nichtendliche Aufnahme.")
    differences = np.diff(timestamps)
    if np.any(differences <= 0):
        raise ValueError(f"{path}: Zeitstempel müssen streng ansteigen.")
    digest = hashlib.sha256(values.tobytes() + timestamps.tobytes()).hexdigest()
    report = {"path": str(path.resolve()), "sha256": sha256(path),
              "sample_content_sha256": digest, "sample_count": len(values),
              "label": label, "state": state,
              "timestamp_rate_hz": float((len(values) - 1) / (timestamps[-1] - timestamps[0])),
              "timestamp_interval_median_s": float(np.median(differences)),
              "timestamp_interval_max_s": float(differences.max()),
              "timestamp_note": "Zeitstempelrate belegt allein keine neuen Sensorwerte."}
    return values, timestamps, report


def make_windows(values: np.ndarray, timestamps: np.ndarray, window_size: int,
                 step_size: int, recording: dict) -> tuple[np.ndarray, list[dict]]:
    if window_size < 1 or step_size < 1 or step_size > window_size:
        raise ValueError("Fenster-/Schrittweite müssen positiv sein; Schrittweite <= Fenster.")
    starts = list(range(0, len(values) - window_size + 1, step_size))
    if not starts:
        raise ValueError(f"{recording['path']}: kein vollständiges Fenster.")
    windows = np.stack([values[start:start + window_size] for start in starts])
    metadata = [{"recording": recording["path"], "recording_sha256": recording["sha256"],
                 "window_index": index, "start_sample": start,
                 "end_sample_exclusive": start + window_size,
                 "start_timestamp_s": float(timestamps[start]),
                 "end_timestamp_s": float(timestamps[start + window_size - 1]),
                 "label": recording["label"], "state": recording["state"]}
                for index, start in enumerate(starts)]
    recording["windows"] = len(windows)
    recording["trailing_samples_excluded"] = len(values) - (starts[-1] + window_size)
    return windows, metadata


def assert_disjoint(recordings: list[dict]) -> None:
    for key in ("path", "sha256", "sample_content_sha256"):
        seen = set()
        for recording in recordings:
            value = recording[key]
            if value in seen:
                raise ValueError(f"Aufnahme mehrfach/zwischen Splits wiederverwendet ({key}): {recording['path']}")
            seen.add(value)


def standardize(raw: np.ndarray, scaler: dict) -> np.ndarray:
    # Entspricht StandardScaler.transform auf Float32, ohne sklearn für RMS zu laden.
    values = np.array(raw, dtype=np.float32, copy=True)
    # sklearn 1.9 castet mean_/scale_ vor beiden In-place-Schritten auf X.dtype.
    mean = np.asarray(scaler["mean"], dtype=np.float32)
    scale = np.asarray(scaler["scale"], dtype=np.float32)
    if values.ndim != 2 or values.shape[1] != 3 or not np.isfinite(values).all():
        raise ValueError("Erwartet wird ein endliches Rohfenster H×3.")
    if mean.shape != (3,) or scale.shape != (3,) or not np.isfinite(mean).all() or not np.isfinite(scale).all() or np.any(scale <= 0):
        raise ValueError("Ungültige Skalierungsparameter.")
    np.subtract(values, mean, out=values, casting="unsafe")
    np.divide(values, scale, out=values, casting="unsafe")
    if not np.isfinite(values).all():
        raise ValueError("Skalierung erzeugte ungültige Werte.")
    return values


def rms_score(standardized: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(standardized), dtype=np.float64)))


def load_interpreter(model: Path, runtime: str, threads: int):
    if runtime in ("auto", "litert"):
        try:
            from ai_edge_litert.interpreter import Interpreter
            name = "ai_edge_litert.Interpreter (Float32 TFLite)"
        except ImportError:
            if runtime == "litert":
                raise
            runtime = "tensorflow"
    if runtime == "tensorflow":
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
        import tensorflow as tf
        Interpreter = tf.lite.Interpreter
        name = "tensorflow.lite.Interpreter (Float32 TFLite; kein Keras-Benchmark)"
    interpreter = Interpreter(model_path=str(model), num_threads=threads)
    interpreter.allocate_tensors()
    inputs, outputs = interpreter.get_input_details(), interpreter.get_output_details()
    if len(inputs) != 1 or len(outputs) != 1:
        raise ValueError("AE muss genau einen Ein- und Ausgang besitzen.")
    incoming, outgoing = inputs[0], outputs[0]
    if incoming["dtype"] != np.float32 or outgoing["dtype"] != np.float32:
        raise ValueError("Der Vergleich erfordert Float32-TFLite ohne Quantisierung.")
    if tuple(incoming["shape"]) != tuple(outgoing["shape"]):
        raise ValueError("AE-Ausgabeform entspricht nicht der Eingabeform.")
    return interpreter, incoming, outgoing, name


def scorer(method: str, bundle: dict, directory: Path, *, runtime: str, threads: int):
    if method == "rms":
        return rms_score, "NumPy RMS (standardisiertes H×3-Fenster)"
    if method == "isolation_forest":
        import joblib
        model = joblib.load(directory / "isolation_forest.joblib")
        return lambda x: float(-model.score_samples(x.reshape(1, -1))[0]), "scikit-learn IsolationForest.score_samples"
    interpreter, incoming, outgoing, name = load_interpreter(directory / "autoencoder_float32.tflite", runtime, threads)
    expected_shape = (1, bundle["window_size"], 3)
    if tuple(incoming["shape"]) != expected_shape:
        raise ValueError(f"TFLite-Eingabe {incoming['shape']} statt {expected_shape}.")
    def infer(x):
        interpreter.set_tensor(incoming["index"], x[np.newaxis, ...])
        interpreter.invoke()
        reconstruction = interpreter.get_tensor(outgoing["index"])[0]
        if reconstruction.shape != x.shape or not np.isfinite(reconstruction).all():
            raise ValueError("Ungültige Autoencoder-Rekonstruktion.")
        return float(np.mean(np.square(x - reconstruction), dtype=np.float64))
    return infer, name


def classify_raw(raw: np.ndarray, scaler: dict, score_function, threshold: float) -> tuple[float, int]:
    score = float(score_function(standardize(raw, scaler)))
    return score, finite_score(score, threshold)


def binary_metrics(labels: list[int], predictions: list[int]) -> dict:
    true, pred = np.asarray(labels), np.asarray(predictions)
    if true.shape != pred.shape or not np.isin(true, [0, 1]).all() or not np.isin(pred, [0, 1]).all():
        raise ValueError("Gleich lange binäre Labels und Vorhersagen erforderlich.")
    tn, fp, fn, tp = [int(np.sum((true == a) & (pred == b)))
                      for a, b in ((0, 0), (0, 1), (1, 0), (1, 1))]
    def ratio(a, b):
        return float(a / b) if b else None
    return {"windows": len(true), "normal_windows": tn + fp, "anomaly_windows": tp + fn,
            "normal_fraction": ratio(tn + fp, len(true)),
            "anomaly_fraction": ratio(tp + fn, len(true)),
            "tn": tn, "fp": fp, "fn": fn, "tp": tp,
            "accuracy": ratio(tn + tp, len(true)), "precision": ratio(tp, tp + fp),
            "recall": ratio(tp, tp + fn), "specificity": ratio(tn, tn + fp),
            "false_positive_rate": ratio(fp, fp + tn), "false_negative_rate": ratio(fn, fn + tp),
            "f1": ratio(2 * tp, 2 * tp + fp + fn) if tp + fn else None,
            "undefined_metric_representation": "null (Nenner 0 oder keine positive Klasse für F1)"}


def quality_report(rows: list[dict], methods=METHODS) -> dict:
    report = {}
    for method in methods:
        selected = [row for row in rows if row["method"] == method]
        groups = {"all": selected}
        groups.update({f"recording:{path}": [r for r in selected if r["recording"] == path]
                       for path in dict.fromkeys(r["recording"] for r in selected)})
        groups.update({f"state:{state}": [r for r in selected if r["state"] == state]
                       for state in dict.fromkeys(r["state"] for r in selected)})
        report[method] = {}
        for group, entries in groups.items():
            valid = [r for r in entries if r["decision"] != "INVALID"]
            report[method][group] = {
                "attempted_windows": len(entries), "invalid_windows": len(entries) - len(valid),
                "valid_decision_fraction": len(valid) / len(entries) if entries else None,
                "metrics_on_valid_decisions_only": binary_metrics(
                    [r["label"] for r in valid], [r["prediction"] for r in valid])}
    return report


def evaluate_windows(windows: np.ndarray, metadata: list[dict], bundle: dict,
                     directory: Path, runtime: str, threads: int) -> tuple[list[dict], dict]:
    rows, runtimes = [], {}
    for method in METHODS:
        score_function, runtimes[method] = scorer(method, bundle, directory, runtime=runtime, threads=threads)
        threshold = bundle["thresholds"][method]["value"]
        for raw, meta in zip(windows, metadata, strict=True):
            ready_ns = time.perf_counter_ns()
            try:
                score, prediction = classify_raw(raw, bundle["scaler"], score_function, threshold)
                decision = "ANOMALY" if prediction else "NORMAL"
                error = None
            except (ValueError, FloatingPointError, RuntimeError) as exc:
                score, prediction, decision, error = None, None, "INVALID", str(exc)
            decision_ns = time.perf_counter_ns()
            rows.append({**meta, "method": method, "score": score, "prediction": prediction,
                         "decision": decision, "error": error, "threshold": threshold,
                         "threshold_source": bundle["thresholds"][method]["source"],
                         "processing_latency_ms": (decision_ns - ready_ns) / 1e6})
    return rows, runtimes


def write_rows(path: Path, rows: list[dict]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_bundle(directory: Path) -> dict:
    bundle = read_json(directory / "bundle.json")
    for name, digest in bundle["artifact_sha256"].items():
        if sha256(directory / name) != digest:
            raise ValueError(f"Eingefrorenes Artefakt verändert: {name}")
    for method in METHODS:
        finite_score(0.0, bundle["thresholds"][method]["value"])
    return bundle


def calibrate(args) -> None:
    import joblib
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    profile_path = resolve_source(args.profile)
    if not profile_path.exists():
        profile_path = ROOT / "profiles" / args.profile
    if profile_path.is_dir():
        profile_path /= "profile.json"
    profile = read_json(profile_path)
    if profile.get("status") != "ready" or profile.get("axes") != list(AXES):
        raise ValueError("Fertiges XYZ-Profil erforderlich.")
    size, step = int(profile["window_size"]), int(profile["step_size"])
    groups, metadata, reports = {"train": [], "validation": []}, {"train": [], "validation": []}, []
    for entry in profile["data"]["recordings"]:
        split = entry["split"]
        if split not in groups:
            raise ValueError("Kalibrierung darf ausschließlich normale Train/Val-Aufnahmen lesen.")
        path = resolve_source(entry["path"])
        if sha256(path) != entry["sha256"]:
            raise ValueError(f"Aufnahme stimmt nicht mit Profilhash überein: {path}")
        values, times, report = load_recording(path, label=0, state="normal_calibration")
        report["split"] = split
        windows, meta = make_windows(values, times, size, step, report)
        groups[split].append(windows)
        metadata[split].extend(meta)
        reports.append(report)
    assert_disjoint(reports)
    for split, key in (("train", "training_files"), ("validation", "validation_files")):
        listed = [Path(r["path"]).name for r in reports if r["split"] == split]
        if listed != profile["data"][key] or not listed:
            raise ValueError("Profil-Splitlisten widersprechen den Aufnahmezuordnungen.")
    raw = {split: np.concatenate(parts) for split, parts in groups.items()}
    original_scaler = resolve_source(profile["artifacts"]["scaler"])
    original_model = resolve_source(profile["artifacts"]["tflite_model"])
    original_threshold = resolve_source(profile["artifacts"]["threshold"])
    for path, expected in ((original_scaler, profile["scaler"]["sha256"]),
                           (original_model, profile["autoencoder"]["tflite_model_sha256"]),
                           (original_threshold, profile["threshold"]["sha256"])):
        if sha256(path) != expected:
            raise ValueError(f"Profil-Artefakt verändert: {path}")
    fitted = StandardScaler().fit(raw["train"].reshape(-1, 3))
    saved = joblib.load(original_scaler)
    for attribute in ("mean_", "scale_", "var_", "n_samples_seen_"):
        if not np.allclose(getattr(fitted, attribute), getattr(saved, attribute), rtol=1e-10, atol=1e-12):
            raise ValueError(f"Gespeicherte Skalierung nicht aus manifestierten Trainfenstern reproduziert: {attribute}")
    scaler = {"mean": saved.mean_.tolist(), "scale": saved.scale_.tolist(),
              "fit_samples": int(saved.n_samples_seen_), "fit_source": "normal_train_windows_only",
              "verified_against_train_only_refit": True}
    scaled = {split: np.stack([standardize(w, scaler) for w in raw[split]]) for split in groups}
    for split in groups:
        expected = saved.transform(raw[split].reshape(-1, 3)).reshape(raw[split].shape)
        if not np.array_equal(scaled[split], expected):
            raise ValueError("Exportierte Float32-Skalierung reproduziert StandardScaler.transform nicht exakt.")
    if_model = IsolationForest(**IF_PARAMETERS).fit(scaled["train"].reshape(len(raw["train"]), -1))
    rms_validation = np.asarray([rms_score(w) for w in scaled["validation"]])
    if_validation = -if_model.score_samples(scaled["validation"].reshape(len(raw["validation"]), -1))
    threshold_document = read_json(original_threshold)
    if threshold_document.get("percentile") != 99 or not threshold_document.get("normal_validation_only") or threshold_document.get("test_or_anomaly_data_used") is not False:
        raise ValueError("AE-Schwelle benötigt nachgewiesene normale P99-Validierung ohne Testdaten.")
    output = resolve_source(args.output)
    if output.exists():
        raise FileExistsError(f"Output wird nicht überschrieben: {output}")
    output.mkdir(parents=True, exist_ok=False)
    for source, name in ((profile_path, "source_profile.json"), (original_scaler, "scaler.joblib"),
                         (original_model, "autoencoder_float32.tflite"),
                         (original_threshold, "source_ae_threshold.json"),
                         (Path(__file__), "comparison_implementation.py")):
        shutil.copy2(source, output / name)
    joblib.dump(if_model, output / "isolation_forest.joblib")
    np.save(output / "validation_raw.npy", raw["validation"], allow_pickle=False)
    write_json(output / "validation_windows.json", {"windows": metadata["validation"]})
    sensor = profile.get("sensor", {})
    chain_verified = sensor.get("measurement_chain_verified") is True
    bundle = {"schema_version": 1, "profile_name": profile["profile_name"],
              "source_profile_path": str(profile_path), "provenance": provenance(),
              "window_size": size, "step_size": step, "axes": list(AXES),
              "sampling_rate_hz": profile["sampling_rate_hz"],
              "measurement_chain_status": "verified" if chain_verified else "unverified_legacy",
              "sensor": sensor, "scaler": scaler, "recordings": reports,
              "window_counts": {split: len(values) for split, values in raw.items()},
              "if_parameters": IF_PARAMETERS,
              "score_definitions": {"rms": "sqrt(mean(square(standardized_Hx3)))",
                                    "isolation_forest": "-score_samples(standardized_Hx3.flatten(order=C))",
                                    "tflite_autoencoder": "mean(square(standardized_Hx3 - reconstruction), dtype=float64)"},
              "thresholds": {
                  "rms": {"value": p99(rms_validation), "source": "P99_NORMAL_VALIDATION", "percentile": 99},
                  "isolation_forest": {"value": p99(if_validation), "source": "P99_NORMAL_VALIDATION", "percentile": 99},
                  "tflite_autoencoder": {"value": float(threshold_document["selected_threshold"]),
                                         "source": "PROFILE/P99_FROZEN_KERAS_CALIBRATION", "percentile": 99}},
              "decision_rule": "score > threshold = ANOMALY; <= = NORMAL; nonfinite = INVALID",
              "development_only": True,
              "limitations": ["Validierung ist Schwellenkalibrierung, keine unabhängige Testgüte.",
                              "Profil-AE verwendete dieselbe Normalvalidierung auch für Trainingsüberwachung/Early Stopping; kein dritter Kalibrierungssplit.",
                              "Software-Zeitstempel belegen keine Sensor-ODR oder neue Messwerte.",
                              "Zweites separat trainiertes Profil ist kein Betriebspunktwechsel mit eingefrorenem Modell."]}
    ae, runtime_name = scorer("tflite_autoencoder", bundle, output, runtime=args.runtime, threads=args.threads)
    ae_validation = np.asarray([ae(w) for w in scaled["validation"]])
    frozen = bundle["thresholds"]["tflite_autoencoder"]["value"]
    calculated = p99(ae_validation)
    # Konvertierungstoleranz aus dem bestehenden Profil; niemals Schwelle nachziehen.
    tolerance = float(profile["tflite_consistency"]["acceptance_limits"]["maximum_absolute_mse_difference"])
    if abs(calculated - frozen) > tolerance:
        raise ValueError("TFLite-P99 widerspricht eingefrorener Profil-P99 außerhalb Konvertierungstoleranz.")
    bundle["ae_validation_check"] = {"runtime": runtime_name, "tflite_p99_observed": calculated,
                                     "frozen_threshold_used": frozen, "absolute_difference": abs(calculated - frozen),
                                     "acceptance_tolerance": tolerance, "threshold_recalibrated": False}
    artifacts = [path for path in output.iterdir() if path.is_file()]
    bundle["artifact_sha256"] = {path.name: sha256(path) for path in artifacts}
    write_json(output / "bundle.json", bundle)
    rows, runtimes = evaluate_windows(raw["validation"], metadata["validation"], bundle, output, args.runtime, args.threads)
    write_rows(output / "validation_predictions.csv", rows)
    write_json(output / "validation_diagnostics.json", {
        "evidence_scope": "Kalibrierungsdiagnose; keine unabhängige Testgüte/Hypothesenbestätigung",
        "runtime": runtimes, "metrics": quality_report(rows), "bundle_sha256": sha256(output / "bundle.json")})
    print(json.dumps({"output": str(output), "window_counts": bundle["window_counts"],
                      "thresholds": bundle["thresholds"], "measurement_chain_status": bundle["measurement_chain_status"]}, ensure_ascii=False))


def test_data(manifest_path: Path, bundle: dict, bundle_path: Path, pilot: bool):
    manifest = read_json(manifest_path)
    if manifest.get("frozen_bundle_sha256") != sha256(bundle_path / "bundle.json"):
        raise ValueError("Testmanifest muss den vor Aufnahme eingefrorenen Bundle-Hash benennen.")
    if manifest.get("detection_dependent_fan_shutdown") is not False:
        raise ValueError("Vergleich erfordert ausdrücklich deaktivierte detektionsabhängige Lüfterabschaltung.")
    if manifest.get("independent_recordings") is not True:
        raise ValueError("Testmanifest muss neue unabhängige Aufnahmen deklarieren.")
    if not pilot:
        if bundle["measurement_chain_status"] != "verified":
            raise ValueError("Alte/unbestätigte Messkette: nur --pilot, kein abschließender Vergleich.")
        if manifest.get("measurement_chain_verified") is not True:
            raise ValueError("Testmesskette wurde nicht als überprüft deklariert.")
        for key in ("odr_hz", "range_g", "acquisition_mode"):
            expected = bundle["sensor"].get(key)
            if expected is None or manifest.get("sensor", {}).get(key) != expected:
                raise ValueError(f"Messkette unbestätigt/inkompatibel: {key}; keine neue Skalierung erlaubt.")
        if manifest.get("sampling_rate_hz") != bundle["sampling_rate_hz"]:
            raise ValueError("Test- und Kalibrierungsabtastrate unterscheiden sich.")
    windows, metadata, reports = [], [], []
    for entry in manifest["recordings"]:
        for required in ("path", "sha256", "label", "state", "pwm_setpoint_percent", "measured_rpm"):
            if required not in entry:
                raise ValueError(f"Aufnahmemanifestfeld fehlt: {required}")
        pwm = entry["pwm_setpoint_percent"]
        rpm = entry["measured_rpm"]
        if not isinstance(pwm, (int, float)) or not math.isfinite(pwm) or not 0 <= pwm <= 100:
            raise ValueError("PWM-Vorgabe muss separat in Prozent 0..100 dokumentiert sein.")
        if rpm is not None and (not isinstance(rpm, (int, float)) or not math.isfinite(rpm) or rpm < 0):
            raise ValueError("Gemessene Drehzahl muss endlich >= 0 oder null (nicht gemessen) sein.")
        path = resolve_source(entry["path"], manifest_path.parent)
        if sha256(path) != entry["sha256"]:
            raise ValueError(f"Testaufnahme-Hash stimmt nicht: {path}")
        values, times, report = load_recording(path, label=entry["label"], state=entry["state"])
        report.update(split="test", pwm_setpoint_percent=pwm, measured_rpm=rpm)
        file_windows, file_meta = make_windows(values, times, bundle["window_size"], bundle["step_size"], report)
        windows.append(file_windows)
        metadata.extend(file_meta)
        reports.append(report)
    if not reports:
        raise ValueError("Testmanifest enthält keine Aufnahmen.")
    assert_disjoint(bundle["recordings"] + reports)
    return np.concatenate(windows), metadata, reports, manifest


def evaluate(args) -> None:
    directory, output = resolve_source(args.bundle), resolve_source(args.output)
    bundle = load_bundle(directory)
    manifest_path = resolve_source(args.test_manifest)
    windows, metadata, reports, manifest = test_data(manifest_path, bundle, directory, args.pilot)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(manifest_path, output / "test_manifest.json")
    shutil.copy2(Path(__file__), output / "comparison_implementation.py")
    rows, runtimes = evaluate_windows(windows, metadata, bundle, directory, args.runtime, args.threads)
    write_rows(output / "predictions.csv", rows)
    write_json(output / "quality.json", {
        "evidence_scope": "explorativer Pilot" if args.pilot else "unabhängige Testauswertung; Hypothesen separat beurteilen",
        "provenance": provenance(), "runtime": runtimes,
        "bundle_sha256": sha256(directory / "bundle.json"), "test_manifest_sha256": sha256(manifest_path),
        "thresholds": bundle["thresholds"], "frozen_model_scaler_thresholds": True,
        "recordings": reports, "metrics": quality_report(rows),
        "invalid_total": sum(r["decision"] == "INVALID" for r in rows),
        "limitations": bundle["limitations"] + [
            "Fenster derselben Aufnahme sind abhängig; Anzahl Fenster ersetzt keine unabhängigen Wiederholungen.",
            "Keine Konfidenz-/Hypothesenentscheidung allein aus gepoolten Fenstern.",
            "Replay-Latenzen hier sind Diagnose; kontrollierte Ressourcenmessung über benchmark."]})
    print(f"Auswertung gespeichert: {output}")


class ResourceSampler:
    def __init__(self, process, interval_s=0.005):
        self.process, self.interval_s = process, interval_s
        self.samples = []
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        while not self.stop_event.is_set():
            self.samples.append(self.process.memory_info().rss)
            self.stop_event.wait(self.interval_s)

    def __enter__(self):
        self.samples.append(self.process.memory_info().rss)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop_event.set()
        self.thread.join()
        self.samples.append(self.process.memory_info().rss)


def benchmark_worker(args) -> None:
    import psutil
    process = psutil.Process()
    directory = resolve_source(args.bundle)
    bundle = load_bundle(directory)
    raw = np.load(directory / "validation_raw.npy", mmap_mode="r", allow_pickle=False)
    rss_before_load = process.memory_info().rss
    start_load = time.perf_counter_ns()
    score_function, runtime = scorer(args.method, bundle, directory, runtime=args.runtime, threads=args.threads)
    load_ms = (time.perf_counter_ns() - start_load) / 1e6
    threshold = bundle["thresholds"][args.method]["value"]
    for index in range(args.warmup):
        classify_raw(raw[index % len(raw)], bundle["scaler"], score_function, threshold)
    durations, cpu_start, wall_start = [], process.cpu_times(), time.perf_counter_ns()
    rss_loaded = process.memory_info().rss
    with ResourceSampler(process) as resources:
        # Stets vollständige Durchläufe desselben Fenstersatzes. Die Mindestdauer
        # verhindert bedeutungsarme CPU-Prozentwerte aus wenigen Millisekunden.
        while (len(durations) < args.windows or
               (time.perf_counter_ns() - wall_start) / 1e9 < args.minimum_seconds):
            for window in raw:
                ready = time.perf_counter_ns()
                score, prediction = classify_raw(window, bundle["scaler"], score_function, threshold)
                available = time.perf_counter_ns()
                durations.append((available - ready) / 1e6)
    wall_s = (time.perf_counter_ns() - wall_start) / 1e9
    cpu_end = process.cpu_times()
    cpu_s = (cpu_end.user - cpu_start.user) + (cpu_end.system - cpu_start.system)
    result = {"method": args.method, "runtime": runtime, "provenance": provenance(),
              "measurement_mode": "offline_sequential_replay_without_GUI_without_sensor",
              "latency_boundary": "vollständiges unskaliertes Fenster im RAM bis skalierter Score + endliche Schwellenentscheidung",
              "excluded_from_latency": ["Fensterfüllzeit/Sensor", "Dateilesen", "Warteschlange", "GUI/CSV-Ausgabe", "Modellimport/-laden (separat)"],
              "included_in_latency": ["Float32-Kopie", "Skalierung", "Featureform", "Inferenz/RMS", "Score", "Validierung", "Schwellenentscheidung"],
              "warmup_windows": args.warmup, "measured_windows": len(durations),
              "minimum_requested_windows": args.windows,
              "minimum_requested_seconds": args.minimum_seconds,
              "complete_passes_over_same_windows": len(durations) // len(raw),
              "unique_source_windows": len(raw), "tflite_threads": args.threads,
              "framework_and_model_load_ms": load_ms,
              "latency_ms": {"mean": float(np.mean(durations)), "p50": float(np.median(durations)),
                             "p95": float(np.percentile(durations, 95)), "p99": p99(np.asarray(durations)),
                             "min": min(durations), "max": max(durations)},
              "process_cpu_seconds": cpu_s, "measurement_wall_seconds": wall_s,
              "process_cpu_percent_one_core_100": 100 * cpu_s / wall_s,
              "process_cpu_percent_machine_normalized": 100 * cpu_s / wall_s / (os.cpu_count() or 1),
              "process_rss_before_model_import_bytes": rss_before_load,
              "process_rss_loaded_bytes": rss_loaded,
              "process_rss_sampled_peak_bytes": max(resources.samples),
              "rss_sample_interval_s": resources.interval_s,
              "rss_note": "Gesamtprozess inkl. Python, NumPy, Vorverarbeitung und geladener Methodenbibliotheken; stichprobenartiges Maximum, keine allokationsgenaue Spitze.",
              "cpu_note": "CPU-Zeit gesamter Prozess inkl. RSS-Sampler und Schleifenverwaltung; voller Durchsatz ohne Echtzeit-Pacing. CPU-Prozent sind daher keine Live-CPU-Prognose.",
              "window_duration_from_config_ms": 1000 * bundle["window_size"] / bundle["sampling_rate_hz"],
              "configured_duration_is_sensor_verified": bundle["measurement_chain_status"] == "verified",
              "bundle_sha256": sha256(directory / "bundle.json"),
              "threshold": threshold, "threshold_source": bundle["thresholds"][args.method]["source"],
              "model_artifact_bytes": ((directory / "isolation_forest.joblib").stat().st_size if args.method == "isolation_forest"
                                       else (directory / "autoencoder_float32.tflite").stat().st_size if args.method == "tflite_autoencoder" else 0),
              "gui_overhead_measured": False,
              "warning": "Kalibrierungsfenster-Replay; kein vollständiger Live-/GUI-/Gütenachweis."}
    output = resolve_source(args.output)
    write_json(output / f"{args.method}.json", result)
    write_rows(output / f"{args.method}_latencies.csv", [
        {"iteration": i, "source_window": i % len(raw), "processing_latency_ms": d}
        for i, d in enumerate(durations)])


def benchmark(args) -> None:
    directory, output = resolve_source(args.bundle), resolve_source(args.output)
    load_bundle(directory)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(Path(__file__), output / "comparison_implementation.py")
    for method in METHODS:
        command = [sys.executable, str(Path(__file__).resolve()), "_benchmark-worker",
                   "--bundle", str(directory), "--output", str(output), "--method", method,
                   "--runtime", args.runtime, "--threads", str(args.threads),
                   "--windows", str(args.windows), "--warmup", str(args.warmup),
                   "--minimum-seconds", str(args.minimum_seconds)]
        subprocess.run(command, check=True, cwd=ROOT)
    write_json(output / "summary.json", {"benchmarks": {method: read_json(output / f"{method}.json") for method in METHODS},
                                          "method_order": list(METHODS),
                                          "gui_overhead_measured": False,
                                          "benchmark_order_limitation": "Feste Methodenreihenfolge; wiederholte thermisch kontrollierte Versuche mit variierter Reihenfolge bleiben erforderlich."})
    print(f"Ressourcenpilot gespeichert: {output}")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    subs = command.add_subparsers(dest="command", required=True)
    for name in ("calibrate", "evaluate", "benchmark", "_benchmark-worker"):
        sub = subs.add_parser(name)
        sub.add_argument("--output", required=True, help="Neuer Ausgabeordner; niemals überschreiben")
        sub.add_argument("--runtime", choices=("auto", "litert", "tensorflow"), default="auto")
        sub.add_argument("--threads", type=int, default=1)
        if name == "calibrate":
            sub.add_argument("--profile", required=True)
        else:
            sub.add_argument("--bundle", required=True)
        if name == "evaluate":
            sub.add_argument("--test-manifest", required=True)
            sub.add_argument("--pilot", action="store_true", help="Explorativ; erlaubt unbestätigte/abweichende Messkette, nie finale Güte")
        if name in ("benchmark", "_benchmark-worker"):
            sub.add_argument("--windows", type=int, default=1000)
            sub.add_argument("--warmup", type=int, default=20)
            sub.add_argument("--minimum-seconds", type=float, default=2.0)
        if name == "_benchmark-worker":
            sub.add_argument("--method", choices=METHODS, required=True)
    return command


def main():
    args = parser().parse_args()
    if (args.threads < 1 or getattr(args, "windows", 1) < 1 or getattr(args, "warmup", 0) < 0
            or not math.isfinite(getattr(args, "minimum_seconds", 0))
            or getattr(args, "minimum_seconds", 0) < 0):
        raise ValueError("Threads/Fenster positiv; Warmup/Mindestdauer endlich und nichtnegativ erforderlich.")
    {"calibrate": calibrate, "evaluate": evaluate, "benchmark": benchmark,
     "_benchmark-worker": benchmark_worker}[args.command](args)


if __name__ == "__main__":
    main()
