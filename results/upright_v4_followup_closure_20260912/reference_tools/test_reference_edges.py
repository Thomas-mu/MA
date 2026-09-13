"""All fixtures in this module are SYNTHETIC SOFTWARE TESTS, never measurements."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

import analyze_reference_edges as reference


class SyntheticReferenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="SYNTHETIC_reference_test_")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.metadata = {
            "schema_version": 1, "dataset_kind": "SYNTHETIC",
            "source": "SYNTHETIC unittest generator; no acquired physical data",
            "instrument": "SYNTHETIC ideal test clock; no real instrument",
            "clock_relation": "external_independent",
            "clock_relation_basis": "SYNTHETIC condition for software test only",
            "time_accuracy_s": 0.000001,
            "time_accuracy_basis": "SYNTHETIC assumed value, not a calibrated instrument",
            "capture_integrity_confirmed": True,
            "capture_integrity_evidence": "SYNTHETIC complete generated edge list",
            "channels": {"drdy": {"kind": "adxl_data_ready", "selected_edge": "rising",
                                    "one_edge_per_sample_confirmed": False}},
        }

    def write(self, rows, quality_column=True):
        csv_path = self.root / "SYNTHETIC_edges.csv"
        metadata_path = self.root / "SYNTHETIC_metadata.json"
        with csv_path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["reference_time_s", "channel", "edge"]
                            + (["quality_flag"] if quality_column else []))
            writer.writerows(rows)
        metadata_path.write_text(json.dumps(self.metadata))
        return csv_path, metadata_path

    def evaluate(self, rows, quality_column=True):
        return reference.analyze(*self.write(rows, quality_column))

    def edges(self, hz, cycles=100, channel="drdy", both=False):
        rows = []
        for i in range(cycles):
            rows.append([i / hz, channel, "rising", "ok"])
            if both:
                rows.append([(i + 0.5) / hz, channel, "falling", "ok"])
        return rows

    def test_synthetic_200_hz_and_207_hz(self):
        for rate in (200, 207):
            with self.subTest(rate=rate):
                result = self.evaluate(self.edges(rate))
                self.assertEqual(result["dataset_kind"], "SYNTHETIC")
                self.assertFalse(result["physical_measurement_declared_in_metadata"])
                channel = result["channels"]["drdy"]
                self.assertAlmostEqual(channel["observed_same_direction_edge_frequency_hz"], rate)
                self.assertEqual(channel["selected_edge_count"], 100)
                self.assertEqual(channel["same_direction_intervals"]["count"], 99)
                self.assertIsNone(channel["physical_sample_losses"])

    def test_both_edges_are_never_double_counted(self):
        result = self.evaluate(self.edges(200, both=True))["channels"]["drdy"]
        self.assertEqual(result["all_edge_count"], 200)
        self.assertEqual(result["selected_edge_count"], 100)
        self.assertAlmostEqual(result["observed_same_direction_edge_frequency_hz"], 200)
        self.metadata["channels"]["drdy"]["selected_edge"] = "falling"
        result = self.evaluate(self.edges(207, both=True))["channels"]["drdy"]
        self.assertAlmostEqual(result["observed_same_direction_edge_frequency_hz"], 207)

    def test_tachometer_confirmed_two_ppr_is_synthetic_example(self):
        self.metadata["channels"] = {
            "tach": {"kind": "tachometer", "selected_edge": "rising",
                     "pulses_per_revolution": 2, "ppr_confirmed": True,
                     "ppr_evidence": "SYNTHETIC assumed two PPR; not the actual fan specification"}}
        result = self.evaluate(self.edges(80, channel="tach", both=True))
        self.assertEqual(result["dataset_kind"], "SYNTHETIC")
        self.assertAlmostEqual(result["channels"]["tach"]["rpm_estimate"], 2400)

    def test_unknown_or_unconfirmed_ppr_never_produces_rpm(self):
        for ppr in (None, 2):
            with self.subTest(ppr=ppr):
                self.metadata["channels"] = {
                    "tach": {"kind": "tachometer", "selected_edge": "rising",
                             "pulses_per_revolution": ppr, "ppr_confirmed": False}}
                result = self.evaluate(self.edges(80, channel="tach"))["channels"]["tach"]
                self.assertAlmostEqual(result["observed_same_direction_edge_frequency_hz"], 80)
                self.assertIsNone(result["rpm_estimate"])

    def test_same_time_different_channels_allowed(self):
        self.metadata["channels"]["aux"] = {"kind": "other", "selected_edge": "rising"}
        rows = sorted(self.edges(200) + self.edges(200, channel="aux"), key=lambda row: row[0])
        result = self.evaluate(rows)
        for channel in ("drdy", "aux"):
            self.assertAlmostEqual(result["channels"][channel]["observed_same_direction_edge_frequency_hz"], 200)

    def test_nonmonotone_and_nonfinite_times_rejected(self):
        for rows in ([ [0.01, "drdy", "rising", "ok"], [0, "drdy", "rising", "ok"] ],
                     [ [float("nan"), "drdy", "rising", "ok"] ],
                     [ [float("inf"), "drdy", "rising", "ok"] ]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.evaluate(rows)

    def test_duplicate_same_channel_time_rejected(self):
        with self.assertRaises(ValueError):
            self.evaluate([[0, "drdy", "rising", "ok"], [0, "drdy", "falling", "ok"]])

    def test_cross_channel_reordering_rejected(self):
        self.metadata["channels"]["aux"] = {"kind": "other", "selected_edge": "rising"}
        with self.assertRaises(ValueError):
            self.evaluate([[0.1, "drdy", "rising", "ok"], [0, "aux", "rising", "ok"]])

    def test_output_never_overwritten(self):
        inputs = self.write(self.edges(200))
        output = self.root / "new_output"
        reference.run(*inputs, output)
        original = (output / "analysis.json").read_bytes()
        with self.assertRaises(FileExistsError):
            reference.run(*inputs, output)
        self.assertEqual((output / "analysis.json").read_bytes(), original)

    def test_invalid_input_creates_no_output(self):
        inputs = self.write([[float("nan"), "drdy", "rising", "ok"]])
        output = self.root / "must_remain_absent"
        with self.assertRaises(ValueError):
            reference.run(*inputs, output)
        self.assertFalse(output.exists())

    def test_held_data_ready_is_not_odr(self):
        # SYNTHETIC: held line rises only twice although samples could occur meanwhile.
        result = self.evaluate([[0, "drdy", "rising", "ok"], [1, "drdy", "falling", "ok"],
                                [1.01, "drdy", "rising", "ok"]])["channels"]["drdy"]
        self.assertFalse(result["eligibility"]["independent_sensor_odr_reference_eligible"])
        self.assertIsNone(result["sensor_odr_estimate_hz"])
        self.assertIsNone(result["physical_sample_losses"])

    def test_host_time_or_unknown_accuracy_not_independent_odr_reference(self):
        self.metadata["channels"]["drdy"].update({
            "one_edge_per_sample_confirmed": True,
            "one_edge_per_sample_evidence": "SYNTHETIC explicit ideal one-to-one condition"})
        for relation, accuracy in (("shared_host", 1e-6), ("external_independent", None)):
            with self.subTest(relation=relation, accuracy=accuracy):
                self.metadata.update(clock_relation=relation, time_accuracy_s=accuracy)
                result = self.evaluate(self.edges(200))["channels"]["drdy"]
                self.assertFalse(result["eligibility"]["independent_sensor_odr_reference_eligible"])
                self.assertIsNone(result["sensor_odr_estimate_hz"])

    def test_confirmations_require_evidence(self):
        self.metadata["channels"]["drdy"]["one_edge_per_sample_confirmed"] = True
        with self.assertRaises(ValueError):
            self.evaluate(self.edges(200))

    def test_synthetic_data_never_eligible_as_physical_odr_evidence(self):
        self.metadata["channels"]["drdy"].update({
            "one_edge_per_sample_confirmed": True,
            "one_edge_per_sample_evidence": "SYNTHETIC ideal one-to-one condition"})
        result = self.evaluate(self.edges(207))["channels"]["drdy"]
        self.assertTrue(result["eligibility"]["metadata_odr_conversion_claims_complete"])
        self.assertFalse(result["eligibility"]["independent_sensor_odr_reference_eligible"])
        self.assertIsNone(result["sensor_odr_estimate_hz"])

    def test_flagged_edges_not_bridged(self):
        rows = self.edges(200, cycles=4, both=True)
        rows[1][3] = "gap"  # Even an opposite-direction gap invalidates that interval.
        rows[4][3] = "invalid"
        result = self.evaluate(rows)["channels"]["drdy"]
        self.assertEqual(result["same_direction_intervals"]["count"], 3)
        self.assertEqual(result["quality_ok_contiguous_intervals"]["count"], 0)
        self.assertFalse(result["eligibility"]["all_event_quality_ok"])

    def test_missing_quality_is_explicitly_unknown(self):
        rows = [row[:3] for row in self.edges(200)]
        result = self.evaluate(rows, quality_column=False)["channels"]["drdy"]
        self.assertEqual(result["quality_counts"]["unknown"], 100)
        self.assertEqual(result["quality_ok_contiguous_intervals"]["count"], 0)
        self.assertAlmostEqual(result["observed_same_direction_edge_frequency_hz"], 200)

    def test_unknown_flags_rejected(self):
        with self.assertRaises(ValueError):
            self.evaluate([[0, "drdy", "rising", "overflow_maybe"]])

    def test_zero_edges_not_standstill(self):
        result = self.evaluate([])["channels"]["drdy"]
        self.assertIsNone(result["observed_same_direction_edge_frequency_hz"])
        self.assertFalse(result["mechanical_standstill_confirmed"])

    def test_source_hashes_match(self):
        csv_path, metadata_path = self.write(self.edges(207))
        result = reference.analyze(csv_path, metadata_path)
        self.assertEqual(result["provenance"]["csv_sha256"], reference.sha256(csv_path))
        self.assertEqual(result["provenance"]["metadata_sha256"], reference.sha256(metadata_path))

    def test_nonfinite_metadata_rejected_before_output(self):
        self.metadata["additional_documentation"] = {"bad_value": float("nan")}
        inputs = self.write(self.edges(200))
        output = self.root / "invalid_metadata_output"
        with self.assertRaises(ValueError):
            reference.run(*inputs, output)
        self.assertFalse(output.exists())

    def test_cli_accepts_synthetic_input_and_exclusively_writes_output(self):
        csv_path, metadata_path = self.write(self.edges(207))
        output = self.root / "SYNTHETIC_cli_result"
        command = [sys.executable, reference.__file__, "--csv", str(csv_path),
                   "--metadata", str(metadata_path), "--output", str(output)]
        first = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("SYNTHETIC", first.stdout)
        second = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(second.returncode, 2)
        self.assertIn("Reference import rejected", second.stderr)

    def test_measurement_label_and_mapping_claim_never_verify_physical_odr(self):
        # SYNTHETIC adversarial input: claims MEASUREMENT, but remains generated test data.
        self.metadata["dataset_kind"] = "MEASUREMENT"
        self.metadata["channels"]["drdy"].update({
            "one_edge_per_sample_confirmed": True,
            "one_edge_per_sample_evidence": "SYNTHETIC free-text claim; no mapping file imported"})
        result = self.evaluate(self.edges(207))
        channel = result["channels"]["drdy"]
        self.assertTrue(result["physical_measurement_declared_in_metadata"])
        self.assertFalse(result["software_verified_physical_reference"])
        self.assertFalse(channel["eligibility"]["software_verified_physical_reference"])
        self.assertFalse(channel["eligibility"]["independent_sensor_odr_reference_eligible"])
        self.assertIsNone(channel["sensor_odr_estimate_hz"])
        self.assertAlmostEqual(channel["conditional_sensor_odr_estimate_hz"], 207)
        self.assertEqual(channel["conditional_sensor_odr_estimate_status"],
                         "conditional_on_external_mapping_claim")

    def test_measurement_label_and_ppr_claim_never_verify_physical_rpm(self):
        # SYNTHETIC adversarial input: an untrusted label cannot establish a measurement.
        self.metadata["dataset_kind"] = "MEASUREMENT"
        self.metadata["channels"] = {
            "tach": {"kind": "tachometer", "selected_edge": "rising",
                     "pulses_per_revolution": 2, "ppr_confirmed": True,
                     "ppr_evidence": "SYNTHETIC externally supplied PPR claim"}}
        result = self.evaluate(self.edges(80, channel="tach"))["channels"]["tach"]
        self.assertAlmostEqual(result["rpm_estimate"], 2400)
        self.assertEqual(result["rpm_estimate_status"], "conditional_on_external_ppr_and_capture_claims")
        self.assertFalse(result["eligibility"]["independent_rpm_reference_eligible"])
        self.assertFalse(result["eligibility"]["software_verified_physical_reference"])

    def test_finite_timestamps_with_overflowing_derivatives_rejected_before_output(self):
        cases = {
            "frequency_overflow": [0, 1e-320],
            "difference_overflow": [-1e308, 1e308],
            "median_overflow": [-1.6e308, -1e307, 1.4e308],
        }
        for name, timestamps in cases.items():
            with self.subTest(name=name):
                inputs = self.write([[t, "drdy", "rising", "ok"] for t in timestamps])
                output = self.root / name
                with self.assertRaises(ValueError):
                    reference.run(*inputs, output)
                self.assertFalse(output.exists())

    def test_rpm_arithmetic_overflow_rejected_before_output(self):
        self.metadata["channels"] = {
            "tach": {"kind": "tachometer", "selected_edge": "rising",
                     "pulses_per_revolution": 2, "ppr_confirmed": True,
                     "ppr_evidence": "SYNTHETIC arithmetic boundary test"}}
        inputs = self.write([[0, "tach", "rising", "ok"], [5e-308, "tach", "rising", "ok"]])
        output = self.root / "rpm_overflow"
        with self.assertRaises(ValueError):
            reference.run(*inputs, output)
        self.assertFalse(output.exists())

    def test_cli_rejects_overflow_without_partial_output(self):
        csv_path, metadata_path = self.write([[0, "drdy", "rising", "ok"],
                                             [1e-320, "drdy", "rising", "ok"]])
        output = self.root / "SYNTHETIC_cli_invalid_numeric"
        result = subprocess.run([sys.executable, reference.__file__, "--csv", str(csv_path),
                                 "--metadata", str(metadata_path), "--output", str(output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Reference import rejected", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
