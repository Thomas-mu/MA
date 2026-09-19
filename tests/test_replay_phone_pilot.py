"""Offline replay preserves window identity and honest ranking semantics."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from replay_phone_pilot import assign_ranks, extract_windows, phase_of


class ReplayTests(unittest.TestCase):
    def test_equal_windows_are_tied_and_no_alarm_has_no_rank(self):
        entries = {key: {'first_alarm_window_between_cues': index}
                   for key, index in [('a', 9), ('b', 10), ('c', 10), ('none', None)]}
        assign_ranks(entries)
        self.assertEqual([e['first_alarm_window_rank'] for e in entries.values()], [1, 2, 2, None])

    def test_boundary_windows_are_not_in_event_phase(self):
        for bounds, expected in [((1, 9), 'pre_cue'), ((9, 11), 'straddling'),
                                 ((10, 20), 'between_cues'), ((19, 21), 'straddling'), ((20, 22), 'post_cue')]:
            self.assertEqual(phase_of(dict(window_start_ns=bounds[0], window_complete_ns=bounds[1]), 10, 20), expected)

    def test_alignment_quality_and_partial_window(self):
        raw = [dict(window_index=1, host_monotonic_ns=n, x_g='0', y_g='1', z_g='2',
                    gap='0', overrun='0', saturated='0') for n in (10, 20)]
        raw.append(dict(raw[-1], window_index=2, host_monotonic_ns=30))
        decisions = [dict(window=1, window_start_ns=10, window_complete_ns=20, prediction='0', error='')]
        windows, partial = extract_windows(raw, decisions, 2)
        self.assertEqual(windows[0].shape, (2, 3))
        self.assertEqual(partial, 1)
        raw[0]['host_monotonic_ns'] = 11
        with self.assertRaises(ValueError):
            extract_windows(raw, decisions, 2)
        raw[0]['host_monotonic_ns'] = 10
        raw[0]['gap'] = '1'
        with self.assertRaises(ValueError):
            extract_windows(raw, decisions, 2)


if __name__ == '__main__':
    unittest.main()
