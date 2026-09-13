#!/usr/bin/env python3
"""Offline-only reference-edge analysis. Never accesses GPIO/I2C or controls a fan."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
from datetime import datetime, timezone


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reject_nonfinite_json(value):
    raise ValueError(f"nonfinite JSON numeric constant {value!r}")


def positive_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: finite positive number required")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name}: finite positive number required")
    return value


def nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: nonempty documentation required")


def finite_tree(value, path="result"):
    """Reject nonfinite derived values before any output directory is created."""
    if isinstance(value, dict):
        for key, child in value.items():
            finite_tree(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            finite_tree(child, f"{path}[{index}]")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            valid = math.isfinite(value)
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError(f"{path}: nonfinite or unrepresentable numeric value")


def validate_metadata(meta):
    if not isinstance(meta, dict):
        raise ValueError("metadata must be an object")
    if type(meta.get("schema_version")) is not int or meta.get("schema_version") != 1:
        raise ValueError("metadata schema_version must be 1")
    if meta.get("dataset_kind") not in {"SYNTHETIC", "MEASUREMENT"}:
        raise ValueError("dataset_kind must explicitly be SYNTHETIC or MEASUREMENT")
    for name in ("source", "instrument"):
        nonempty(meta.get(name), name)
    if meta.get("clock_relation") not in {"external_independent", "shared_host", "unknown"}:
        raise ValueError("clock_relation must be external_independent, shared_host, or unknown")
    nonempty(meta.get("clock_relation_basis"), "clock_relation_basis")
    if "time_accuracy_s" not in meta:
        raise ValueError("time_accuracy_s required; use null for unknown")
    if meta["time_accuracy_s"] is not None:
        positive_number(meta["time_accuracy_s"], "time_accuracy_s")
        nonempty(meta.get("time_accuracy_basis"), "time_accuracy_basis")
    if type(meta.get("capture_integrity_confirmed")) is not bool:
        raise ValueError("capture_integrity_confirmed must explicitly be boolean")
    if meta["capture_integrity_confirmed"]:
        nonempty(meta.get("capture_integrity_evidence"), "capture_integrity_evidence")
    channels = meta.get("channels")
    if not isinstance(channels, dict) or not channels:
        raise ValueError("nonempty channels object required")
    for name, config in channels.items():
        nonempty(name, "channel name")
        if not isinstance(config, dict):
            raise ValueError(f"{name}: channel configuration must be an object")
        if config.get("kind") not in {"tachometer", "adxl_data_ready", "pwm", "other"}:
            raise ValueError(f"{name}: unsupported channel kind")
        if config.get("selected_edge") not in {"rising", "falling"}:
            raise ValueError(f"{name}: select exactly one edge direction")
        if config.get("pulses_per_revolution") is not None:
            positive_number(config["pulses_per_revolution"], f"{name}.pulses_per_revolution")
        for key in ("ppr_confirmed", "one_edge_per_sample_confirmed"):
            if key in config and type(config[key]) is not bool:
                raise ValueError(f"{name}.{key}: boolean required")
        if config.get("ppr_confirmed", False):
            if config["kind"] != "tachometer" or config.get("pulses_per_revolution") is None:
                raise ValueError(f"{name}: confirmed PPR requires tachometer and PPR value")
            nonempty(config.get("ppr_evidence"), f"{name}.ppr_evidence")
        if config.get("one_edge_per_sample_confirmed", False):
            if config["kind"] != "adxl_data_ready":
                raise ValueError(f"{name}: sample-edge correspondence only applies to DATA_READY")
            nonempty(config.get("one_edge_per_sample_evidence"), f"{name}.one_edge_per_sample_evidence")
    return meta


def read_events(path, channels):
    events = {channel: [] for channel in channels}
    previous_global = None
    previous_channel = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"reference_time_s", "channel", "edge"}
        names = reader.fieldnames or []
        if not required.issubset(names) or len(names) != len(set(names)):
            raise ValueError("CSV requires unique reference_time_s, channel, edge columns")
        if set(names) - required - {"quality_flag"}:
            raise ValueError("unexpected CSV columns")
        for line, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"CSV line {line}: malformed row")
            try:
                stamp = float(row["reference_time_s"])
            except (ValueError, TypeError):
                raise ValueError(f"CSV line {line}: invalid timestamp") from None
            if not math.isfinite(stamp):
                raise ValueError(f"CSV line {line}: nonfinite timestamp")
            channel, edge = row["channel"], row["edge"]
            if channel not in channels or edge not in {"rising", "falling"}:
                raise ValueError(f"CSV line {line}: unknown channel or edge")
            if previous_global is not None and stamp < previous_global:
                raise ValueError(f"CSV line {line}: globally nonmonotone timestamps")
            if channel in previous_channel and stamp <= previous_channel[channel]:
                raise ValueError(f"CSV line {line}: duplicate/nonincreasing channel timestamp")
            flag = row.get("quality_flag", "unknown") or "unknown"
            if flag not in {"ok", "invalid", "gap", "unknown"}:
                raise ValueError(f"CSV line {line}: unsupported quality_flag {flag!r}")
            events[channel].append({"t": stamp, "edge": edge, "quality": flag})
            previous_global = stamp
            previous_channel[channel] = stamp
    return events


def interval_stats(intervals):
    if not intervals:
        return {"count": 0, "mean_s": None, "median_s": None, "min_s": None,
                "max_s": None, "sample_sd_s": None}
    return {"count": len(intervals), "mean_s": statistics.mean(intervals),
            "median_s": statistics.median(intervals), "min_s": min(intervals),
            "max_s": max(intervals),
            "sample_sd_s": statistics.stdev(intervals) if len(intervals) > 1 else None}


def _analyze(csv_path, metadata_path):
    meta = validate_metadata(json.loads(Path(metadata_path).read_text(encoding="utf-8"),
                                        parse_constant=reject_nonfinite_json))
    finite_tree(meta, "metadata")
    by_channel = read_events(csv_path, meta["channels"])
    results = {}
    for name, config in meta["channels"].items():
        events = by_channel[name]
        selected = [(i, e) for i, e in enumerate(events) if e["edge"] == config["selected_edge"]]
        intervals, qualified_intervals = [], []
        for (previous_i, previous), (current_i, current) in zip(selected, selected[1:]):
            interval = current["t"] - previous["t"]
            positive_number(interval, f"{name}.derived_interval_s")
            intervals.append(interval)
            # No bridging over a flagged event, including an opposite-direction edge.
            if all(e["quality"] == "ok" for e in events[previous_i:current_i + 1]):
                qualified_intervals.append(interval)
        frequency = 1 / statistics.mean(intervals) if intervals else None
        if frequency is not None:
            positive_number(frequency, f"{name}.derived_frequency_hz")
        all_quality_ok = bool(events) and all(e["quality"] == "ok" for e in events)
        quality_eligible = all_quality_ok and bool(intervals)
        independent_timing = (meta["clock_relation"] == "external_independent"
                              and meta["time_accuracy_s"] is not None)
        capture_eligible = meta["capture_integrity_confirmed"] and quality_eligible
        ppr = config.get("pulses_per_revolution")
        ppr_confirmed = config.get("ppr_confirmed", False)
        rpm_eligible = config["kind"] == "tachometer" and ppr_confirmed and capture_eligible
        sample_correspondence = (config["kind"] == "adxl_data_ready"
                                 and config.get("one_edge_per_sample_confirmed", False))
        odr_conditions = sample_correspondence and capture_eligible and independent_timing
        conditional_odr_available = odr_conditions and meta["dataset_kind"] == "MEASUREMENT"
        rpm_estimate = frequency * 60 / ppr if rpm_eligible else None
        if rpm_estimate is not None:
            positive_number(rpm_estimate, f"{name}.conditional_rpm_estimate")
        reasons = []
        if not intervals:
            reasons.append("Fewer than two selected edges; no period estimate. Zero edges do not prove mechanical standstill.")
        if not all_quality_ok:
            reasons.append("Missing or non-ok quality flags; frequency remains descriptive, not a confirmed physical rate.")
        if not meta["capture_integrity_confirmed"]:
            reasons.append("Capture completeness is not confirmed; missed edges and physical losses remain unknown.")
        if not independent_timing:
            reasons.append("Independent instrument timing with documented accuracy is not established.")
        if config["kind"] == "tachometer" and not ppr_confirmed:
            reasons.append("Pulses per revolution are not confirmed: report frequency only, never RPM.")
        if config["kind"] == "adxl_data_ready" and not sample_correspondence:
            reasons.append("DATA_READY may stay asserted or merge events; edge rate is not established as sensor ODR.")
        if config["kind"] == "adxl_data_ready":
            reasons.append("No independently checkable burst-to-sample/pulse mapping is imported. Metadata claims never establish software-verified ODR or an independent ODR reference.")
        if config["kind"] == "tachometer":
            reasons.append("RPM conversion is conditional on external PPR, timing, and capture claims. The program does not verify their physical truth or establish an independent RPM reference.")
        results[name] = {
            "kind": config["kind"], "selected_edge": config["selected_edge"],
            "all_edge_count": len(events), "selected_edge_count": len(selected),
            "quality_counts": {q: sum(e["quality"] == q for e in events)
                               for q in ("ok", "invalid", "gap", "unknown")},
            "first_selected_edge_s": selected[0][1]["t"] if selected else None,
            "last_selected_edge_s": selected[-1][1]["t"] if selected else None,
            "same_direction_intervals": interval_stats(intervals),
            "quality_ok_contiguous_intervals": interval_stats(qualified_intervals),
            "observed_same_direction_edge_frequency_hz": frequency,
            "pulses_per_revolution_documented": ppr,
            "ppr_confirmed_by_metadata": ppr_confirmed,
            "rpm_estimate": rpm_estimate,
            "rpm_estimate_status": ("conditional_on_external_ppr_and_capture_claims"
                                    if rpm_eligible else "unavailable"),
            "sensor_odr_estimate_hz": None,
            "conditional_sensor_odr_estimate_hz": frequency if conditional_odr_available else None,
            "conditional_sensor_odr_estimate_status": ("conditional_on_external_mapping_claim"
                                                       if conditional_odr_available else "unavailable"),
            "physical_sample_losses": None,
            "mechanical_standstill_confirmed": False,
            "eligibility": {
                "period_estimate_available": bool(intervals),
                "all_event_quality_ok": all_quality_ok,
                "capture_integrity_claimed_in_metadata": meta["capture_integrity_confirmed"],
                "conditional_rpm_conversion_available": rpm_eligible,
                "independent_rpm_reference_eligible": False,
                "one_edge_per_sensor_sample_claimed_in_metadata": sample_correspondence,
                "metadata_odr_conversion_claims_complete": odr_conditions,
                "independent_sensor_odr_reference_eligible": False,
                "software_verified_physical_reference": False,
                "physical_loss_count_eligible": False,
            },
            "limitations": reasons,
        }
    return {
        "schema_version": 2,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_kind": meta["dataset_kind"],
        "physical_measurement_declared_in_metadata": meta["dataset_kind"] == "MEASUREMENT",
        "software_verified_physical_reference": False,
        "metadata": meta,
        "provenance": {"csv_path": str(Path(csv_path).resolve()), "csv_sha256": sha256(csv_path),
                       "metadata_path": str(Path(metadata_path).resolve()),
                       "metadata_sha256": sha256(metadata_path), "tool_sha256": sha256(__file__)},
        "channels": results,
        "interpretation": [
            "This program reads files only; metadata confirmations are external claims, not independently checked physical evidence.",
            "All independent physical-reference eligibility fields remain false. Conditional estimates must not be reported as verified RPM or ODR.",
            "Edge frequency is (N-1)/(last-first) using only the selected edge direction, not all transitions.",
            "No uncertainty interval is inferred from one stated timestamp accuracy value; clock calibration and systematic errors require separate assessment.",
            "No sample-loss count is inferred from nominal-versus-observed frequency differences.",
            "SYNTHETIC datasets test software only and establish no physical measurement evidence.",
        ],
    }


def analyze(csv_path, metadata_path):
    try:
        result = _analyze(csv_path, metadata_path)
        finite_tree(result)
        return result
    except ArithmeticError as error:
        raise ValueError(f"numeric derivation not representable: {error}") from None


def run(csv_path, metadata_path, output):
    # Validate before creating any output. An existing directory is never reused.
    result = analyze(csv_path, metadata_path)
    serialized = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "analysis.json").write_text(serialized, encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path,
                        help="new directory, must not already exist")
    args = parser.parse_args()
    try:
        result = run(args.csv, args.metadata, args.output)
    except (ValueError, OSError, TypeError) as error:
        parser.exit(2, f"Reference import rejected: {error}\n")
    print(f"{result['dataset_kind']}: {args.output / 'analysis.json'}")


if __name__ == "__main__":
    main()
