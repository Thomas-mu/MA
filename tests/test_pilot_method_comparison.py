"""Offline contracts for the prepared-pilot RMS/IF/TFLite adapter.

All numerical inputs are synthetic. Scorer stand-ins exercise the shared
preprocessing contract without creating models, fitting real data, or accessing
the measurement hardware.
"""

from pathlib import Path
import builtins
import copy
import json
import sys

import numpy as np
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pilot_method_comparison as comparison
from test_prepare_pilot_dataset import source_plan


METHODS = ("rms", "isolation_forest", "tflite_autoencoder")


def synthetic_raw():
    samples = np.arange(128, dtype=np.float64)
    return np.stack(
        (0.700000003 + np.sin(samples * 0.29) * 0.017,
         -0.600000007 + np.cos(samples * 0.31) * 0.023,
         0.120000011 + np.sin(samples * 0.17) * 0.041), axis=1)


def frozen_scaler():
    # Explicit constants, never fitted from any real or synthetic recording.
    return {"mean": [0.0001, -0.0002, 0.0003], "scale": [0.01, 0.02, 0.04]}


def constant_scorers(value=1.0):
    return {method: (lambda window: value) for method in METHODS}


def thresholds(value=1.0):
    return dict.fromkeys(METHODS, value)


def test_raw_centering_preserves_float64_until_mean_is_removed():
    raw = synthetic_raw()
    before = raw.copy()
    expected = (raw - raw.mean(axis=0, keepdims=True)).astype(np.float32)
    result = comparison.center_raw_window(raw)
    assert result.dtype == np.float32
    assert result.shape == (128, 3)
    np.testing.assert_array_equal(result, expected)
    np.testing.assert_array_equal(raw, before)
    # This input makes a prematurely quantized route detectably different.
    quantized = raw.astype(np.float32).astype(np.float64)
    wrong = (quantized - quantized.mean(axis=0, keepdims=True)).astype(np.float32)
    assert not np.array_equal(result, wrong)


@pytest.mark.parametrize("dtype", [np.float32, np.int64, np.float16])
def test_raw_centering_rejects_insufficient_or_ambiguous_precision(dtype):
    with pytest.raises((TypeError, ValueError)):
        comparison.center_raw_window(synthetic_raw().astype(dtype))


@pytest.mark.parametrize("shape", [(127, 3), (129, 3), (128, 2), (1, 128, 3), (384,)])
def test_raw_centering_requires_exact_xyz_window_shape(shape):
    with pytest.raises(ValueError):
        comparison.center_raw_window(np.zeros(shape, dtype=np.float64))


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_raw_centering_rejects_nonfinite_values(value):
    raw = synthetic_raw()
    raw[33, 1] = value
    with pytest.raises(ValueError):
        comparison.center_raw_window(raw)


def test_standardization_preserves_canonical_ac_residual_without_recentering():
    ac = comparison.center_raw_window(synthetic_raw())
    before = ac.copy()
    # Quantized canonical AC need not have an exactly zero mean. Adding an
    # explicit small residual makes a second centering operation observable.
    ac[0, 0] += np.float32(0.0001)
    expected = ac.copy()
    scaler = frozen_scaler()
    expected -= np.asarray(scaler["mean"], dtype=np.float32)
    expected /= np.asarray(scaler["scale"], dtype=np.float32)
    preserved = ac.copy()
    actual = comparison.standardize_ac(ac, scaler)
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(ac, preserved)
    assert actual.dtype == np.float32
    assert not np.array_equal(ac, before)


@pytest.mark.parametrize("shape", [(127, 3), (128, 4), (2, 128, 3), (384,)])
def test_standardization_requires_exact_window_shape(shape):
    with pytest.raises(ValueError):
        comparison.standardize_ac(np.zeros(shape, dtype=np.float32), frozen_scaler())


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_standardization_rejects_nonfinite_ac(value):
    ac = np.zeros((128, 3), dtype=np.float32)
    ac[1, 2] = value
    with pytest.raises(ValueError):
        comparison.standardize_ac(ac, frozen_scaler())


@pytest.mark.parametrize("dtype", [np.float64, np.float16, np.int64])
def test_standardization_requires_the_canonical_float32_ac_representation(dtype):
    with pytest.raises((TypeError, ValueError)):
        comparison.standardize_ac(np.zeros((128, 3), dtype=dtype), frozen_scaler())


@pytest.mark.parametrize("field,value", [("scale", 0.), ("scale", -1.),
                                         ("scale", np.nan), ("scale", np.inf),
                                         ("mean", np.nan), ("mean", np.inf)])
def test_standardization_rejects_invalid_frozen_scaler(field, value):
    scaler = frozen_scaler()
    scaler[field][0] = value
    with pytest.raises(ValueError):
        comparison.standardize_ac(np.zeros((128, 3), dtype=np.float32), scaler)


def test_all_methods_receive_identical_standardized_ac_windows():
    ac = comparison.center_raw_window(synthetic_raw())
    preserved = ac.copy()
    expected = comparison.standardize_ac(ac, frozen_scaler())
    observed = {}

    def make_score(method):
        def score(window):
            observed[method] = window.copy()
            return 1.0
        return score

    result = comparison.score_window(ac, frozen_scaler(),
        {method: make_score(method) for method in METHODS}, thresholds())
    assert set(result) == set(METHODS)
    for method in METHODS:
        np.testing.assert_array_equal(observed[method], expected)
        assert result[method]["score"] == 1.0
        assert result[method]["prediction"] == 0
        assert result[method]["decision"] == "NORMAL"
        assert result[method]["error"] is None
    np.testing.assert_array_equal(ac, preserved)


def test_scorer_mutation_cannot_affect_other_methods_or_input():
    ac = comparison.center_raw_window(synthetic_raw())
    preserved = ac.copy()
    expected = comparison.standardize_ac(ac, frozen_scaler())
    seen = {}

    def make_score(method):
        def score(window):
            seen[method] = window.copy()
            window[:] = np.nan
            return 0.5
        return score

    result = comparison.score_window(ac, frozen_scaler(),
        {method: make_score(method) for method in METHODS}, thresholds())
    for method in METHODS:
        np.testing.assert_array_equal(seen[method], expected)
        assert result[method]["decision"] == "NORMAL"
    np.testing.assert_array_equal(ac, preserved)


@pytest.mark.parametrize("value,prediction,decision", [(0.999, 0, "NORMAL"),
    (1.0, 0, "NORMAL"), (1.001, 1, "ANOMALY")])
def test_frozen_threshold_uses_strict_greater_than(value, prediction, decision):
    result = comparison.score_window(comparison.center_raw_window(synthetic_raw()),
        frozen_scaler(), constant_scorers(value), thresholds())
    for row in result.values():
        assert row["prediction"] == prediction
        assert row["decision"] == decision


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
def test_nonfinite_score_is_invalid_only_for_affected_method(method, bad_value):
    scores = constant_scorers(0.0)
    scores[method] = lambda window: bad_value
    result = comparison.score_window(comparison.center_raw_window(synthetic_raw()),
        frozen_scaler(), scores, thresholds())
    for name, row in result.items():
        if name == method:
            assert row["decision"] == "INVALID"
            assert row["score"] is None
            assert row["prediction"] is None
            assert row["error"]
        else:
            assert row["decision"] == "NORMAL"


@pytest.mark.parametrize("exception", [ValueError, RuntimeError, FloatingPointError])
def test_scorer_failure_does_not_become_normal_or_skip_remaining_methods(exception):
    def broken(window):
        raise exception("synthetic inference failure")
    scores = constant_scorers(0.0)
    scores["rms"] = broken
    result = comparison.score_window(comparison.center_raw_window(synthetic_raw()),
        frozen_scaler(), scores, thresholds())
    assert result["rms"]["decision"] == "INVALID"
    assert result["rms"]["score"] is None
    assert result["rms"]["prediction"] is None
    assert "synthetic inference failure" in result["rms"]["error"]
    assert result["isolation_forest"]["decision"] == "NORMAL"
    assert result["tflite_autoencoder"]["decision"] == "NORMAL"


@pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
def test_nonfinite_threshold_rejected_before_any_scoring(bad_value):
    calls = []
    scores = {method: lambda window: calls.append(1) or 0. for method in METHODS}
    limits = thresholds()
    limits["isolation_forest"] = bad_value
    with pytest.raises(ValueError):
        comparison.score_window(comparison.center_raw_window(synthetic_raw()),
            frozen_scaler(), scores, limits)
    assert calls == []


@pytest.mark.parametrize("mapping_name", ["scorers", "thresholds"])
def test_missing_method_configuration_rejected(mapping_name):
    scores, limits = constant_scorers(), thresholds()
    del (scores if mapping_name == "scorers" else limits)["isolation_forest"]
    with pytest.raises(ValueError):
        comparison.score_window(comparison.center_raw_window(synthetic_raw()),
            frozen_scaler(), scores, limits)


def test_shared_preprocessing_failure_marks_every_method_invalid_without_scoring():
    calls = []
    functions = {method: lambda window: calls.append(1) or 0. for method in METHODS}
    ac = np.zeros((128, 3), dtype=np.float32)
    ac[0, 0] = np.nan
    result = comparison.score_window(ac, frozen_scaler(), functions, thresholds())
    assert calls == []
    for row in result.values():
        assert row["decision"] == "INVALID"
        assert row["score"] is None
        assert row["prediction"] is None
        assert row["error"]


@pytest.fixture
def synthetic_dataset(source_plan, tmp_path):
    plan_path, _ = source_plan
    dataset = tmp_path / "prepared_dataset"
    comparison.preparation.prepare(plan_path, dataset)
    return dataset


def file_hashes(directory):
    return {str(path.relative_to(directory)): comparison.common.sha256(path)
            for path in directory.rglob("*") if path.is_file()}


def test_audit_verifies_all_windows_without_fit_inference_or_hardware(synthetic_dataset, tmp_path, monkeypatch):
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    def forbidden(*args, **kwargs):
        raise AssertionError("Audit must not fit, infer with models, or touch hardware")

    monkeypatch.setattr(StandardScaler, "fit", forbidden)
    monkeypatch.setattr(IsolationForest, "fit", forbidden)
    monkeypatch.setattr(comparison, "train", forbidden)
    monkeypatch.setattr(comparison, "training_payload", forbidden)
    monkeypatch.setattr(comparison, "model_scorers", forbidden)
    monkeypatch.setattr(comparison.common, "scorer", forbidden)
    monkeypatch.setattr(comparison.common, "load_interpreter", forbidden)
    real_import = builtins.__import__

    def checked_import(name, *args, **kwargs):
        if name.split(".")[0] in {"tensorflow", "ai_edge_litert", "smbus", "smbus2",
                                  "gpiod", "gpiozero", "RPi", "fan_pwm", "fan_controller"}:
            forbidden()
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", checked_import)
    preserved = file_hashes(tmp_path)
    output = tmp_path / "audit"
    report = comparison.audit(synthetic_dataset, output)
    assert report["status"] == "adapter_audited_without_training"
    assert report["window_counts"] == {"train": 18, "validation": 9}
    assert report["all_windows_raw_to_ac_exact"] == 27
    for key in ("models_trained", "scaler_fitted", "thresholds_calibrated",
                "real_model_inference_executed", "hardware_access"):
        assert report[key] is False
    assert report["legacy_profile_compatible"] is False
    assert (output / "adapter_audit.json").is_file()
    assert (output / "adapter_source.py").is_file()
    after = file_hashes(tmp_path)
    assert {name: after[name] for name in preserved} == preserved


def test_audit_refuses_existing_output_before_modification(synthetic_dataset, tmp_path):
    output = tmp_path / "audit"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("original audit artifact")
    before = file_hashes(output)
    with pytest.raises(ValueError, match="exists"):
        comparison.audit(synthetic_dataset, output)
    assert file_hashes(output) == before


def test_audit_rejects_changed_canonical_input_before_writing_output(synthetic_dataset, tmp_path):
    target = synthetic_dataset / "train_ac_g.npy"
    values = np.load(target, allow_pickle=False)
    values[0, 0, 0] += 1.0
    np.save(target, values, allow_pickle=False)
    output = tmp_path / "rejected_audit"
    with pytest.raises(ValueError, match="hash mismatch"):
        comparison.audit(synthetic_dataset, output)
    assert not output.exists()


def write_bundle_header(directory, bundle):
    """Update only synthetic fingerprints when testing deeper schema checks."""
    header = directory / "pilot_bundle.json"
    header.write_text(json.dumps(bundle), encoding="utf-8")
    (directory / "pilot_bundle.sha256").write_text(comparison.common.sha256(header) + "\n")


@pytest.fixture
def synthetic_bundle(tmp_path):
    """Schema-only artifact bytes; these are deliberately not loadable models."""
    directory = tmp_path / "synthetic_bundle"
    directory.mkdir()
    for name in ("scaler.joblib", "isolation_forest.joblib", "autoencoder_float32.tflite",
                 "tflite_consistency.json", "adapter_source.py", "common_comparison_source.py",
                 "prepared_manifest.json", "prepared_plan.json"):
        (directory / name).write_text("synthetic metadata test, no model fitting\n")
    (directory / "adapter_source.py").write_bytes(Path(comparison.__file__).read_bytes())
    (directory / "common_comparison_source.py").write_bytes(Path(comparison.common.__file__).read_bytes())
    (directory / "source_ae_threshold.json").write_text(json.dumps({"selected_threshold": 0.3}))
    bundle = {
        "contract": copy.deepcopy(comparison.CONTRACT),
        "status": "ready_development_only", "window_size": 128,
        "dataset_manifest_sha256": comparison.common.sha256(directory / "prepared_manifest.json"),
        "thresholds": {method: {"value": 0.3, "percentile": 99, "source": "SYNTHETIC_TEST_ONLY"}
                       for method in METHODS},
        "scaler": {**frozen_scaler(), "fit_source": "canonical_normal_train_AC_only"},
        "if_parameters": dict(comparison.common.IF_PARAMETERS),
        "artifact_sha256": file_hashes(directory),
    }
    write_bundle_header(directory, bundle)
    return directory, bundle


def test_bundle_loader_checks_metadata_without_loading_any_model(synthetic_bundle, monkeypatch):
    directory, bundle = synthetic_bundle

    def forbidden(*args, **kwargs):
        raise AssertionError("Metadata validation must not load or train models")

    monkeypatch.setattr(comparison, "model_scorers", forbidden)
    monkeypatch.setattr(comparison.common, "scorer", forbidden)
    before = file_hashes(directory)
    assert comparison.load_bundle(directory) == bundle
    assert file_hashes(directory) == before
    assert not (directory / "bundle.json").exists()


def test_bundle_loader_rejects_changed_frozen_header(synthetic_bundle):
    directory, _ = synthetic_bundle
    header = directory / "pilot_bundle.json"
    header.write_text(header.read_text() + "\n")
    with pytest.raises(ValueError, match="fingerprint"):
        comparison.load_bundle(directory)


def test_bundle_loader_rejects_changed_model_bytes(synthetic_bundle):
    directory, _ = synthetic_bundle
    (directory / "autoencoder_float32.tflite").write_bytes(b"changed")
    with pytest.raises(ValueError, match="artifact changed"):
        comparison.load_bundle(directory)


@pytest.mark.parametrize("mutation", ["extra", "removed", "unlisted"])
def test_bundle_loader_rejects_inventory_changes(synthetic_bundle, mutation):
    directory, bundle = synthetic_bundle
    if mutation == "extra":
        (directory / "unlisted.bin").write_bytes(b"not frozen")
    elif mutation == "removed":
        (directory / "scaler.joblib").unlink()
    else:
        del bundle["artifact_sha256"]["scaler.joblib"]
        write_bundle_header(directory, bundle)
    with pytest.raises(ValueError, match="inventory"):
        comparison.load_bundle(directory)


def test_bundle_loader_rejects_missing_required_artifact_even_if_rehashed(synthetic_bundle):
    directory, bundle = synthetic_bundle
    (directory / "scaler.joblib").unlink()
    del bundle["artifact_sha256"]["scaler.joblib"]
    write_bundle_header(directory, bundle)
    with pytest.raises(ValueError, match="required frozen"):
        comparison.load_bundle(directory)


@pytest.mark.parametrize("key,value", [("preprocessing_id", "legacy_raw"),
    ("window_size", 256), ("step_size", 64), ("independent_test", True),
    ("selection_seconds_since_pwm_command", [0, 300])])
def test_bundle_loader_rejects_rehashed_incompatible_preprocessing(synthetic_bundle, key, value):
    directory, bundle = synthetic_bundle
    bundle["contract"][key] = value
    write_bundle_header(directory, bundle)
    with pytest.raises(ValueError, match="contract"):
        comparison.load_bundle(directory)


def test_bundle_loader_rejects_wrong_dataset_anchor(synthetic_bundle):
    directory, bundle = synthetic_bundle
    bundle["dataset_manifest_sha256"] = "a" * 64
    write_bundle_header(directory, bundle)
    with pytest.raises(ValueError, match="anchor mismatch"):
        comparison.load_bundle(directory)


@pytest.mark.parametrize("name", ["adapter_source.py", "common_comparison_source.py"])
def test_bundle_loader_rejects_runtime_code_drift_even_with_valid_artifact_hash(synthetic_bundle, name):
    directory, bundle = synthetic_bundle
    artifact = directory / name
    artifact.write_bytes(artifact.read_bytes() + b"\n# synthetic older runtime version\n")
    bundle["artifact_sha256"][name] = comparison.common.sha256(artifact)
    write_bundle_header(directory, bundle)
    with pytest.raises(ValueError):
        comparison.load_bundle(directory)


def test_bundle_loader_rejects_adjusted_ae_threshold(synthetic_bundle):
    directory, bundle = synthetic_bundle
    bundle["thresholds"]["tflite_autoencoder"]["value"] = 0.7
    write_bundle_header(directory, bundle)
    with pytest.raises(ValueError, match="AE threshold"):
        comparison.load_bundle(directory)


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_bundle_loader_rejects_nonfinite_threshold(synthetic_bundle, value):
    directory, bundle = synthetic_bundle
    bundle["thresholds"]["rms"]["value"] = value
    write_bundle_header(directory, bundle)
    with pytest.raises(ValueError):
        comparison.load_bundle(directory)


def test_bundle_loader_rejects_symlink_escape(synthetic_bundle, tmp_path):
    directory, bundle = synthetic_bundle
    outside = tmp_path / "external_model.bin"
    outside.write_bytes(b"outside frozen bundle")
    artifact = directory / "scaler.joblib"
    artifact.unlink()
    artifact.symlink_to(outside)
    bundle["artifact_sha256"]["scaler.joblib"] = comparison.common.sha256(outside)
    write_bundle_header(directory, bundle)
    with pytest.raises(ValueError, match="escapes bundle"):
        comparison.load_bundle(directory)


def test_loaded_metadata_retains_source_identity_and_supports_common_metrics(synthetic_dataset):
    inputs = comparison.load_inputs(synthetic_dataset)
    frame = inputs["metadata"]["validation"]
    assert frame["recording_id"].nunique() == 1
    assert frame["original_state"].unique().tolist() == ["normal_followup"]
    assert frame["state"].equals(frame["original_state"])
    assert frame["recording_sha256"].equals(frame["source_csv_sha256"])
    source = next(s for s in inputs["manifest"]["sources"] if s["split"] == "validation")
    assert frame["recording"].unique().tolist() == [source["csv"]]
    bundle = {"thresholds": {method: {"value": 1., "source": "SYNTHETIC_TEST_ONLY"}
                             for method in METHODS}, "scaler": frozen_scaler()}
    rows = comparison.dispatch_prepared(inputs["ac"]["validation"], frame.to_dict("records"),
                                         bundle, constant_scorers(0.))
    metrics = comparison.common.quality_report(rows)
    for method in METHODS:
        assert metrics[method]["all"]["attempted_windows"] == 9
        assert metrics[method]["all"]["invalid_windows"] == 0
        assert metrics[method]["all"]["metrics_on_valid_decisions_only"]["tn"] == 9
        assert metrics[method]["all"]["metrics_on_valid_decisions_only"]["recall"] is None
        assert "state:normal_followup" in metrics[method]


def test_replay_keeps_models_scaler_thresholds_and_dataset_frozen(synthetic_dataset, synthetic_bundle,
                                                               tmp_path, monkeypatch):
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    directory, bundle = synthetic_bundle
    target = directory / "prepared_manifest.json"
    target.write_bytes((synthetic_dataset / "manifest.json").read_bytes())
    bundle["dataset_manifest_sha256"] = comparison.common.sha256(target)
    bundle["artifact_sha256"][target.name] = comparison.common.sha256(target)
    write_bundle_header(directory, bundle)

    def forbidden(*args, **kwargs):
        raise AssertionError("Frozen replay must never fit or recalibrate")

    monkeypatch.setattr(StandardScaler, "fit", forbidden)
    monkeypatch.setattr(IsolationForest, "fit", forbidden)
    monkeypatch.setattr(comparison, "training_payload", forbidden)
    monkeypatch.setattr(comparison, "train", forbidden)
    monkeypatch.setattr(comparison.common, "p99", forbidden)
    monkeypatch.setattr(comparison, "model_scorers", lambda *args, **kwargs:
                        (constant_scorers(0.2), dict.fromkeys(METHODS, "synthetic scorer")))
    old_dataset = file_hashes(synthetic_dataset)
    old_bundle = file_hashes(directory)
    output = tmp_path / "replay"
    report = comparison.replay(synthetic_dataset, directory, output)
    assert report["models_or_scaler_fitted"] is False
    assert report["thresholds_recalibrated"] is False
    assert report["evidence_scope"] == "existing_development_validation_replay_not_independent_test"
    assert file_hashes(synthetic_dataset) == old_dataset
    assert file_hashes(directory) == old_bundle
    rows = comparison.pd.read_csv(output / "development_validation_replay.csv")
    assert len(rows) == 27
    assert rows["threshold"].eq(0.3).all()
    assert rows["score"].eq(0.2).all()
    assert rows["decision"].eq("NORMAL").all()
