import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from joint_phone_vibration_experiment import METHODS, evaluate_shared_window, summarize_joint


class JointPhoneTests(unittest.TestCase):
    def test_identical_inputs_are_isolated_and_timestamped(self):
        raw=np.ones((128,3),dtype=np.float64)
        def scorer(values):
            np.testing.assert_array_equal(values,np.ones((128,3)))
            values[:]=7  # Mutating one scorer cannot alter another worker's input.
            return 7.0
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows=evaluate_shared_window(raw,{m:scorer for m in METHODS},
                dict(mean=[0,0,0],scale=[1,1,1]),{m:1 for m in METHODS},pool)
        self.assertEqual(len({r['input_sha256'] for r in rows}),1)
        self.assertEqual(len({r['dispatch_ns'] for r in rows}),1)
        for row in rows:
            self.assertEqual(row['prediction'],1)
            self.assertEqual(row['error'],'')
            self.assertLessEqual(row['dispatch_ns'],row['worker_start_ns'])
            self.assertLessEqual(row['worker_start_ns'],row['decision_ns'])
        np.testing.assert_array_equal(raw,np.ones((128,3)))

    def test_invalid_sensor_window_invalidates_all_methods(self):
        def unexpected(_):
            raise AssertionError('Invalid sensor data must not reach scorer')
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows=evaluate_shared_window(np.ones((128,3)),{m:unexpected for m in METHODS},
                dict(mean=[0,0,0],scale=[1,1,1]),{m:1 for m in METHODS},pool,invalid=True)
        self.assertTrue(all(r['prediction'] is None and 'Sensorfenster' in r['error'] for r in rows))

    def test_summary_preserves_ties_and_checks_shared_input(self):
        rows=[dict(window='1',method=m,input_sha256='a',dispatch_ns='10',window_start_ns='11',
                   window_complete_ns='15',prediction='1',error='') for m in METHODS]
        cues=[dict(event='call_requested',monotonic_ns=10),dict(event='end_reported',monotonic_ns=20)]
        result=summarize_joint(rows,cues)
        self.assertEqual(result['shared_windows'],1)
        self.assertIsNone(result['true_detection_delay_ms'])
        self.assertTrue(all(v['first_alarm_window_rank']==1 for v in result['methods'].values()))
        with self.assertRaises(ValueError):
            summarize_joint(rows[:2],cues)
        changed=copy.deepcopy(rows);changed[0]['input_sha256']='different'
        with self.assertRaises(ValueError):
            summarize_joint(changed,cues)


if __name__=='__main__':
    unittest.main()
