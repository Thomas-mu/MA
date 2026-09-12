#!/usr/bin/env python3
"""Read-only frozen-model evaluation of a new Normal / altered airflow / Normal sequence.

No hardware access, training, fitting, threshold selection, or automatic retries.
The protocol and acquisition journals are required provenance, not optional labels.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import pilot_method_comparison as pilot
import prepare_pilot_dataset as preparation
import independent_normal_test as independent
import controlled_airflow_contract as contract
from controlled_airflow_contract import PHASES, conditions, validate_release_conditions

# Reuse the verified inference inputs and quality conventions without modifying them.
build_windows = independent.build_windows
summarize_quality = independent.summarize_quality
verify_pwm = independent.verify_pwm
flag_values = independent.flag_values

check = preparation.check
sha256 = preparation.sha256
write_json = preparation.write_json
AXES = preparation.AXES
METHODS = pilot.METHODS
FLAGS = ("gap", "overrun", "saturated")
FROZEN_BUNDLE_SHA256 = "cec1859bfb354bafef77a619e6d2c1ffd85b50787c87595aba9a1e20a80cdae5"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def utc(value):
    parsed = datetime.fromisoformat(value)
    check(parsed.tzinfo is not None, "UTC timestamp requires timezone")
    return parsed.astimezone(timezone.utc)


def load_protocol(path):
    path = Path(path).resolve()
    digest = sha256(path)
    check((path.parent / "protocol.sha256").read_text().strip() == digest,
          "Protocol fingerprint changed")
    p = read_json(path)
    check(p.get("schema_version") == 1 and p.get("purpose") == "controlled_airflow_test",
          "Unsupported test protocol")
    check(p.get("protocol_id") and p.get("boot_id"), "Missing protocol identity/boot")
    check(isinstance(p.get("frozen_at_monotonic_ns"), int), "Missing protocol freeze time")
    utc(p["frozen_at_utc"])
    check(p.get("mounting_id") == preparation.EXPECTED_MOUNTING, "Wrong mounting version")
    for name, expected in preparation.EXPECTED_SENSOR.items():
        check(p.get("sensor", {}).get(name) == expected, f"Wrong planned sensor setting: {name}")
    for name, expected in {"selection_seconds_since_pwm_command": [180, 300],
                           "window_size": 128, "step_size": 128, "pwm_percent": 75,
                           "pwm_frequency_hz": 25000, "duration_s": 300,
                           "additional_off_after_release_s": 60,
                           "planned_runs": list(PHASES)}.items():
        check(p.get(name) == expected, f"Unsupported frozen test parameter: {name}")
    frozen = p["frozen_bundle"]
    check(frozen.get("sha256") == FROZEN_BUNDLE_SHA256, "Wrong authorized frozen pilot package")
    directory = Path(frozen["directory"]).resolve()
    check(sha256(directory / "pilot_bundle.json") == frozen["sha256"], "Bundle protocol anchor mismatch")
    bundle = pilot.load_bundle(directory)
    check(p.get("evaluator_sha256") == sha256(__file__), "Test evaluator differs from protocol")
    pinned = p.get("implementation_sha256", {})
    required_modules = {str(Path(module.__file__).resolve()) for module in
                        (independent, contract, pilot, preparation)} | {str(Path(__file__).resolve())}
    check(isinstance(pinned, dict) and required_modules <= set(pinned),
          "Missing shared implementation fingerprints")
    for source_path, expected_digest in pinned.items():
        source_path = Path(source_path)
        check(source_path.is_absolute() and source_path.is_file() and sha256(source_path) == expected_digest,
              f"Protocol implementation changed: {source_path}")
    excluded = p.get("excluded_recordings", {})
    for key in ("csv_sha256", "recording_ids", "csv_paths"):
        check(isinstance(excluded.get(key), list) and excluded[key], f"Missing historical exclusion inventory: {key}")
    historical = read_json(directory / "prepared_manifest.json")["sources"]
    for source in historical:
        check(source["csv_sha256"] in excluded["csv_sha256"] and
              source["recording_id"] in excluded["recording_ids"] and
              str(Path(source["csv"]).resolve()) in excluded["csv_paths"],
              "Training/validation recording missing from test exclusion inventory")
    return p, digest, bundle, directory


def load_test_recording(csv, sidecar, protocol, session):
    """Reject structural/provenance corruption; flag affected windows for all methods."""
    csv, sidecar, session = (Path(x).resolve() for x in (csv, sidecar, session))
    p, protocol_hash, bundle, directory = load_protocol(protocol)
    m, journal = read_json(sidecar), read_json(session)
    csv_hash = sha256(csv)
    source = {"csv": str(csv), "csv_sha256": csv_hash, "sidecar": str(sidecar),
              "sidecar_sha256": sha256(sidecar), "session": str(session),
              "session_sha256": sha256(session), "protocol_sha256": protocol_hash,
              "frozen_bundle_sha256": p["frozen_bundle"]["sha256"],
              "recording_id": m.get("recording_id"), "phase": m.get("phase")}
    excluded = p["excluded_recordings"]
    check(csv_hash not in excluded["csv_sha256"] and str(csv) not in excluded["csv_paths"] and
          m.get("recording_id") not in excluded["recording_ids"], "Recording is not independent of prior data")
    check(m.get("recording_id") == csv.stem, "Recording ID must equal unique CSV stem")
    check(m.get("phase") in p["planned_runs"], "Unplanned run identity")
    check(m.get("schema_version") == 1 and m.get("status") == "completed", "Incomplete source recording")
    state, label = conditions(m["phase"])
    for name, expected in {"purpose": "test", "split": "independent_test", "state": state,
                           "condition_label": state, "label": label, "mounting_id": p["mounting_id"],
                           "fan_pwm_setpoint_percent": 75, "fan_pwm_frequency_hz": 25000,
                           "configured_duration_seconds": 300, "detection_controls_fan": False,
                           "protocol_id": p["protocol_id"], "protocol_sha256": protocol_hash,
                           "frozen_bundle_sha256": p["frozen_bundle"]["sha256"]}.items():
        check(m.get(name) == expected, f"Recording contract mismatch: {name}")
    check(m.get("csv_sha256") == csv_hash, "Source CSV hash mismatch")
    check(m.get("code"), "Acquisition implementation provenance missing")
    for name, expected in p["sensor"].items():
        check(m.get("sensor", {}).get(name) == expected, f"Acquired sensor mismatch: {name}")
    check(journal.get("status") == "completed" and journal.get("recording") == m,
          "Incomplete session or sidecar/session mismatch")
    for name in ("phase", "mounting_id", "protocol_id", "protocol_sha256", "frozen_bundle_sha256"):
        check(journal.get(name) == m[name], f"Session identity mismatch: {name}")
    check(Path(journal["csv"]).resolve() == csv, "Session CSV path mismatch")
    command = m.get("pwm_command_invocation_monotonic_ns")
    check(isinstance(command, int) and command > p["frozen_at_monotonic_ns"], "Acquisition predates frozen protocol")
    check(journal.get("command_invocation_monotonic_ns") == command, "Session command time mismatch")
    command_utc = utc(m["pwm_command_invocation_utc"])
    check(command_utc > utc(p["frozen_at_utc"]) and utc(journal["command_invocation_utc"]) == command_utc,
          "Command UTC predates frozen protocol or differs across journals")
    release = m.get("user_release", {})
    check(release.get("released") is True and release.get("phase") == m["phase"] and
          release.get("boot_id") == p["boot_id"], "Missing matching same-boot explicit release")
    check(journal.get("boot_id") == p["boot_id"], "Session boot differs from frozen protocol")
    for field, expected in {"source": "explicit_user_message", "authorized_phases": [m["phase"]],
                            "protocol_id": p["protocol_id"], "protocol_sha256": protocol_hash,
                            "mounting_id": p["mounting_id"]}.items():
        check(release.get(field) == expected, f"Release identity mismatch: {field}")
    validate_release_conditions(release, m["phase"])
    check(m.get("plate_geometry") == release.get("plate_geometry") == journal.get("plate_geometry"),
          "Planned/released/recorded geometry differs")
    check(journal.get("user_release") == release, "Session/reported release mismatch")
    accepted = release.get("accepted_monotonic_ns")
    check(isinstance(accepted, int) and accepted >= p["frozen_at_monotonic_ns"] and
          command - accepted >= 60_000_000_000, "Additional off time/release chronology invalid")
    check(utc(release["accepted_utc"]) >= utc(p["frozen_at_utc"]), "Release UTC predates protocol")
    verify_pwm(journal.get("after_capture_readback", {}), 30000)
    verify_pwm(journal.get("final_readback", {}), 0)
    zero = journal.get("zero_command_completed_monotonic_ns")
    check(isinstance(zero, int) and zero > command, "Final zero command chronology missing")
    frame = pd.read_csv(csv, float_precision="round_trip")
    required = {*AXES, "sample_index", "host_monotonic_ns", "timestamp_s", "sensor_time_estimate_s",
                "fifo_depth", "read_duration_ns", "label", "anomaly_type", *FLAGS}
    check(required <= set(frame) and len(frame) > 128, "Missing acquisition columns/points")
    check(frame["label"].eq(label).all() and set(frame["anomaly_type"]) == {state},
          "CSV condition labels differ from released phase")
    idx = preparation.integral_column(frame, "sample_index")
    host = preparation.integral_column(frame, "host_monotonic_ns")
    check(idx[0] == 0 and np.all(np.diff(idx) == 1), "Structural sample index discontinuity")
    check(np.all(np.diff(host) > 0), "Structural nonmonotonic host time")
    ts = frame["timestamp_s"].to_numpy(np.float64)
    nominal = frame["sensor_time_estimate_s"].to_numpy(np.float64)
    check(np.isfinite(ts).all() and np.all(np.diff(ts) > 0) and
          np.allclose(ts - ts[0], (host - host[0]) / 1e9, rtol=0, atol=1e-7), "Inconsistent relative time base")
    check(np.isfinite(nominal).all() and np.allclose(nominal, idx / 200, rtol=0, atol=1e-7),
          "Inconsistent nominal sensor time estimate")
    fifo = preparation.integral_column(frame, "fifo_depth")
    reads = preparation.integral_column(frame, "read_duration_ns")
    check(np.all((fifo >= 1) & (fifo <= 32)) and np.all(reads >= 0), "Invalid FIFO/read-duration fields")
    quality = summarize_quality(frame, command)
    check(0 <= quality["first_xyz_after_command_s"] < 1 and quality["first_to_last_host_span_s"] >= 299.8 and
          quality["last_xyz_after_command_s"] >= 299.9 and host[-1] < zero,
          "Incomplete 300-second recording or impossible command chronology")
    summary = m.get("summary", {})
    check(summary.get("samples") == len(frame), "Journal point count mismatch")
    check(abs(summary.get("observed_host_rate_hz", -1) - quality["observed_xyz_per_second"]) < 1e-6,
          "Journal throughput mismatch")
    for flag, field in (("gap", "gap_flagged_samples"), ("overrun", "overrun_flagged_samples"),
                        ("saturated", "saturated_samples")):
        check(summary.get(field) == quality[f"{flag}_flagged_xyz"], f"Journal quality count mismatch: {flag}")
    check(summary.get("nonmonotonic_host_intervals") == 0, "Journal time quality mismatch")
    check(summary.get("lost_samples_exact") is None, "Physical loss count must remain unknown")
    windows, selected = build_windows(frame, command)
    quality["selected_interval"] = selected
    return {"frame": frame, "windows": windows, "metadata": m, "quality": quality,
            "source": source, "protocol": p, "bundle": bundle, "bundle_directory": directory,
            "session": journal}


def score_loaded(recording, score_functions):
    """Apply each frozen scorer to the same verified, centered and scaled inputs."""
    bundle = recording["bundle"]
    thresholds = {method: bundle["thresholds"][method]["value"] for method in METHODS}
    state, label = conditions(recording["metadata"]["phase"])
    rows = []
    for window in recording["windows"]:
        meta = {**recording["source"], **window["metadata"], "label": label, "state": state}
        if not meta["quality_valid"]:
            decisions = {method: {"score": None, "prediction": None, "decision": "INVALID",
                                  "error": ", ".join(meta["quality_reasons"])} for method in METHODS}
        else:
            decisions = pilot.score_window(window["ac_float32"], bundle["scaler"], score_functions, thresholds)
        for method in METHODS:
            rows.append({**meta, "method": method, "threshold": thresholds[method], **decisions[method]})
    return rows


def condition_metrics(rows):
    """Normal FPR or altered-state alarm fraction; label 1 is not a defect truth."""
    check(bool(rows), "No scored rows")
    states = {(row["state"], row["label"]) for row in rows}
    check(len(states) == 1 and next(iter(states)) in {("normal", 0), ("airflow_modified", 1)},
          "Metrics require one genuine condition")
    state, label = next(iter(states))
    for row in rows:
        check(conditions(row["phase"]) == (state, label), "Phase/label mismatch in scored rows")
    output = {}
    for method in METHODS:
        chosen = [r for r in rows if r["method"] == method]
        valid = [r for r in chosen if r["decision"] in ("NORMAL", "ANOMALY")]
        check(len(chosen) == len(valid) + sum(r["decision"] == "INVALID" for r in chosen), "Unknown decision")
        alarms = sum(r["decision"] == "ANOMALY" for r in valid)
        value = {"total_windows": len(chosen), "valid_windows": len(valid),
                 "invalid_windows": len(chosen) - len(valid), "alarms": alarms,
                 "alarm_fraction_among_valid_windows": alarms / len(valid) if valid else None,
                 "condition": state}
        if state == "normal":
            value.update(false_alarms=alarms,
                         false_alarm_rate_among_valid_normal_windows=alarms / len(valid) if valid else None)
        else:
            value["interpretation"] = "Alarm fraction for a controlled altered operating state; not defect recall."
        output[method] = value
    return output


def rms_5s(recording):
    """Sixty time intervals; subtract each axis mean within each interval in Float64."""
    frame = recording["frame"]
    command = recording["metadata"]["pwm_command_invocation_monotonic_ns"]
    host = preparation.integral_column(frame, "host_monotonic_ns")
    relative = host - command
    raw = frame[AXES].to_numpy(np.float64)
    # The quality mask also marks a gap ending at the first point of a time block.
    rail_raw = raw / preparation.EXPECTED_SENSOR["scale_g_per_lsb"]
    masks = {**{flag: flag_values(frame, flag) for flag in FLAGS},
             "host_interval_over_160ms": np.r_[False, np.diff(host) > 160_000_000],
             "fifo_full": frame["fifo_depth"].to_numpy() == 32,
             "raw_saturation_rail": ((rail_raw <= -511) | (rail_raw >= 510)).any(axis=1),
             "nonfinite_xyz": (~np.isfinite(raw)).any(axis=1)}
    rows = []
    for block in range(60):
        start, end = block * 5, (block + 1) * 5
        chosen = np.flatnonzero((relative >= start * 1_000_000_000) & (relative < end * 1_000_000_000))
        errors = [name for name, mask in masks.items() if mask[chosen].any()]
        if len(chosen) < 2:
            errors.append("fewer_than_two_xyz_points")
        value = raw[chosen].copy(order="F")
        means = np.mean(value, axis=0) if len(chosen) and np.isfinite(value).all() else None
        rms = None
        std = None
        if not errors:
            centered = value - means
            rms = float(np.sqrt(np.mean(np.sum(centered * centered, axis=1))))
            std = np.std(value, axis=0, ddof=0)
        rows.append({"recording_id": recording["source"]["recording_id"],
                     "phase": recording["source"]["phase"], "block_index": block,
                     "start_since_command_s": start, "end_since_command_s_exclusive": end,
                     "midpoint_since_command_s": (start + end) / 2,
                     "xyz_points": len(chosen),
                     "first_since_command_s": float(relative[chosen[0]] / 1e9) if len(chosen) else None,
                     "last_since_command_s": float(relative[chosen[-1]] / 1e9) if len(chosen) else None,
                     "quality_valid": not errors, "quality_reasons": errors,
                     "axis_mean_g": means.tolist() if means is not None else None,
                     "axis_std_population_g": std.tolist() if std is not None else None,
                     "vector_ac_rms_g": rms, "vector_ac_rms_mg": 1000 * rms if rms is not None else None})
    return rows


def interval_description(rows, start=180, end=300):
    selected = [r for r in rows if start <= r["start_since_command_s"] and r["end_since_command_s_exclusive"] <= end]
    valid = [r for r in selected if r["quality_valid"] and r["vector_ac_rms_mg"] is not None]
    result = {"interval_seconds": [start, end], "total_5s_blocks": len(selected),
              "valid_5s_blocks": len(valid), "invalid_5s_blocks": len(selected) - len(valid),
              "mean_mg": None, "std_sample_mg": None, "min_mg": None, "max_mg": None,
              "coefficient_of_variation": None, "linear_slope_mg_per_min": None,
              "linear_change_over_interval_mg": None,
              "first_half_mean_mg": None, "second_half_mean_mg": None,
              "second_minus_first_half_mg": None,
              "inference": "Descriptive within-recording changes; blocks are not independent replicates."}
    if not valid:
        return result
    values = np.array([r["vector_ac_rms_mg"] for r in valid], dtype=np.float64)
    times = np.array([r["midpoint_since_command_s"] for r in valid], dtype=np.float64)
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1)) if len(values) > 1 else None
    result.update(mean_mg=mean, std_sample_mg=std, min_mg=float(values.min()), max_mg=float(values.max()),
                  coefficient_of_variation=std / mean if std is not None and mean != 0 else None)
    if len(values) > 1:
        centered_times = times - np.mean(times)
        slope = float(np.sum(centered_times * (values - mean)) / np.sum(centered_times**2))
        result.update(linear_slope_mg_per_min=60 * slope, linear_change_over_interval_mg=(end - start) * slope)
    halves = [values[times < (start + end) / 2], values[times >= (start + end) / 2]]
    if len(halves[0]):
        result["first_half_mean_mg"] = float(halves[0].mean())
    if len(halves[1]):
        result["second_half_mean_mg"] = float(halves[1].mean())
    if all(len(h) for h in halves):
        result["second_minus_first_half_mg"] = float(halves[1].mean() - halves[0].mean())
    return result


def compare_rms(rows):
    phases = list(dict.fromkeys(r["phase"] for r in rows))
    descriptions = {phase: interval_description([r for r in rows if r["phase"] == phase]) for phase in phases}
    result = {"late_interval_seconds": [180, 300], "per_phase": descriptions,
              "warmup_180_seconds_validated": False,
              "interpretation": "Within-run slopes and between-run means describe different effects. One sequence cannot establish general reproducibility or successful anomaly detection."}
    if not all(phase in descriptions for phase in PHASES):
        result["return_comparison"] = None
        return result
    before, modified, after = (descriptions[p] for p in PHASES)
    if any(r["mean_mg"] is None for r in (before, modified, after)):
        result["return_comparison"] = {"status": "insufficient_valid_blocks"}
        return result
    normal = [r for r in rows if r["phase"] in (PHASES[0], PHASES[2]) and
              180 <= r["start_since_command_s"] and r["quality_valid"]]
    after_values = [r["vector_ac_rms_mg"] for r in normal if r["phase"] == PHASES[2]]
    normal_min = min(before["min_mg"], after["min_mg"])
    normal_max = max(before["max_mg"], after["max_mg"])
    normal_span = normal_max - normal_min
    differences = {"modified_minus_before_mean_mg": modified["mean_mg"] - before["mean_mg"],
                   "modified_minus_after_mean_mg": modified["mean_mg"] - after["mean_mg"]}
    result["return_comparison"] = {
        "status": "descriptive", **differences,
        "after_minus_before_mean_mg": after["mean_mg"] - before["mean_mg"],
        "after_minus_before_percent_of_before_mean": 100 * (after["mean_mg"] / before["mean_mg"] - 1) if before["mean_mg"] != 0 else None,
        "before_observed_5s_range_mg": [before["min_mg"], before["max_mg"]],
        "after_mean_within_before_observed_5s_range": before["min_mg"] <= after["mean_mg"] <= before["max_mg"],
        "after_5s_blocks_within_before_observed_range": sum(before["min_mg"] <= x <= before["max_mg"] for x in after_values),
        "after_valid_5s_blocks": len(after_values),
        "normal_observed_combined_5s_span_mg": normal_span,
        "modified_mean_offset_exceeds_combined_normal_5s_span_for_both_references": all(abs(v) > normal_span for v in differences.values()),
        "observed_5s_range_overlap_before_after_mg": max(0., min(before["max_mg"], after["max_mg"]) - max(before["min_mg"], after["min_mg"])),
        "caveat": "Observed ranges are neither confidence intervals nor acceptance limits. Returning inside a range does not prove equivalence; outside does not on its own disprove the warmup interval."}
    return result


def save_score_plot(rows, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    phases = list(dict.fromkeys(row["phase"] for row in rows))
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    for ax, method in zip(axes, METHODS, strict=True):
        threshold = None
        for phase in phases:
            chosen = [r for r in rows if r["method"] == method and r["phase"] == phase]
            threshold = chosen[0]["threshold"]
            xs = [(r["start_since_command_s"] + r["last_since_command_s"]) / 2 for r in chosen]
            ys = [r["score"] if r["decision"] != "INVALID" else np.nan for r in chosen]
            ax.plot(xs, ys, label=phase, linewidth=1)
            bad = [x for x, r in zip(xs, chosen, strict=True) if r["decision"] == "INVALID"]
            if bad:
                ax.scatter(bad, np.zeros(len(bad)), marker="x", transform=ax.get_xaxis_transform(),
                           label=f"{phase}: ungültig", clip_on=False)
        ax.axhline(threshold, color="black", linestyle="--", label="eingefrorene Schwelle")
        ax.set_ylabel(method + "\nScore")
        ax.grid(alpha=.25)
        ax.legend(loc="best", fontsize=8)
    axes[-1].set_xlabel("Sekunden seit PWM-Stellbefehl; Modellbewertung ausschließlich [180, 300)")
    fig.suptitle("Normal → veränderte Luftströmung → Normal, Aufbau v4, 75 % PWM\nKontrolliert veränderter Betriebszustand; kein nachgewiesener Defekt")
    fig.tight_layout()
    for extension in ("png", "pdf"):
        fig.savefig(Path(output) / f"scores.{extension}", dpi=150)
    plt.close(fig)


def save_rms_plot(rows, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    phases = list(dict.fromkeys(row["phase"] for row in rows))
    for phase in phases:
        chosen = [r for r in rows if r["phase"] == phase]
        x = [r["midpoint_since_command_s"] for r in chosen]
        y = [r["vector_ac_rms_mg"] if r["quality_valid"] else np.nan for r in chosen]
        for ax in axes:
            ax.plot(x, y, marker=".", markersize=3, linewidth=1, label=phase)
    axes[0].set_xlim(0, 300)
    axes[0].axvline(180, color="black", linestyle="--", label="180 s: vorläufiger Prüfkandidat")
    axes[1].set_xlim(180, 300)
    late_values = [r["vector_ac_rms_mg"] for r in rows if r["start_since_command_s"] >= 180 and r["quality_valid"]]
    if late_values:
        lo, hi = min(late_values), max(late_values)
        margin = max((hi - lo) * .08, .01)
        axes[1].set_ylim(lo - margin, hi + margin)
    for ax in axes:
        ax.set_ylabel("Vektor-AC-RMS / mg")
        ax.set_xlabel("Sekunden seit PWM-Stellbefehl")
        ax.grid(alpha=.25)
        ax.legend(loc="best", fontsize=8)
    axes[0].set_title("Vollständiger Verlauf in aufeinanderfolgenden 5-s-Abschnitten")
    axes[1].set_title("Ausschnitt [180, 300) s; je Abschnitt achsenweise Mittelwertentfernung")
    fig.suptitle("Aufbau v4, 75 % PWM; Fenster sind keine unabhängigen Versuchsreplikate")
    fig.tight_layout()
    for extension in ("png", "pdf"):
        fig.savefig(Path(output) / f"rms_5s.{extension}", dpi=150)
    plt.close(fig)


def evaluate_recording(csv, sidecar, protocol, session, output, runtime="auto", threads=1):
    output = Path(output).resolve()
    check(not output.exists(), "Evaluation output exists; no overwrite")
    recording = load_test_recording(csv, sidecar, protocol, session)
    functions, runtimes = pilot.model_scorers(recording["bundle"], recording["bundle_directory"], runtime, threads)
    rows = score_loaded(recording, functions)
    rms = rms_5s(recording)
    # Recheck frozen inputs after inference, before committing success artifacts.
    pilot.load_bundle(recording["bundle_directory"])
    for key, hash_key in (("csv", "csv_sha256"), ("sidecar", "sidecar_sha256"), ("session", "session_sha256")):
        check(sha256(recording["source"][key]) == recording["source"][hash_key], "Source changed during inference")
    check(sha256(protocol) == recording["source"]["protocol_sha256"], "Protocol changed during inference")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "scores.json", rows)
    pd.DataFrame(rows).to_csv(output / "scores.csv", index=False, mode="x")
    write_json(output / "rms_5s.json", rms)
    pd.DataFrame(rms).to_csv(output / "rms_5s.csv", index=False, mode="x")
    save_score_plot(rows, output)
    save_rms_plot(rms, output)
    journal = recording["session"]
    report = {"status": "evaluated_controlled_airflow_recording", **recording["source"],
              "mounting_id": recording["metadata"]["mounting_id"], "condition": recording["metadata"]["state"],
              "quality": recording["quality"], "sensor": recording["metadata"]["sensor"],
              "acquisition_timing": journal.get("timing"),
              "metrics": condition_metrics(rows), "runtimes": runtimes,
              "rms_5s_summary": interval_description(rms), "rms_full_run_summary": interval_description(rms, 0, 300),
              "pwm_command_invocation_utc": recording["metadata"]["pwm_command_invocation_utc"],
              "pwm_command_invocation_monotonic_ns": recording["metadata"]["pwm_command_invocation_monotonic_ns"],
              "zero_command_completed_monotonic_ns": journal["zero_command_completed_monotonic_ns"],
              "zero_command_completed_utc": journal.get("zero_command_completed_utc"),
              "additional_off_from_release_actual_s": journal.get("additional_off_from_release_actual_s"),
              "total_off_since_previous_zero_s": journal.get("total_off_since_previous_zero_s"),
              "total_off_time_note": journal.get("total_off_time_note"),
              "plate_geometry": recording["metadata"].get("plate_geometry"),
              "models_changed": False, "scaler_fitted": False, "thresholds_changed": False,
              "physical_loss_count": None, "mechanical_stop_measured": False,
              "final_readback": journal["final_readback"],
              "selection_seconds_since_pwm_command": [180, 300],
              "evaluator_sha256": sha256(__file__),
              "limitation": "One sequence is not general reproducibility. The altered state is not a verified defect; no defect recall, F1 or general detection performance is inferred. Adjacent windows are dependent.",
              "artifact_sha256": {p.name: sha256(p) for p in output.iterdir() if p.is_file()}}
    write_json(output / "summary.json", report)
    return report


def combine_results(results, output):
    output = Path(output).resolve()
    check(not output.exists(), "Combined output exists; no overwrite")
    reports, rows, rms = [], [], []
    for directory in map(Path, results):
        report = read_json(directory / "summary.json")
        check(report.get("status") == "evaluated_controlled_airflow_recording", "Unsupported run result")
        for name, digest in report["artifact_sha256"].items():
            check(Path(name).name == name and sha256(directory / name) == digest, "Run result artifact changed")
        own_rows = read_json(directory / "scores.json")
        own_rms = read_json(directory / "rms_5s.json")
        check(condition_metrics(own_rows) == report["metrics"], "Run metrics mismatch")
        check(interval_description(own_rms) == report["rms_5s_summary"], "RMS summary mismatch")
        check(all(r["recording_id"] == report["recording_id"] and r["phase"] == report["phase"]
                  for r in [*own_rows, *own_rms]), "Mixed recording identity in run result")
        check(report["evaluator_sha256"] == sha256(__file__), "Changed evaluation implementation")
        verify_pwm(report["final_readback"], 0)
        reports.append(report)
        rows.extend(own_rows)
        rms.extend(own_rms)
    check(1 <= len(reports) <= 3, "Expected at most three planned phases")
    for key in ("recording_id", "csv_sha256", "csv", "phase", "session_sha256"):
        check(len({r[key] for r in reports}) == len(reports), f"Test source reused across phases: {key}")
    check([r["phase"] for r in reports] == list(PHASES[:len(reports)]), "Wrong planned phase order")
    for key in ("protocol_sha256", "frozen_bundle_sha256", "evaluator_sha256", "mounting_id"):
        check(len({r[key] for r in reports}) == 1, f"Different frozen contract across phases: {key}")
    commands = [r["pwm_command_invocation_monotonic_ns"] for r in reports]
    check(commands == sorted(set(commands)), "Run command chronology invalid")
    check(all(b - a >= 360_000_000_000 for a, b in zip(commands, commands[1:])), "Run intervals overlap or off time is missing")
    check(all(b["pwm_command_invocation_monotonic_ns"] - a["zero_command_completed_monotonic_ns"] >= 60_000_000_000
              for a, b in zip(reports, reports[1:])), "Off time after previous zero is missing")
    for method in METHODS:
        check(len({r["threshold"] for r in rows if r["method"] == method}) == 1, "Different frozen thresholds")
    output.mkdir(parents=True, exist_ok=False)
    table = [{"phase": r["phase"], "recording_id": r["recording_id"], "method": method, **metrics}
             for r in reports for method, metrics in r["metrics"].items()]
    normal_rows = [r for r in rows if r["state"] == "normal"]
    pooled_normal = condition_metrics(normal_rows) if normal_rows else None
    if pooled_normal:
        table += [{"phase": "normal_references_pooled", "recording_id": "whole_normal_recordings_pooled", "method": method, **metrics}
                  for method, metrics in pooled_normal.items()]
    pd.DataFrame(table).to_csv(output / "comparison.csv", index=False, mode="x")
    save_score_plot(rows, output)
    save_rms_plot(rms, output)
    write_json(output / "rms_comparison.json", compare_rms(rms))
    summary = {"status": "complete" if len(reports) == 3 else "partial",
               "whole_recordings": len(reports), "per_run": reports, "pooled_normal": pooled_normal,
               "rms_comparison": compare_rms(rms),
               "window_dependence": "Window counts are descriptive, not independent experimental replicates.",
               "controlled_altered_state_is_proven_defect": False,
               "general_reproducibility_established": False, "defect_performance_evaluated": False,
               "artifact_sha256": {p.name: sha256(p) for p in output.iterdir() if p.is_file()}}
    write_json(output / "comparison.json", summary)
    lines = ["# Kontrollierter Normal–Luftstrom–Normal-Versuch mit eingefrorenem v4-Pilotpaket", "",
             f"Ausgewertet: {len(reports)} vollständige Aufnahmen. Modellbewertung ausschließlich [180,300) s "
             "in 128er-XYZ-Fenstern ohne Überlappung, bei 75 % PWM und 25 kHz.", "",
             "| Phase | Methode | Gültig | Ungültig | Alarme | Anteil unter gültigen Fenstern |",
             "|---|---|---:|---:|---:|---:|"]
    for row in table:
        rate = row["alarm_fraction_among_valid_windows"]
        rate_text = "nicht definiert" if rate is None else f"{100 * rate:.2f} %"
        lines.append(f"| {row['phase']} | {row['method']} | {row['valid_windows']} | {row['invalid_windows']} | {row['alarms']} | {rate_text} |")
    lines += ["", "| Phase | XYZ-Punkte | Beobachtet / XYZ/s | Erste XYZ nach Stellbefehl / s | Host-Abstand P99 / ms | Max. / ms | Lücke / Überlauf / Sättigung |",
              "|---|---:|---:|---:|---:|---:|---|"]
    for report in reports:
        q = report["quality"]
        lines.append(f"| {report['phase']} | {q['xyz_points']} | {q['observed_xyz_per_second']:.6f} | "
                     f"{q['first_xyz_after_command_s']:.6f} | {q['host_interval_p99_ms']:.4f} | "
                     f"{q['host_interval_max_ms']:.4f} | {q['gap_flagged_xyz']} / "
                     f"{q['overrun_flagged_xyz']} / {q['saturated_flagged_xyz']} |")
    lines += ["", "| Phase | Zusätzliche Auszeit ab Freigabe / s | Gesamte Stellvorgaben-Auszeit seit vorherigem 0-%-Befehl / s |",
              "|---|---:|---:|"]
    for report in reports:
        durations = [report.get(k) for k in ("additional_off_from_release_actual_s", "total_off_since_previous_zero_s")]
        texts = ["unbekannt" if duration is None else f"{duration:.6f}" for duration in durations]
        lines.append("| " + " | ".join([report["phase"], *texts]) + " |")
    lines += ["", "Die nominelle Sensor-Abtastrate beträgt unverändert 200 Hz. Je 60 s zusätzliche Auszeit "
              "bedeuten keine identischen gesamten Auszeiten; manuelle Umbauten und Antwortzeiten kommen hinzu. "
              "Die gesamten Zeiten beziehen sich auf protokollierte Stellbefehle, nicht auf gemessenen mechanischen Stillstand."]
    lines += ["", "Alarme im Normalzustand sind Fehlalarme. Der Alarmanteil bei veränderter Luftströmung "
              "beschreibt die Reaktion auf einen kontrolliert veränderten Betriebszustand; er ist kein Defekt-Recall.", "",
              "![Scoreverläufe mit eingefrorenen Schwellen](scores.png)", "",
              "![Vektor-AC-RMS in vollständigen 5-s-Abschnitten](rms_5s.png)", "",
              "| Phase | Mittlerer AC-RMS 180–300 s / mg | Streuung der 5-s-Werte / mg | Linearer Verlauf / (mg/min) | Zweite minus erste Minute / mg |",
              "|---|---:|---:|---:|---:|"]
    for phase, values in summary["rms_comparison"]["per_phase"].items():
        rendered = ["nicht definiert" if values[k] is None else f"{values[k]:.4f}" for k in
                    ("mean_mg", "std_sample_mg", "linear_slope_mg_per_min", "second_minus_first_half_mg")]
        lines.append("| " + " | ".join([phase, *rendered]) + " |")
    lines += ["", "Jeder 5-s-Abschnitt wird in Float64 um seinen jeweiligen Achsenmittelwert bereinigt. "
              "Die Tabelle trennt zeitliche Veränderungen innerhalb einer Aufnahme von unterschiedlichen "
              "Mittelwerten zwischen Aufnahmen. Der Zeitabschnitt ab 180 s bleibt ein Prüfkandidat.", ""]
    returned = summary["rms_comparison"]["return_comparison"]
    if returned and returned.get("status") == "descriptive":
        lines += [f"Nach Entfernen der Platte unterscheidet sich der späte Normalmittelwert um "
                  f"{returned['after_minus_before_mean_mg']:.4f} mg vom vorherigen Normalmittelwert. "
                  f"{returned['after_5s_blocks_within_before_observed_range']} von {returned['after_valid_5s_blocks']} "
                  "gültigen späten Rückkehrabschnitten liegen im zuvor beobachteten 5-s-Bereich. "
                  "Dieser Bereich ist keine statistisch gesicherte Akzeptanzgrenze.", "",
                  f"Der veränderte Zustand liegt gegenüber normal_before bei "
                  f"{returned['modified_minus_before_mean_mg']:+.4f} mg und gegenüber normal_after bei "
                  f"{returned['modified_minus_after_mean_mg']:+.4f} mg. Der gesamte beobachtete Bereich der "
                  f"beiden Normalreferenzen beträgt {returned['normal_observed_combined_5s_span_mg']:.4f} mg.", ""]
    lines += ["Nominell 200 Hz und beobachteter XYZ-Durchsatz bleiben getrennt. Host-Leseabstände, "
              "Zeitstempel und Qualitätsflags stehen je Aufnahme in summary.json. Genaue physische "
              "Verluste und die tatsächliche Drehzahl sind unbekannt. 0 % PWM im Steuerjournal belegen "
              "keinen mechanischen Stillstand.", "",
              "Modelle, Skalierung, Schwellen und Abschnittsauswahl sind eingefroren. Ungültige Fenster "
              "zählen weder als NORMAL noch zum Nenner der Alarmanteile. Fenster innerhalb einer Aufnahme "
              "sind abhängig. Eine einzelne Folge belegt weder allgemeine Reproduzierbarkeit noch "
              "erfolgreiche Anomalieerkennung; es werden kein Defekt-Recall und kein F1-Wert abgeleitet.", "",
              "Nächster Schritt: anhand dieser vollständigen Folge die Rückkehr zur Normalreferenz "
              "und beide Normalfehlalarmraten beurteilen. Für einen belastbareren Vergleich sind unabhängig "
              "freigegebene Wiederholungen derselben dokumentierten äußeren Geometrie vorzusehen. "
              "Bei fehlender Rückkehr zuerst die konkrete offene Frage zu zeitlicher Normalvariabilität "
              "oder unveränderter Geometrie prüfen. Keine Schwelle anhand dieser Tests nachträglich ändern; "
              "Änderungen benötigen ein neues Modellpaket und neue unabhängige Tests."]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("evaluate")
    for argument in ("csv", "sidecar", "protocol", "session", "output"):
        run.add_argument(f"--{argument}", required=True)
    run.add_argument("--runtime", default="auto")
    run.add_argument("--threads", type=int, default=1)
    combine = commands.add_parser("combine")
    combine.add_argument("--results", nargs="+", required=True)
    combine.add_argument("--output", required=True)
    args = vars(parser.parse_args())
    command = args.pop("command")
    result = evaluate_recording(**args) if command == "evaluate" else combine_results(**args)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
