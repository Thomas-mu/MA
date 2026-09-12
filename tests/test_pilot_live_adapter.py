"""Frozen on-disk parity and failure/quality boundaries, no hardware."""
import sys
from pathlib import Path
import json
import time
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import pilot_live_adapter as live
import independent_normal_test as offline
import pilot_method_comparison as pilot

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT/'results/upright_v4_training_pilot_20260911_130614/run_001/frozen'
SESSION = ROOT/'results/upright_v4_frozen_airflow_test_20260912_073015/normal_before_session.json'

@pytest.fixture(scope='module')
def actual():
    s = json.loads(SESSION.read_text())
    frame = pd.read_csv(s['csv'], float_precision='round_trip')
    command = s['command_invocation_monotonic_ns']
    return frame, command, offline.build_windows(frame, command)[0]


def stream_windows(frame, command):
    assembler = live.WindowAssembler(command)
    result = []
    for row in frame.to_dict('records'):
        window = assembler.push(row)
        if window is not None:
            result.append(window)
    return result, assembler


def test_actual_stream_exact_frozen_194_windows_and_three_scores(actual):
    frame, command, expected = actual
    obtained, assembler = stream_windows(frame, command)
    assert len(obtained) == len(expected) == 194
    assert assembler.summary()['trailing_selected_xyz'] == 22
    engine = live.FrozenEngine(BUNDLE)
    thresholds = {m:engine.bundle['thresholds'][m]['value'] for m in pilot.METHODS}
    for a,b in zip(obtained, expected, strict=True):
        assert a['metadata'] == b['metadata']
        assert np.array_equal(a['raw_float64'], b['raw_float64'])
        assert np.array_equal(a['ac_float32'], b['ac_float32'])
        frozen = pilot.score_window(b['ac_float32'], engine.bundle['scaler'], engine.functions, thresholds)
        for decision in engine.score(a):
            assert decision['score'] == frozen[decision['method']]['score']
            assert decision['decision'] == frozen[decision['method']]['decision']


def synthetic():
    count=260
    return pd.DataFrame(dict(sample_index=np.arange(count),host_monotonic_ns=180_000_000_000+np.arange(count)*5_000_000,
        x_g=np.full(count,.01),y_g=np.full(count,.02),z_g=np.full(count,1.0),
        fifo_depth=np.ones(count,dtype=int), read_duration_ns=np.full(count,100),gap=False,overrun=False,saturated=False))

@pytest.mark.parametrize('field,value,reason', [('gap',True,'gap'),('overrun',True,'overrun'),('saturated',True,'saturated'),
    ('fifo_depth',32,'fifo_full'),('x_g',float('nan'),'nonfinite_xyz'),('y_g',1.99,'raw_saturation_rail')])
def test_same_invalid_window_for_each_quality_flag(field,value,reason):
    f=synthetic();f.loc[130,field]=value
    windows,_=stream_windows(f,0)
    assert windows[0]['metadata']['quality_valid']
    assert windows[1]['ac_float32'] is None
    assert reason in windows[1]['metadata']['quality_reasons']


def test_gap_across_window_boundary_is_not_lost():
    f=synthetic(); f.loc[128:,'host_monotonic_ns']+=200_000_000
    windows,_=stream_windows(f,0)
    assert windows[0]['metadata']['quality_valid']
    assert windows[1]['metadata']['quality_reasons']==['host_interval_over_160ms']


def test_interval_clip_no_startup_partition_and_no_cross_record_tail():
    f=synthetic();f.host_monotonic_ns+=119_360_000_000
    w,a=stream_windows(f,0)
    assert len(w)==1 and a.selected==128
    assert live.WindowAssembler(0).summary()['trailing_selected_xyz']==0

@pytest.mark.parametrize('field,value',[('host_monotonic_ns',180_000_000_000),('sample_index',50)])
def test_structural_corruption_rejects_source(field,value):
    f=synthetic();f.loc[1,field]=value
    with pytest.raises(ValueError): stream_windows(f,0)


def test_mutating_scorer_cannot_change_other_inputs():
    w,_=stream_windows(synthetic(),0)
    e=live.FrozenEngine(BUNDLE)
    seen=[]
    def scorer(x):
        seen.append(x.copy());x[:]=900;return 0
    e.functions={m:scorer for m in e.methods}
    e.score(w[0])
    assert all(np.array_equal(seen[0],x) for x in seen)


def test_slow_consumer_drops_decisions_preserves_raw_and_counts(tmp_path):
    f=synthetic()
    f=pd.concat([f]*10,ignore_index=True)
    f.sample_index=np.arange(len(f));f.host_monotonic_ns=180_000_000_000+f.sample_index*5_000_000
    e=live.FrozenEngine(BUNDLE, methods=['rms'])
    original=e.score
    def slow(w): time.sleep(.1);return original(w)
    e.score=slow
    out=tmp_path/'stream'
    s=live.run_stream(f.to_dict('records'),0,e,out,capacity=1)
    assert len(pd.read_csv(out/'raw.csv'))==len(f)
    assert s['windows_dropped']>0
    assert s['complete_windows']==s['decision_rows']+s['windows_dropped']
    assert s['queue_high_watermark']<=1
    with pytest.raises(FileExistsError): live.run_stream([],0,e,out)


def test_reader_failure_preserves_partial_raw_and_error(tmp_path):
    rows=synthetic().to_dict('records')
    def failing():
        yield from rows[:7]
        raise OSError('test sensor error')
    e=live.FrozenEngine(BUNDLE,methods=['rms'])
    out=tmp_path/'failure'
    with pytest.raises(RuntimeError,match='test sensor error'):
        live.run_stream(failing(),0,e,out)
    assert len(pd.read_csv(out/'raw.csv'))==7
    assert json.loads((out/'summary.json').read_text())['status']=='error'


def test_live_recorder_keeps_normal_raw_contract_and_requires_declared_load(tmp_path,monkeypatch):
    import pilot_live_recorder as recorder
    import adxl345
    import collect_real_data as collector
    monkeypatch.setattr(adxl345,'sensor_configuration',lambda bus:pilot.preparation.EXPECTED_SENSOR)
    monkeypatch.setattr(collector,'provenance',lambda:{'test_only':True})
    f=synthetic()
    f['timestamp_s']=np.arange(len(f))/200
    f['sensor_time_estimate_s']=f['timestamp_s']
    f['label']=0;f['anomaly_type']='normal';f['source']='synthetic_test_only';f['signal']=1.
    monkeypatch.setattr(recorder,'sensor_rows',lambda *args:f.to_dict('records'))
    engine=live.FrozenEngine(BUNDLE,methods=['rms'])
    call=recorder.make_recorder(engine)
    path=tmp_path/'test_only.csv'
    with pytest.raises(ValueError,match='declared'):
        call(object(),300,200,output_path=path,label=0,state='normal',metadata={})
    result=call(object(),300,200,output_path=path,label=0,state='normal',
                metadata={'capture_mode':'sensor_live','pwm_command_invocation_monotonic_ns':0})
    assert result.attrs['report']['summary']['samples']==260
    assert result.attrs['report']['status']=='completed'
    assert json.loads(path.with_suffix('.json').read_text())==result.attrs['report']
    assert path.exists() and not path.with_suffix('.runtime').joinpath('raw.csv').exists()
