"""Hardware-free regressions for the persistent ten-call recording protocol."""
import csv
import fcntl
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import phone_series_experiment as experiment


NS = 1_000_000_000
BUNDLE = dict(profile_name='standlauf_pwm75_200hz', sampling_rate_hz=200,
              window_size=128, step_size=128, artifact_sha256={'model': 'frozen'},
              thresholds={'rms': .2, 'isolation_forest': .3, 'tflite_autoencoder': .4})
READBACK = dict(pwm_configuration=dict(period_ns=40000, duty_cycle_ns=30000,
    enable=1, configured_frequency_hz=25000, configured_duty_percent=75),
    mechanical_state='not_measured')


def write_json(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def cue(event, number, seconds):
    return dict(event=event, number=number, monotonic_ns=int(seconds * NS))


class FakeFan:
    def __init__(self, operations=None, fail_verify=None):
        self.operations = [] if operations is None else operations
        self.fail_verify = fail_verify
        self.verify_calls = 0
        self.closed = False

    def __enter__(self):
        self.operations.append('fan_enter')
        return self

    def __exit__(self, *args):
        self.operations.append('fan_close')
        self.closed = True

    def read_state(self):
        self.operations.append('read_before')
        return READBACK

    def set_percent(self, percent):
        self.operations.append(('set', percent))
        return READBACK

    def verify(self, percent):
        self.operations.append(('verify', percent))
        self.verify_calls += 1
        if self.verify_calls == self.fail_verify:
            raise RuntimeError('PWM readback differs from requested 75 percent / 25 kHz')
        return READBACK


class RecordingFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.run = Path(self.temporary.name) / 'recording'
        self.run.mkdir()
        (self.run / 'bundle').mkdir()
        write_json(self.run / 'bundle/bundle.json', BUNDLE)
        (self.run / 'source').mkdir()
        self.source = self.run / 'source/frozen.py'
        self.source.write_text('# frozen source\n')
        self.plan = dict(profile_name=BUNDLE['profile_name'], sampling_rate_hz=200,
            window_size=128, step_size=128, trials=10, warmup_seconds=30,
            normal_seconds=30, maximum_duration_seconds=None,
            pwm=dict(percent=75, frequency_hz=25000, period_ns=40000,
                     duty_cycle_ns=30000, enable=1, hold_all_phases=True),
            bundle_sha256=experiment.common.sha256(self.run / 'bundle/bundle.json'),
            source_sha256={'frozen.py': experiment.common.sha256(self.source)})
        write_json(self.run / 'plan.json', self.plan)
        (self.run / 'cues.jsonl').touch()

    def current_status(self, now_ns, *, last_sample_ns=None, state='recording'):
        last_sample_ns = now_ns if last_sample_ns is None else last_sample_ns
        value = dict(state=state, pid=os.getpid(), heartbeat_monotonic_ns=now_ns,
            start_monotonic_ns=NS, normal_start_monotonic_ns=31 * NS,
            last_sample_monotonic_ns=last_sample_ns,
            last_sample_age_seconds=(now_ns - last_sample_ns) / NS)
        write_json(self.run / 'status.json', value)
        return value

    def at(self, seconds, function, *args):
        with patch.object(experiment.time, 'monotonic_ns', return_value=int(seconds * NS)):
            return function(self.run, *args)

    def fake_sensor(self, reader=None, operations=None):
        operations = [] if operations is None else operations
        bus = SimpleNamespace(close=Mock())
        def connect(**kwargs):
            operations.append('sensor_connect')
            return bus
        sensor = SimpleNamespace(connect=Mock(side_effect=connect),
            sensor_configuration=Mock(return_value={'odr_hz': 200, 'test_only': True}),
            reset_fifo=Mock(side_effect=lambda bus: operations.append('reset_fifo')),
            read_fresh_sample=Mock(side_effect=reader))
        return sensor, bus

    def capture(self, sensor, fan):
        with patch.object(experiment.common, 'load_bundle', return_value=BUNDLE):
            return experiment.capture(self.run, sensor_module=sensor,
                                      fan_factory=lambda **kwargs: fan)


class CueProtocolTests(RecordingFixture):
    def test_ten_pairs_with_variable_call_lengths_and_normal_intervals(self):
        next_start = 61
        for number in range(1, 11):
            self.current_status(next_start * NS)
            start = self.at(next_start, experiment.mark, 'call_requested', number)
            duration = number * 3 + 1
            self.current_status((next_start + duration) * NS)
            end = self.at(next_start + duration, experiment.mark, 'end_reported', number)
            self.assertEqual(end['monotonic_ns'] - start['monotonic_ns'], duration * NS)
            self.assertFalse(start['physical_onset_verified'])
            self.assertIn('local_timestamp', start)
            self.assertIn('utc_ns', start)
            next_start += duration + 30
        records = experiment.read_cues(self.run)
        self.assertEqual(experiment.validate_cues(records), (10, None))
        self.assertEqual(len(records), 20)
        self.current_status(next_start * NS)
        with self.assertRaises(ValueError):
            self.at(next_start, experiment.mark, 'call_requested', 11)
        self.assertEqual(experiment.read_cues(self.run), records)

    def test_first_call_requires_run_in_and_thirty_recorded_normal_seconds(self):
        for seconds, latest in ((30, 30), (60.999, 60.999), (61, 60.999)):
            with self.subTest(seconds=seconds, latest=latest):
                self.current_status(int(seconds * NS), last_sample_ns=int(latest * NS))
                with self.assertRaisesRegex(ValueError, '30 Sekunden'):
                    self.at(seconds, experiment.mark, 'call_requested', 1)
        self.current_status(61 * NS)
        self.at(61, experiment.mark, 'call_requested', 1)

    def test_next_call_requires_thirty_seconds_after_end_report(self):
        experiment.append_cue(self.run, cue('call_requested', 1, 61))
        experiment.append_cue(self.run, cue('end_reported', 1, 77))
        self.current_status(106 * NS)
        with self.assertRaisesRegex(ValueError, '30 Sekunden'):
            self.at(106, experiment.mark, 'call_requested', 2)
        self.current_status(107 * NS)
        self.at(107, experiment.mark, 'call_requested', 2)

    def test_invalid_markers_do_not_append_or_rewrite_existing_cues(self):
        invalid = [('end_reported', 1), ('call_requested', 0), ('call_requested', 2),
                   ('unknown_event', 1)]
        self.current_status(61 * NS)
        for event, number in invalid:
            with self.subTest(event=event, number=number), self.assertRaises(ValueError):
                self.at(61, experiment.mark, event, number)
        self.assertEqual(experiment.read_cues(self.run), [])
        self.at(61, experiment.mark, 'call_requested', 1)
        original = (self.run / 'cues.jsonl').read_bytes()
        self.current_status(62 * NS)
        for event, number in [('call_requested', 1), ('call_requested', 2), ('end_reported', 2)]:
            with self.subTest(event=event, number=number), self.assertRaises(ValueError):
                self.at(62, experiment.mark, event, number)
            self.assertEqual((self.run / 'cues.jsonl').read_bytes(), original)

    def test_validate_rejects_gaps_duplicates_reversed_and_nonmonotonic_pairs(self):
        valid_start = cue('call_requested', 1, 10)
        valid_end = cue('end_reported', 1, 20)
        invalid = [[valid_end], [cue('call_requested', 2, 10)],
            [valid_start, cue('call_requested', 1, 11)],
            [valid_start, cue('end_reported', 2, 20)],
            [valid_start, cue('end_reported', 1, 10)],
            [valid_start, cue('end_reported', 1, 9)],
            [valid_start, valid_end, cue('call_requested', 3, 50)],
            [valid_start, valid_end, cue('end_reported', 1, 21)],
            [cue('arbitrary', 1, 10)]]
        for records in invalid:
            with self.subTest(records=records), self.assertRaises(ValueError):
                experiment.validate_cues(records)

    def test_unfinished_trial_remains_visible(self):
        records = [cue('call_requested', 1, 10), cue('end_reported', 1, 15),
                   cue('call_requested', 2, 50)]
        self.assertEqual(experiment.validate_cues(records), (1, 2))

    def test_status_requires_live_process_fresh_samples_and_no_stop_or_finish(self):
        self.current_status(100 * NS)
        self.assertTrue(experiment.status(self.run, now_ns=100 * NS)['healthy'])
        self.assertFalse(experiment.status(self.run, now_ns=104 * NS)['healthy'])
        self.assertFalse(experiment.status(self.run, now_ns=106 * NS)['healthy'])
        with patch.object(experiment.os, 'kill', side_effect=ProcessLookupError):
            self.assertFalse(experiment.status(self.run, now_ns=100 * NS)['healthy'])
        for terminal_file in ('stop.request.json', 'run.json'):
            path = self.run / terminal_file
            path.write_text('{}')
            self.assertFalse(experiment.status(self.run, now_ns=100 * NS)['healthy'])
            with self.assertRaises(ValueError):
                self.at(100, experiment.mark, 'call_requested', 1)
            path.unlink()

    def test_stop_request_is_persistent_and_does_not_change_fan(self):
        self.current_status(100 * NS)
        result = self.at(100, experiment.request_stop, 'Operator stop')
        self.assertTrue(result['stop_requested'])
        stored = experiment.common.read_json(self.run / 'stop.request.json')
        self.assertEqual(stored['note'], 'Operator stop')
        self.assertEqual(stored['monotonic_ns'], 100 * NS)
        self.assertFalse(experiment.status(self.run, now_ns=100 * NS)['healthy'])
        write_json(self.run / 'run.json', {'status': 'aborted'})
        with self.assertRaises(ValueError):
            experiment.request_stop(self.run)


class CaptureTests(RecordingFixture):
    def test_signal_stop_preserves_partial_window_and_verified_pwm_configuration(self):
        operations = []
        count = 0
        def read(bus, *, stop_event):
            nonlocal count
            count += 1
            self.assertTrue((self.run / 'config.json').exists())
            if count == 131:
                # Exercise the actual SIGTERM handler installed by capture.
                signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
            return SimpleNamespace(xyz_g=(count / 1000, 0., 1.),
                monotonic_ns=time.monotonic_ns(), gap=False, overrun=False,
                saturated=False, sample_index=count)
        sensor, bus = self.fake_sensor(read, operations)
        fan = FakeFan(operations)
        prior_sigterm = signal.getsignal(signal.SIGTERM)
        report = self.capture(sensor, fan)
        self.assertEqual(report['status'], 'aborted')
        self.assertEqual(report['stop_reason'], 'signal')
        self.assertEqual(report['acquisition']['samples_captured'], 131)
        self.assertEqual(report['acquisition']['partial_samples_saved'], 3)
        with (self.run / 'raw.csv').open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 131)
        self.assertEqual(rows[-1]['sample_index'], '131')
        self.assertEqual(rows[-1]['window_index'], '2')
        self.assertEqual(json.loads(rows[-1]['diagnostics_json'])['sensor_sample_index'], 131)
        config = experiment.common.read_json(self.run / 'config.json')
        self.assertEqual(config['pwm_readback'], READBACK)
        self.assertEqual(config['pwm']['percent'], 75)
        self.assertEqual(config['pwm']['frequency_hz'], 25000)
        self.assertEqual(config['profile_name'], 'standlauf_pwm75_200hz')
        self.assertEqual(operations.count(('set', 75)), 1)
        self.assertLess(operations.index('sensor_connect'), operations.index(('set', 75)))
        self.assertLess(operations.index(('verify', 75)), operations.index('reset_fifo'))
        self.assertTrue(fan.closed)
        bus.close.assert_called_once()
        self.assertIs(signal.getsignal(signal.SIGTERM), prior_sigterm)
        saved = experiment.common.read_json(self.run / 'run.json')
        self.assertEqual(saved['file_sha256']['raw.csv'], experiment.common.sha256(self.run / 'raw.csv'))
        self.assertFalse(experiment.status(self.run)['healthy'])

    def test_operator_stop_is_consumed_and_partial_samples_saved(self):
        count = 0
        def read(bus, *, stop_event):
            nonlocal count
            count += 1
            if count > 131:
                stop_event.wait(3)
                return None
            if count == 131:
                experiment.request_stop(self.run, 'test operator stop')
            return SimpleNamespace(xyz_g=(0., 0., 1.), monotonic_ns=time.monotonic_ns(),
                gap=False, overrun=False, saturated=False, sample_index=count)
        sensor, bus = self.fake_sensor(read)
        fan = FakeFan()
        report = self.capture(sensor, fan)
        self.assertEqual(report['status'], 'aborted')
        self.assertEqual(report['stop_reason'], 'operator_request')
        self.assertEqual(report['acquisition']['partial_samples_saved'], 3)
        self.assertEqual(report['acquisition']['samples_captured'], 131)
        self.assertEqual(fan.operations.count(('set', 75)), 1)
        bus.close.assert_called_once()

    def test_sensor_error_preserves_samples_and_marks_run_failed(self):
        count = 0
        def read(bus, *, stop_event):
            nonlocal count
            count += 1
            if count == 4:
                raise OSError('synthetic I2C error')
            return SimpleNamespace(xyz_g=(0., 0., 1.), monotonic_ns=time.monotonic_ns(),
                gap=False, overrun=False, saturated=False, sample_index=count)
        sensor, bus = self.fake_sensor(read)
        fan = FakeFan()
        with self.assertRaisesRegex(RuntimeError, 'synthetic I2C error'):
            self.capture(sensor, fan)
        report = experiment.common.read_json(self.run / 'run.json')
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['acquisition']['samples_captured'], 3)
        self.assertEqual(report['acquisition']['partial_samples_saved'], 3)
        self.assertEqual(fan.operations.count(('set', 75)), 1)
        bus.close.assert_called_once()

    def test_initial_pwm_mismatch_prevents_sensor_acquisition(self):
        sensor, bus = self.fake_sensor()
        fan = FakeFan(fail_verify=1)
        with self.assertRaisesRegex(RuntimeError, 'PWM readback differs'):
            self.capture(sensor, fan)
        sensor.read_fresh_sample.assert_not_called()
        sensor.reset_fifo.assert_not_called()
        self.assertFalse((self.run / 'raw.csv').exists())
        self.assertFalse((self.run / 'config.json').exists())
        self.assertEqual(experiment.common.read_json(self.run / 'run.json')['status'], 'failed')
        bus.close.assert_called_once()
        self.assertEqual(fan.operations.count(('set', 75)), 1)

    def test_preexisting_started_config_or_report_prevents_hardware_access_and_overwrite(self):
        for filename in ('started.json', 'config.json', 'run.json'):
            with self.subTest(filename=filename):
                path = self.run / filename
                path.write_text('{"original": true}')
                sensor, bus = self.fake_sensor()
                fan = FakeFan()
                with self.assertRaises(FileExistsError):
                    self.capture(sensor, fan)
                self.assertEqual(path.read_text(), '{"original": true}')
                sensor.connect.assert_not_called()
                self.assertEqual(fan.operations, [])
                path.unlink()

    def test_changed_bundle_or_source_prevents_hardware_access(self):
        for path in (self.run / 'bundle/bundle.json', self.source):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b' ')
                sensor, bus = self.fake_sensor()
                fan = FakeFan()
                with self.assertRaisesRegex(ValueError, 'verändert'):
                    self.capture(sensor, fan)
                sensor.connect.assert_not_called()
                self.assertEqual(fan.operations, [])
                path.write_bytes(original)

    def test_second_capture_cannot_enter_already_locked_run(self):
        sensor, bus = self.fake_sensor()
        fan = FakeFan()
        with (self.run / 'recording.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, 'bereits eine Aufnahme'):
                self.capture(sensor, fan)
        sensor.connect.assert_not_called()
        self.assertEqual(fan.operations, [])

    def stepped_capture(self, seconds, *, fail_verify=None, stop_request=False):
        """Advance simulated host time without waiting or changing sensor data."""
        clock = SimpleNamespace(now=NS)
        steps = iter(seconds)
        observations = []
        class SteppedAcquisition:
            def __init__(self, reader, raw_path, *, window_size, capacity, stop_event):
                self.stop_event = stop_event
                self.raw_path = raw_path
                self.done = threading.Event()
                self.error = None
                self.thread = SimpleNamespace(is_alive=lambda: not self.done.is_set())
            def start(self):
                self.raw_path.write_text('test_only_raw_fixture\n')
                return self
            def get(self, timeout):
                observations.append((clock.now, self.stop_event.is_set()))
                clock.now = next(steps) * NS
                return None
            def snapshot(self):
                return dict(last_sample_host_monotonic_ns=clock.now, samples_captured=128)
            def stop(self):
                self.stop_event.set()
                self.done.set()
        sensor, bus = self.fake_sensor()
        fan = FakeFan(fail_verify=fail_verify)
        if stop_request:
            experiment.request_stop(self.run)
        with patch.object(experiment, 'BufferedAcquisition', SteppedAcquisition), \
                patch.object(experiment.time, 'monotonic_ns', side_effect=lambda: clock.now):
            try:
                report = self.capture(sensor, fan)
            except RuntimeError:
                report = experiment.common.read_json(self.run / 'run.json')
        return report, fan, bus, observations

    def test_exceeds_six_hundred_seconds_and_waits_for_recorded_postrun(self):
        for number in range(1, 11):
            experiment.append_cue(self.run, cue('call_requested', number, 61 + (number - 1) * 90))
            experiment.append_cue(self.run, cue('end_reported', number, 71 + (number - 1) * 90))
        report, fan, bus, observations = self.stepped_capture([602, 900, 911])
        self.assertEqual(report['status'], 'completed')
        self.assertEqual(report['stop_reason'], 'ten_trials_and_postrun_complete')
        self.assertEqual(report['end_monotonic_ns'], 911 * NS)
        self.assertGreater((report['end_monotonic_ns'] - report['start_monotonic_ns']) / NS, 600)
        self.assertEqual(len(observations), 3)
        self.assertTrue(all(not stopped for _, stopped in observations))
        self.assertEqual(fan.operations.count(('set', 75)), 1)
        self.assertGreaterEqual(fan.verify_calls, 4)
        bus.close.assert_called_once()

    def test_periodic_pwm_mismatch_stops_recording_without_changing_setting(self):
        report, fan, bus, observations = self.stepped_capture([2], fail_verify=2)
        self.assertEqual(report['status'], 'failed')
        self.assertIn('PWM readback differs', report['error'])
        self.assertEqual(fan.operations.count(('set', 75)), 1)
        self.assertEqual(len(observations), 1)
        bus.close.assert_called_once()


class PrepareTests(unittest.TestCase):
    def test_prepare_freezes_expected_profile_and_refuses_existing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / 'profile'
            (profile / 'comparison_bundle').mkdir(parents=True)
            write_json(profile / 'comparison_bundle/bundle.json', BUNDLE)
            write_json(profile / 'profile.json', {'name': BUNDLE['profile_name']})
            (root / 'src').mkdir()
            for name in ('phone_series_experiment.py', 'analyze_phone_series.py',
                         'common_comparison.py', 'fan_pwm.py', 'live_pipeline.py', 'adxl345.py'):
                (root / 'src' / name).write_text('# fixture source\n')
            output = root / 'new_run'
            with patch.object(experiment, 'ROOT', root), patch.object(experiment, 'PROFILE', profile), \
                    patch.object(experiment.common, 'load_bundle', return_value=BUNDLE), \
                    patch.object(experiment.common, 'provenance', return_value={'test_only': True}), \
                    patch.dict(sys.modules, {'analyze_phone_series': SimpleNamespace(RULES={'test_only': True})}):
                self.assertEqual(experiment.prepare(output), output)
                plan_bytes = (output / 'plan.json').read_bytes()
                with self.assertRaises(FileExistsError):
                    experiment.prepare(output)
                self.assertEqual((output / 'plan.json').read_bytes(), plan_bytes)
            plan = experiment.common.read_json(output / 'plan.json')
            self.assertEqual(plan['trials'], 10)
            self.assertEqual(plan['warmup_seconds'], 30)
            self.assertEqual(plan['normal_seconds'], 30)
            self.assertIsNone(plan['maximum_duration_seconds'])
            self.assertIsNone(plan['fixed_call_duration_seconds'])
            self.assertEqual(plan['pwm']['percent'], 75)
            self.assertEqual(plan['pwm']['frequency_hz'], 25000)
            self.assertTrue(plan['pwm']['hold_all_phases'])
            self.assertFalse(plan['pwm']['change_after_start'])
            self.assertEqual(plan['profile_name'], 'standlauf_pwm75_200hz')
            self.assertEqual(plan['thresholds'], BUNDLE['thresholds'])
            self.assertEqual(plan['artifact_sha256'], BUNDLE['artifact_sha256'])
            self.assertEqual(len(plan['source_sha256']), 6)
            self.assertTrue((output / 'analysis_rules.json').is_file())

    def test_incompatible_profile_rejected_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'new_run'
            for field, value in [('profile_name', 'standlauf_pwm50_200hz'),
                                 ('sampling_rate_hz', 100), ('window_size', 64), ('step_size', 64)]:
                with self.subTest(field=field), \
                        patch.object(experiment.common, 'load_bundle', return_value={**BUNDLE, field: value}), \
                        self.assertRaises(ValueError):
                    experiment.prepare(output)
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
