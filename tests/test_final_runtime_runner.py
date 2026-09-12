"""Hardware-free shutdown/protocol tests of the final single-trial entry."""
import sys,json
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import run_final_runtime_evidence as runner
import pilot_runtime_final
import pilot_recorder_final
import adxl345,fan_pwm

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'results/upright_v4_training_pilot_20260911_130614/run_001/frozen'

class FakeFan:
    calls=[]
    def __init__(self,**kw):pass
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def verify(self,pct):
        self.calls.append(('verify',pct))
        return {'gpio_bcm':18,'physical_pin':12,'pwm_mux_confirmed':True,
                'pwm_configuration':{'period_ns':40000,'duty_cycle_ns':pct*400,'enable':1,'polarity':'normal','configured_duty_percent':pct}}
    def set_percent(self,pct):self.calls.append(('set',pct));return self.verify(pct)
    def stop(self):self.calls.append(('stop',0));return self.verify(0)

@pytest.fixture
def fixture(tmp_path,monkeypatch):
    FakeFan.calls=[]
    monkeypatch.setattr(fan_pwm,'FanPWM',FakeFan)
    class Bus:
        def __enter__(self):return self
        def __exit__(self,*a):pass
    monkeypatch.setattr(adxl345,'connect',lambda **kw:Bus())
    monkeypatch.setattr(adxl345,'sensor_configuration',lambda bus:{'test_only':True})
    monkeypatch.setattr(runner,'environment',lambda:{'test_only':True})
    monkeypatch.setattr(runner.signal,'signal',lambda *a:None)
    monkeypatch.setattr(runner.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=1,stdout='',stderr=''))
    clock=[1_000_000_000_000]
    monkeypatch.setattr(runner.time,'monotonic_ns',lambda:clock[0])
    monkeypatch.setattr(runner.time,'sleep',lambda s:clock.__setitem__(0,clock[0]+round(s*1e9)))
    class Engine:
        def __init__(self,*a):self.load_ns=1;self.warmup_ns=1
        def warmup(self):pass
    monkeypatch.setattr(pilot_runtime_final,'FrozenEngine',Engine)
    p=dict(purpose='frozen_runtime_evidence_v4',pwm_percent=75,duration_s=300,selection_seconds=[180,300],window_size=128,step_size=128,warmup_invocations=20,additional_off_s=60,
       authorization={'source':'explicit_user_message','automatic_planned_starts_and_stops':True},boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
       implementation_sha256={},trials=[{'id':'one','mode':'sensor_live','method':'rms'}],bundle_directory=str(BUNDLE),frozen_bundle_sha256=runner.sha(BUNDLE/'pilot_bundle.json'),sensor={'test_only':True},data_directory=str(tmp_path/'data'),mounting_id='test_only')
    path=tmp_path/'protocol.json';path.write_text(json.dumps(p));path.with_suffix('.sha256').write_text(runner.sha(path))
    return path

@pytest.mark.parametrize('error',[OSError('sensor failure'),KeyboardInterrupt('interrupt')])
def test_capture_failure_always_requests_zero_no_retry(fixture,monkeypatch,error):
    attempts=[]
    def capture(*a,**kw):attempts.append(1);raise error
    monkeypatch.setattr(pilot_recorder_final,'make_recorder',lambda engine:capture)
    with pytest.raises(SystemExit):runner.trial(fixture,'one')
    s=json.loads((fixture.parent/'one_session.json').read_text())
    assert s['status']=='error' and s['final_readback']['pwm_configuration']['duty_cycle_ns']==0
    assert attempts==[1]
    assert [c for c in FakeFan.calls if c[0]=='set']==[('set',75)]
    assert ('stop',0) in FakeFan.calls
    with pytest.raises(AssertionError,match='Already attempted'):runner.trial(fixture,'one')


def test_bad_protocol_cannot_open_fan(fixture):
    fixture.write_text(fixture.read_text()+' ')
    with pytest.raises(AssertionError,match='Protocol changed'):runner.trial(fixture,'one')
    assert FakeFan.calls==[]
