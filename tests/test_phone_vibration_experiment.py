"""Checks for scientific labeling and single-call operator journaling."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from phone_vibration_experiment import mark, summarize


class PhonePilotTests(unittest.TestCase):
    def test_alarm_counts_do_not_become_ground_truth_metrics(self):
        rows = [dict(prediction=prediction, error=error, processing_ms='2',
                     process_rss_bytes=str(2**20))
                for prediction, error in [('1', ''), ('0', ''), ('', 'sensor gap')]]
        result = summarize(rows)
        self.assertEqual(result['alarm_windows'], 1)
        self.assertEqual(result['invalid_windows'], 1)
        self.assertEqual(result['processing_median_ms'], 2)
        for field in ('true_detection_delay_ms', 'detection_rate', 'false_alarm_rate'):
            self.assertIsNone(result[field])

    def test_cues_are_single_call_and_never_physical_onset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with self.assertRaises(ValueError):
                mark(path, 'call_requested', 1, '')
            (path / 'started.json').write_text('{}')
            with self.assertRaises(ValueError):
                mark(path, 'end_reported', 1, '')
            record = mark(path, 'call_requested', 1, '')
            self.assertFalse(record['physical_onset_verified'])
            with self.assertRaises(ValueError):
                mark(path, 'call_requested', 1, '')
            mark(path, 'end_reported', 1, 'Rückmeldung')
            records = [json.loads(line) for line in (path/'cues.jsonl').read_text().splitlines()]
            self.assertEqual(len(records), 2)
            (path/'run.json').write_text('{}')
            with self.assertRaises(ValueError):
                mark(path, 'note', 1, '')


if __name__ == '__main__':
    unittest.main()
