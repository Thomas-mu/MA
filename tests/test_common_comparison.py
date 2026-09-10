"""Methodische Schutzregeln des gemeinsamen Vergleichs, ohne Sensorzugriff."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import common_comparison as comparison


class CommonComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def recording(self, name="recording.csv", labels=None, times=None):
        path = self.root / name
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["timestamp_s", *comparison.AXES, "label"])
            for i in range(9):
                writer.writerow([times[i] if times else i / 200,
                                 i * .01, .1, -1., labels[i] if labels else 0])
        return path

    def test_windowing_never_crosses_recording_and_reports_tail(self):
        path = self.recording()
        values, times, report = comparison.load_recording(path, label=0, state="normal")
        windows, metadata = comparison.make_windows(values, times, 4, 4, report)
        self.assertEqual(windows.shape, (2, 4, 3))
        self.assertEqual([m["start_sample"] for m in metadata], [0, 4])
        self.assertEqual(report["trailing_samples_excluded"], 1)
        self.assertEqual(metadata[1]["end_sample_exclusive"], 8)

    def test_duplicate_timestamp_rejected(self):
        path = self.recording(times=[0, .005, .01, .015, .015, .025, .03, .035, .04])
        with self.assertRaisesRegex(ValueError, "streng"):
            comparison.load_recording(path, label=0, state="normal")

    def test_mixed_state_recording_rejected(self):
        path = self.recording(labels=[0] * 8 + [1])
        with self.assertRaisesRegex(ValueError, "Zustandslabel"):
            comparison.load_recording(path, label=0, state="normal")

    def test_nonfinite_sensor_values_rejected(self):
        path = self.recording()
        path.write_text(path.read_text().replace("-1.0", "nan", 1))
        with self.assertRaisesRegex(ValueError, "nichtendliche"):
            comparison.load_recording(path, label=0, state="normal")

    def test_renamed_duplicate_cannot_cross_train_test_boundary(self):
        path = self.recording("training.csv")
        duplicate = self.root / "independent_claim.csv"
        duplicate.write_text(path.read_text(), newline="")
        _, _, training = comparison.load_recording(path, label=0, state="train")
        _, _, test = comparison.load_recording(duplicate, label=0, state="test")
        self.assertNotEqual(training["sha256"], test["sha256"])
        with self.assertRaisesRegex(ValueError, "sample_content_sha256"):
            comparison.assert_disjoint([training, test])

    def test_scaling_matches_saved_standard_scaler_float32(self):
        rng = np.random.default_rng(21)
        train = rng.normal(size=(100, 3)).astype(np.float32)
        validation = rng.normal(8, 2, size=(128, 3)).astype(np.float32)
        fitted = StandardScaler().fit(train)
        exported = {"mean": fitted.mean_.tolist(), "scale": fitted.scale_.tolist()}
        np.testing.assert_array_equal(comparison.standardize(validation, exported), fitted.transform(validation))
        np.testing.assert_array_equal(fitted.mean_, StandardScaler().fit(train).mean_)

    def test_rms_is_over_all_standardized_axes(self):
        self.assertAlmostEqual(comparison.rms_score(np.array([[0, 3, 4]], dtype=np.float32)), np.sqrt(25 / 3))

    def test_p99_only_given_validation_scores_not_test(self):
        validation = np.arange(101, dtype=float)
        self.assertEqual(comparison.p99(validation), 99.)
        with self.assertRaises(ValueError):
            comparison.p99(np.array([0., np.nan]))

    def test_nonfinite_scores_never_normal(self):
        for score in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(score=score), self.assertRaises(ValueError):
                comparison.finite_score(score, .3)
        with self.assertRaises(ValueError):
            comparison.finite_score(0., float("nan"))
        self.assertEqual(comparison.finite_score(.3, .3), 0)
        self.assertEqual(comparison.finite_score(.31, .3), 1)

    def test_no_anomaly_recall_and_f1_remain_undefined(self):
        metrics = comparison.binary_metrics([0, 0], [0, 0])
        self.assertIsNone(metrics["recall"])
        self.assertIsNone(metrics["precision"])
        self.assertIsNone(metrics["f1"])
        self.assertEqual(metrics["false_positive_rate"], 0.)
        self.assertEqual(comparison.binary_metrics([0, 0], [1, 0])["f1"], 0.)

    def test_invalid_decision_reported_not_silently_excluded(self):
        rows = [dict(method="rms", recording="one", state="normal", label=0,
                     decision="INVALID", prediction=None),
                dict(method="rms", recording="one", state="normal", label=0,
                     decision="NORMAL", prediction=0)]
        report = comparison.quality_report(rows, methods=("rms",))["rms"]["all"]
        self.assertEqual(report["invalid_windows"], 1)
        self.assertEqual(report["valid_decision_fraction"], .5)
        self.assertEqual(report["metrics_on_valid_decisions_only"]["tn"], 1)

    def test_changed_frozen_artifact_rejected(self):
        model = self.root / "model.bin"
        model.write_bytes(b"original")
        comparison.write_json(self.root / "bundle.json", {
            "artifact_sha256": {model.name: comparison.sha256(model)},
            "thresholds": {m: {"value": .2} for m in comparison.METHODS}})
        comparison.load_bundle(self.root)
        model.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "verändert"):
            comparison.load_bundle(self.root)

    def test_legacy_measurement_chain_cannot_be_final_test(self):
        bundle_path = self.root / "bundle"
        bundle_path.mkdir()
        comparison.write_json(bundle_path / "bundle.json", {})
        manifest = {"frozen_bundle_sha256": comparison.sha256(bundle_path / "bundle.json"),
                    "independent_recordings": True, "detection_dependent_fan_shutdown": False}
        manifest_path = self.root / "test.json"
        comparison.write_json(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, "nur --pilot"):
            comparison.test_data(manifest_path, {"measurement_chain_status": "unverified_legacy"}, bundle_path, False)

    def test_test_manifest_must_bind_frozen_bundle(self):
        comparison.write_json(self.root / "bundle.json", {})
        manifest_path = self.root / "manifest.json"
        comparison.write_json(manifest_path, {"frozen_bundle_sha256": "wrong"})
        with self.assertRaisesRegex(ValueError, "Bundle-Hash"):
            comparison.test_data(manifest_path, {}, self.root, True)

    def test_all_methods_get_identical_windows_and_frozen_thresholds(self):
        bundle = {"scaler": {"mean": [0., 0., 0.], "scale": [1., 1., 1.]},
                  "thresholds": {method: {"value": .3, "source": "P99_FROZEN"}
                                 for method in comparison.METHODS}}
        before = json.dumps(bundle, sort_keys=True)
        windows = np.arange(24, dtype=np.float32).reshape(2, 4, 3)
        metadata = [{"window_index": i, "label": 0, "state": "independent", "recording": "test"}
                    for i in range(2)]
        seen = {method: [] for method in comparison.METHODS}
        def fake_loader(method, *_args, **_kwargs):
            def record(window):
                seen[method].append(window.copy())
                return float("nan") if method == "tflite_autoencoder" else 10.
            return record, "test-double"
        with patch.object(comparison, "scorer", side_effect=fake_loader):
            rows, _ = comparison.evaluate_windows(windows, metadata, bundle, self.root, "auto", 1)
        for method in comparison.METHODS:
            np.testing.assert_array_equal(np.stack(seen[method]), windows)
        self.assertEqual(before, json.dumps(bundle, sort_keys=True))
        invalid = [row for row in rows if row["method"] == "tflite_autoencoder"]
        self.assertTrue(all(row["decision"] == "INVALID" and row["prediction"] is None for row in invalid))
        self.assertTrue(all(row["threshold"] == .3 for row in rows))

    def fifo_recording(self, bad_flag=None):
        path = self.root / "fifo.csv"
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp_s", *comparison.AXES,
                                                        "label", "gap", "overrun", "saturated", "sample_index"])
            writer.writeheader()
            for i in range(9):
                row = dict(timestamp_s=i / 200, x_g=.1, y_g=.2, z_g=-1., label=0,
                           gap="False", overrun="0", saturated="false", sample_index=i)
                if bad_flag and i == 8:
                    row[bad_flag] = "True"
                writer.writerow(row)
        return path

    def test_quality_flag_in_discarded_tail_still_rejects_recording(self):
        for flag in ("gap", "overrun", "saturated"):
            path = self.fifo_recording(flag)
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, "zurückgewiesen"):
                comparison.load_recording(path, label=0, state="normal")

    def test_fifo_sidecar_requires_completed_matching_hashed_capture(self):
        path = self.fifo_recording()
        _, _, report = comparison.load_recording(path, label=0, state="normal")
        self.assertTrue(report["quality_flags_present"])
        document = {"csv_sha256": report["sha256"], "status": "completed",
                    "purpose": "test", "label": 0, "state": "normal", "mounting": "M1",
                    "sensor": {"odr_hz": 200, "range_g": 2, "acquisition_mode": "fifo_stream",
                               "register_readback": {"0x2c": "0xb"}}, "detection_controls_fan": False}
        metadata = path.with_suffix(".json")
        comparison.write_json(metadata, document)
        comparison.acquisition_sidecar(path, report, purpose="test", expected_hash=comparison.sha256(metadata))
        self.assertEqual(report["acquisition_sidecar"]["sensor"]["odr_hz"], 200)
        with self.assertRaisesRegex(ValueError, "Sidecar-Hash"):
            comparison.acquisition_sidecar(path, report, purpose="test", expected_hash="changed")
        document["status"] = "interrupted"
        metadata.write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError, "Status"):
            comparison.acquisition_sidecar(path, report, purpose="test")

    def calibration_input(self, *, verified=False, sidecar=True, bind_hash=True,
                          quality_flags=True):
        path = self.fifo_recording() if quality_flags else self.recording()
        sensor = {"odr_hz": 200, "range_g": 2, "acquisition_mode": "fifo_stream",
                  "register_readback": {"0x2c": "0xb"},
                  "measurement_chain_verified": verified}
        entry = {"path": str(path), "filename": path.name,
                 "sha256": comparison.sha256(path), "split": "train"}
        metadata = path.with_suffix(".json")
        if sidecar:
            comparison.write_json(metadata, {
                "csv_sha256": entry["sha256"], "status": "completed",
                "purpose": "training", "label": 0, "state": "normal", "mounting": "M1",
                "sensor": sensor, "detection_controls_fan": False})
            if bind_hash:
                entry["metadata_sha256"] = comparison.sha256(metadata)
        profile = {"status": "ready", "axes": list(comparison.AXES), "sensor": sensor,
                   "window_size": 4, "step_size": 4, "data": {"recordings": [entry]}}
        profile_path = self.root / "profile.json"
        comparison.write_json(profile_path, profile)
        args = SimpleNamespace(profile=str(profile_path), output=str(self.root / "output"),
                               runtime="auto", threads=1)
        return args, metadata, profile_path

    def test_calibration_rejects_changed_sidecar_bound_in_unverified_profile(self):
        args, metadata, _ = self.calibration_input()
        document = comparison.read_json(metadata)
        document["mounting"] = "changed_but_semantically_valid"
        metadata.write_text(json.dumps(document))
        with patch.object(comparison, "assert_disjoint") as next_stage:
            with self.assertRaisesRegex(ValueError, "Profilhash"):
                comparison.calibrate(args)
            next_stage.assert_not_called()
        self.assertFalse(Path(args.output).exists())

    def test_calibration_rejects_missing_bound_sidecar(self):
        args, metadata, _ = self.calibration_input(verified=True)
        metadata.unlink()
        with self.assertRaisesRegex(ValueError, "Sidecar fehlt"):
            comparison.calibrate(args)
        self.assertFalse(Path(args.output).exists())

    def test_verified_calibration_requires_profile_sidecar_hash(self):
        args, _, _ = self.calibration_input(verified=True, bind_hash=False)
        with self.assertRaisesRegex(ValueError, "metadata_sha256"):
            comparison.calibrate(args)

    def test_verified_calibration_rejects_hashed_legacy_capture_without_flags(self):
        args, _, _ = self.calibration_input(verified=True, quality_flags=False)
        with self.assertRaisesRegex(ValueError, "Qualitätsflags"):
            comparison.calibrate(args)

    def test_calibration_checks_matching_sidecar_before_any_fit(self):
        args, _, _ = self.calibration_input(verified=True)
        with patch.object(comparison, "assert_disjoint", side_effect=RuntimeError("stop before fitting")) as checked:
            with self.assertRaisesRegex(RuntimeError, "stop before fitting"):
                comparison.calibrate(args)
        report = checked.call_args.args[0][0]
        self.assertTrue(report["profile_sidecar_hash_verified"])
        self.assertIn("acquisition_sidecar", report)
        self.assertFalse(Path(args.output).exists())

    def test_unverified_legacy_without_sidecar_remains_explorative(self):
        args, _, _ = self.calibration_input(sidecar=False, quality_flags=False)
        with patch.object(comparison, "assert_disjoint", side_effect=RuntimeError("stop before fitting")) as checked:
            with self.assertRaisesRegex(RuntimeError, "stop before fitting"):
                comparison.calibrate(args)
        report = checked.call_args.args[0][0]
        self.assertFalse(report["profile_sidecar_hash_verified"])
        self.assertNotIn("acquisition_sidecar", report)

    def test_unverified_fifo_without_profile_hash_is_not_hash_verified(self):
        args, _, _ = self.calibration_input(bind_hash=False)
        with patch.object(comparison, "assert_disjoint", side_effect=RuntimeError("stop before fitting")) as checked:
            with self.assertRaisesRegex(RuntimeError, "stop before fitting"):
                comparison.calibrate(args)
        report = checked.call_args.args[0][0]
        self.assertFalse(report["profile_sidecar_hash_verified"])
        self.assertIn("acquisition_sidecar", report)

    def test_calibration_rejects_invalid_present_sidecar_hash(self):
        args, _, profile_path = self.calibration_input()
        profile = comparison.read_json(profile_path)
        profile["data"]["recordings"][0]["metadata_sha256"] = False
        profile_path.write_text(json.dumps(profile))
        with self.assertRaisesRegex(ValueError, "ungültiger Sidecar-Hash"):
            comparison.calibrate(args)

    def test_latency_journal_requires_measurement_end_and_retains_every_value(self):
        timings = comparison.TimingJournal(self.root / "timings.bin")
        for i in range(1000):
            timings.add(float(i))
        self.assertEqual(timings.count, 1000)
        with self.assertRaisesRegex(ValueError, "Messende"):
            timings.read_after_measurement()
        timings.close()
        values = timings.read_after_measurement()
        np.testing.assert_array_equal(values, np.arange(1000))
        self.assertEqual(timings.path.stat().st_size, 8000)
        self.assertEqual(comparison.p99(values), 989.01)


if __name__ == "__main__":
    unittest.main()
