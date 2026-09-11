#!/usr/bin/env python3
"""Offline, non-overwriting preparation of recorded normal development pilots.

This module neither imports hardware drivers nor fits models or a scaler.
Its dataset schema deliberately differs from a trained calibration profile.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

AXES = ["x_g", "y_g", "z_g"]
ALLOWED_STATES = {"normal_before", "normal_after", "normal_followup"}
PREPROCESSING_ID = "xyz_window128_axis_mean_removed_unscaled_v1"
EXPECTED_MOUNTING = "fan_upright_position_v4_20260911_103726"
EXPECTED_SENSOR = {
    "model": "ADXL345", "odr_hz": 200, "range_g": 2, "full_resolution": True,
    "scale_g_per_lsb": 0.0039, "acquisition_mode": "fifo_stream",
    "register_readback": {"0x2c": "0xb", "0x31": "0x8", "0x2e": "0x0", "0x38": "0x90", "0x2d": "0x8"},
    "timestamp_source": "host_monotonic_read_completion", "bus_number": 1,
    "i2c_clock_configured_hz": 100000,
}


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def check(condition, message):
    if not condition:
        raise ValueError(message)


def integral_column(frame, name):
    values = frame[name].to_numpy()
    check(np.all(np.isfinite(values)), f"{name}: non-finite values")
    integers = values.astype(np.int64)
    check(np.array_equal(values, integers), f"{name}: noninteger values")
    return integers


def make_windows(df, command_ns, start_s=180., end_s=300., size=128):
    """Select by host completion relative to command; never join recordings."""
    check(0 <= start_s < end_s and size >= 1, "Invalid window parameters")
    host = integral_column(df, "host_monotonic_ns")
    indices = integral_column(df, "sample_index")
    axes = df[AXES].to_numpy(dtype=np.float64)
    check(len(df) > 1 and np.all(np.diff(host) > 0), "Nonmonotonic host time")
    check(np.all(np.diff(indices) == 1), "Noncontiguous source indices")
    check(np.all(np.isfinite(axes)), "Non-finite XYZ")
    relative_ns = host - int(command_ns)
    selected = np.flatnonzero((relative_ns >= round(start_s * 1e9)) &
                              (relative_ns < round(end_s * 1e9)))
    count = len(selected) // size
    check(count > 0, "Fewer than one complete window in selected interval")
    start = int(selected[0])
    used = count * size
    raw64 = axes[start:start + used].reshape(count, size, 3)
    ac64 = raw64 - raw64.mean(axis=1, keepdims=True)
    rows = []
    for i in range(count):
        first = start + i * size
        last = first + size - 1
        rows.append({
            "window_index_in_recording": i,
            "source_start_index": int(indices[first]),
            "source_end_index_exclusive": int(indices[last]) + 1,
            "start_host_monotonic_ns": int(host[first]),
            "last_host_monotonic_ns": int(host[last]),
            "start_since_command_s": float(relative_ns[first] / 1e9),
            "last_since_command_s": float(relative_ns[last] / 1e9),
            "first_to_last_span_s": float((host[last] - host[first]) / 1e9),
        })
    return {"raw_g": raw64.astype(np.float32), "ac_g": ac64.astype(np.float32),
            "window_rows": rows, "xyz_selected": len(selected),
            "trailing_xyz_dropped": len(selected) - used}


def validate_plan(plan):
    check(plan.get("schema_version") == 1 and plan.get("purpose") == "development_pilot_preparation",
          "Not a supported development preparation plan")
    check(plan.get("preprocessing_id") == PREPROCESSING_ID, "Unsupported preprocessing")
    check(plan.get("selection_seconds_since_pwm_command") == [180, 300], "Unsupported interval")
    check(plan.get("window_size") == 128 and plan.get("step_size") == 128, "Unsupported window size/step")
    check(plan.get("mounting_id") == EXPECTED_MOUNTING, "Unsupported mounting version")
    for key, value in EXPECTED_SENSOR.items():
        check(plan.get("sensor", {}).get(key) == value, f"Invalid sensor plan: {key}")
    sources = plan["sources"]
    check(len(sources) == 3, "This pilot requires exactly three whole recordings")
    check([s["state"] for s in sources] == ["normal_before", "normal_after", "normal_followup"],
          "Unexpected source order or condition")
    check([s["split"] for s in sources] == ["train", "train", "validation"], "Unexpected whole-record split")
    for key in ("csv", "csv_sha256", "recording_id", "metadata", "metadata_sha256"):
        check(len({str(s[key]) for s in sources}) == len(sources), f"Duplicate source identity: {key}")
    for source in sources:
        check(Path(source["recording_id"]).name == source["recording_id"], "Unsafe recording ID")
        check(source.get("evidence"), "Evidence references missing")


def timing_summary(df, command_ns):
    host = integral_column(df, "host_monotonic_ns")
    intervals = np.diff(host) / 1e6
    span = float((host[-1] - host[0]) / 1e9)
    return {
        "xyz_points": len(df), "individual_axis_values": 3 * len(df),
        "first_to_last_host_span_s": span,
        "observed_xyz_per_second": (len(df) - 1) / span,
        "nominal_sensor_odr_hz": 200,
        "first_xyz_after_command_s": float((host[0] - command_ns) / 1e9),
        "last_xyz_after_command_s": float((host[-1] - command_ns) / 1e9),
        "host_interval_p50_ms": float(np.median(intervals)),
        "host_interval_p99_ms": float(np.percentile(intervals, 99)),
        "host_interval_max_ms": float(intervals.max()),
        "host_intervals_over_10ms": int(np.count_nonzero(intervals > 10)),
        "read_duration_max_ms": float(df["read_duration_ns"].max() / 1e6),
        "fifo_depth_max": int(df["fifo_depth"].max()),
        "gap_flagged_xyz": 0, "overrun_flagged_xyz": 0, "saturated_xyz": 0,
        "exact_lost_sensor_samples": None,
    }


def validate_recording(csv, metadata, source, plan):
    """Check full original recording before selecting any sample."""
    check(sha256(csv) == source["csv_sha256"], "CSV hash mismatch")
    check(sha256(metadata) == source["metadata_sha256"], "Metadata hash mismatch")
    m = json.loads(Path(metadata).read_text())
    check(m.get("csv_sha256") == source["csv_sha256"], "Acquisition journal CSV hash mismatch")
    check(m.get("status") == "completed" and m.get("schema_version") == 1, "Incomplete recording")
    check(m.get("purpose") == "pilot" and m.get("split") == "development_pilot", "Unexpected acquisition purpose")
    check(m.get("recording_id") == source["recording_id"], "Recording ID mismatch")
    check(m.get("state") == source["state"] in ALLOWED_STATES and m.get("label") == 0,
          "Source is not the designated normal condition")
    check(m.get("phase") == source["state"] and m.get("condition_label") == source["state"], "Phase mismatch")
    check(m.get("mounting_id") == plan["mounting_id"], "Different mounting version")
    check(m.get("fan_pwm_setpoint_percent") == 75 and m.get("fan_pwm_frequency_hz") == 25000,
          "Different PWM specification")
    check(m.get("configured_duration_seconds") == 300 and m.get("code"), "Duration or code journal missing")
    check(m.get("detection_controls_fan") is False, "Detection-dependent fan control not permitted")
    sensor = m.get("sensor", {})
    for key, expected in plan["sensor"].items():
        check(sensor.get(key) == expected, f"Sensor configuration mismatch: {key}")
    df = pd.read_csv(csv, float_precision="round_trip")
    required = {*AXES, "sample_index", "host_monotonic_ns", "timestamp_s", "sensor_time_estimate_s",
                "fifo_depth", "read_duration_ns", "label", "anomaly_type", "gap", "overrun", "saturated"}
    check(required <= set(df.columns) and len(df) > 128, "Missing acquisition fields")
    check(set(df["anomaly_type"]) == {source["state"]} and df["label"].eq(0).all(), "Invalid normal labels")
    for flag in ("gap", "overrun", "saturated"):
        check(df[flag].astype(str).str.lower().isin(["false", "0", "0.0"]).all(), f"Invalid or set {flag} flag")
    host = integral_column(df, "host_monotonic_ns")
    idx = integral_column(df, "sample_index")
    check(idx[0] == 0 and np.all(np.diff(idx) == 1), "Invalid source sample indices")
    check(np.all(np.diff(host) > 0), "Nonmonotonic host timestamps")
    check(np.all(np.isfinite(df[AXES].to_numpy())), "Non-finite acceleration")
    ts = df["timestamp_s"].to_numpy(dtype=np.float64)
    estimate = df["sensor_time_estimate_s"].to_numpy(dtype=np.float64)
    check(np.all(np.isfinite(ts)) and np.all(np.diff(ts) > 0), "Nonmonotonic relative timestamps")
    check(np.allclose(ts - ts[0], (host - host[0]) / 1e9, atol=1e-7, rtol=0), "Inconsistent timestamp bases")
    check(np.allclose(estimate, idx / 200, atol=1e-7, rtol=0), "Inconsistent nominal time estimates")
    fifo = integral_column(df, "fifo_depth")
    read_ns = integral_column(df, "read_duration_ns")
    check(np.all((fifo >= 1) & (fifo < 32)), "Invalid or full FIFO")
    check(np.all(read_ns >= 0), "Invalid read duration")
    check(np.max(np.diff(host)) <= 160_000_000, "Host gap exceeds nominal FIFO capacity")
    summary = m.get("summary", {})
    check(summary.get("samples") == len(df), "Journal sample count mismatch")
    for key in ("overrun_flagged_samples", "gap_flagged_samples", "saturated_samples", "nonmonotonic_host_intervals"):
        check(summary.get(key) == 0, f"Journal missing or nonzero: {key}")
    command_ns = m.get("pwm_command_invocation_monotonic_ns")
    check(isinstance(command_ns, int), "Missing command monotonic origin")
    quality = timing_summary(df, command_ns)
    check(0 <= quality["first_xyz_after_command_s"] < 1 and quality["last_xyz_after_command_s"] >= 299.9,
          "Incomplete 300-second acquisition coverage")
    check(abs(quality["observed_xyz_per_second"] - summary["observed_host_rate_hz"]) < 1e-6,
          "Observed rate differs from acquisition journal")
    return df, m, quality


def copy_exclusive(source, target):
    with Path(source).open("rb") as inp, Path(target).open("xb") as out:
        while chunk := inp.read(1024 * 1024):
            out.write(chunk)
    check(sha256(source) == sha256(target), "Copy integrity failure")


def source_summary(source, df, meta, quality, windows):
    command_ns = meta["pwm_command_invocation_monotonic_ns"]
    host = df["host_monotonic_ns"].to_numpy(dtype=np.int64)
    chosen = df.loc[(host - command_ns >= 180_000_000_000) & (host - command_ns < 300_000_000_000)]
    return {**source, "snapshot_directory": f"sources/{source['recording_id']}",
            "quality_full_recording": quality, "quality_selected_interval": timing_summary(chosen, command_ns),
            "xyz_selected": windows["xyz_selected"], "window_count": len(windows["raw_g"]),
            "trailing_xyz_dropped": windows["trailing_xyz_dropped"],
            "pwm_command_invocation_utc": meta["pwm_command_invocation_utc"],
            "pwm_command_invocation_monotonic_ns": command_ns}


def prepare(plan_path, output):
    plan_path, output = Path(plan_path).resolve(), Path(output).resolve()
    plan = json.loads(plan_path.read_text())
    validate_plan(plan)
    check(not output.exists(), "Output exists; overwriting is prohibited")
    # Reject invalid sources before creating the export.
    recordings = []
    for source in plan["sources"]:
        df, m, quality = validate_recording(source["csv"], source["metadata"], source, plan)
        for evidence in source["evidence"]:
            check(sha256(evidence["path"]) == evidence["sha256"], "Evidence hash mismatch")
        windows = make_windows(df, m["pwm_command_invocation_monotonic_ns"])
        recordings.append((source, df, m, quality, windows))
    commands = [r[2]["pwm_command_invocation_monotonic_ns"] for r in recordings]
    check(commands == sorted(set(commands)), "Sources are not in chronological command order")
    boot_ids = [r[2]["user_release"]["boot_id"] for r in recordings]
    check(len(set(boot_ids)) == 1, "Cannot compare monotonic origins across different boots")
    output.mkdir(parents=True, exist_ok=False)
    (output / "sources").mkdir()
    copy_exclusive(plan_path, output / "plan.json")
    copy_exclusive(__file__, output / "preparation_source.py")
    manifest = {"schema_version": 1, "status": "prepared_unscaled_development_dataset",
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "plan_sha256": sha256(plan_path), "preprocessing_id": PREPROCESSING_ID,
                "models_trained": False, "scaler_fitted": False, "thresholds_calibrated": False,
                "independent_test_set": False, "sources": [], "splits": {}, "artifacts": {}}
    all_arrays = {s: {"raw_g": [], "ac_g": []} for s in ("train", "validation")}
    rows = {s: [] for s in all_arrays}
    for source, df, m, quality, windows in recordings:
        split = source["split"]
        dest = output / "sources" / source["recording_id"]
        dest.mkdir()
        copy_exclusive(source["csv"], dest / "original.csv")
        copy_exclusive(source["metadata"], dest / "original.json")
        for i, evidence in enumerate(source["evidence"]):
            copy_exclusive(evidence["path"], dest / f"evidence_{i}{Path(evidence['path']).suffix}")
        for kind in ("raw_g", "ac_g"):
            all_arrays[split][kind].append(windows[kind])
        for row in windows["window_rows"]:
            rows[split].append({"split_index": len(rows[split]), "split": split,
                                "recording_id": source["recording_id"], "original_state": source["state"],
                                "source_csv_sha256": source["csv_sha256"], "label": 0, **row})
        manifest["sources"].append(source_summary(source, df, m, quality, windows))
    for split in all_arrays:
        for kind in ("raw_g", "ac_g"):
            values = np.concatenate(all_arrays[split][kind])
            with (output / f"{split}_{kind}.npy").open("xb") as handle:
                np.save(handle, values, allow_pickle=False)
        with (output / f"{split}_labels.npy").open("xb") as handle:
            np.save(handle, np.zeros(len(rows[split]), dtype=np.int8), allow_pickle=False)
        pd.DataFrame(rows[split]).to_csv(output / f"{split}_windows.csv", index=False, mode="x")
        manifest["splits"][split] = {"recordings": sum(s["split"] == split for s in plan["sources"]),
                                     "windows": len(rows[split]), "shape": [len(rows[split]), 128, 3]}
    for path in sorted(output.rglob("*")):
        if path.is_file():
            manifest["artifacts"][str(path.relative_to(output))] = sha256(path)
    write_json(output / "manifest.json", manifest)
    verify(output)
    return manifest


def verify(output):
    """Verify exports against all original source samples, not just examples."""
    output = Path(output).resolve()
    manifest = json.loads((output / "manifest.json").read_text())
    plan = json.loads((output / "plan.json").read_text())
    validate_plan(plan)
    check(sha256(output / "plan.json") == manifest["plan_sha256"], "Plan hash mismatch")
    check(manifest["sources"] and manifest["status"] == "prepared_unscaled_development_dataset", "Invalid dataset status")
    check(manifest["preprocessing_id"] == PREPROCESSING_ID, "Preprocessing mismatch")
    for name in ("models_trained", "scaler_fitted", "thresholds_calibrated", "independent_test_set"):
        check(manifest[name] is False, f"Unexpected dataset claim: {name}")
    inventory = {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file() and p != output / "manifest.json"}
    check(set(manifest["artifacts"]) == inventory, "Artifact inventory mismatch")
    for name, expected in manifest["artifacts"].items():
        target = (output / name).resolve()
        check(target.is_relative_to(output), "Artifact path escapes dataset")
        check(sha256(target) == expected, f"Artifact hash mismatch: {name}")
    expected = {s: {"raw_g": [], "ac_g": []} for s in ("train", "validation")}
    expected_rows = {s: [] for s in expected}
    expected_sources = []
    for source in plan["sources"]:
        df, meta, quality = validate_recording(source["csv"], source["metadata"], source, plan)
        snapshot = output / "sources" / source["recording_id"]
        check(sha256(snapshot / "original.csv") == source["csv_sha256"], "Source snapshot mismatch")
        check(sha256(snapshot / "original.json") == source["metadata_sha256"], "Journal snapshot mismatch")
        for i, evidence in enumerate(source["evidence"]):
            check(sha256(evidence["path"]) == evidence["sha256"], "Original evidence changed")
            check(sha256(snapshot / f"evidence_{i}{Path(evidence['path']).suffix}") == evidence["sha256"], "Evidence snapshot mismatch")
        derived = make_windows(df, meta["pwm_command_invocation_monotonic_ns"])
        expected_sources.append(source_summary(source, df, meta, quality, derived))
        split = source["split"]
        for kind in ("raw_g", "ac_g"):
            expected[split][kind].append(derived[kind])
        for row in derived["window_rows"]:
            expected_rows[split].append({"split_index": len(expected_rows[split]), "split": split,
                "recording_id": source["recording_id"], "original_state": source["state"],
                "source_csv_sha256": source["csv_sha256"], "label": 0, **row})
    check(manifest["sources"] == expected_sources, "Source summary mismatch")
    commands = [row["pwm_command_invocation_monotonic_ns"] for row in expected_sources]
    check(commands == sorted(set(commands)), "Invalid chronological source order")
    for split in expected:
        for kind in ("raw_g", "ac_g"):
            actual = np.load(output / f"{split}_{kind}.npy", allow_pickle=False)
            check(np.array_equal(actual, np.concatenate(expected[split][kind])), f"Derived {split}/{kind} mismatch")
        labels = np.load(output / f"{split}_labels.npy", allow_pickle=False)
        check(labels.shape == (len(expected_rows[split]),) and np.all(labels == 0), "Label mismatch")
        actual_rows = pd.read_csv(output / f"{split}_windows.csv", float_precision="round_trip")
        pd.testing.assert_frame_equal(actual_rows, pd.DataFrame(expected_rows[split]), check_exact=True)
        check(manifest["splits"][split] == {"recordings": sum(s["split"] == split for s in plan["sources"]),
              "windows": len(expected_rows[split]), "shape": [len(expected_rows[split]), 128, 3]}, "Split summary mismatch")
    return {"verified": True, "original_recordings": 3,
            "all_raw_and_ac_windows_recomputed_exactly": True,
            "train_windows": len(expected_rows["train"]), "validation_windows": len(expected_rows["validation"])}


def load_prepared_pilot(output):
    """Future consumers must verify provenance and use this shared AC input.

    Returned arrays are unscaled. Fitting a train-only scaler and adapting the
    legacy training/comparison entry points are separate, explicit operations.
    """
    verify(output)
    output = Path(output)
    return {split: np.load(output / f"{split}_ac_g.npy", allow_pickle=False)
            for split in ("train", "validation")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan", type=Path)
    group.add_argument("--verify", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.verify:
        parser.error("--output is not used with --verify") if args.output else None
        print(json.dumps(verify(args.verify), indent=2))
    else:
        if args.output is None:
            parser.error("--output is required with --plan")
        manifest = prepare(args.plan, args.output)
        print(json.dumps({"status": manifest["status"], "splits": manifest["splits"]}, indent=2))


if __name__ == "__main__":
    main()
