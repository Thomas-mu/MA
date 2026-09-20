"""Offline-Auswertung einer durchgehenden Serie mit zehn Smartphoneanrufen.

Keine Sensor-/Lüfterzugriffe, kein Training, keine künstlichen Vibrationslabels.
Die Zuordnungsregeln sind vor dem Vergleich in RULES festgelegt.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import platform
import shlex
import shutil
import time
from pathlib import Path

import numpy as np

import common_comparison as common


RULES = {
    "version": 1,
    "windowing": "Originale gespeicherte window_index-Gruppen, 128 Samples, Schritt 128; keine Neuausrichtung an Markern.",
    "search_intervals": "[call_requested, end_reported); Marker begrenzen den Suchbereich, nicht die Vibration.",
    "primary_windows": "Erstes Sample >= Startmarker und letztes Sample < Endmarker.",
    "boundary_windows": "Überlappende, nicht vollständig enthaltene Fenster separat als unklar; kein primärer Rang.",
    "first_alarm": "Erstes gültiges Alarmfenster vollständig im Suchbereich, auch bei schon bestehendem Alarm.",
    "first_new_alarm": "Erstes primäres Alarmfenster mit unmittelbar vorherigem gültigem NORMAL-Fenster; fortlaufende Fenster-/Sampleindizes und Zeiten erforderlich.",
    "ties": "Gleicher Original-Fensterindex bedeutet Gleichstand. Kein Tie-Break durch Rechenzeiten.",
    "invalid": "Unvollständige Fenster, Qualitätsflags, Index-/Zeitfehler und Scorefehler bleiben INVALID und werden nie NORMAL.",
    "normal": "Nach Einlauf bis erster Aufforderung, zwischen Rückmeldung und nächster Aufforderung, nach letzter abgeschlossener Rückmeldung bis Aufnahmeende; nur dokumentierte Intervalle.",
    "denominators": "Alarmanteile beziehen sich auf gültige, vollständig enthaltene Fenster; ungültige und Randfenster separat, Zeitdauer zusätzlich.",
    "retention": "Alle Versuche 1 bis 10, auch fehlende, abgebrochene oder unklare, bleiben erhalten.",
    "timing": "Relative Host-Empfangszeiten; kein präziser Vibrationsbeginn und keine nachträgliche Live-Reaktionszeit.",
}

METHOD_LABELS = {"rms": "RMS", "isolation_forest": "Isolation Forest", "tflite_autoencoder": "Autoencoder"}
FLAGS = ("gap", "overrun", "saturated")


def _flag(value):
    if str(value).lower() not in ("0", "1", "false", "true"):
        raise ValueError(f"Ungültiges Qualitätsflag: {value}")
    return str(value).lower() in ("1", "true")


def read_windows(path, size=128):
    """Behält die originalen Gruppen einschließlich technisch ungültiger Fenster."""
    windows, all_times, all_xyz = [], [], []
    required = {"sample_index", "window_index", "host_monotonic_ns", *common.AXES, *FLAGS}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("raw.csv: erforderliche Index-, Zeit-, XYZ- oder Qualitätsfelder fehlen.")
        previous = None
        for window_index, grouped in itertools.groupby(reader, key=lambda r: int(r["window_index"])):
            rows = list(grouped)
            indices = np.asarray([int(r["sample_index"]) for r in rows], dtype=np.int64)
            stamps = np.asarray([int(r["host_monotonic_ns"]) for r in rows], dtype=np.int64)
            xyz = np.asarray([[float(r[a]) for a in common.AXES] for r in rows], dtype=np.float32)
            quality = {flag: sum(_flag(r[flag]) for r in rows) for flag in FLAGS}
            errors = []
            if len(rows) != size:
                errors.append("incomplete_or_oversized_window")
            if indices[0] != (window_index - 1) * size + 1 or np.any(np.diff(indices) != 1):
                errors.append("sample_index_discontinuity")
            if window_index < 1 or (previous and window_index != previous["window_index"] + 1):
                errors.append("window_index_discontinuity")
            if np.any(np.diff(stamps) <= 0) or (previous and stamps[0] <= previous["end_ns"]):
                errors.append("nonmonotonic_timestamps")
            if not np.isfinite(xyz).all():
                errors.append("nonfinite_xyz")
            errors.extend(flag for flag, count in quality.items() if count)
            previous = {"window_index": window_index, "start_sample": int(indices[0]),
                        "end_sample": int(indices[-1]), "sample_count": len(rows),
                        "start_ns": int(stamps[0]), "end_ns": int(stamps[-1]),
                        "valid_raw": not errors, "raw_error": ";".join(errors),
                        **{f"{flag}_count": count for flag, count in quality.items()},
                        "float32_raw_sha256": hashlib.sha256(xyz.tobytes(order="C")).hexdigest(), "raw": xyz}
            windows.append(previous)
            all_times.extend(stamps.tolist())
            all_xyz.extend(xyz.tolist())
    return windows, np.asarray(all_times, dtype=np.int64), np.asarray(all_xyz, dtype=np.float32).reshape(-1, 3)


def read_trials(cues, count=10):
    trials = [{"number": n, "start_ns": None, "end_ns": None, "issues": []} for n in range(1, count + 1)]
    global_issues = []
    for cue in cues:
        if cue.get("event") not in ("call_requested", "end_reported"):
            continue
        number = cue.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or not 1 <= number <= count:
            global_issues.append("marker_with_invalid_trial_number")
            continue
        trial = trials[number - 1]
        key = "start_ns" if cue["event"] == "call_requested" else "end_ns"
        if trial[key] is not None:
            trial["issues"].append(f"duplicate_{cue['event']}")
            continue
        stamp = cue.get("monotonic_ns")
        if not isinstance(stamp, int) or isinstance(stamp, bool):
            trial["issues"].append("invalid_marker_timestamp")
            continue
        trial[key] = stamp
        if not cue.get("local_timestamp"):
            trial["issues"].append("missing_local_timestamp")
    for trial in trials:
        start, end = trial["start_ns"], trial["end_ns"]
        if start is None:
            trial["issues"].append("missing_call_requested")
        if end is None:
            trial["issues"].append("missing_end_reported")
        if start is not None and end is not None and end <= start:
            trial["issues"].append("unordered_markers")
    for left, right in itertools.combinations(trials, 2):
        if left["start_ns"] is None or right["start_ns"] is None:
            continue
        if right["start_ns"] <= left["start_ns"] or (left["end_ns"] is not None and left["end_ns"] > right["start_ns"]):
            left["issues"].append("overlapping_or_out_of_order_trials")
            right["issues"].append("overlapping_or_out_of_order_trials")
    for trial in trials:
        trial["marker_status"] = "valid" if not trial["issues"] else "unclear"
    return trials, global_issues


def position(window, start, end):
    """Intervalle sind halboffen, damit gemeinsame Grenzen eindeutig bleiben."""
    first, last = window["start_ns"], window["end_ns"]
    if first >= start and last < end:
        return "inside"
    if last >= start and first < end:
        return "boundary"
    return "outside"


def is_new_alarm(previous, current):
    return bool(previous and current["prediction"] == 1 and previous["prediction"] == 0
                and current["decision"] == "ANOMALY" and previous["decision"] == "NORMAL"
                and current["window_index"] == previous["window_index"] + 1
                and current["start_sample"] == previous["end_sample"] + 1
                and current["start_ns"] > previous["end_ns"])


def evaluate(windows, bundle, directory, *, runtime="auto", threads=1):
    decisions, runtimes = [], {}
    for method in common.METHODS:
        try:
            function, runtimes[method] = common.scorer(method, bundle, directory, runtime=runtime, threads=threads)
            loader_error = None
        except Exception as exc:
            function, loader_error = None, f"model_load_error: {type(exc).__name__}: {exc}"
            runtimes[method] = loader_error
        threshold = bundle["thresholds"][method]["value"]
        previous = None
        for window in windows:
            row = {key: value for key, value in window.items() if key != "raw"}
            row.update(method=method, score=None, threshold=threshold, prediction=None,
                       decision="INVALID", error=window["raw_error"] or loader_error,
                       threshold_source=bundle["thresholds"][method].get("source"))
            if window["valid_raw"] and function is not None:
                try:
                    row["score"], row["prediction"] = common.classify_raw(window["raw"], bundle["scaler"], function, threshold)
                    row["decision"] = "ANOMALY" if row["prediction"] else "NORMAL"
                except Exception as exc:
                    row["error"] = f"{type(exc).__name__}: {exc}"
            row["new_alarm"] = is_new_alarm(previous, row)
            decisions.append(row)
            previous = row
    return decisions, runtimes


def _interval_counts(rows, start, end):
    contained = [r for r in rows if position(r, start, end) == "inside"]
    boundary = [r for r in rows if position(r, start, end) == "boundary"]
    valid = [r for r in contained if r["decision"] != "INVALID"]
    return {"contained_windows": len(contained), "valid_windows": len(valid),
            "invalid_windows": len(contained) - len(valid),
            "alarm_windows": sum(r["prediction"] == 1 for r in valid),
            "alarm_window_fraction": sum(r["prediction"] == 1 for r in valid) / len(valid) if valid else None,
            "boundary_windows": len(boundary), "boundary_alarm_windows": sum(r["prediction"] == 1 for r in boundary),
            "boundary_invalid_windows": sum(r["decision"] == "INVALID" for r in boundary)}


def compare_trials(trials, decisions, origin_ns, coverage_start_ns=None, coverage_end_ns=None):
    comparisons = []
    for trial in trials:
        start, end = trial["start_ns"], trial["end_ns"]
        entries = []
        for method in common.METHODS:
            rows = [r for r in decisions if r["method"] == method]
            valid_markers = trial["marker_status"] == "valid"
            contained = [r for r in rows if valid_markers and position(r, start, end) == "inside"]
            alarms = [r for r in contained if r["prediction"] == 1]
            new_alarms = [r for r in alarms if r["new_alarm"]]
            first, new = next(iter(alarms), None), next(iter(new_alarms), None)
            first_position = next((i for i, row in enumerate(rows) if row is first), None)
            predecessor = rows[first_position - 1] if first_position is not None and first_position > 0 else None
            issues = list(trial["issues"])
            if valid_markers and (coverage_start_ns is None or coverage_end_ns is None or start < coverage_start_ns or end > coverage_end_ns):
                issues.append("search_not_fully_recorded")
            counts = _interval_counts(rows, start, end) if valid_markers else {key: None for key in _interval_counts([], 0, 1)}
            if valid_markers and not contained:
                issues.append("no_complete_search_window")
            if counts["invalid_windows"]:
                issues.append("invalid_search_windows")
            if counts["boundary_alarm_windows"]:
                issues.append("boundary_alarm_attribution_unclear")
            if not valid_markers:
                result = "unclear_markers"
            elif new:
                result = "new_alarm_found"
            elif first:
                result = "alarm_present_no_unambiguous_new_alarm"
            elif counts["invalid_windows"] or counts["boundary_alarm_windows"] or not contained:
                result = "unclear_no_primary_alarm"
            else:
                result = "no_alarm"
            entry = {"trial": trial["number"], "method": method, "marker_status": trial["marker_status"],
                     "result": result, "issues": ";".join(dict.fromkeys(issues)),
                     "cue_start_relative_s": (start - origin_ns) / 1e9 if start is not None else None,
                     "cue_end_relative_s": (end - origin_ns) / 1e9 if end is not None else None,
                     "search_duration_s": (end - start) / 1e9 if valid_markers else None,
                     "recorded_search_duration_s": max(0, min(end, coverage_end_ns) - max(start, coverage_start_ns)) / 1e9 if valid_markers and coverage_start_ns is not None and coverage_end_ns is not None else 0,
                     "first_alarm_is_new": first["new_alarm"] if first else None,
                     "first_alarm_previous_window": predecessor["window_index"] if predecessor else None,
                     "first_alarm_previous_decision": predecessor["decision"] if predecessor else None,
                     "first_alarm_previous_error": predecessor.get("error") if predecessor else None,
                     **counts}
            for prefix, alarm in (("first_alarm", first), ("first_new_alarm", new)):
                entry[f"{prefix}_window"] = alarm["window_index"] if alarm else None
                entry[f"{prefix}_complete_relative_s"] = (alarm["end_ns"] - origin_ns) / 1e9 if alarm else None
                entry[f"{prefix}_complete_after_cue_s"] = (alarm["end_ns"] - start) / 1e9 if alarm else None
            entries.append(entry)
        for prefix in ("first_alarm", "first_new_alarm"):
            ordering = sorted({e[f"{prefix}_window"] for e in entries if e[f"{prefix}_window"] is not None})
            fastest = min((e[f"{prefix}_complete_relative_s"] for e in entries if e[f"{prefix}_window"] is not None), default=None)
            for entry in entries:
                index = entry[f"{prefix}_window"]
                entry[f"{prefix}_rank"] = ordering.index(index) + 1 if index is not None else None
                entry[f"{prefix}_tie"] = index is not None and sum(e[f"{prefix}_window"] == index for e in entries) > 1
                entry[f"{prefix}_difference_to_earliest_s"] = entry[f"{prefix}_complete_relative_s"] - fastest if index is not None else None
        comparisons.extend(entries)
    return comparisons


def normal_intervals(trials, warmup_end_ns, capture_end_ns):
    intervals = []
    if not any(trial["start_ns"] is not None or trial["end_ns"] is not None for trial in trials):
        return [("normal_before_trial_1", warmup_end_ns, capture_end_ns)] if capture_end_ns > warmup_end_ns else []
    if trials[0]["start_ns"] is not None and trials[0]["start_ns"] > warmup_end_ns:
        intervals.append(("normal_before_trial_1", warmup_end_ns, trials[0]["start_ns"]))
    for left, right in zip(trials, trials[1:]):
        if left["marker_status"] == "valid" and right["start_ns"] is not None and not any("duplicate_call_requested" == i or "overlapping_or_out_of_order_trials" == i for i in right["issues"]) and right["start_ns"] > left["end_ns"]:
            intervals.append((f"normal_before_trial_{right['number']}", left["end_ns"], right["start_ns"]))
    requested = [trial for trial in trials if trial["start_ns"] is not None]
    if requested and requested[-1]["marker_status"] == "valid" and capture_end_ns > requested[-1]["end_ns"]:
        intervals.append(("normal_tail", requested[-1]["end_ns"], capture_end_ns))
    return intervals


def summarize_normal(intervals, decisions, origin_ns, coverage_start_ns, coverage_end_ns):
    result = []
    for name, start, end in intervals:
        for method in common.METHODS:
            rows = [r for r in decisions if r["method"] == method]
            result.append({"phase": name, "method": method,
                           "start_relative_s": (start - origin_ns) / 1e9,
                           "end_relative_s": (end - origin_ns) / 1e9,
                           "phase_duration_s": (end - start) / 1e9,
                           "recorded_duration_s": max(0, min(end, coverage_end_ns) - max(start, coverage_start_ns)) / 1e9 if coverage_start_ns is not None and coverage_end_ns is not None else 0,
                           **_interval_counts(rows, start, end)})
    return result


def _csv(path, rows, empty_fields=("no_rows",)):
    with Path(path).open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else list(empty_fields))
        writer.writeheader()
        writer.writerows(rows)


def benchmark_windows(windows, bundle, directory, *, runtime="auto", threads=1, rounds=6):
    """Separates Replay: 20 Warm-up-Fenster, sechs wechselnde Methodenreihenfolgen."""
    device = Path("/proc/device-tree/model")
    device_model = device.read_text().strip("\0\n") if device.exists() else ""
    if "Raspberry Pi" not in device_model:
        raise ValueError("Der separate Verarbeitungsbenchmark muss auf dem Raspberry Pi laufen.")
    if rounds < 1:
        raise ValueError("Mindestens eine Benchmark-Runde erforderlich.")
    valid = [w for w in windows if w["valid_raw"]]
    if not valid:
        raise ValueError("Keine gültigen identischen Benchmarkfenster vorhanden.")
    functions, names = {}, {}
    for method in common.METHODS:
        functions[method], names[method] = common.scorer(method, bundle, directory, runtime=runtime, threads=threads)
    from threadpoolctl import threadpool_limits
    timings, orders = [], list(itertools.permutations(common.METHODS))
    conditions = {"device_model": device_model, "platform": platform.platform(), "threads": threads,
                  "orders": [], "warmup_windows_per_method_per_round": 20,
                  "rounds": rounds, "identical_source_windows": [w["window_index"] for w in valid],
                  "invalid_source_windows_excluded_for_all_methods": len(windows) - len(valid),
                  "runtime": names, "boundary": "Unskaliertes RAM-Fenster bis Score und Schwellenentscheidung; Dateizugriff/Plot/Modellladen ausgeschlossen.",
                  "live_reaction_time": False, "thermal_conditions": []}
    with threadpool_limits(limits=threads):
        for round_index in range(rounds):
            order = orders[round_index % len(orders)]
            conditions["orders"].append(list(order))
            thermal = Path("/sys/class/thermal/thermal_zone0/temp")
            conditions["thermal_conditions"].append({"round": round_index + 1, "temperature_celsius_before": float(thermal.read_text()) / 1000 if thermal.exists() else None})
            for method in order:
                threshold = bundle["thresholds"][method]["value"]
                for i in range(20):
                    common.classify_raw(valid[i % len(valid)]["raw"], bundle["scaler"], functions[method], threshold)
                for window in valid:
                    begin = time.perf_counter_ns()
                    common.classify_raw(window["raw"], bundle["scaler"], functions[method], threshold)
                    elapsed_ms = (time.perf_counter_ns() - begin) / 1e6
                    timings.append({"round": round_index + 1, "method": method,
                                    "window_index": window["window_index"], "processing_ms": elapsed_ms})
    conditions["methods"] = {}
    for method in common.METHODS:
        values = [r["processing_ms"] for r in timings if r["method"] == method]
        conditions["methods"][method] = {"measured_windows": len(values), "median_ms": float(np.median(values)), "p95_ms": float(np.percentile(values, 95))}
    return timings, conditions


def plots(output, times, xyz, decisions, trials, comparisons, origin_ns):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output.mkdir()
    for trial in trials:
        figure, axes = plt.subplots(4, 1, figsize=(11, 9), sharex=True, constrained_layout=True)
        start, end = trial["start_ns"], trial["end_ns"]
        usable = start is not None and end is not None and end > start
        if usable:
            # Alle Daten im Suchbereich plus je 5 s Kontext; kein Vibrationslabel.
            lower, upper = start - 5_000_000_000, end + 5_000_000_000
            selected = (times >= lower) & (times <= upper)
            for axis, name in enumerate(("X", "Y", "Z")):
                axes[0].plot((times[selected] - start) / 1e9, xyz[selected, axis], linewidth=.6, label=name)
            axes[0].legend(loc="upper right")
            for ax in axes:
                ax.axvspan(0, (end - start) / 1e9, alpha=.09, color="grey")
                ax.axvline(0, color="grey", linestyle=":")
                ax.axvline((end - start) / 1e9, color="grey", linestyle=":")
            for ax, method in zip(axes[1:], common.METHODS):
                rows = [r for r in decisions if r["method"] == method and lower <= r["end_ns"] <= upper]
                threshold = rows[0]["threshold"] if rows else 1
                divisor = abs(threshold) if threshold != 0 else 1
                ax.plot([(r["end_ns"] - start) / 1e9 for r in rows], [r["score"] / divisor if r["score"] is not None else np.nan for r in rows], linewidth=.8)
                ax.axhline(threshold / divisor, color="black", linestyle="--", linewidth=.8)
                entry = next(e for e in comparisons if e["trial"] == trial["number"] and e["method"] == method)
                for prefix, color, style in (("first_alarm", "tab:orange", ":"), ("first_new_alarm", "tab:red", "--")):
                    index = entry[f"{prefix}_window"]
                    if index is not None:
                        window = next(r for r in rows if r["window_index"] == index)
                        ax.axvspan((window["start_ns"] - start) / 1e9, (window["end_ns"] - start) / 1e9, color=color, alpha=.2)
                        ax.axvline((window["end_ns"] - start) / 1e9, color=color, linestyle=style, label="erster Alarm" if prefix == "first_alarm" else "erster neuer Alarm")
                for row in rows:
                    if row["decision"] == "INVALID":
                        ax.axvspan((row["start_ns"] - start) / 1e9, (row["end_ns"] - start) / 1e9, color="black", alpha=.15)
                ax.set_ylabel(f"{METHOD_LABELS[method]}\nScore / |Schwelle|" if threshold != 0 else f"{METHOD_LABELS[method]}\nScore (Schwelle = 0)")
                if ax.get_legend_handles_labels()[0]:
                    ax.legend(loc="upper right", fontsize="small")
            axes[-1].set_xlabel("Zeit seit Aufforderung [s]; grauer Bereich = Suchbereich")
        else:
            axes[0].text(.5, .5, "Suchbereich fehlt oder ist unklar", ha="center", transform=axes[0].transAxes)
            axes[-1].set_xlabel("Relative Zeit [s]")
        axes[0].set_ylabel("Beschleunigung [g]")
        axes[0].set_title(f"Versuch {trial['number']} – wiederholte Untersuchung an diesem Aufbau")
        for ax in axes:
            ax.grid(alpha=.2)
        figure.savefig(output / f"versuch_{trial['number']:02d}.png", dpi=150)
        plt.close(figure)
    figure, ax = plt.subplots(figsize=(12, 4), constrained_layout=True)
    for i, label in enumerate(("X", "Y", "Z")):
        ax.plot((times - origin_ns) / 1e9, xyz[:, i], linewidth=.5, label=label)
    for trial in trials:
        if trial["start_ns"] is not None:
            seconds = (trial["start_ns"] - origin_ns) / 1e9
            ax.axvline(seconds, color="grey", linewidth=.6)
            ax.text(seconds, .98, f"Versuch {trial['number']}", rotation=90, va="top", transform=ax.get_xaxis_transform(), fontsize=7)
    ax.set(xlabel="Relative Aufnahmezeit [s]", ylabel="Beschleunigung [g]", title="XYZ der gesamten Serie")
    ax.legend()
    figure.savefig(output / "serie_xyz.png", dpi=150)
    plt.close(figure)


def analyze(run, output, *, runtime="auto", threads=1, benchmark=False):
    run, output = Path(run).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Ergebnisordner existiert bereits: {output}")
    if output.is_relative_to(run):
        raise ValueError("Ergebnisordner muss außerhalb der unveränderten Aufnahme liegen.")
    config = common.read_json(run / "config.json")
    final = common.read_json(run / "run.json")
    if final.get("status") not in ("completed", "stopped", "aborted", "interrupted", "failed", "error"):
        raise ValueError("Auswertung erst nach kontrolliertem Aufnahmeende oder dokumentiertem Fehler.")
    if (run / "status.json").exists():
        status = common.read_json(run / "status.json")
        if status.get("state", status.get("status")) in ("running", "starting", "warming_up", "recording", "stopping"):
            raise ValueError("status.json meldet eine laufende Aufnahme.")
    if common.read_json(run / "analysis_rules.json").get("rules") != RULES:
        raise ValueError("Auswertungsregeln widersprechen den vor Aufnahmebeginn eingefrorenen Regeln.")
    if config.get("trials") != 10 or config.get("window_size") != 128 or config.get("step_size") != 128:
        raise ValueError("Zehn Versuche und unveränderte Fenster-/Schrittweite 128/128 erforderlich.")
    warmup = float(config["warmup_seconds"])
    if not math.isfinite(warmup) or warmup < 0:
        raise ValueError("Ungültige Einlaufzeit.")
    directory = run / "bundle"
    bundle = common.load_bundle(directory)
    for key in ("window_size", "step_size", "profile_name"):
        if bundle.get(key) != config.get(key):
            raise ValueError(f"Konfiguration und eingefrorenes Bundle widersprechen sich: {key}")
    bundle_hash = common.sha256(directory / "bundle.json")
    if config.get("bundle_sha256", bundle_hash) != bundle_hash:
        raise ValueError("Bundle-Hash widerspricht Versuchskonfiguration.")
    for name, digest in final.get("file_sha256", {}).items():
        if common.sha256(run / name) != digest:
            raise ValueError(f"Aufnahmedatei verändert: {name}")
    origin_ns = int(common.read_json(run / "started.json")["start_monotonic_ns"])
    windows, times, xyz = read_windows(run / "raw.csv")
    cues = [json.loads(line) for line in (run / "cues.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    trials, cue_issues = read_trials(cues)
    first_ns, last_ns = (int(times.min()), int(times.max())) if len(times) else (None, None)
    capture_end = int(final.get("end_monotonic_ns", final.get("stop_monotonic_ns", last_ns if last_ns is not None else origin_ns)))
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(run, output / "source")
    shutil.copy2(__file__, output / "analyze_phone_series.py")
    shutil.copy2(common.__file__, output / "common_comparison.py")
    common.write_json(output / "analysis_rules.json", RULES)
    decisions, runtimes = evaluate(windows, bundle, directory, runtime=runtime, threads=threads)
    comparisons = compare_trials(trials, decisions, origin_ns, first_ns, last_ns)
    intervals = normal_intervals(trials, origin_ns + int(warmup * 1e9), capture_end)
    normal = summarize_normal(intervals, decisions, origin_ns, first_ns, last_ns)
    for row in decisions:
        row["start_relative_s"] = (row["start_ns"] - origin_ns) / 1e9
        row["end_relative_s"] = (row["end_ns"] - origin_ns) / 1e9
        row["search_trials_inside"] = ";".join(str(t["number"]) for t in trials if t["marker_status"] == "valid" and position(row, t["start_ns"], t["end_ns"]) == "inside")
        row["search_trials_boundary_unclear"] = ";".join(str(t["number"]) for t in trials if t["marker_status"] == "valid" and position(row, t["start_ns"], t["end_ns"]) == "boundary")
    _csv(output / "window_results.csv", decisions)
    _csv(output / "trial_comparison.csv", comparisons)
    _csv(output / "normal_phases.csv", normal)
    summary = {"trials_planned": 10, "trials_with_valid_markers": sum(t["marker_status"] == "valid" for t in trials),
               "capture_status": final["status"], "capture_error": final.get("error"),
               "samples_saved": len(times), "raw_window_groups": len(windows),
               "valid_raw_windows": sum(w["valid_raw"] for w in windows),
               "invalid_raw_windows": sum(not w["valid_raw"] for w in windows),
               "incomplete_samples": sum(w["sample_count"] for w in windows if w["sample_count"] != 128),
               "recorded_observation_duration_s": (last_ns - first_ns) / 1e9 if len(times) else 0,
               "rules": RULES, "trials": trials, "cue_issues": cue_issues, "runtime": runtimes,
               "profile_name": config["profile_name"], "pwm": config.get("pwm"),
               "bundle_sha256": bundle_hash, "source_file_sha256": {str(p.relative_to(run)): common.sha256(p) for p in sorted(run.rglob("*")) if p.is_file()},
               "provenance": common.provenance(), "methods": {}, "benchmark": None,
               "scope": "Wiederholte Untersuchung an diesem Aufbau; kein Nachweis allgemeiner Überlegenheit.",
               "true_vibration_onset_known": False, "live_output_timing_measured": False,
               "models_scaler_thresholds_changed": False}
    for method in common.METHODS:
        entries = [e for e in comparisons if e["method"] == method]
        normal_rows = [r for r in normal if r["method"] == method]
        valid_count = sum(r["valid_windows"] for r in normal_rows)
        alarms = sum(r["alarm_windows"] for r in normal_rows)
        summary["methods"][method] = {"denominator_trials": 10,
            "trials_with_first_alarm": sum(e["first_alarm_window"] is not None for e in entries),
            "trials_with_first_new_alarm": sum(e["first_new_alarm_window"] is not None for e in entries),
            "trials_without_new_alarm": sum(e["first_new_alarm_window"] is None for e in entries),
            "trials_with_issues": sum(bool(e["issues"]) for e in entries),
            "normal_recorded_duration_s": sum(r["recorded_duration_s"] for r in normal_rows),
            "normal_valid_windows": valid_count, "normal_alarm_windows": alarms,
            "normal_alarm_window_fraction": alarms / valid_count if valid_count else None,
            "normal_invalid_windows": sum(r["invalid_windows"] for r in normal_rows)}
    if benchmark:
        timing_rows, benchmark_summary = benchmark_windows(windows, bundle, directory, runtime=runtime, threads=threads)
        _csv(output / "processing_benchmark.csv", timing_rows)
        common.write_json(output / "processing_benchmark.json", benchmark_summary)
        summary["benchmark"] = benchmark_summary
    plots(output / "figures", times, xyz, decisions, trials, comparisons, origin_ns)
    common.write_json(output / "summary.json", summary)
    command = f"python {shlex.quote(str(output / 'analyze_phone_series.py'))} --run {shlex.quote(str(output / 'source'))} --output NEUER_ERGEBNISORDNER --runtime {runtime} --threads {threads}" + (" --benchmark" if benchmark else "")
    (output / "reproduce.sh").write_text("#!/bin/sh\nset -eu\n" + command + "\n", encoding="utf-8")
    report = ["# Smartphoneversuch: zehn Anrufe", "",
              f"Geplant: zehn Versuche; vollständig und eindeutig markiert: {summary['trials_with_valid_markers']}/10. Aufnahmestatus: {final['status']}.",
              f"Profil: {config['profile_name']}; PWM-Konfiguration: `{json.dumps(config.get('pwm'), ensure_ascii=False)}`. Einlaufzeit: {warmup:g} s. Beobachtungsdauer gespeicherter Samples: {summary['recorded_observation_duration_s']:.3f} s.",
              "Die Serie ist eine wiederholte Untersuchung am unveränderten Aufbau mit Google Pixel 9a. Die Konfiguration und die vollständige Aufnahme einschließlich Modellversionen sind unter source archiviert.", "",
              "Die Chatmarker begrenzen Suchbereiche; Vibrationsbeginn und -ende wurden nicht separat gemessen. Nur vollständig enthaltene Fenster gehen in den primären Vergleich ein. Randfenster sind separat unklar. Ein bestehender Alarm ist keine neue Reaktion: Ein neuer Alarm erfordert ein direkt vorheriges gültiges, lückenlos anschließendes NORMAL-Fenster. Zeitabstände beruhen auf gespeicherten Host-Empfangszeiten, nicht auf Live-Ausgabezeiten.",
              "Modelle, Skalierung, 128/128-Fenster und Schwellen bleiben unverändert. Alle Verfahren erhalten dieselben Rohfenster. Technisch ungültige Fenster und fehlende Versuche bleiben sichtbar. Es wurden keine künstlichen Vibrationsdauern oder verfahrensabhängigen Vergleichslabels erzeugt.", "",
              "| Verfahren | Erstes Alarmfenster (Versuche/10) | Neuer Alarm (Versuche/10) | Normal: Alarmfenster/gültige Fenster | Normaler Alarmfensteranteil | Normale Beobachtung [s] |",
              "|---|---:|---:|---:|---:|---:|"]
    for method, values in summary["methods"].items():
        fraction = f"{values['normal_alarm_window_fraction']:.1%}" if values['normal_alarm_window_fraction'] is not None else "nicht bestimmbar"
        report.append(f"| {METHOD_LABELS[method]} | {values['trials_with_first_alarm']}/10 | {values['trials_with_first_new_alarm']}/10 | {values['normal_alarm_windows']}/{values['normal_valid_windows']} | {fraction} | {values['normal_recorded_duration_s']:.3f} |")
    report.extend(["", "| Versuch | Verfahren | Erstes Alarmfenster | Erstes neues Alarmfenster | Rang neuer Alarm | Befund / Unklarheiten |", "|---|---|---:|---:|---:|---|"])
    for entry in comparisons:
        report.append(f"| Versuch {entry['trial']} | {METHOD_LABELS[entry['method']]} | {entry['first_alarm_window'] if entry['first_alarm_window'] is not None else 'fehlt'} | {entry['first_new_alarm_window'] if entry['first_new_alarm_window'] is not None else 'fehlt'} | {entry['first_new_alarm_rank'] if entry['first_new_alarm_rank'] is not None else '–'}{' (Gleichstand)' if entry['first_new_alarm_tie'] else ''} | {entry['result']}; {entry['issues']} |")
    report.extend(["", "Alarmfensteranteile werden auf gültige vollständig enthaltene Fenster bezogen. Die CSV-Dateien nennen zusätzlich ungültige Fenster und Randfenster sowie Suchbereichs- und Beobachtungsdauern. Unterschiedlich lange Suchbereiche werden nicht allein anhand der Alarmanzahl verglichen. Es wird keine allgemeine Überlegenheit eines Verfahrens abgeleitet.", "",
                   "Der separate Benchmark enthält je Verfahren und Runde 20 Warm-up-Fenster, identische gespeicherte gültige Fenster und wechselnde Methodenreihenfolgen; Median und P95 stehen in processing_benchmark.json. Dies ist Rechenzeit auf dem Raspberry Pi, keine Live-Reaktionszeit." if benchmark else "Es wurde kein Verarbeitungszeitbenchmark ausgeführt. Er kann nach Aufnahmeende auf dem Raspberry Pi mit --benchmark in einem neuen Ergebnisordner ausgeführt werden. Offline-Replayzeiten sind keine Live-Reaktionszeiten.",
                   "", "Reproduktion (neuer Ausgabeordner erforderlich):", "", f"```sh\n{command}\n```", ""])
    if benchmark:
        report.extend(["", "| Verfahren | Gemessene Fenster | Median [ms] | P95 [ms] |", "|---|---:|---:|---:|"])
        for method, values in summary["benchmark"]["methods"].items():
            report.append(f"| {METHOD_LABELS[method]} | {values['measured_windows']} | {values['median_ms']:.6f} | {values['p95_ms']:.6f} |")
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--output", required=True, help="Neuer Ordner außerhalb der Aufnahme; wird nie überschrieben")
    parser.add_argument("--runtime", choices=("auto", "litert", "tensorflow"), default="auto")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--benchmark", action="store_true", help="Separater Rechenzeitbenchmark nach Aufnahmeende auf Raspberry Pi")
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("--threads muss positiv sein")
    summary = analyze(args.run, args.output, runtime=args.runtime, threads=args.threads, benchmark=args.benchmark)
    print(json.dumps({"output": str(Path(args.output).resolve()), "methods": summary["methods"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
