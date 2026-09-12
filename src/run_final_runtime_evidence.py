#!/usr/bin/env python3
"""One frozen, preauthorized runtime trial. No repetition/recovery loop."""
import argparse,json,hashlib,sys,time,os,signal,subprocess
from pathlib import Path
from datetime import datetime,timezone
ENTRY_NS=time.monotonic_ns()

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def save(path,value):
    temp=Path(str(path)+'.tmp')
    with temp.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)

def environment():
    from importlib.metadata import version
    import platform,psutil
    result={'utc':utc(),'platform':platform.platform(),'python':sys.version,
            'versions':{n:version(n) for n in ['numpy','pandas','scikit-learn','ai-edge-litert','psutil']},
            'thread_environment':{n:os.environ.get(n) for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']},
            'cpu_count':os.cpu_count(),'system_cpu_percent_1s':psutil.cpu_percent(interval=1),
            'process_memory':dict(psutil.Process().memory_info()._asdict())}
    for name,path in [('temperature_mC','/sys/class/thermal/thermal_zone0/temp'),('cpu_frequency_kHz','/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq')]:
        try:result[name]=int(Path(path).read_text())
        except OSError:result[name]=None
    try:
        p=subprocess.run(['vcgencmd','get_throttled'],capture_output=True,text=True,timeout=3)
        result['throttled_readback']=p.stdout.strip()
    except (OSError,subprocess.TimeoutExpired):result['throttled_readback']=None
    return result

def trial(protocol_path, trial_id):
    protocol_path=Path(protocol_path).resolve();base=protocol_path.parent
    p=json.loads(protocol_path.read_text())
    assert sha(protocol_path)==protocol_path.with_suffix('.sha256').read_text().strip(),'Protocol changed'
    assert p['purpose']=='frozen_runtime_evidence_v4' and p['pwm_percent']==75 and p['duration_s']==300
    assert p['selection_seconds']==[180,300] and p['window_size']==128 and p['step_size']==128
    assert p['warmup_invocations']==20 and p['additional_off_s']==60
    assert p['authorization']['source']=='explicit_user_message' and p['authorization']['automatic_planned_starts_and_stops'] is True
    assert p['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'Different boot'
    for path,h in p['implementation_sha256'].items():assert sha(path)==h, f'Implementation changed: {path}'
    chosen=[t for t in p['trials'] if t['id']==trial_id];assert len(chosen)==1
    spec=chosen[0];index=p['trials'].index(spec)
    assert spec['mode'] in ['sensor_live','offline_replay'] and spec['method'] in ['rms','isolation_forest','tflite_autoencoder']
    for prior in p['trials'][:index]:
        old=json.loads((base/(prior['id']+'_session.json')).read_text())
        assert old['status']=='completed','Earlier trial failed/missing: stop sequence'
    out=base/trial_id;session_path=base/(trial_id+'_session.json')
    assert not out.exists() and not session_path.exists(),'Already attempted; no replacement'
    session=dict(spec,status='preflight',started_utc=utc(),protocol_sha256=sha(protocol_path),boot_id=p['boot_id'],
                 frozen_bundle_sha256=p['frozen_bundle_sha256'],automatic_restarts=False,physical_stop_observed=False)
    with session_path.open('x') as f:json.dump(session,f,indent=2)
    def cancel(*_):raise KeyboardInterrupt('Stop requested; no retry')
    signal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel)
    failure=None;fan=None
    try:
        import pilot_method_comparison as pilot
        from pilot_runtime_final import FrozenEngine
        from pilot_stream_final import run_stream
        session['environment_before']=environment()
        assert sha(Path(p['bundle_directory'])/'pilot_bundle.json')==p['frozen_bundle_sha256']
        engine=FrozenEngine(p['bundle_directory'],[spec['method']]);engine.warmup()
        session.update(model_load_ns=engine.load_ns,model_warmup_ns=engine.warmup_ns,
                       process_entry_to_ready_ns=time.monotonic_ns()-ENTRY_NS)
        if spec['mode']=='offline_replay':
            import pandas as pd
            assert sha(p['replay_csv'])==p['replay_csv_sha256']
            frame=pd.read_csv(p['replay_csv'],float_precision='round_trip')
            session['command_invocation_monotonic_ns']=p['replay_command_ns']
            session['source_csv']=p['replay_csv'];session['source_csv_sha256']=p['replay_csv_sha256']
            result=run_stream(frame.to_dict('records'),p['replay_command_ns'],engine,out,paced=True)
            session['recording']=result
            session['status']='completed'
        else:
            from run_independent_normal_test import confirmed_zero,return_to_zero
            from fan_pwm import FanPWM
            from adxl345 import connect,sensor_configuration
            from pilot_recorder_final import make_recorder
            occupied=subprocess.run(['fuser','-v','/dev/i2c-1','/dev/gpiochip0','/dev/gpiomem0'],capture_output=True,text=True,timeout=5)
            assert occupied.returncode==1 and not occupied.stdout and not occupied.stderr,'Controller/sensor occupied'
            with FanPWM(journal_path=base/(trial_id+'_fan.jsonl')) as fan:
                try:
                    session['initial_readback']=fan.verify(0);assert confirmed_zero(session['initial_readback'])
                    session['off_reference_ns']=time.monotonic_ns();session['off_reference_utc']=utc()
                    save(session_path,session)
                    deadline=session['off_reference_ns']+60_000_000_000
                    while time.monotonic_ns()<deadline:time.sleep(min(1,max(0,(deadline-time.monotonic_ns())/1e9)))
                    session['precommand_zero']=fan.verify(0)
                    with connect(odr_hz=200,range_g=2,fifo=True) as bus:
                        cfg=sensor_configuration(bus)
                        assert all(cfg.get(k)==v for k,v in p['sensor'].items()),'Sensor configuration changed'
                        session['sensor']=cfg
                        csv=Path(p['data_directory'])/(trial_id+'_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')+'.csv')
                        session['csv']=str(csv)
                        metadata=dict(capture_mode='sensor_live',purpose='runtime_test',split='runtime_evidence',
                            phase=trial_id,condition_label='normal',mounting_id=p['mounting_id'],
                            fan_pwm_setpoint_percent=75,fan_pwm_frequency_hz=25000,detection_controls_fan=False,
                            frozen_bundle_sha256=p['frozen_bundle_sha256'],protocol_sha256=sha(protocol_path),
                            rpm_measured=None,mechanical_standstill_before_start=None,
                            authorization=p['authorization'],primary_interval_seconds=[180,300])
                        session['command_invocation_utc']=utc();session['command_invocation_monotonic_ns']=time.monotonic_ns()
                        session['setting_result']=fan.set_percent(75)
                        session['command_completed_monotonic_ns']=time.monotonic_ns()
                        metadata.update(pwm_command_invocation_utc=session['command_invocation_utc'],pwm_command_invocation_monotonic_ns=session['command_invocation_monotonic_ns'])
                        session['status']='recording';save(session_path,session)
                        frame=make_recorder(engine)(bus,300,200,output_path=csv,label=0,state='normal',metadata=metadata)
                        session['recording']=frame.attrs['report']
                        session['after_capture_readback']=fan.verify(75)
                        session['first_xyz_delay_s']=(int(frame.host_monotonic_ns.iloc[0])-session['command_invocation_monotonic_ns'])/1e9
                        session['additional_off_actual_s']=(session['command_invocation_monotonic_ns']-session['off_reference_ns'])/1e9
                        session['status']='completed'
                finally:
                    shutdown=return_to_zero(fan,session)
                    if shutdown:raise shutdown
        session['environment_after']=environment()
        pilot.load_bundle(p['bundle_directory'])
    except BaseException as exc:
        failure=exc;session.update(status='error',error=f'{type(exc).__name__}: {exc}')
    finally:
        session['finished_utc']=utc();save(session_path,session)
    print(json.dumps({'trial':trial_id,'status':session['status'],'error':session.get('error')}),flush=True)
    if failure:raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',required=True);parser.add_argument('--trial',required=True)
    args=parser.parse_args();trial(args.protocol,args.trial)
