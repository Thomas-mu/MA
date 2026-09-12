"""Synthetic independent-test contracts; no hardware, model fits, or real scoring."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import independent_normal_test as evaluation
import pilot_method_comparison as pilot
import prepare_pilot_dataset as preparation

COMMAND = 1_000_000_000_000
FREEZE = COMMAND - 70_000_000_000
DIGEST = "synthetic-protocol-digest"


def dump(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")


def bundle():
    return {"scaler": {"mean": [.00001, -.00002, .00003], "scale": [.01, .02, .04]},
            "thresholds": {method: {"value": 1., "source": "frozen normal validation P99"}
                           for method in evaluation.METHODS}}


@pytest.fixture(scope="module")
def synthetic_frame():
    # 300 seconds, nominal 200 Hz but intentionally observed 207 XYZ/s.
    index = np.arange(62101, dtype=np.int64)
    ns = COMMAND + 50_000_000 + np.rint(index * (1e9 / 207)).astype(np.int64)
    return pd.DataFrame({"sample_index": index, "host_monotonic_ns": ns,
                         "timestamp_s": (ns - ns[0]) / 1e9, "sensor_time_estimate_s": index / 200,
                         "x_g": .700000003 + .017 * np.sin(index * .29),
                         "y_g": -.600000007 + .023 * np.cos(index * .31),
                         "z_g": .120000011 + .041 * np.sin(index * .17),
                         "fifo_depth": 1, "read_duration_ns": 500000,
                         "label": 0, "anomaly_type": "normal",
                         "gap": False, "overrun": False, "saturated": False})


@pytest.fixture
def source(tmp_path, monkeypatch, synthetic_frame):
    csv, sidecar, session = [tmp_path / n for n in ("new_normal_test.csv", "new_normal_test.json", "session.json")]
    protocol_path = tmp_path / "protocol.json"
    p = {"schema_version": 1, "purpose": "independent_normal_test", "protocol_id": "independent_test_fixture",
         "boot_id": "same-boot", "frozen_at_monotonic_ns": FREEZE,
         "frozen_at_utc": "2026-09-11T12:00:00+00:00", "mounting_id": preparation.EXPECTED_MOUNTING,
         "sensor": copy.deepcopy(preparation.EXPECTED_SENSOR), "planned_runs": ["normal_test_01", "normal_test_02", "normal_test_03"],
         "selection_seconds_since_pwm_command": [180, 300], "window_size": 128, "step_size": 128,
         "pwm_percent": 75, "pwm_frequency_hz": 25000, "duration_s": 300,
         "additional_off_after_release_s": 60, "evaluator_sha256": evaluation.sha256(evaluation.__file__),
         "frozen_bundle": {"directory": str(tmp_path / "frozen"), "sha256": evaluation.FROZEN_BUNDLE_SHA256},
         "excluded_recordings": {"csv_sha256": ["old-hash"], "csv_paths": ["/old.csv"], "recording_ids": ["old"]}}
    m = {"schema_version": 1, "status": "completed", "recording_id": csv.stem,
         "phase": "normal_test_01", "purpose": "test", "split": "independent_test", "state": "normal",
         "condition_label": "normal", "label": 0, "mounting_id": p["mounting_id"],
         "fan_pwm_setpoint_percent": 75, "fan_pwm_frequency_hz": 25000, "configured_duration_seconds": 300,
         "detection_controls_fan": False, "protocol_id": p["protocol_id"], "protocol_sha256": DIGEST,
         "frozen_bundle_sha256": p["frozen_bundle"]["sha256"], "sensor": copy.deepcopy(p["sensor"]),
         "code": {"synthetic_fixture": True}, "pwm_command_invocation_monotonic_ns": COMMAND,
         "pwm_command_invocation_utc": "2026-09-11T12:01:10+00:00",
         "user_release": {"released": True, "phase": "normal_test_01", "boot_id": "same-boot",
                          "source": "explicit_user_message", "authorized_phases": ["normal_test_01"],
                          "protocol_id": p["protocol_id"], "protocol_sha256": DIGEST,
                          "mounting_id": p["mounting_id"],
                          "ready_normal_no_plate": True, "external_supply_connected": True,
                          "mechanical_standstill_confirmed": True, "mounting_unchanged": True,
                          "accepted_monotonic_ns": COMMAND - 60_000_000_000,
                          "accepted_utc": "2026-09-11T12:00:10+00:00"}}
    journal = {"status": "completed", "phase": m["phase"], "mounting_id": m["mounting_id"], "boot_id": "same-boot",
               "protocol_id": p["protocol_id"], "protocol_sha256": DIGEST,
               "frozen_bundle_sha256": m["frozen_bundle_sha256"], "csv": str(csv),
               "command_invocation_monotonic_ns": COMMAND,
               "command_invocation_utc": m["pwm_command_invocation_utc"],
               "zero_command_completed_monotonic_ns": COMMAND + 301_000_000_000,
               "after_capture_readback": {"pwm_configuration": {"period_ns": 40000, "duty_cycle_ns": 30000,
                                                                "enable": 1, "polarity": "normal"},
                                          "pwm_mux_confirmed": True},
               "final_readback": {"pwm_configuration": {"period_ns": 40000, "duty_cycle_ns": 0,
                                                        "enable": 1, "polarity": "normal"},
                                  "pwm_mux_confirmed": True}}
    state = {"csv": csv, "sidecar": sidecar, "session": session, "protocol": protocol_path,
             "p": p, "m": m, "journal": journal, "frame": synthetic_frame.copy(deep=True), "bundle": bundle()}
    monkeypatch.setattr(evaluation, "load_protocol", lambda path: (p, DIGEST, state["bundle"], tmp_path / "frozen"))

    def flush():
        state["frame"].to_csv(csv, index=False)
        m["csv_sha256"] = evaluation.sha256(csv)
        quality = evaluation.summarize_quality(state["frame"], COMMAND)
        m["summary"] = {"samples": len(state["frame"]), "observed_host_rate_hz": quality["observed_xyz_per_second"],
                        "nonmonotonic_host_intervals": quality["nonmonotonic_host_intervals"], "lost_samples_exact": None,
                        "gap_flagged_samples": quality["gap_flagged_xyz"],
                        "overrun_flagged_samples": quality["overrun_flagged_xyz"],
                        "saturated_samples": quality["saturated_flagged_xyz"]}
        journal["recording"] = copy.deepcopy(m)
        journal["user_release"] = copy.deepcopy(m["user_release"])
        dump(sidecar, m)
        dump(session, journal)
        dump(protocol_path, p)
    state["flush"] = flush
    flush()
    return state


def load(source):
    return evaluation.load_test_recording(*(source[key] for key in ("csv", "sidecar", "protocol", "session")))


def test_import_matches_training_selection_and_original_float64_centering(source):
    loaded = load(source)
    expected = preparation.make_windows(source["frame"], COMMAND)
    assert loaded["quality"]["nominal_sensor_odr_hz"] == 200
    assert loaded["quality"]["observed_xyz_per_second"] == pytest.approx(207, abs=1e-6)
    assert loaded["quality"]["exact_lost_sensor_samples"] is None
    assert len(loaded["windows"]) == 194
    assert loaded["quality"]["selected_interval"]["trailing_xyz_not_windowed"] == expected["trailing_xyz_dropped"]
    for actual, ac, metadata in zip(loaded["windows"], expected["ac_g"], expected["window_rows"], strict=True):
        np.testing.assert_array_equal(actual["ac_float32"], ac)
        assert actual["raw_float64"].dtype == np.float64
        assert 180 <= actual["metadata"]["start_since_command_s"] < actual["metadata"]["last_since_command_s"] < 300
        assert actual["metadata"]["source_start_index"] == metadata["source_start_index"]


def test_all_methods_receive_identical_saved_scaler_inputs_and_mutations_are_isolated(source):
    loaded = load(source)
    loaded["windows"] = loaded["windows"][:1]
    seen = []
    def score(shared):
        seen.append(shared.copy())
        shared[:] = 999
        return .5
    rows = evaluation.score_loaded(loaded, {method: score for method in evaluation.METHODS})
    canonical = pilot.standardize_ac(loaded["windows"][0]["ac_float32"], loaded["bundle"]["scaler"])
    for value in seen:
        np.testing.assert_array_equal(value, canonical)
        assert value.dtype == np.float32
    assert len(rows) == 3 and all(row["decision"] == "NORMAL" for row in rows)


@pytest.mark.parametrize("flag", evaluation.FLAGS)
def test_flagged_window_is_invalid_for_all_methods_and_not_in_false_alarm_denominator(source, flag):
    chosen = evaluation.build_windows(source["frame"], COMMAND)[0]
    source["frame"].loc[chosen[0]["metadata"]["source_start_index"], flag] = True
    source["flush"]()
    loaded = load(source)
    rows = evaluation.score_loaded(loaded, {method: lambda x: 2. for method in evaluation.METHODS})
    metrics = evaluation.normal_metrics(rows)
    for method in evaluation.METHODS:
        assert rows[list(evaluation.METHODS).index(method)]["decision"] == "INVALID"
        assert metrics[method]["invalid_windows"] == 1
        assert metrics[method]["valid_windows"] == 193
        assert metrics[method]["false_alarms"] == 193
        assert metrics[method]["false_alarm_rate_among_valid_normal_windows"] == 1


@pytest.mark.parametrize("kind", ["nan", "fifo_full", "raw_rail", "host_gap"])
def test_additional_quality_problems_invalidate_affected_window(synthetic_frame, kind):
    frame = synthetic_frame.copy(deep=True)
    first = evaluation.build_windows(frame, COMMAND)[0][0]["metadata"]["source_start_index"]
    if kind == "nan":
        frame.loc[first, "x_g"] = np.nan
    elif kind == "fifo_full":
        frame.loc[first, "fifo_depth"] = 32
    elif kind == "raw_rail":
        frame.loc[first, "z_g"] = 510 * .0039
    else:
        frame.loc[first:, "host_monotonic_ns"] += 200_000_000
    windows, quality = evaluation.build_windows(frame, COMMAND)
    assert quality["quality_invalid_windows"] == 1
    assert windows[0]["ac_float32"] is None
    assert windows[0]["metadata"]["quality_valid"] is False


@pytest.mark.parametrize("field,value", [("purpose", "pilot"), ("split", "validation"), ("state", "normal_after"),
                                         ("fan_pwm_setpoint_percent", 50), ("mounting_id", "old"),
                                         ("configured_duration_seconds", 30), ("detection_controls_fan", True),
                                         ("phase", "normal_test_04"), ("recording_id", "old"),
                                         ("status", "failed"), ("protocol_sha256", "changed")])
def test_import_rejects_wrong_metadata_contract(source, field, value):
    source["m"][field] = value
    source["flush"]()
    with pytest.raises(ValueError):
        load(source)


@pytest.mark.parametrize("key", ["csv_sha256", "csv_paths", "recording_ids"])
def test_historical_exclusion_by_each_identity(source, key):
    value = {"csv_sha256": evaluation.sha256(source["csv"]), "csv_paths": str(source["csv"]),
             "recording_ids": source["csv"].stem}[key]
    source["p"]["excluded_recordings"][key].append(value)
    with pytest.raises(ValueError, match="not independent"):
        load(source)


@pytest.mark.parametrize("kind", ["csv_hash", "session_embedding", "zero", "early_release", "boot",
                                   "sensor", "nominal_time", "host_time", "sample_index", "normal_label"])
def test_import_rejects_corrupt_provenance_or_structural_time(source, kind):
    if kind == "csv_hash":
        source["m"]["csv_sha256"] = "wrong"
        dump(source["sidecar"], source["m"])
    elif kind == "session_embedding":
        source["journal"]["recording"]["label"] = 1
        dump(source["session"], source["journal"])
    elif kind == "zero":
        source["journal"]["final_readback"]["pwm_configuration"]["duty_cycle_ns"] = 30000
        source["flush"]()
    elif kind == "early_release":
        source["m"]["user_release"]["accepted_monotonic_ns"] = COMMAND - 59_000_000_000
        source["flush"]()
    elif kind == "boot":
        source["m"]["user_release"]["boot_id"] = "other-boot"
        source["flush"]()
    elif kind == "sensor":
        source["m"]["sensor"]["odr_hz"] = 400
        source["flush"]()
    else:
        field = {"nominal_time": "sensor_time_estimate_s", "host_time": "host_monotonic_ns",
                 "sample_index": "sample_index", "normal_label": "label"}[kind]
        source["frame"].loc[1000, field] = source["frame"].loc[999, field] if kind != "normal_label" else 1
        source["flush"]()
    with pytest.raises(ValueError):
        load(source)


def test_quality_flags_outside_selected_interval_do_not_invalidate_late_windows(source):
    source["frame"].loc[100, "gap"] = True
    source["flush"]()
    loaded = load(source)
    assert loaded["quality"]["gap_flagged_xyz"] == 1
    assert loaded["quality"]["selected_interval"]["quality_invalid_windows"] == 0


@pytest.mark.parametrize("field,value", [("ready_normal_no_plate", False), ("external_supply_connected", False),
                                         ("mechanical_standstill_confirmed", False), ("mounting_unchanged", False),
                                         ("source", "inferred"), ("authorized_phases", ["normal_test_02"]),
                                         ("protocol_sha256", "changed")])
def test_missing_explicit_current_release_condition_is_rejected(source, field, value):
    source["m"]["user_release"][field] = value
    source["flush"]()
    with pytest.raises(ValueError):
        load(source)


def test_recording_start_delay_over_one_second_is_rejected(source):
    source["frame"]["host_monotonic_ns"] += 1_100_000_000
    source["journal"]["zero_command_completed_monotonic_ns"] += 2_000_000_000
    source["flush"]()
    with pytest.raises(ValueError, match="Incomplete 300-second"):
        load(source)


def test_invalid_method_output_remains_invalid_without_changing_other_method_denominators(source):
    loaded = load(source)
    loaded["windows"] = loaded["windows"][:1]
    scorers = {method: lambda x: .5 for method in evaluation.METHODS}
    scorers["isolation_forest"] = lambda x: float("nan")
    metrics = evaluation.normal_metrics(evaluation.score_loaded(loaded, scorers))
    assert metrics["isolation_forest"]["valid_windows"] == 0
    assert metrics["isolation_forest"]["false_alarm_rate_among_valid_normal_windows"] is None
    assert metrics["rms"]["valid_windows"] == 1


def test_flag_parser_rejects_unknown_values(synthetic_frame):
    frame = synthetic_frame.iloc[:3].copy()
    frame["gap"] = ["False", "maybe", "True"]
    with pytest.raises(ValueError, match="Unrecognized"):
        evaluation.flag_values(frame, "gap")


def test_normal_metrics_rejects_non_normal_ground_truth():
    with pytest.raises(ValueError, match="normal-only"):
        evaluation.normal_metrics([{"label": 1, "state": "normal"}])


def test_protocol_validates_hash_fixed_parameters_code_and_training_exclusions(tmp_path, monkeypatch):
    directory = tmp_path / "frozen"
    directory.mkdir()
    dump(directory / "pilot_bundle.json", {"synthetic": True})
    bundle_hash = evaluation.sha256(directory / "pilot_bundle.json")
    monkeypatch.setattr(evaluation, "FROZEN_BUNDLE_SHA256", bundle_hash)
    monkeypatch.setattr(pilot, "load_bundle", lambda path: bundle())
    source = {"csv_sha256": "old-hash", "recording_id": "old", "csv": "/old.csv"}
    dump(directory / "prepared_manifest.json", {"sources": [source]})
    p = {"schema_version": 1, "purpose": "independent_normal_test", "protocol_id": "fixture", "boot_id": "boot",
         "frozen_at_monotonic_ns": FREEZE, "frozen_at_utc": "2026-09-11T12:00:00+00:00",
         "mounting_id": preparation.EXPECTED_MOUNTING, "sensor": preparation.EXPECTED_SENSOR,
         "selection_seconds_since_pwm_command": [180, 300], "window_size": 128, "step_size": 128,
         "pwm_percent": 75, "pwm_frequency_hz": 25000, "duration_s": 300, "additional_off_after_release_s": 60,
         "planned_runs": ["normal_test_01", "normal_test_02", "normal_test_03"],
         "frozen_bundle": {"directory": str(directory), "sha256": bundle_hash},
         "evaluator_sha256": evaluation.sha256(evaluation.__file__),
         "excluded_recordings": {"csv_sha256": ["old-hash"], "recording_ids": ["old"], "csv_paths": ["/old.csv"]}}
    path = tmp_path / "protocol.json"
    def freeze():
        dump(path, p)
        (tmp_path / "protocol.sha256").write_text(evaluation.sha256(path))
    freeze()
    assert evaluation.load_protocol(path)[0] == p
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="fingerprint"):
        evaluation.load_protocol(path)
    for key, value in (("window_size", 256), ("selection_seconds_since_pwm_command", [200, 300]),
                       ("evaluator_sha256", "changed")):
        old = p[key]
        p[key] = value
        freeze()
        with pytest.raises(ValueError):
            evaluation.load_protocol(path)
        p[key] = old
    p["excluded_recordings"]["recording_ids"] = ["someone-else"]
    freeze()
    with pytest.raises(ValueError, match="exclusion"):
        evaluation.load_protocol(path)


def test_synthetic_evaluation_and_combination_write_separate_artifacts(source, monkeypatch, tmp_path):
    loaded = load(source)
    monkeypatch.setattr(evaluation, "load_test_recording", lambda *args: loaded)
    monkeypatch.setattr(pilot, "model_scorers", lambda *args: ({m: lambda x: .5 for m in evaluation.METHODS}, {m: "synthetic" for m in evaluation.METHODS}))
    monkeypatch.setattr(pilot, "load_bundle", lambda path: bundle())
    loaded["source"]["protocol_sha256"] = evaluation.sha256(source["protocol"])
    out = tmp_path / "evaluated"
    report = evaluation.evaluate_recording(source["csv"], source["sidecar"], source["protocol"], source["session"], out)
    assert report["metrics"]["rms"]["valid_windows"] == 194
    assert (out / "scores.png").stat().st_size > 1000
    summary = evaluation.combine_results([out], tmp_path / "combined")
    assert summary["status"] == "partial"
    assert summary["anomaly_performance_evaluated"] is False
    assert summary["pooled"]["rms"]["false_alarms"] == 0
    with pytest.raises(ValueError, match="reused"):
        evaluation.combine_results([out, out], tmp_path / "duplicate")
    with pytest.raises(ValueError, match="no overwrite"):
        evaluation.evaluate_recording(source["csv"], source["sidecar"], source["protocol"], source["session"], out)
