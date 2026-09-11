"""Offline orchestration tests; every fitting/runtime dependency is a stand-in.

No real scaler, forest, neural network, TFLite runtime, or hardware is used.
Dummy model bytes and synthetic source journals exist only below tmp_path.
"""

from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pilot_method_comparison as comparison
from test_prepare_pilot_dataset import source_plan  # noqa: F401; shared synthetic fixture


@pytest.fixture
def prepared_dataset(source_plan, tmp_path):
    path, _ = source_plan
    directory = tmp_path / "prepared"
    comparison.preparation.prepare(path, directory)
    return directory


@pytest.fixture
def stand_ins(monkeypatch):
    calls = SimpleNamespace(scaler_fit=[], forest_fit=[], stage=[], scorer_inputs={},
                            stage_error=None, runtime_case="matching")

    class RecordingScaler:
        """Records routing and uses fixed constants; estimates no parameters."""

        def fit(self, values):
            calls.scaler_fit.append(values.copy())
            self.mean_ = np.array([0.0001, -0.0002, 0.0003], dtype=np.float64)
            self.scale_ = np.array([0.01, 0.02, 0.04], dtype=np.float64)
            self.n_samples_seen_ = len(values)
            return self

        def transform(self, values):
            result = values.copy()
            result -= self.mean_.astype(result.dtype)
            result /= self.scale_.astype(result.dtype)
            return result

    class RecordingForest:
        def __init__(self, **parameters):
            assert parameters == comparison.common.IF_PARAMETERS

        def fit(self, values):
            calls.forest_fit.append(values.copy())
            return self

    preprocessing = ModuleType("sklearn.preprocessing")
    preprocessing.StandardScaler = RecordingScaler
    ensemble = ModuleType("sklearn.ensemble")
    ensemble.IsolationForest = RecordingForest
    sklearn = ModuleType("sklearn")
    sklearn.preprocessing, sklearn.ensemble = preprocessing, ensemble
    joblib = ModuleType("joblib")
    joblib.dump = lambda value, path: Path(path).write_bytes(b"dummy forest; not a model")
    calibration = ModuleType("calibrate_and_train")

    def fake_stage(directory, payload, config):
        calls.stage.append(payload)
        if calls.stage_error is not None:
            raise calls.stage_error
        models, results = directory / "models", directory / "results"
        models.mkdir(parents=True)
        results.mkdir()
        (models / "scaler.joblib").write_bytes(b"dummy scaler; fixed test constants")
        (models / "autoencoder_float32.tflite").write_bytes(b"dummy model; never interpreted")
        # Deliberately differ slightly from runtime P99 so a silent recalibration
        # would be observable while the legitimate tolerance remains satisfied.
        threshold = 0.20002
        consistency = {"acceptance_limits": {"maximum_absolute_mse_difference": 0.0001}}
        comparison.common.write_json(models / "threshold.json", {"selected_threshold": threshold})
        comparison.common.write_json(results / "tflite_consistency.json", consistency)
        pd.DataFrame({"reconstruction_error_mse": np.full(len(payload["features"]["validation"]), threshold)}).to_csv(
            results / "validation_reconstruction_errors.csv", index=False)
        return {"threshold": threshold, "consistency": consistency}

    calibration.write_training_stage = fake_stage
    for name, module in (("sklearn", sklearn), ("sklearn.preprocessing", preprocessing),
                         ("sklearn.ensemble", ensemble), ("joblib", joblib),
                         ("calibrate_and_train", calibration)):
        monkeypatch.setitem(sys.modules, name, module)

    def fake_scorers(bundle, directory, runtime="auto", threads=1):
        functions = {}
        for method in comparison.METHODS:
            def score(window, method=method):
                calls.scorer_inputs.setdefault(method, []).append(window.copy())
                if method == "tflite_autoencoder":
                    return {"matching": 0.2, "mse_mismatch": 0.3,
                            "decision_mismatch": 0.20004}[calls.runtime_case]
                return 0.4 if method == "rms" else 0.6
            functions[method] = score
        return functions, dict.fromkeys(comparison.METHODS, "synthetic_standin")

    monkeypatch.setattr(comparison, "model_scorers", fake_scorers)
    monkeypatch.setattr(comparison.common, "provenance", lambda: {"synthetic_test_only": True})
    return calls


def test_training_payload_fits_only_training_and_preserves_split_features(prepared_dataset, stand_ins):
    inputs = comparison.load_inputs(prepared_dataset)
    # Give validation an unmistakable sentinel; this direct payload test does
    # not mutate any on-disk array or bypass verification in train/replay.
    inputs["ac"]["validation"] = inputs["ac"]["validation"] + np.float32(100)
    before = {split: values.copy() for split, values in inputs["ac"].items()}
    payload, document = comparison.training_payload(inputs)

    assert len(stand_ins.scaler_fit) == 1
    np.testing.assert_array_equal(stand_ins.scaler_fit[0], before["train"].reshape(-1, 3))
    assert np.max(stand_ins.scaler_fit[0]) < 1
    assert document["fit_samples"] == len(before["train"]) * 128
    assert document["fit_source"] == "canonical_normal_train_AC_only"
    assert payload["manifest"]["split_level"] == "whole_recording"
    assert not set(payload["manifest"]["train_files"]) & set(payload["manifest"]["validation_files"])
    for split, original in before.items():
        expected = np.stack([comparison.standardize_ac(window, document) for window in original])
        np.testing.assert_array_equal(payload["features"][split], expected)
        np.testing.assert_array_equal(inputs["ac"][split], original)
    assert stand_ins.forest_fit == []
    assert stand_ins.stage == []


def test_existing_training_output_is_refused_before_loading_or_fitting(tmp_path, monkeypatch, stand_ins):
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_bytes(b"untouched")
    monkeypatch.setattr(comparison, "load_inputs", lambda _: pytest.fail("Input load before output guard"))
    with pytest.raises(ValueError, match="no overwrite"):
        comparison.train(tmp_path / "missing_dataset", output)
    assert sentinel.read_bytes() == b"untouched"
    assert list(output.iterdir()) == [sentinel]
    assert stand_ins.scaler_fit == stand_ins.forest_fit == stand_ins.stage == []


@pytest.mark.parametrize("error", [RuntimeError("injected stage failure"), KeyboardInterrupt("injected stop")])
def test_failed_stage_is_journaled_without_ready_bundle(prepared_dataset, tmp_path, stand_ins, error):
    stand_ins.stage_error = error
    output = tmp_path / "failed_training"
    with pytest.raises(type(error), match="injected"):
        comparison.train(prepared_dataset, output)
    failure = comparison.common.read_json(output / "training_failed.json")
    assert failure["status"] == "failed_no_automatic_restart"
    assert failure["error_type"] == type(error).__name__
    assert not (output / "training_completed.json").exists()
    assert not (output / "frozen" / "pilot_bundle.json").exists()
    assert len(stand_ins.scaler_fit) == len(stand_ins.stage) == 1
    assert stand_ins.forest_fit == []


@pytest.mark.parametrize("runtime_case, message", [
    ("mse_mismatch", "differs from frozen Keras errors"),
    ("decision_mismatch", "changes frozen decisions"),
])
def test_runtime_mse_or_decision_mismatch_never_commits_ready_bundle(
        prepared_dataset, tmp_path, stand_ins, runtime_case, message):
    stand_ins.runtime_case = runtime_case
    output = tmp_path / runtime_case
    with pytest.raises(ValueError, match=message):
        comparison.train(prepared_dataset, output)
    assert (output / "training_failed.json").exists()
    assert not (output / "training_completed.json").exists()
    assert not (output / "frozen" / "pilot_bundle.json").exists()
    assert not (output / "frozen" / "pilot_bundle.sha256").exists()


def test_mock_stage_freezes_shared_features_and_replay_never_refits(prepared_dataset, tmp_path, stand_ins):
    inputs = comparison.load_inputs(prepared_dataset)
    output = tmp_path / "mock_training"
    bundle = comparison.train(prepared_dataset, output)
    assert bundle["status"] == "ready_development_only"
    assert len(stand_ins.scaler_fit) == len(stand_ins.forest_fit) == len(stand_ins.stage) == 1
    stage = stand_ins.stage[0]
    np.testing.assert_array_equal(stand_ins.forest_fit[0], stage["features"]["train"].reshape(len(inputs["ac"]["train"]), -1))
    for method in comparison.METHODS:
        observed = np.stack(stand_ins.scorer_inputs[method])
        expected = stage["features"]["validation"]
        # Once for calibration, then once for the shared dispatch diagnostics.
        np.testing.assert_array_equal(observed, np.concatenate([expected, expected]))
    frozen = output / "frozen"
    anchor = comparison.common.sha256(frozen / "pilot_bundle.json")
    ae = bundle["thresholds"]["tflite_autoencoder"]
    assert ae == {"value": 0.20002, "percentile": 99, "source": "FROZEN_KERAS_NORMAL_VALIDATION_P99"}
    assert ae["value"] != 0.2  # Runtime P99; using it would silently change threshold.
    assert bundle["ae_runtime_check"]["threshold_recalibrated"] is False

    report = comparison.replay(prepared_dataset, frozen, tmp_path / "mock_replay")
    assert len(stand_ins.scaler_fit) == len(stand_ins.forest_fit) == len(stand_ins.stage) == 1
    assert report["models_or_scaler_fitted"] is False
    assert report["thresholds_recalibrated"] is False
    assert report["evidence_scope"] == "existing_development_validation_replay_not_independent_test"
    assert comparison.common.sha256(frozen / "pilot_bundle.json") == anchor
    replay = pd.read_csv(tmp_path / "mock_replay" / "development_validation_replay.csv")
    ae_rows = replay.loc[replay["method"] == "tflite_autoencoder"]
    assert set(ae_rows["threshold"]) == {0.20002}
    assert set(ae_rows["threshold_source"]) == {"FROZEN_KERAS_NORMAL_VALIDATION_P99"}
    assert set(ae_rows["decision"]) == {"NORMAL"}
    assert not (output / "training_failed.json").exists()


def test_completion_journal_failure_revokes_ready_markers_and_cannot_retry(
        prepared_dataset, tmp_path, monkeypatch, stand_ins):
    output = tmp_path / "failed_completion"
    original_write = comparison.common.write_json

    def fail_completion(path, document):
        if Path(path).name == "training_completed.json":
            raise OSError("injected completion journal failure")
        return original_write(path, document)

    monkeypatch.setattr(comparison.common, "write_json", fail_completion)
    with pytest.raises(OSError, match="injected completion"):
        comparison.train(prepared_dataset, output)
    frozen = output / "frozen"
    assert (output / "training_failed.json").exists()
    assert not (frozen / "pilot_bundle.json").exists()
    assert not (frozen / "pilot_bundle.sha256").exists()
    assert (frozen / "uncommitted_pilot_bundle.json").exists()
    assert (frozen / "uncommitted_pilot_bundle.sha256").exists()
    # Retain evidence while making even an explicit repeated invocation fail
    # at the output guard, before any additional stand-in fit is reached.
    with pytest.raises(ValueError, match="no overwrite"):
        comparison.train(prepared_dataset, output)
    assert len(stand_ins.scaler_fit) == len(stand_ins.forest_fit) == len(stand_ins.stage) == 1
    with pytest.raises(ValueError):
        comparison.load_bundle(frozen)
