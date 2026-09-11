"""Independent offline checks of the v4 development-dataset preparation.

All recordings here are synthetic. No acquisition, model fitting, scaling,
GPIO access, or changes to historical project artifacts are needed.
"""

from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import prepare_pilot_dataset as preparation


COMMAND_NS = 2**53 + 3
AXES = ["x_g", "y_g", "z_g"]


def synthetic_frame(offsets_ns, *, first_index=0):
    """Give host time and original sample index different, explicit origins."""
    offsets_ns = np.asarray(offsets_ns, dtype=np.int64)
    index = np.arange(len(offsets_ns), dtype=np.int64)
    return pd.DataFrame(
        {
            "host_monotonic_ns": COMMAND_NS + offsets_ns,
            "sample_index": first_index + index,
            "x_g": 0.5 + ((index % 19) - 9) / 1024,
            "y_g": -0.75 + ((index % 13) - 6) / 1024,
            "z_g": 0.125 + ((index % 11) - 5) / 1024,
        }
    )


def regular_frame(count=260, *, first_index=0):
    offsets = 180_000_000_000 + np.arange(count, dtype=np.int64) * 5_000_000
    return synthetic_frame(offsets, first_index=first_index)


def test_crop_uses_command_origin_and_exact_half_open_bounds():
    # These one-nanosecond distinctions disappear if large absolute host
    # timestamps are converted to Float64 before subtracting the command.
    offsets = np.concatenate(
        (
            np.array([179_999_999_999], dtype=np.int64),
            180_000_000_000 + np.arange(259, dtype=np.int64) * 5_000_000,
            np.array([300_000_000_000, 300_000_000_001], dtype=np.int64),
        )
    )
    frame = synthetic_frame(offsets, first_index=710)
    original = frame.copy(deep=True)

    result = preparation.make_windows(frame, COMMAND_NS)

    assert result["xyz_selected"] == 259
    assert result["trailing_xyz_dropped"] == 3
    assert result["raw_g"].shape == (2, 128, 3)
    assert result["raw_g"].dtype == np.float32
    assert result["ac_g"].shape == (2, 128, 3)
    assert result["ac_g"].dtype == np.float32
    expected_raw = frame.loc[1:256, AXES].to_numpy(np.float32).reshape(2, 128, 3)
    np.testing.assert_array_equal(result["raw_g"], expected_raw)
    rows = result["window_rows"]
    assert len(rows) == 2
    assert rows[0]["source_start_index"] == 711
    assert rows[0]["source_end_index_exclusive"] == 839
    assert rows[1]["source_start_index"] == 839
    assert rows[1]["source_end_index_exclusive"] == 967
    assert rows[0]["start_since_command_s"] == pytest.approx(180.0, abs=1e-10)
    assert rows[0]["last_since_command_s"] == pytest.approx(180.635, abs=1e-10)
    assert rows[1]["start_since_command_s"] == pytest.approx(180.640, abs=1e-10)
    assert rows[1]["last_since_command_s"] == pytest.approx(181.275, abs=1e-10)
    pd.testing.assert_frame_equal(frame, original)


def test_windows_preserve_source_rows_and_do_not_overlap():
    frame = regular_frame(389, first_index=4000)
    result = preparation.make_windows(frame, COMMAND_NS)

    assert result["xyz_selected"] == 389
    assert result["trailing_xyz_dropped"] == 5
    assert len(result["window_rows"]) == 3
    covered = []
    for window, row in zip(result["raw_g"], result["window_rows"], strict=True):
        first = row["source_start_index"]
        end = row["source_end_index_exclusive"]
        assert end - first == 128
        rows = frame.loc[frame["sample_index"].between(first, end - 1)]
        np.testing.assert_array_equal(window, rows[AXES].to_numpy(np.float32))
        covered.extend(range(first, end))
    assert len(covered) == len(set(covered)) == 384
    assert covered == list(range(4000, 4384))


def test_ac_is_translation_invariant_and_centered_per_window_and_axis():
    frame = regular_frame(256)
    # Independent DC levels in the two windows must both disappear.
    frame.loc[128:, AXES] += np.array([1.0, -2.0, 0.5])
    translated = frame.copy(deep=True)
    translated[AXES] += np.array([8.0, -16.0, 4.0])

    baseline = preparation.make_windows(frame, COMMAND_NS)
    moved_dc = preparation.make_windows(translated, COMMAND_NS)

    np.testing.assert_array_equal(baseline["ac_g"], moved_dc["ac_g"])
    np.testing.assert_allclose(
        baseline["ac_g"].astype(np.float64).mean(axis=1), 0.0, atol=1e-9, rtol=0
    )
    assert not np.array_equal(baseline["raw_g"], moved_dc["raw_g"])
    # This is vector AC RMS, not RMS averaged across all three components.
    vector_rms = np.sqrt(np.mean(np.sum(baseline["ac_g"].astype(np.float64) ** 2, axis=2), axis=1))
    translated_rms = np.sqrt(np.mean(np.sum(moved_dc["ac_g"].astype(np.float64) ** 2, axis=2), axis=1))
    np.testing.assert_array_equal(vector_rms, translated_rms)


def test_ac_centering_precedes_float32_quantization():
    frame = regular_frame(128)
    # Deliberately sub-Float32 variation tests the stated arithmetic order.
    # These synthetic values are not a claim about ADXL345 resolution.
    for axis, offset in zip(AXES, (0.5, -0.75, 0.25), strict=True):
        frame[axis] = offset + np.arange(128, dtype=np.float64) * 1e-11
    values = frame[AXES].to_numpy(np.float64).reshape(1, 128, 3)
    expected = (values - values.mean(axis=1, keepdims=True)).astype(np.float32)

    result = preparation.make_windows(frame, COMMAND_NS)

    np.testing.assert_array_equal(result["ac_g"], expected)
    assert np.any(result["ac_g"] != 0)
    assert np.all(result["raw_g"] == result["raw_g"][:, :1, :])


@pytest.mark.parametrize("problem", ("duplicate_host", "reversed_host", "missing_index", "duplicate_index"))
def test_invalid_time_or_sample_sequence_is_rejected(problem):
    frame = regular_frame()
    if problem == "duplicate_host":
        frame.loc[17, "host_monotonic_ns"] = frame.loc[16, "host_monotonic_ns"]
    elif problem == "reversed_host":
        frame.loc[17, "host_monotonic_ns"] = frame.loc[15, "host_monotonic_ns"]
    elif problem == "missing_index":
        frame.loc[17:, "sample_index"] += 1
    else:
        frame.loc[17, "sample_index"] = frame.loc[16, "sample_index"]
    with pytest.raises(ValueError):
        preparation.make_windows(frame, COMMAND_NS)


@pytest.mark.parametrize("axis", AXES)
@pytest.mark.parametrize("value", (np.nan, np.inf, -np.inf))
def test_nonfinite_axis_values_are_rejected(axis, value):
    frame = regular_frame()
    frame.loc[17, axis] = value
    with pytest.raises(ValueError):
        preparation.make_windows(frame, COMMAND_NS)


@pytest.mark.parametrize("count", (0, 1, 127))
def test_missing_complete_window_is_rejected(count):
    with pytest.raises(ValueError):
        preparation.make_windows(regular_frame(count), COMMAND_NS)


def test_empty_command_relative_selection_is_rejected():
    frame = regular_frame(256)
    # A shifted command changes selection even when the first sample stays put.
    with pytest.raises(ValueError):
        preparation.make_windows(frame, COMMAND_NS + 180_000_000_000)


def test_exactly_one_complete_window_needs_no_tail_drop():
    result = preparation.make_windows(regular_frame(128), COMMAND_NS)
    assert result["xyz_selected"] == 128
    assert result["trailing_xyz_dropped"] == 0
    assert result["raw_g"].shape == (1, 128, 3)


@pytest.fixture
def source_plan(tmp_path):
    """Small synthetic full-duration journals, entirely below tmp_path.

    The sparse 100-ms host spacing keeps file-based interface tests cheap;
    it is deliberately not evidence of real ADXL345 behavior or valid SNR.
    """
    sensor = {
        "model": "ADXL345", "odr_hz": 200, "range_g": 2,
        "full_resolution": True, "scale_g_per_lsb": 0.0039,
        "acquisition_mode": "fifo_stream",
        "register_readback": {"0x2c": "0xb", "0x31": "0x8", "0x2e": "0x0", "0x38": "0x90", "0x2d": "0x8"},
        "timestamp_source": "host_monotonic_read_completion",
        "bus_number": 1, "i2c_clock_configured_hz": 100000,
    }
    plan = {
        "schema_version": 1, "purpose": "development_pilot_preparation",
        "preprocessing_id": preparation.PREPROCESSING_ID,
        "selection_seconds_since_pwm_command": [180, 300],
        "window_size": 128, "step_size": 128,
        "mounting_id": "fan_upright_position_v4_20260911_103726", "sensor": sensor, "sources": [],
    }
    states = ("normal_before", "normal_after", "normal_followup")
    for ordinal, state in enumerate(states):
        directory = tmp_path / state
        directory.mkdir()
        command = COMMAND_NS + ordinal * 400_000_000_000
        index = np.arange(3001, dtype=np.int64)
        frame = synthetic_frame(50_000_000 + index * 100_000_000)
        frame["host_monotonic_ns"] += ordinal * 400_000_000_000
        frame["timestamp_s"] = index / 10
        frame["sensor_time_estimate_s"] = index / 200
        frame["read_duration_ns"] = 1_000_000
        frame["fifo_depth"] = 1
        frame["label"] = 0
        frame["anomaly_type"] = state
        for flag in ("gap", "overrun", "saturated"):
            frame[flag] = False
        csv = directory / "original.csv"
        frame.to_csv(csv, index=False)
        metadata = directory / "original.json"
        recording_id = f"synthetic_{state}"
        journal = {
            "schema_version": 1, "status": "completed", "purpose": "pilot",
            "split": "development_pilot", "recording_id": recording_id,
            "state": state, "phase": state, "condition_label": state, "label": 0,
            "mounting_id": plan["mounting_id"], "sensor": sensor,
            "fan_pwm_setpoint_percent": 75, "fan_pwm_frequency_hz": 25000,
            "configured_duration_seconds": 300, "code": {"synthetic_test_only": True},
            "detection_controls_fan": False,
            "csv_sha256": preparation.sha256(csv),
            "pwm_command_invocation_monotonic_ns": command,
            "pwm_command_invocation_utc": f"2026-09-11T12:{ordinal * 10:02d}:00+00:00",
            "user_release": {"boot_id": "synthetic_same_boot"},
            "summary": {
                "samples": len(frame), "observed_host_rate_hz": 10.,
                "overrun_flagged_samples": 0, "gap_flagged_samples": 0,
                "saturated_samples": 0, "nonmonotonic_host_intervals": 0,
            },
        }
        metadata.write_text(json.dumps(journal), encoding="utf-8")
        evidence = directory / "control.json"
        evidence.write_text(json.dumps({"synthetic_test_only": True, "ordinal": ordinal}), encoding="utf-8")
        plan["sources"].append({
            "csv": str(csv), "csv_sha256": preparation.sha256(csv),
            "metadata": str(metadata), "metadata_sha256": preparation.sha256(metadata),
            "recording_id": recording_id, "state": state,
            "split": "validation" if ordinal == 2 else "train",
            "evidence": [{"path": str(evidence), "sha256": preparation.sha256(evidence)}],
        })
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path, plan


def rehash_synthetic_source(source):
    """Update a synthetic journal after intentionally damaging its fixture CSV."""
    metadata = Path(source["metadata"])
    journal = json.loads(metadata.read_text())
    source["csv_sha256"] = preparation.sha256(source["csv"])
    journal["csv_sha256"] = source["csv_sha256"]
    metadata.write_text(json.dumps(journal), encoding="utf-8")
    source["metadata_sha256"] = preparation.sha256(metadata)


@pytest.mark.parametrize("key", ("csv", "csv_sha256", "recording_id", "metadata", "metadata_sha256"))
def test_plan_rejects_duplicate_source_identity(source_plan, key):
    _, plan = source_plan
    plan["sources"][2][key] = plan["sources"][0][key]
    with pytest.raises(ValueError):
        preparation.validate_plan(plan)


def test_plan_rejects_changed_whole_record_split(source_plan):
    _, plan = source_plan
    plan["sources"][0]["split"] = "validation"
    with pytest.raises(ValueError):
        preparation.validate_plan(plan)


def test_plan_rejects_missing_sensor_contract(source_plan):
    _, plan = source_plan
    plan["sensor"] = {}
    with pytest.raises(ValueError, match="sensor"):
        preparation.validate_plan(plan)


def test_recording_rejects_csv_hash_mismatch(source_plan):
    _, plan = source_plan
    source = plan["sources"][0]
    with Path(source["csv"]).open("a") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="hash"):
        preparation.validate_recording(source["csv"], source["metadata"], source, plan)


@pytest.mark.parametrize("flag", ("gap", "overrun", "saturated"))
def test_quality_flag_before_crop_is_not_silently_discarded(source_plan, flag):
    _, plan = source_plan
    source = plan["sources"][0]
    frame = pd.read_csv(source["csv"], float_precision="round_trip")
    frame.loc[0, flag] = True  # 50 ms after command, far before 180-s crop.
    frame.to_csv(source["csv"], index=False)
    rehash_synthetic_source(source)
    with pytest.raises(ValueError, match=flag):
        preparation.validate_recording(source["csv"], source["metadata"], source, plan)


def test_recording_rejects_sensor_mismatch(source_plan):
    _, plan = source_plan
    source = plan["sources"][0]
    metadata = Path(source["metadata"])
    journal = json.loads(metadata.read_text())
    journal["sensor"]["odr_hz"] = 100
    metadata.write_text(json.dumps(journal), encoding="utf-8")
    source["metadata_sha256"] = preparation.sha256(metadata)
    with pytest.raises(ValueError, match="Sensor"):
        preparation.validate_recording(source["csv"], metadata, source, plan)


def test_prepare_rejects_existing_output_without_touching_it(source_plan, tmp_path):
    path, plan = source_plan
    output = tmp_path / "already_there"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_bytes(b"existing content\n")
    hashes = {s["csv"]: preparation.sha256(s["csv"]) for s in plan["sources"]}
    with pytest.raises(ValueError, match="overwrit"):
        preparation.prepare(path, output)
    assert sentinel.read_bytes() == b"existing content\n"
    assert list(output.iterdir()) == [sentinel]
    assert hashes == {s["csv"]: preparation.sha256(s["csv"]) for s in plan["sources"]}


def test_prepare_validates_all_sources_before_creating_output(source_plan, tmp_path):
    path, plan = source_plan
    plan["sources"][-1]["metadata_sha256"] = "0" * 64
    path.write_text(json.dumps(plan), encoding="utf-8")
    output = tmp_path / "invalid_dataset"
    with pytest.raises(ValueError, match="hash"):
        preparation.prepare(path, output)
    assert not output.exists()


def test_prepare_and_verify_preserve_sources_and_whole_record_split(source_plan, tmp_path):
    path, plan = source_plan
    original_bytes = {s[key]: Path(s[key]).read_bytes() for s in plan["sources"] for key in ("csv", "metadata")}
    output = tmp_path / "prepared"
    manifest = preparation.prepare(path, output)
    result = preparation.verify(output)
    assert result["verified"] is True
    assert result["original_recordings"] == 3
    assert result["train_windows"] == 18
    assert result["validation_windows"] == 9
    assert manifest["models_trained"] is False
    assert manifest["scaler_fitted"] is False
    for source_path, content in original_bytes.items():
        assert Path(source_path).read_bytes() == content
    train = pd.read_csv(output / "train_windows.csv")
    validation = pd.read_csv(output / "validation_windows.csv")
    assert set(train.recording_id) == {s["recording_id"] for s in plan["sources"][:2]}
    assert set(validation.recording_id) == {plan["sources"][2]["recording_id"]}
    assert not set(train.source_csv_sha256) & set(validation.source_csv_sha256)


def test_verify_recomputes_arrays_even_if_artifact_hash_is_updated(source_plan, tmp_path):
    path, _ = source_plan
    output = tmp_path / "prepared"
    preparation.prepare(path, output)
    array_path = output / "validation_ac_g.npy"
    array = np.load(array_path, allow_pickle=False)
    array[0, 0, 0] += 0.25
    np.save(array_path, array, allow_pickle=False)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"][array_path.name] = preparation.sha256(array_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        preparation.verify(output)


def test_verify_rejects_false_split_summary(source_plan, tmp_path):
    path, _ = source_plan
    output = tmp_path / "prepared"
    preparation.prepare(path, output)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["splits"]["validation"]["windows"] = 999
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        preparation.verify(output)


def test_verify_rejects_missing_artifact_inventory(source_plan, tmp_path):
    path, _ = source_plan
    output = tmp_path / "prepared"
    preparation.prepare(path, output)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"] = {}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        preparation.verify(output)


def test_verify_rejects_changed_manifest_source_identity(source_plan, tmp_path):
    path, _ = source_plan
    output = tmp_path / "prepared"
    preparation.prepare(path, output)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["sources"][0]["recording_id"] = "invented_other_recording"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        preparation.verify(output)


@pytest.mark.parametrize("artifact", ("train_raw_g.npy", "validation_ac_g.npy", "validation_labels.npy"))
def test_verify_rejects_changed_array_dtype_even_with_updated_hash(source_plan, tmp_path, artifact):
    path, _ = source_plan
    output = tmp_path / "prepared"
    preparation.prepare(path, output)
    array_path = output / artifact
    array = np.load(array_path, allow_pickle=False).astype(np.float64)
    np.save(array_path, array, allow_pickle=False)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"][artifact] = preparation.sha256(array_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        preparation.verify(output)


def test_prepare_rejects_evidence_hash_mismatch(source_plan, tmp_path):
    path, plan = source_plan
    evidence_path = Path(plan["sources"][1]["evidence"][0]["path"])
    evidence_path.write_bytes(b"changed evidence\n")
    output = tmp_path / "invalid_evidence"
    with pytest.raises(ValueError, match="Evidence"):
        preparation.prepare(path, output)
    assert not output.exists()


def test_prepare_rejects_cross_boot_monotonic_origins(source_plan, tmp_path):
    path, plan = source_plan
    source = plan["sources"][2]
    metadata_path = Path(source["metadata"])
    metadata = json.loads(metadata_path.read_text())
    metadata["user_release"]["boot_id"] = "another_boot"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    source["metadata_sha256"] = preparation.sha256(metadata_path)
    path.write_text(json.dumps(plan), encoding="utf-8")
    output = tmp_path / "cross_boot"
    with pytest.raises(ValueError, match="boot"):
        preparation.prepare(path, output)
    assert not output.exists()
