"""Hardwarefreie Regressionen; keine Aussage über Sensor-/GUI-Laufzeit."""
import csv
import json
import queue
import sys
import tempfile
import threading
import time
import types
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch, Mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import live_tflite_monitor as monitor
from live_pipeline import BufferedAcquisition, Sample, decision_status, is_stale, summarize_decisions


class FakeInterpreter:
    def __init__(self, output):
        self.output = output
    def set_tensor(self, index, value):
        self.input = value
    def invoke(self):
        pass
    def get_tensor(self, index):
        return self.output


def runtime(output=None):
    return monitor.TFLiteRuntime(FakeInterpreter(np.zeros((1, 128, 3), np.float32) if output is None else output),
                                 0, 1, (1, 128, 3), (1, 128, 3), np.dtype('float32'), np.dtype('float32'),
                                 "FAKE TEST ONLY")


class IdentityScaler:
    def transform(self, values):
        return values


class LivePipelineTests(unittest.TestCase):
    def test_full_queue_keeps_raw_and_partial_window(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw.csv"
            values = iter(Sample((float(i), 0, 1), 1000000 * i, i) for i in range(19))
            pipeline = BufferedAcquisition(lambda stop: next(values, None), path, window_size=4, capacity=1).start()
            self.assertTrue(pipeline.done.wait(3))
            pipeline.stop()
            stats = pipeline.snapshot()
            self.assertEqual(stats['windows_formed'], 4)
            self.assertEqual(stats['windows_dropped'], 3)
            self.assertEqual(stats['partial_samples_saved'], 3)
            self.assertEqual(stats['queue_high_watermark'], 1)
            with path.open() as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 19)
            self.assertEqual(len(pipeline.event_path.read_text().splitlines()), 3)

    def test_cooperative_stop_saves_last_captured_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw.csv"
            stop = threading.Event()
            count = 0
            def read(event):
                nonlocal count
                count += 1
                if count == 3:
                    stop.set()
                return Sample((count, 0, 1), count, count)
            pipeline = BufferedAcquisition(read, path, window_size=4, stop_event=stop).start()
            self.assertTrue(pipeline.done.wait(3))
            pipeline.stop()
            self.assertEqual(pipeline.stats['partial_samples_saved'], 3)
            with path.open() as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 3)

    def test_reader_failure_preserves_previous_samples_and_surfaces(self):
        with tempfile.TemporaryDirectory() as directory:
            count = 0
            def read(stop):
                nonlocal count
                count += 1
                if count == 3:
                    raise OSError("I2C failure")
                return Sample((1, 0, 1), count, count)
            pipeline = BufferedAcquisition(read, Path(directory) / 'raw.csv').start()
            self.assertTrue(pipeline.done.wait(3))
            with self.assertRaisesRegex(RuntimeError, "I2C failure"):
                pipeline.get(timeout=0)
            pipeline.stop()
            self.assertEqual(pipeline.stats['partial_samples_saved'], 2)

    def test_nonfinite_model_outputs_and_wrong_shape_are_rejected(self):
        for output in (np.full((1,128,3), np.nan), np.full((1,128,3), np.inf), np.zeros((1,1,3))):
            with self.subTest(shape=output.shape), self.assertRaises(ValueError):
                monitor.infer_window(runtime(output), np.zeros((128,3), np.float32), 0.2)
        for threshold in (float('nan'), float('inf'), -1):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                monitor.infer_window(runtime(), np.zeros((128,3), np.float32), threshold)
        self.assertEqual(monitor.infer_window(runtime(), np.zeros((128,3), np.float32), 0.2)[1], 0)

    def test_overflow_score_is_rejected(self):
        with np.errstate(over='ignore'), self.assertRaisesRegex(ValueError, "nicht endlich"):
            monitor.infer_window(runtime(np.full((1,128,3), 1e30, np.float32)), np.zeros((128,3), np.float32), 0.2)

    def test_invalid_scores_never_normal_and_stale_clock(self):
        self.assertEqual(decision_status(0, float('nan'), 0.2), 'ERROR')
        self.assertEqual(decision_status(-1, 0.1, 0.2), 'ERROR')
        self.assertEqual(decision_status(0, 0.1, float('inf')), 'ERROR')
        self.assertTrue(is_stale(None))
        self.assertTrue(is_stale(10, now_ns=2_000_000_010))
        self.assertFalse(is_stale(10, now_ns=10))

    def test_full_session_logs_invalid_output_and_closes_bus(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "artifact"
            artifact.write_text('test artifact')
            config = monitor.LiveConfiguration(None, artifact, artifact, artifact, 0.2, root/'decisions.csv',
                                                threshold_source="MANUAL", profile_sampling_rate_hz=200)
            bus = types.SimpleNamespace(closed=False)
            bus.close = lambda: setattr(bus, 'closed', True)
            count = 0
            def read(bus, stop_event=None):
                nonlocal count
                count += 1
                return types.SimpleNamespace(xyz_g=(0,0,0), monotonic_ns=time.monotonic_ns(),
                     gap=False, overrun=False, saturated=False, sample_index=count,
                     sensor_time_estimate_s=count/200, fifo_depth=1, read_duration_ns=100)
            fake_sensor = types.SimpleNamespace(read_fresh_sample=read, sensor_configuration=lambda bus: {'odr_hz':200},
                                               reset_fifo=lambda bus: None)
            with patch.dict(sys.modules, {'adxl345': fake_sensor}), \
                    patch.object(monitor, 'load_sensor_access', return_value=(lambda **kwargs: bus, None)):
                stream = monitor.iter_live_measurements(runtime(np.full((1,128,3),np.nan)), IdentityScaler(),
                                                       config, config.default_log_path, max_windows=1)
                row = next(stream)
                self.assertEqual(row['status'], 'ERROR')
                self.assertEqual(row['predicted_label'], -1)
                with self.assertRaises(RuntimeError):
                    next(stream)
            self.assertTrue(bus.closed)
            manifest = json.loads(config.default_log_path.with_suffix('.run.json').read_text())
            self.assertEqual(manifest['status'], 'failed')
            self.assertEqual(manifest['invalid_windows'], 1)
            self.assertEqual(manifest['threshold_source'], 'MANUAL')
            self.assertEqual(manifest['acquisition']['samples_captured'], 128)
            self.assertIn('source_sha256',manifest)
            self.assertGreaterEqual(row['decision_latency_ms'], row['inference_time_ms'])
            self.assertGreater(row['process_rss_bytes'], 0)

    def test_sampling_mismatch_fails_before_sensor_access(self):
        config = monitor.LiveConfiguration(None, Path('model'),Path('scaler'),Path('threshold'),0.2,Path('log'))
        with patch.object(monitor,'load_sensor_access') as sensor, self.assertRaisesRegex(ValueError,'!= Profil'):
            next(monitor.iter_live_measurements(runtime(), IdentityScaler(), config, Path('/unneeded.csv')))
        sensor.assert_not_called()

    def test_gui_queue_is_bounded_and_preserves_terminal_error(self):
        import live_tflite_gui as gui
        config = monitor.LiveConfiguration(None, Path('m'),Path('s'),Path('t'),0.2,Path('l'))
        worker = gui.AcquisitionWorker(configuration=config, metadata=None, output_queue=queue.Queue(maxsize=2),
                                       stop_event=threading.Event(), self_test=True)
        for i in range(10):
            worker.emit('measurement', i)
        self.assertEqual(worker.output_queue.qsize(), 2)
        self.assertEqual(worker.gui_messages_dropped, 8)
        worker.emit('error', 'failure')
        worker.emit('finished')
        self.assertEqual([message.kind for message in worker.take_control_messages()], ['error', 'finished'])
        self.assertEqual(worker.output_queue.qsize(), 2)
        self.assertEqual(worker.take_control_messages(), [])

    def test_gui_log_path_survives_measurement_overflow_and_opens_journal(self):
        import live_tflite_gui as gui
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = monitor.LiveConfiguration(None, Path('m'),Path('s'),Path('t'),0.2,root/'live.csv')
            worker = gui.AcquisitionWorker(configuration=config, metadata=None, output_queue=queue.Queue(maxsize=8),
                                           stop_event=threading.Event(), self_test=True)
            worker.emit('log_path', config.default_log_path)
            worker.emit('status', 'live')
            for i in range(50):
                worker.emit('measurement', i)
                worker.emit('status', f'live {i}')
            self.assertEqual(worker.output_queue.qsize(), 8)
            self.assertEqual(len(worker.control_messages), 2)
            self.assertEqual(worker.gui_messages_dropped, 42)
            app = object.__new__(gui.LiveTFLiteApplication)
            app.worker = worker
            app.message_queue = worker.output_queue
            app.worker_status_text = Mock()
            app.log_text = Mock()
            app.update_measurement = Mock()
            app.acquisition_configuration = {}
            app.closing = True
            with patch.object(gui, 'PROJECT_ROOT', root):
                app.process_queue()
            self.assertTrue(config.default_log_path.with_suffix('.gui.csv').is_file())
            self.assertEqual(app.log_path, config.default_log_path)
            self.assertEqual(app.update_measurement.call_count, 8)
            app.close_gui_metrics()

    def test_fresh_decision_on_old_window_is_stale_in_actual_gui_update(self):
        import live_tflite_gui as gui
        now_ns = 20_000_000_000
        measurement = gui.Measurement('test timestamp',1,.1,.2,0,.5,200,
                                      decision_monotonic_ns=now_ns,
                                      window_complete_monotonic_ns=now_ns - 5_000_000_000)
        self.assertEqual(gui.measurement_display_status(measurement, now_ns=now_ns), 'STALE / VERALTET')
        app = object.__new__(gui.LiveTFLiteApplication)
        for name in ('decision_text','latency_text','status_text','status_label','worker_status_text',
                     'mse_text','threshold_text','sampling_text','inference_text','window_text','update_plot'):
            setattr(app, name, Mock())
        app.acquisition_configuration = {'sensor_odr':200}
        app.normal_seen = False
        app.anomaly_seen = False
        app.window_indices = []
        app.reconstruction_errors = []
        with patch('live_pipeline.time.monotonic_ns', return_value=now_ns):
            app.update_measurement(measurement)
        app.status_text.set.assert_called_once_with('STALE / VERALTET')
        self.assertFalse(app.normal_seen)
        self.assertEqual(app.last_window_complete_ns, measurement.window_complete_monotonic_ns)

    def test_empirical_budget_p99_and_missing_decisions_remain_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'decisions.csv'
            path.write_text('status,decision_latency_ms\nNORMAL,100\nANOMALY,700\nERROR,10\n')
            summary = summarize_decisions(path, {'samples_captured':201,
                'first_sample_host_monotonic_ns':1_000_000_000,
                'last_sample_host_monotonic_ns':2_000_000_000, 'windows_formed':4})
            self.assertEqual(summary['observed_host_delivery_rate_hz'], 200)
            self.assertEqual(summary['empirical_window_step_budget_ms'], 640)
            self.assertEqual(summary['valid_decision_latency_p99_ms'], 694)
            self.assertEqual(summary['deadline_misses_valid_decisions'], 1)
            self.assertEqual(summary['deadline_miss_fraction_valid_decisions'], .5)
            self.assertEqual(summary['complete_windows_without_valid_decision'], 2)
            self.assertFalse(summary['h2_confirmed'])

    def test_fan_confirmation_safety_sequences(self):
        from live_tflite_fan_control import run_synthetic_safety_tests
        result = run_synthetic_safety_tests()
        self.assertEqual(result['three_anomalies']['confirmation_indices'], [3])


if __name__ == '__main__':
    unittest.main()
