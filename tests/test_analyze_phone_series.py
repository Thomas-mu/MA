"""Auswertungsregeln der zehn Anrufe, ohne Hardware und echte Modelle."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import analyze_phone_series as series


def cue(event, number, seconds):
    return {"event": event, "number": number, "monotonic_ns": int(seconds * 1e9),
            "local_timestamp": "2026-09-20T12:00:00+02:00"}


def decision(index, prediction, start, end, method="rms", **extra):
    return {"window_index": index, "start_sample": (index - 1) * 128 + 1,
            "end_sample": index * 128, "start_ns": int(start * 1e9),
            "end_ns": int(end * 1e9), "prediction": prediction,
            "decision": "INVALID" if prediction is None else "ANOMALY" if prediction else "NORMAL",
            "new_alarm": False, "method": method, **extra}


class SeriesAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def raw_file(self, windows=3, tail=0, bad_flag=None, missing_sample=None):
        path = self.root / "raw.csv"
        fields = ["sample_index", "window_index", "host_monotonic_ns", "host_utc_ns",
                  "x_g", "y_g", "z_g", "gap", "overrun", "saturated"]
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for i in range(windows * 128 + tail):
                if i + 1 == missing_sample:
                    continue
                row = {"sample_index": i + 1, "window_index": i // 128 + 1,
                       "host_monotonic_ns": 1_000_000_000 + i * 5_000_000,
                       "host_utc_ns": 1_700_000_000_000_000_000 + i * 5_000_000,
                       "x_g": i / 1000, "y_g": .1, "z_g": 1.,
                       "gap": 0, "overrun": 0, "saturated": 0}
                if bad_flag and i == 130:
                    row[bad_flag] = 1
                writer.writerow(row)
        return path

    def test_original_group_boundaries_quality_errors_and_tail_retained(self):
        windows, times, xyz = series.read_windows(self.raw_file(tail=17, bad_flag="gap"))
        self.assertEqual([w["sample_count"] for w in windows], [128, 128, 128, 17])
        self.assertEqual([w["valid_raw"] for w in windows], [True, False, True, False])
        self.assertEqual(windows[1]["raw_error"], "gap")
        self.assertEqual(times.shape, (401,))
        self.assertEqual(xyz.shape, (401, 3))

    def test_missing_sample_never_realigns_following_windows(self):
        windows, *_ = series.read_windows(self.raw_file(missing_sample=130))
        self.assertFalse(windows[1]["valid_raw"])
        self.assertEqual(windows[2]["start_sample"], 257)
        self.assertTrue(windows[2]["valid_raw"])

    def test_multiple_markers_and_missing_trials_are_preserved(self):
        trials, issues = series.read_trials([cue("call_requested", 1, 60), cue("end_reported", 1, 68),
                                             cue("call_requested", 2, 98), cue("end_reported", 2, 111)])
        self.assertEqual(len(trials), 10)
        self.assertEqual([t["marker_status"] for t in trials[:3]], ["valid", "valid", "unclear"])
        self.assertEqual(issues, [])
        comparisons = series.compare_trials(trials, [], 0)
        self.assertEqual(len(comparisons), 30)
        self.assertEqual(comparisons[-1]["trial"], 10)
        self.assertIn("missing_call_requested", comparisons[-1]["issues"])

    def test_duplicate_and_overlapping_markers_cannot_produce_primary_ranking(self):
        trials, _ = series.read_trials([cue("call_requested", 1, 60), cue("call_requested", 1, 61),
                                        cue("end_reported", 1, 72), cue("call_requested", 2, 70),
                                        cue("end_reported", 2, 80)])
        results = series.compare_trials(trials, [decision(1, 1, 64, 65)], 0)
        self.assertTrue(all(e["first_alarm_window"] is None for e in results))
        self.assertIn("duplicate_call_requested", trials[0]["issues"])

    def test_boundaries_are_half_open_and_separate(self):
        for bounds, expected in [((9, 10), "boundary"), ((10, 19), "inside"),
                                 ((19, 20), "boundary"), ((20, 21), "outside")]:
            self.assertEqual(series.position({"start_ns": bounds[0], "end_ns": bounds[1]}, 10, 20), expected)

    def test_existing_alarm_is_not_new_and_ties_remain(self):
        trials, _ = series.read_trials([cue("call_requested", 1, 10), cue("end_reported", 1, 20)])
        rows = []
        for method in series.common.METHODS:
            previous = None
            for index, pred, start, end in [(1, 1, 8, 9), (2, 1, 10, 11),
                                          (3, 0, 12, 13), (4, 1, 14, 15)]:
                row = decision(index, pred, start, end, method)
                row["new_alarm"] = series.is_new_alarm(previous, row)
                rows.append(row)
                previous = row
        entries = series.compare_trials(trials, rows, 0, 0, 30_000_000_000)[:3]
        self.assertTrue(all(e["first_alarm_window"] == 2 for e in entries))
        self.assertTrue(all(e["first_alarm_is_new"] is False for e in entries))
        self.assertTrue(all(e["first_alarm_previous_decision"] == "ANOMALY" for e in entries))
        self.assertTrue(all(e["first_new_alarm_window"] == 4 for e in entries))
        self.assertTrue(all(e["first_new_alarm_tie"] and e["first_new_alarm_rank"] == 1 for e in entries))
        self.assertTrue(all(e["first_new_alarm_difference_to_earliest_s"] == 0 for e in entries))

    def test_invalid_or_missing_predecessor_never_claims_new_alarm(self):
        alarm = decision(2, 1, 10, 11)
        for previous in [None, decision(1, None, 8, 9), decision(1, 1, 8, 9),
                         decision(1, 0, 8, 9, end_sample=126), decision(0, 0, 8, 9)]:
            self.assertFalse(series.is_new_alarm(previous, alarm))
        self.assertTrue(series.is_new_alarm(decision(1, 0, 8, 9), alarm))

    def test_boundary_alarm_without_primary_alarm_is_unclear(self):
        trials, _ = series.read_trials([cue("call_requested", 1, 10), cue("end_reported", 1, 20)])
        rows = [decision(1, 1, 9, 11), decision(2, 0, 12, 13)]
        entry = series.compare_trials(trials, rows, 0, 0, 30_000_000_000)[0]
        self.assertEqual(entry["boundary_alarm_windows"], 1)
        self.assertEqual(entry["result"], "unclear_no_primary_alarm")
        self.assertIsNone(entry["first_alarm_window"])

    def test_normal_phases_exclude_warmup_calls_and_keep_real_durations(self):
        trials, _ = series.read_trials([cue("call_requested", 1, 60), cue("end_reported", 1, 69),
                                        cue("call_requested", 2, 99), cue("end_reported", 2, 116)])
        phases = series.normal_intervals(trials, 30_000_000_000, 150_000_000_000)
        self.assertEqual([(name, (end - start) / 1e9) for name, start, end in phases],
                         [("normal_before_trial_1", 30), ("normal_before_trial_2", 30), ("normal_tail", 34)])
        rows = [decision(1, 1, 32, 33), decision(2, 0, 34, 35), decision(3, None, 36, 37)]
        normal = series.summarize_normal(phases, rows, 0, 1_000_000_000, 149_000_000_000)
        self.assertEqual(normal[0]["valid_windows"], 2)
        self.assertEqual(normal[0]["invalid_windows"], 1)
        self.assertEqual(normal[0]["alarm_window_fraction"], .5)
        self.assertEqual(normal[-1]["recorded_duration_s"], 33)

    def test_incomplete_last_call_has_no_assumed_normal_tail(self):
        trials, _ = series.read_trials([cue("call_requested", 1, 60), cue("end_reported", 1, 68),
                                        cue("call_requested", 2, 100)])
        phases = series.normal_intervals(trials, 30_000_000_000, 150_000_000_000)
        self.assertEqual(len(phases), 2)
        self.assertFalse(any(name == "normal_tail" for name, *_ in phases))

    def bundle(self):
        return {"window_size": 128, "step_size": 128, "profile_name": "existing_75pct",
                "artifact_sha256": {}, "scaler": {"mean": [0., 0., 0.], "scale": [1., 1., 1.]},
                "thresholds": {method: {"value": .3, "source": "FROZEN"} for method in series.common.METHODS}}

    def test_identical_windows_thresholds_and_invalids_for_every_method(self):
        windows, *_ = series.read_windows(self.raw_file(tail=7, bad_flag="saturated"))
        seen = {m: [] for m in series.common.METHODS}
        def load(method, *_args, **_kwargs):
            def score(raw):
                seen[method].append(raw.copy())
                return 1
            return score, "test"
        bundle = self.bundle()
        before = json.dumps(bundle, sort_keys=True)
        with patch.object(series.common, "scorer", side_effect=load):
            rows, _ = series.evaluate(windows, bundle, self.root)
        self.assertEqual(len(rows), 12)
        for method in series.common.METHODS:
            np.testing.assert_array_equal(seen[method], seen["rms"])
            self.assertEqual(len(seen[method]), 2)
            self.assertEqual([r["decision"] for r in rows if r["method"] == method], ["ANOMALY", "INVALID", "ANOMALY", "INVALID"])
        self.assertEqual(before, json.dumps(bundle, sort_keys=True))

    def test_model_load_failure_keeps_all_trial_and_window_rows(self):
        windows, *_ = series.read_windows(self.raw_file())
        with patch.object(series.common, "scorer", side_effect=ImportError("runtime unavailable")):
            rows, _ = series.evaluate(windows, self.bundle(), self.root)
        self.assertEqual(len(rows), 9)
        self.assertTrue(all(r["decision"] == "INVALID" for r in rows))
        self.assertTrue(all("model_load_error" in r["error"] for r in rows))

    def prepare_run(self):
        run = self.root / "run"
        run.mkdir()
        self.raw_file().rename(run / "raw.csv")
        (run / "bundle").mkdir()
        series.common.write_json(run / "bundle" / "bundle.json", self.bundle())
        series.common.write_json(run / "config.json", {"trials": 10, "window_size": 128, "step_size": 128,
            "profile_name": "existing_75pct", "warmup_seconds": 30, "normal_seconds": 30,
            "pwm": {"frequency_hz": 25000, "duty_percent": 75}})
        series.common.write_json(run / "started.json", {"start_monotonic_ns": 1_000_000_000})
        series.common.write_json(run / "analysis_rules.json", {"rules": series.RULES})
        series.common.write_json(run / "run.json", {"status": "aborted", "end_monotonic_ns": 3_000_000_000})
        (run / "cues.jsonl").write_text("")
        return run

    def test_end_to_end_archives_sources_preserves_ten_trials_and_refuses_overwrite(self):
        run, output = self.prepare_run(), self.root / "results"
        before = series.common.sha256(run / "raw.csv")
        with patch.object(series.common, "scorer", return_value=(lambda raw: .1, "test")), patch.object(series, "plots"):
            summary = series.analyze(run, output)
        self.assertEqual(summary["trials_planned"], 10)
        with (output / "trial_comparison.csv").open() as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 30)
        self.assertEqual(series.common.sha256(output / "source" / "raw.csv"), before)
        self.assertEqual(series.common.sha256(run / "raw.csv"), before)
        self.assertTrue((output / "analysis_rules.json").exists())
        self.assertTrue((output / "report.md").exists())
        self.assertFalse(summary["live_output_timing_measured"])
        with self.assertRaises(FileExistsError):
            series.analyze(run, output)

    def test_running_capture_and_output_inside_capture_rejected(self):
        run = self.prepare_run()
        with self.assertRaisesRegex(ValueError, "außerhalb"):
            series.analyze(run, run / "results")
        series.common.write_json(run / "status.json", {"state": "recording"})
        with self.assertRaisesRegex(ValueError, "laufende"):
            series.analyze(run, self.root / "results")

    def test_changed_preregistered_rules_rejected(self):
        run = self.prepare_run()
        (run / "analysis_rules.json").write_text(json.dumps({"rules": {"version": 0}}))
        with self.assertRaisesRegex(ValueError, "eingefrorenen Regeln"):
            series.analyze(run, self.root / "results")

    def test_benchmark_equal_work_warmup_varied_order_and_quantiles(self):
        windows, *_ = series.read_windows(self.raw_file(windows=1))
        calls = {method: [] for method in series.common.METHODS}
        def scorer(method, *_args, **_kwargs):
            def score(raw):
                calls[method].append(raw.copy())
                return .1
            return score, "test"
        def benchmark_path(path):
            if path == "/proc/device-tree/model":
                device = unittest.mock.Mock()
                device.exists.return_value = True
                device.read_text.return_value = "Raspberry Pi test double"
                return device
            if path == "/sys/class/thermal/thermal_zone0/temp":
                thermal = unittest.mock.Mock()
                thermal.exists.return_value = True
                thermal.read_text.return_value = "45000"
                return thermal
            return Path(path)
        with patch.object(series, "Path", side_effect=benchmark_path), patch.object(series.common, "scorer", side_effect=scorer):
            rows, summary = series.benchmark_windows(windows, self.bundle(), self.root)
        self.assertEqual(len(rows), 18)
        self.assertEqual(len({tuple(order) for order in summary["orders"]}), 6)
        self.assertFalse(summary["live_reaction_time"])
        for method in series.common.METHODS:
            self.assertEqual(len(calls[method]), 6 * 21)
            np.testing.assert_array_equal(calls[method], calls["rms"])
            self.assertEqual(summary["methods"][method]["measured_windows"], 6)
            self.assertGreaterEqual(summary["methods"][method]["p95_ms"], summary["methods"][method]["median_ms"])


if __name__ == "__main__":
    unittest.main()
