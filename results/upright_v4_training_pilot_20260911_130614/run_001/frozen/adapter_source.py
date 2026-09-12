#!/usr/bin/env python3
"""Explicit offline bridge for the upright-v4 AC pilot dataset.

audit: provenance and input contracts, no fitting, models, or hardware.
train: future explicit AE/IF/scaler training and validation calibration.
replay: frozen development validation only; no fitting or capture.

The legacy CLI intentionally cannot load pilot_bundle.json. Raw inference
requires original Float64 XYZ; exported Float32 raw arrays are audit artifacts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import common_comparison as common
import prepare_pilot_dataset as preparation

METHODS = common.METHODS
CONTRACT = {
    "format": "upright_v4_ac_pilot_bundle_v1",
    "preprocessing_id": preparation.PREPROCESSING_ID,
    "window_size": 128, "step_size": 128, "axes": list(common.AXES),
    "centering": "per_window_per_axis_float64_then_float32",
    "scaling": "train_only_axis_StandardScaler_float32_transform",
    "selection_seconds_since_pwm_command": [180, 300],
    "time_origin": "pwm_command_invocation_monotonic_ns",
    "mounting_id": preparation.EXPECTED_MOUNTING,
    "sensor": preparation.EXPECTED_SENSOR,
    "development_only": True, "independent_test": False,
    "second_pwm_rule": "no_model_scaler_threshold_or_preprocessing_change",
}


def center_raw_window(raw_float64):
    """Shared future raw/replay entry: preserve precision used by preparation."""
    raw = np.asarray(raw_float64)
    preparation.check(raw.dtype == np.float64, "Original Float64 raw XYZ required; do not recenter Float32 exports")
    preparation.check(raw.shape == (128, 3) and np.isfinite(raw).all(), "Invalid raw window")
    return (raw - raw.mean(axis=0, keepdims=True)).astype(np.float32)


def standardize_ac(ac_float32, scaler_dict):
    ac = np.asarray(ac_float32)
    preparation.check(ac.dtype == np.float32 and ac.shape == (128, 3) and np.isfinite(ac).all(),
                      "Expected finite canonical Float32 AC window 128x3")
    # Canonical AC is already centered; do not center it again after rounding.
    return common.standardize(ac, scaler_dict)


def score_window(ac, scaler, score_functions, thresholds):
    preparation.check(set(score_functions) == set(METHODS) and set(thresholds) == set(METHODS),
                      "All three methods and thresholds required")
    for method in METHODS:
        common.finite_score(0., thresholds[method])
    try:
        shared = standardize_ac(ac, scaler)
    except (ValueError, FloatingPointError) as exc:
        return {m: {"score": None, "prediction": None, "decision": "INVALID", "error": str(exc)} for m in METHODS}
    result = {}
    for method in METHODS:
        try:
            # A method may use mutable work buffers without altering the next input.
            score = float(score_functions[method](shared.copy()))
            prediction = common.finite_score(score, thresholds[method])
            result[method] = {"score": score, "prediction": prediction,
                              "decision": "ANOMALY" if prediction else "NORMAL", "error": None}
        except Exception as exc:
            result[method] = {"score": None, "prediction": None, "decision": "INVALID",
                              "error": f"{type(exc).__name__}: {exc}"}
    return result


def load_inputs(dataset):
    dataset = Path(dataset).resolve()
    ac = preparation.load_prepared_pilot(dataset)
    manifest = common.read_json(dataset / "manifest.json")
    metadata = {s: pd.read_csv(dataset / f"{s}_windows.csv", float_precision="round_trip") for s in ac}
    source_paths = {s["recording_id"]: s["csv"] for s in manifest["sources"]}
    for frame in metadata.values():
        # Add the existing metrics interface without renaming original columns.
        frame["recording"] = frame["recording_id"].map(source_paths)
        frame["recording_sha256"] = frame["source_csv_sha256"]
        frame["state"] = frame["original_state"]
    labels = {s: np.load(dataset / f"{s}_labels.npy", allow_pickle=False) for s in ac}
    return {"dataset": dataset, "ac": ac, "manifest": manifest,
            "metadata": metadata, "labels": labels}


def audit(dataset, output):
    output = Path(output).resolve()
    preparation.check(not output.exists(), "Audit output exists; no overwrite")
    inputs = load_inputs(dataset)
    manifest = inputs["manifest"]
    checked = 0
    # Original Float64 -> shared raw inference entry must equal prepared AC exactly.
    for source in manifest["sources"]:
        frame = pd.read_csv(source["csv"], float_precision="round_trip")
        rows = inputs["metadata"][source["split"]]
        rows = rows.loc[rows["recording_id"] == source["recording_id"]]
        for row in rows.itertuples(index=False):
            raw = frame.iloc[row.source_start_index:row.source_end_index_exclusive][list(common.AXES)].to_numpy(np.float64)
            expected = inputs["ac"][source["split"]][row.split_index]
            preparation.check(np.array_equal(center_raw_window(raw), expected), "Raw replay disagrees with canonical AC")
            checked += 1
    output.mkdir(parents=True, exist_ok=False)
    report = {"status": "adapter_audited_without_training", "contract": CONTRACT,
              "dataset": str(inputs["dataset"]),
              "dataset_manifest_sha256": common.sha256(inputs["dataset"] / "manifest.json"),
              "all_windows_raw_to_ac_exact": checked,
              "window_counts": {s: len(a) for s, a in inputs["ac"].items()},
              "input_array_sha256": {s: common.sha256(inputs["dataset"] / f"{s}_ac_g.npy") for s in inputs["ac"]},
              "models_trained": False, "scaler_fitted": False, "thresholds_calibrated": False,
              "real_model_inference_executed": False, "hardware_access": False,
              "legacy_profile_compatible": False,
              "future_live_requirement": "Original Float64 XYZ required. Existing Float32 BufferedAcquisition/GUI paths must not silently load this bundle.",
              "implementation_sha256": common.sha256(Path(__file__))}
    common.write_json(output / "adapter_audit.json", report)
    preparation.copy_exclusive(__file__, output / "adapter_source.py")
    return report


def training_payload(inputs):
    """The only scaler fit in this adapter; invoked exclusively by train()."""
    from sklearn.preprocessing import StandardScaler

    ac = inputs["ac"]
    scaler = StandardScaler().fit(ac["train"].reshape(-1, 3))
    scaler_document = {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
                       "fit_samples": int(scaler.n_samples_seen_),
                       "fit_source": "canonical_normal_train_AC_only"}
    features = {s: np.stack([standardize_ac(w, scaler_document) for w in values]) for s, values in ac.items()}
    for split in ac:
        expected = scaler.transform(ac[split].reshape(-1, 3)).reshape(ac[split].shape)
        preparation.check(np.array_equal(features[split], expected), "Scaler transform compatibility failure")
    sources = inputs["manifest"]["sources"]
    manifest = {"contract": CONTRACT, "source_dataset_manifest_sha256": common.sha256(inputs["dataset"] / "manifest.json"),
                "train_files": [s["recording_id"] for s in sources if s["split"] == "train"],
                "validation_files": [s["recording_id"] for s in sources if s["split"] == "validation"],
                "source_recordings": sources, "split_level": "whole_recording", "scaler": scaler_document}
    statistics = pd.DataFrame([{"recording_id": s["recording_id"], "state": s["state"], "split": s["split"],
                                "interval_start_s": 180, "interval_end_exclusive_s": 300,
                                **s["quality_selected_interval"]} for s in sources])
    return {"features": features, "labels": inputs["labels"], "metadata": inputs["metadata"],
            "manifest": manifest, "session_statistics": statistics, "scaler": scaler}, scaler_document


def dispatch_prepared(ac_windows, metadata, bundle, score_functions):
    """Frozen scoring only. Also serves the future provenance-checked test reader."""
    preparation.check(len(ac_windows) == len(metadata), "Window/metadata length mismatch")
    rows = []
    thresholds = {m: bundle["thresholds"][m]["value"] for m in METHODS}
    for ac, meta in zip(ac_windows, metadata, strict=True):
        results = score_window(ac, bundle["scaler"], score_functions, thresholds)
        for method in METHODS:
            rows.append({**meta, "method": method, **results[method], "threshold": thresholds[method],
                         "threshold_source": bundle["thresholds"][method]["source"]})
    return rows


def model_scorers(bundle, directory, runtime="auto", threads=1):
    functions, runtimes = {}, {}
    for method in METHODS:
        functions[method], runtimes[method] = common.scorer(method, bundle, Path(directory), runtime=runtime, threads=threads)
    return functions, runtimes


def validate_bundle_contract(bundle):
    preparation.check(bundle.get("contract") == CONTRACT, "Wrong or missing AC pilot contract")
    preparation.check(bundle.get("status") == "ready_development_only", "Bundle not ready")
    preparation.check(bundle.get("window_size") == 128, "Wrong model input size")
    preparation.check(bundle.get("dataset_manifest_sha256"), "Missing dataset anchor")
    preparation.check(set(bundle.get("thresholds", {})) == set(METHODS), "Missing thresholds")
    for method in METHODS:
        threshold = bundle["thresholds"][method]
        preparation.check(threshold["percentile"] == 99, "Threshold must use normal validation P99")
        common.finite_score(0., threshold["value"])
    standardize_ac(np.zeros((128, 3), np.float32), bundle["scaler"])
    preparation.check(bundle["scaler"]["fit_source"] == "canonical_normal_train_AC_only", "Wrong scaler fit source")
    preparation.check(bundle.get("if_parameters") == common.IF_PARAMETERS, "Changed IF parameters")


def load_bundle(directory):
    directory = Path(directory).resolve()
    preparation.check(not (directory.parent / "training_failed.json").exists(), "Training failed; bundle not released")
    path = directory / "pilot_bundle.json"
    expected = (directory / "pilot_bundle.sha256").read_text().strip()
    preparation.check(common.sha256(path) == expected, "Frozen bundle fingerprint changed")
    bundle = common.read_json(path)
    validate_bundle_contract(bundle)
    required = {"scaler.joblib", "isolation_forest.joblib", "autoencoder_float32.tflite",
                "source_ae_threshold.json", "tflite_consistency.json", "adapter_source.py",
                "common_comparison_source.py", "prepared_manifest.json", "prepared_plan.json"}
    inventory = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()}
    preparation.check(set(bundle["artifact_sha256"]) == inventory - {"pilot_bundle.json", "pilot_bundle.sha256"},
                      "Frozen artifact inventory changed")
    preparation.check(required <= set(bundle["artifact_sha256"]), "Missing required frozen artifacts")
    for name, digest in bundle["artifact_sha256"].items():
        path = (directory / name).resolve()
        preparation.check(path.is_relative_to(directory), "Frozen artifact path escapes bundle")
        preparation.check(common.sha256(path) == digest, f"Frozen artifact changed: {name}")
    for current, archived in ((Path(__file__), "adapter_source.py"),
                              (Path(common.__file__), "common_comparison_source.py")):
        preparation.check(common.sha256(current) == bundle["artifact_sha256"][archived],
                          "Runtime preprocessing/scoring implementation differs from frozen code")
    preparation.check(bundle["artifact_sha256"]["prepared_manifest.json"] == bundle["dataset_manifest_sha256"],
                      "Dataset anchor mismatch")
    source_ae = common.read_json(directory / "source_ae_threshold.json")
    preparation.check(source_ae["selected_threshold"] == bundle["thresholds"]["tflite_autoencoder"]["value"],
                      "Frozen AE threshold changed")
    return bundle


def train(dataset, output, runtime="auto", threads=1):
    """Future explicit training command. Never invoked by audit or replay."""
    output = Path(output).resolve()
    preparation.check(not output.exists(), "Training output exists; no overwrite")
    preparation.check(threads >= 1, "Positive thread count required")
    inputs = load_inputs(dataset)
    output.mkdir(parents=True, exist_ok=False)
    common.write_json(output / "training_request.json", {"dataset": str(inputs["dataset"]), "contract": CONTRACT,
                      "dataset_manifest_sha256": common.sha256(inputs["dataset"] / "manifest.json"),
                      "scope": "explicit_development_training", "provenance": common.provenance()})
    try:
        # Late imports keep every training dependency off the audit/replay path.
        import joblib
        from sklearn.ensemble import IsolationForest
        import calibrate_and_train as calibration

        prepared, scaler_doc = training_payload(inputs)
        stage = output / "training_stage"
        result = calibration.write_training_stage(stage, prepared, {"profile_name": output.name})
        forest = IsolationForest(**common.IF_PARAMETERS).fit(prepared["features"]["train"].reshape(len(inputs["ac"]["train"]), -1))
        frozen = output / "frozen"
        frozen.mkdir()
        copies = [(stage / "models/scaler.joblib", "scaler.joblib"),
                  (stage / "models/autoencoder_float32.tflite", "autoencoder_float32.tflite"),
                  (stage / "models/threshold.json", "source_ae_threshold.json"),
                  (stage / "results/tflite_consistency.json", "tflite_consistency.json"),
                  (Path(__file__), "adapter_source.py"), (Path(common.__file__), "common_comparison_source.py"),
                  (inputs["dataset"] / "manifest.json", "prepared_manifest.json"),
                  (inputs["dataset"] / "plan.json", "prepared_plan.json")]
        for source, name in copies:
            preparation.copy_exclusive(source, frozen / name)
        joblib.dump(forest, frozen / "isolation_forest.joblib")
        bundle = {"status": "ready_development_only", "contract": CONTRACT, "window_size": 128,
                  "dataset_manifest_sha256": common.sha256(inputs["dataset"] / "manifest.json"),
                  "scaler": scaler_doc, "if_parameters": common.IF_PARAMETERS,
                  "recordings": inputs["manifest"]["sources"],
                  "window_counts": {s: len(a) for s, a in inputs["ac"].items()},
                  "measurement_chain_status": "pilot_limitations_unresolved", "thresholds": {}}
        functions, runtimes = model_scorers(bundle, frozen, runtime, threads)
        scores = {m: np.asarray([functions[m](w.copy()) for w in prepared["features"]["validation"]], dtype=np.float64) for m in METHODS}
        for method in METHODS:
            common.p99(scores[method])  # Check all scores finite before committing a bundle.
            frozen_value = result["threshold"] if method == "tflite_autoencoder" else common.p99(scores[method])
            bundle["thresholds"][method] = {"value": float(frozen_value), "percentile": 99,
                "source": "FROZEN_KERAS_NORMAL_VALIDATION_P99" if method == "tflite_autoencoder" else "NORMAL_VALIDATION_P99"}
        threshold = result["threshold"]
        keras_scores = pd.read_csv(stage / "results/validation_reconstruction_errors.csv")["reconstruction_error_mse"].to_numpy(np.float64)
        tolerance = result["consistency"]["acceptance_limits"]["maximum_absolute_mse_difference"]
        ae_scores = scores["tflite_autoencoder"]
        preparation.check(np.max(abs(ae_scores - keras_scores)) <= tolerance,
                          "Selected TFLite runtime differs from frozen Keras errors")
        preparation.check(np.array_equal(ae_scores > threshold, keras_scores > threshold),
                          "Selected TFLite runtime changes frozen decisions")
        preparation.check(abs(common.p99(ae_scores) - threshold) <= tolerance, "TFLite P99 mismatch; threshold not adjusted")
        bundle["ae_runtime_check"] = {"runtime": runtimes["tflite_autoencoder"],
            "maximum_absolute_mse_difference": float(np.max(abs(ae_scores - keras_scores))),
            "acceptance_tolerance": tolerance, "threshold_recalibrated": False}
        bundle["artifact_sha256"] = {p.name: common.sha256(p) for p in frozen.iterdir() if p.is_file()}
        validate_bundle_contract(bundle)
        # Successful preparation is rechecked before a ready bundle is committed.
        preparation.verify(inputs["dataset"])
        rows = dispatch_prepared(inputs["ac"]["validation"], inputs["metadata"]["validation"].to_dict("records"), bundle, functions)
        preparation.check(all(r["decision"] != "INVALID" for r in rows), "Invalid validation decision")
        metrics = common.quality_report(rows)
        common.write_rows(output / "validation_diagnostics.csv", rows)
        common.write_json(frozen / "pilot_bundle.json", bundle)
        with (frozen / "pilot_bundle.sha256").open("x") as handle:
            handle.write(common.sha256(frozen / "pilot_bundle.json") + "\n")
        load_bundle(frozen)
        common.write_json(output / "training_completed.json", {"status": "completed_development_only",
            "bundle_sha256": common.sha256(frozen / "pilot_bundle.json"), "window_counts": bundle["window_counts"],
            "independent_test": False, "validation_used_for_early_stopping_and_thresholds": True,
            "metrics": metrics, "runtimes": runtimes})
        return bundle
    except BaseException as exc:
        # Preserve failed artifacts, but never leave a loadable ready marker.
        for name in ("pilot_bundle.json", "pilot_bundle.sha256"):
            marker = output / "frozen" / name
            if marker.exists():
                marker.rename(marker.with_name("uncommitted_" + name))
        common.write_json(output / "training_failed.json", {"status": "failed_no_automatic_restart", "error_type": type(exc).__name__, "error": str(exc)})
        raise


def replay(dataset, bundle_directory, output, runtime="auto", threads=1):
    """Replay only the existing development validation, with frozen artifacts."""
    output = Path(output).resolve()
    preparation.check(not output.exists(), "Replay output exists; no overwrite")
    bundle_directory = Path(bundle_directory).resolve()
    bundle = load_bundle(bundle_directory)
    anchor = common.sha256(bundle_directory / "pilot_bundle.json")
    inputs = load_inputs(dataset)
    preparation.check(common.sha256(inputs["dataset"] / "manifest.json") == bundle["dataset_manifest_sha256"], "Replay dataset differs from bundle")
    functions, runtimes = model_scorers(bundle, bundle_directory, runtime, threads)
    rows = dispatch_prepared(inputs["ac"]["validation"], inputs["metadata"]["validation"].to_dict("records"), bundle, functions)
    load_bundle(bundle_directory)
    preparation.check(common.sha256(bundle_directory / "pilot_bundle.json") == anchor, "Frozen bundle changed during replay")
    output.mkdir(parents=True, exist_ok=False)
    common.write_rows(output / "development_validation_replay.csv", rows)
    report = {"evidence_scope": "existing_development_validation_replay_not_independent_test", "bundle_sha256": anchor,
              "models_or_scaler_fitted": False, "thresholds_recalibrated": False,
              "runtimes": runtimes, "metrics": common.quality_report(rows)}
    common.write_json(output / "replay_report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("audit", "train", "replay"):
        sub = subs.add_parser(command)
        sub.add_argument("--dataset", type=Path, required=True)
        sub.add_argument("--output", type=Path, required=True)
        if command != "audit":
            sub.add_argument("--runtime", choices=("auto", "litert", "tensorflow"), default="auto")
            sub.add_argument("--threads", type=int, default=1)
        if command == "replay":
            sub.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "audit":
        result = audit(args.dataset, args.output)
    elif args.command == "train":
        result = train(args.dataset, args.output, args.runtime, args.threads)
    else:
        result = replay(args.dataset, args.bundle, args.output, args.runtime, args.threads)
    print(json.dumps({key: value for key, value in result.items() if key in ("status", "window_counts", "evidence_scope", "models_trained")}, indent=2))


if __name__ == "__main__":
    main()
