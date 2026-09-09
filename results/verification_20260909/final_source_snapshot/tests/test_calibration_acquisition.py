"""Calibration integrity tests with temporary journals and no sensor access."""
import json
import os
from pathlib import Path
import signal
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import calibrate_and_train as calibration


class FakeBus:
    def __init__(self):
        self.closed = False
        self._edge_config = dict(odr_hz=200, range_g=2, acquisition_mode='fifo_stream',
                                 full_resolution=True, register_readback={'0x2c': '0xb'})

    def close(self):
        self.closed = True


@pytest.fixture
def profile(tmp_path, monkeypatch):
    args = calibration.parse_args(['--profile', 'test_reference', '--recordings', '2',
                                   '--seconds', '1', '--state', 'normal_pwm25',
                                   '--mounting', 'mount_A', '--fan-pwm-setpoint', '25'])
    monkeypatch.setattr(calibration, 'collect_system_information', lambda: {'test_only': True})
    paths, document = calibration.initialize_profile(tmp_path, args.profile, False,
                                                     calibration.calibration_configuration(args), None)
    return paths, document


def journal(bus, duration_seconds, sample_rate_hz, *, output_path, label, state, metadata):
    n = 128
    df = pd.DataFrame(dict(timestamp_s=np.arange(n) / sample_rate_hz,
                           x_g=np.sin(np.arange(n)), y_g=np.cos(np.arange(n)), z_g=np.full(n, -1.0),
                           label=label, anomaly_type=state, source='real_fifo',
                           sample_index=np.arange(n), host_monotonic_ns=np.arange(n) * 5_000_000 + 100,
                           gap=False, overrun=False, saturated=False))
    with output_path.open('x') as handle:
        df.to_csv(handle, index=False)
    report = dict(metadata, started_at_utc='2026-09-09T10:00:00+00:00', sensor=bus._edge_config,
                  label=label, state=state, status='completed', code={'git_commit': 'test'},
                  csv_sha256=calibration.sha256_file(output_path),
                  summary=dict(samples=n, overrun_flagged_samples=0, gap_flagged_samples=0,
                               saturated_samples=0, nonmonotonic_host_intervals=0))
    output_path.with_suffix('.json').write_text(json.dumps(report))
    return df


def configure_fakes(monkeypatch, recorder=journal):
    bus = FakeBus()
    calls = []

    def connect(**kwargs):
        calls.append(kwargs)
        return bus

    monkeypatch.setattr(calibration, 'load_record_function', lambda: (connect, recorder))
    return bus, calls


def test_new_profile_records_directly_and_preserves_provenance(profile, monkeypatch):
    paths, document = profile
    bus, calls = configure_fakes(monkeypatch)
    calibration.record_normal_sessions(paths, document)
    assert calls == [dict(odr_hz=200, range_g=2, fifo=True)]
    assert bus.closed
    assert document['status'] == 'recorded'
    assert document['sensor']['open_evidence'] == ['usable_bandwidth', 'signal_to_noise_ratio', 'pilot_acceptance_limits']
    records = calibration.validate_recorded_profile(paths, document)
    assert [r['split'] for r in records] == ['train', 'validation']
    assert records[0]['acquisition']['fan_pwm_setpoint_percent'] == 25
    assert records[0]['acquisition']['rpm_measured'] is None
    assert records[0]['acquisition']['rpm_source'] == 'not_measured'
    assert records[0]['acquisition']['mounting'] == 'mount_A'
    assert pd.read_csv(paths.raw / 'normal_001.csv').source.unique().tolist() == ['real_fifo']
    prepared = calibration.prepare_profile_data(paths, document)
    assert prepared is not None  # Only preparation; no TensorFlow or training invoked.


@pytest.mark.parametrize('flag', ['gap', 'overrun', 'saturated'])
def test_quality_flags_fail_and_journals_remain(profile, monkeypatch, flag):
    paths, document = profile

    def flagged(*args, **kwargs):
        df = journal(*args, **kwargs)
        df.loc[3, flag] = True
        return df

    bus, _ = configure_fakes(monkeypatch, flagged)
    with pytest.raises(ValueError, match=flag):
        calibration.record_normal_sessions(paths, document)
    assert bus.closed
    assert document['status'] == 'recording_failed'
    assert (paths.raw / 'normal_001.csv').is_file()
    assert (paths.raw / 'normal_001.json').is_file()
    assert document['data']['active_recording']['recording_index'] == 1
    assert document['data']['recordings'] == []


def test_ctrl_c_preserves_partial_journal_and_profile_status(profile, monkeypatch):
    paths, document = profile

    def interrupted(*args, **kwargs):
        journal(*args, **kwargs)
        raise KeyboardInterrupt('operator stop')

    bus, _ = configure_fakes(monkeypatch, interrupted)
    with pytest.raises(KeyboardInterrupt):
        calibration.record_normal_sessions(paths, document)
    assert bus.closed
    assert json.loads(paths.metadata.read_text())['status'] == 'recording_interrupted'
    assert (paths.raw / 'normal_001.csv').is_file()


def test_sigterm_handler_restored_and_capture_preserved(profile, monkeypatch):
    paths, document = profile

    def terminated(*args, **kwargs):
        journal(*args, **kwargs)
        os.kill(os.getpid(), signal.SIGTERM)
        pytest.fail('SIGTERM should interrupt')

    bus, _ = configure_fakes(monkeypatch, terminated)
    monkeypatch.setattr(calibration, 'run', lambda: calibration.record_normal_sessions(paths, document))
    previous = signal.getsignal(signal.SIGTERM)
    with pytest.raises(SystemExit) as error:
        calibration.main()
    assert error.value.code == 130
    assert signal.getsignal(signal.SIGTERM) == previous
    assert bus.closed and document['status'] == 'recording_interrupted'
    assert (paths.raw / 'normal_001.csv').is_file()


def test_preexisting_sidecar_is_never_overwritten(profile, monkeypatch):
    paths, document = profile
    target = paths.raw / 'normal_001.json'
    target.write_text('existing evidence')
    bus, _ = configure_fakes(monkeypatch)
    with pytest.raises(FileExistsError):
        calibration.record_normal_sessions(paths, document)
    assert target.read_text() == 'existing evidence'
    assert bus.closed


def test_train_validation_rejects_altered_sidecar(profile, monkeypatch):
    paths, document = profile
    configure_fakes(monkeypatch)
    calibration.record_normal_sessions(paths, document)
    sidecar = paths.raw / 'normal_002.json'
    report = json.loads(sidecar.read_text())
    report['status'] = 'stopped'
    sidecar.write_text(json.dumps(report))
    with pytest.raises(ValueError, match='Journal|journal'):
        calibration.validate_recorded_profile(paths, document)


@pytest.mark.parametrize('flag', ['gap', 'overrun', 'saturated'])
def test_training_checks_csv_flags_even_when_hashes_match(profile, monkeypatch, flag):
    paths, document = profile
    configure_fakes(monkeypatch)
    calibration.record_normal_sessions(paths, document)
    path = paths.raw / 'normal_002.csv'
    dataframe = pd.read_csv(path)
    dataframe.loc[127, flag] = True
    dataframe.to_csv(path, index=False)
    sidecar = path.with_suffix('.json')
    report = json.loads(sidecar.read_text())
    report['csv_sha256'] = calibration.sha256_file(path)
    sidecar.write_text(json.dumps(report))
    row = document['data']['recordings'][1]
    row.update(sha256=report['csv_sha256'], metadata_sha256=calibration.sha256_file(sidecar), acquisition=report)
    with pytest.raises(ValueError, match=flag):
        calibration.prepare_profile_data(paths, document)


def test_training_interrupt_updates_status_without_training(profile, monkeypatch):
    paths, document = profile
    configure_fakes(monkeypatch)
    calibration.record_normal_sessions(paths, document)

    def interrupted(*args):
        raise KeyboardInterrupt('test stop before training')

    monkeypatch.setattr(calibration, 'prepare_profile_data', interrupted)
    with pytest.raises(KeyboardInterrupt):
        calibration.train_profile(paths, document)
    assert document['status'] == 'training_interrupted'
    assert (paths.raw / 'normal_001.csv').is_file()
    assert not list(paths.models.iterdir())


def test_rejected_recording_never_becomes_training_ready(profile, monkeypatch):
    paths, document = profile

    def stopped(*args, **kwargs):
        df = journal(*args, **kwargs)
        sidecar = kwargs['output_path'].with_suffix('.json')
        report = json.loads(sidecar.read_text())
        report['status'] = 'stopped'
        sidecar.write_text(json.dumps(report))
        return df

    configure_fakes(monkeypatch, stopped)
    with pytest.raises(ValueError, match='abgebrochen'):
        calibration.record_normal_sessions(paths, document)
    assert document['status'] == 'recording_failed'
    with pytest.raises(ValueError, match='Profilstatus'):
        calibration.train_profile(paths, document)


@pytest.mark.parametrize('extra', [['--seconds', 'nan'], ['--sampling-rate', '500'],
                                  ['--fan-pwm-setpoint', 'nan'], ['--rpm-measured', '1200'],
                                  ['--rpm-measured', 'inf', '--rpm-method', 'tachometer']])
def test_invalid_configuration_rejected(extra):
    with pytest.raises(SystemExit):
        calibration.parse_args(['--profile', 'test', '--state', 'normal', '--mounting', 'A', *extra])


def test_acquisition_requires_explicit_state_and_mounting():
    with pytest.raises(SystemExit):
        calibration.parse_args(['--profile', 'test', '--record-only'])
    args = calibration.parse_args(['--profile', 'test', '--dry-run'])
    assert args.sampling_rate == 200
