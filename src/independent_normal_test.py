#!/usr/bin/env python3
"""Read-only frozen-model evaluation of newly acquired independent normal runs.

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
    check(p.get("schema_version") == 1 and p.get("purpose") == "independent_normal_test",
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
                           "planned_runs": ["normal_test_01", "normal_test_02", "normal_test_03"]}.items():
        check(p.get(name) == expected, f"Unsupported frozen test parameter: {name}")
    frozen = p["frozen_bundle"]
    check(frozen.get("sha256") == FROZEN_BUNDLE_SHA256, "Wrong authorized frozen pilot package")
    directory = Path(frozen["directory"]).resolve()
    check(sha256(directory / "pilot_bundle.json") == frozen["sha256"], "Bundle protocol anchor mismatch")
    bundle = pilot.load_bundle(directory)
    check(p.get("evaluator_sha256") == sha256(__file__), "Test evaluator differs from protocol")
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


def flag_values(frame, name):
    values = frame[name].astype(str).str.lower()
    check(values.isin(["false", "true", "0", "1", "0.0", "1.0"]).all(),
          f"Unrecognized quality flag: {name}")
    return values.isin(["true", "1", "1.0"]).to_numpy()


def summarize_quality(frame, command_ns):
    host = preparation.integral_column(frame, "host_monotonic_ns")
    span = float((host[-1] - host[0]) / 1e9)
    gaps_ms = np.diff(host) / 1e6
    return {"xyz_points": len(frame), "individual_axis_values": 3 * len(frame),
            "nominal_sensor_odr_hz": 200, "observed_xyz_per_second": (len(frame) - 1) / span,
            "first_to_last_host_span_s": span,
            "first_xyz_after_command_s": float((host[0] - command_ns) / 1e9),
            "last_xyz_after_command_s": float((host[-1] - command_ns) / 1e9),
            "host_interval_p50_ms": float(np.median(gaps_ms)),
            "host_interval_p99_ms": float(np.percentile(gaps_ms, 99)),
            "host_interval_max_ms": float(gaps_ms.max()),
            "host_intervals_over_10ms": int(np.count_nonzero(gaps_ms > 10)),
            "host_intervals_over_160ms": int(np.count_nonzero(gaps_ms > 160)),
            "read_duration_max_ms": float(frame["read_duration_ns"].max() / 1e6),
            "fifo_depth_max": int(frame["fifo_depth"].max()),
            **{f"{flag}_flagged_xyz": int(flag_values(frame, flag).sum()) for flag in FLAGS},
            "nonfinite_xyz_points": int((~np.isfinite(frame[AXES].to_numpy(np.float64))).any(axis=1).sum()),
            "nonmonotonic_host_intervals": int(np.count_nonzero(np.diff(host) <= 0)),
            "exact_lost_sensor_samples": None,
            "timebase_limitation": "Host read completion is not a measured sensor conversion clock. Exact physical losses are unknown."}


def build_windows(frame, command_ns):
    """Preserve all selected full windows, including invalid ones; never bridge gaps."""
    host = preparation.integral_column(frame, "host_monotonic_ns")
    relative = host - command_ns
    chosen = np.flatnonzero((relative >= 180_000_000_000) & (relative < 300_000_000_000))
    check(len(chosen) >= 128, "No complete 128-point window in frozen test interval")
    check(np.all(np.diff(chosen) == 1), "Noncontiguous frozen interval")
    count = len(chosen) // 128
    first = int(chosen[0])
    raw = frame[AXES].to_numpy(np.float64)
    inferred_gap = np.r_[False, np.diff(host) > 160_000_000]
    overfull = frame["fifo_depth"].to_numpy() == 32
    rail = 512
    unscaled = raw / preparation.EXPECTED_SENSOR["scale_g_per_lsb"]
    saturated_rail = ((unscaled <= -rail + 1) | (unscaled >= rail - 2)).any(axis=1)
    nonfinite = (~np.isfinite(raw)).any(axis=1)
    masks = {**{flag: flag_values(frame, flag) for flag in FLAGS},
             "host_interval_over_160ms": inferred_gap, "fifo_full": overfull,
             "raw_saturation_rail": saturated_rail, "nonfinite_xyz": nonfinite}
    windows = []
    for index in range(count):
        begin = first + index * 128
        end = begin + 128
        errors = [name for name, mask in masks.items() if mask[begin:end].any()]
        # A trailing incomplete group is never padded or joined to the next run.
        # Pandas training input is column-major. Keep that reduction layout:
        # a C-order copy can change Float64 mean summation at near-zero values.
        value = raw[begin:end].copy(order="F")
        ac = None if errors else pilot.center_raw_window(value)
        windows.append({"raw_float64": value, "ac_float32": ac,
                        "metadata": {"window_index_in_recording": index,
                                     "source_start_index": begin, "source_end_index_exclusive": end,
                                     "start_host_monotonic_ns": int(host[begin]),
                                     "last_host_monotonic_ns": int(host[end - 1]),
                                     "start_since_command_s": float(relative[begin] / 1e9),
                                     "last_since_command_s": float(relative[end - 1] / 1e9),
                                     "quality_valid": not errors, "quality_reasons": errors}})
    return windows, {"xyz_selected": len(chosen), "full_model_windows": count,
                     "trailing_xyz_not_windowed": len(chosen) - count * 128,
                     "quality_valid_windows": sum(w["metadata"]["quality_valid"] for w in windows),
                     "quality_invalid_windows": sum(not w["metadata"]["quality_valid"] for w in windows)}


def verify_pwm(snapshot, duty_ns):
    config = snapshot.get("pwm_configuration", {})
    check(config.get("period_ns") == 40000 and config.get("duty_cycle_ns") == duty_ns and
          config.get("enable") == 1 and config.get("polarity") == "normal" and
          snapshot.get("pwm_mux_confirmed") is True, f"Session PWM readback mismatch: expected {duty_ns} ns duty")


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
    for name, expected in {"purpose": "test", "split": "independent_test", "state": "normal",
                           "condition_label": "normal", "label": 0, "mounting_id": p["mounting_id"],
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
    for field in ("ready_normal_no_plate", "external_supply_connected",
                  "mechanical_standstill_confirmed", "mounting_unchanged"):
        check(release.get(field) is True, f"Missing explicitly confirmed start condition: {field}")
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
    check(frame["label"].eq(0).all() and set(frame["anomaly_type"]) == {"normal"}, "Non-normal CSV labels")
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
    bundle = recording["bundle"]
    thresholds = {method: bundle["thresholds"][method]["value"] for method in METHODS}
    rows = []
    for window in recording["windows"]:
        meta = {**recording["source"], **window["metadata"], "label": 0, "state": "normal"}
        if not meta["quality_valid"]:
            decisions = {method: {"score": None, "prediction": None, "decision": "INVALID",
                                  "error": ", ".join(meta["quality_reasons"])} for method in METHODS}
        else:
            decisions = pilot.score_window(window["ac_float32"], bundle["scaler"], score_functions, thresholds)
        for method in METHODS:
            rows.append({**meta, "method": method, "threshold": thresholds[method], **decisions[method]})
    return rows


def normal_metrics(rows):
    check(all(row["label"] == 0 and row["state"] == "normal" for row in rows), "Metrics require normal-only data")
    output = {}
    for method in METHODS:
        chosen = [r for r in rows if r["method"] == method]
        valid = [r for r in chosen if r["decision"] in ("NORMAL", "ANOMALY")]
        check(len(chosen) == len(valid) + sum(r["decision"] == "INVALID" for r in chosen), "Unknown decision")
        alarms = sum(r["decision"] == "ANOMALY" for r in valid)
        output[method] = {"total_windows": len(chosen), "valid_windows": len(valid),
                          "invalid_windows": len(chosen) - len(valid), "false_alarms": alarms,
                          "false_alarm_rate_among_valid_normal_windows": alarms / len(valid) if valid else None}
    return output


def save_score_plot(rows, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    phases = list(dict.fromkeys(row["phase"] for row in rows))
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    for ax, method in zip(axes, METHODS, strict=True):
        for phase in phases:
            chosen = [r for r in rows if r["method"] == method and r["phase"] == phase]
            xs = [(r["start_since_command_s"] + r["last_since_command_s"]) / 2 for r in chosen]
            ys = [r["score"] if r["decision"] != "INVALID" else np.nan for r in chosen]
            ax.plot(xs, ys, label=phase, linewidth=1)
            bad = [x for x, r in zip(xs, chosen, strict=True) if r["decision"] == "INVALID"]
            if bad:
                ax.scatter(bad, np.zeros(len(bad)), marker="x", transform=ax.get_xaxis_transform(),
                           label=f"{phase}: ungültig", clip_on=False)
        ax.axhline(chosen[0]["threshold"], color="black", linestyle="--", label="eingefrorene Schwelle")
        ax.set_ylabel(method + "\nScore")
        ax.grid(alpha=.25)
        ax.legend(loc="best", fontsize=8)
    axes[-1].set_xlabel("Sekunden seit PWM-Stellbefehl; Bewertung ausschließlich [180, 300)")
    fig.suptitle("Unabhängige normale Aufnahmen, Aufbau v4, 75 % PWM\nFenster sind keine unabhängigen Versuchsreplikate")
    fig.tight_layout()
    for extension in ("png", "pdf"):
        fig.savefig(Path(output) / f"scores.{extension}", dpi=150)
    plt.close(fig)


def evaluate_recording(csv, sidecar, protocol, session, output, runtime="auto", threads=1):
    output = Path(output).resolve()
    check(not output.exists(), "Evaluation output exists; no overwrite")
    recording = load_test_recording(csv, sidecar, protocol, session)
    functions, runtimes = pilot.model_scorers(recording["bundle"], recording["bundle_directory"], runtime, threads)
    rows = score_loaded(recording, functions)
    # Recheck frozen inputs after inference, before committing success artifacts.
    pilot.load_bundle(recording["bundle_directory"])
    for key, hash_key in (("csv", "csv_sha256"), ("sidecar", "sidecar_sha256"), ("session", "session_sha256")):
        check(sha256(recording["source"][key]) == recording["source"][hash_key], "Source changed during inference")
    check(sha256(protocol) == recording["source"]["protocol_sha256"], "Protocol changed during inference")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "scores.json", rows)
    pd.DataFrame(rows).to_csv(output / "scores.csv", index=False, mode="x")
    save_score_plot(rows, output)
    report = {"status": "evaluated_independent_normal_recording", **recording["source"],
              "mounting_id": recording["metadata"]["mounting_id"], "condition": "normal",
              "quality": recording["quality"], "metrics": normal_metrics(rows), "runtimes": runtimes,
              "pwm_command_invocation_utc": recording["metadata"]["pwm_command_invocation_utc"],
              "pwm_command_invocation_monotonic_ns": recording["metadata"]["pwm_command_invocation_monotonic_ns"],
              "models_changed": False, "scaler_fitted": False, "thresholds_changed": False,
              "physical_loss_count": None, "mechanical_stop_measured": False,
              "selection_seconds_since_pwm_command": [180, 300],
              "evaluator_sha256": sha256(__file__),
              "limitation": "One whole run is one experimental replicate. Adjacent windows are dependent. Normal-only tests do not estimate anomaly recall, F1, or general detection performance.",
              "artifact_sha256": {p.name: sha256(p) for p in output.iterdir() if p.is_file()}}
    write_json(output / "summary.json", report)
    return report


def combine_results(results, output):
    output = Path(output).resolve()
    check(not output.exists(), "Combined output exists; no overwrite")
    reports, rows = [], []
    for directory in map(Path, results):
        report = read_json(directory / "summary.json")
        check(report.get("status") == "evaluated_independent_normal_recording", "Unsupported run result")
        for name, digest in report["artifact_sha256"].items():
            check(sha256(directory / name) == digest, "Run result artifact changed")
        own_rows = read_json(directory / "scores.json")
        check(normal_metrics(own_rows) == report["metrics"], "Run metrics mismatch")
        check(all(r["recording_id"] == report["recording_id"] and r["phase"] == report["phase"]
                  for r in own_rows), "Mixed recording identity in run result")
        reports.append(report)
        rows.extend(own_rows)
    check(1 <= len(reports) <= 3, "Expected at most three planned independent runs")
    for key in ("recording_id", "csv_sha256", "csv", "phase", "session_sha256"):
        check(len({r[key] for r in reports}) == len(reports), f"Test source reused across runs: {key}")
    for key in ("protocol_sha256", "frozen_bundle_sha256", "evaluator_sha256"):
        check(len({r[key] for r in reports}) == 1, f"Different frozen contract across runs: {key}")
    commands = [r["pwm_command_invocation_monotonic_ns"] for r in reports]
    check(commands == sorted(set(commands)), "Run command chronology invalid")
    check(all(b - a >= 360_000_000_000 for a, b in zip(commands, commands[1:])), "Run intervals overlap or off time is missing")
    output.mkdir(parents=True, exist_ok=False)
    table = [{"phase": r["phase"], "recording_id": r["recording_id"], "method": method, **metrics}
             for r in reports for method, metrics in r["metrics"].items()]
    pooled = normal_metrics(rows)
    table += [{"phase": "pooled", "recording_id": "whole_recordings_pooled", "method": method, **metrics}
              for method, metrics in pooled.items()]
    pd.DataFrame(table).to_csv(output / "comparison.csv", index=False, mode="x")
    save_score_plot(rows, output)
    summary = {"status": "complete" if len(reports) == 3 else "partial",
               "whole_recordings": len(reports), "per_run": reports, "pooled": pooled,
               "window_dependence": "Window counts are descriptive, not independent experimental replicates.",
               "normal_only": True, "anomaly_performance_evaluated": False,
               "artifact_sha256": {p.name: sha256(p) for p in output.iterdir() if p.is_file()}}
    write_json(output / "comparison.json", summary)
    lines = ["# Unabhängige Normalitätsprüfung des eingefrorenen v4-Pilotpakets", "",
             f"Ausgewertet: {len(reports)} vollständige unabhängige Normalläufe. "
             "Bewertung ausschließlich [180,300) s in 128er-XYZ-Fenstern ohne Überlappung.", "",
             "| Lauf | Methode | Gültig | Ungültig | Fehlalarme | Fehlalarmrate unter gültigen Fenstern |",
             "|---|---|---:|---:|---:|---:|"]
    for row in table:
        rate = row["false_alarm_rate_among_valid_normal_windows"]
        rate_text = "nicht definiert" if rate is None else f"{100 * rate:.2f} %"
        lines.append(f"| {row['phase']} | {row['method']} | {row['valid_windows']} | {row['invalid_windows']} | {row['false_alarms']} | {rate_text} |")
    lines += ["", "![Scoreverläufe mit eingefrorenen Schwellen](scores.png)", "",
              "Die gesamte Anlaufphase bleibt in den Rohdaten. 180 Sekunden sind weiterhin eine vorläufige "
              "Einlaufzeit. Hohe Fehlalarmraten bleiben als Testergebnis erhalten; es erfolgt keine Anpassung.", "",
              "Ungültige Fenster zählen weder als NORMAL noch zum Fehlalarmnenner. Benachbarte Fenster sind "
              "abhängig. Aus diesen ausschließlich normalen Daten werden kein Anomalie-Recall, kein F1-Wert "
              "und keine allgemeine Erkennungsleistung abgeleitet.", "",
              "Nominell 200 Hz und beobachteter XYZ-Durchsatz bleiben getrennt; genaue physische Verluste und "
              "Drehzahl sind unbekannt. 0 % PWM im Steuerjournal belegen keinen mechanischen Stillstand.", "",
              "Nächster kontrolliert veränderter Testzustand: separat und kippsicher befestigte äußere Platte "
              "bei unverändertem Aufbau und 75 % PWM. Vor einer Durchführung sind konkrete Geometrie und "
              "Freigabe zu dokumentieren. Bestehende Testergebnisse dürfen nicht für eine nachträgliche "
              "Schwellenwahl verwendet werden; Änderungen erfordern ein neues Modellpaket und neue unabhängige Tests."]
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
