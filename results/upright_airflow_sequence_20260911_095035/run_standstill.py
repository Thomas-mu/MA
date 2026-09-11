"""One authorized 30-s upright standstill capture, no fan start."""
import json
from pathlib import Path
import signal
import subprocess
import sys
import time
from datetime import datetime,timezone
from sequence_common import BASE,ROOT,MOUNTING_ID,initial_gate,persist,digest,utc
sys.path.insert(0,str(ROOT/'src'))
from adxl345 import connect,sensor_configuration
from collect_real_data import record
from fan_pwm import FanPWM


def main():
    release=initial_gate()
    holders=subprocess.run(['fuser','-v','/dev/i2c-1','/dev/gpiochip0','/dev/gpiomem0'],capture_output=True,text=True,timeout=5)
    if holders.returncode!=1 or holders.stdout or holders.stderr:raise RuntimeError('Competing/unclear device access')
    path=BASE/'standstill_session.json'
    with path.open('x') as f:f.write('{}\n')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    csv=ROOT/'data'/BASE.name/f'standstill_0pwm_30s_{stamp}.csv'
    mounting=json.loads((BASE/'mounting.json').read_text())
    journal=BASE/'standstill_fan.jsonl'
    s={'status':'preflight','phase':'standstill','started_utc':utc(),'csv':str(csv.relative_to(ROOT)),
       'mounting_id':MOUNTING_ID,'mounting':mounting,'requested_duration_s':30,
       'user_release':release,'fan_journal':str(journal.relative_to(ROOT)),
       'runner_sha256':digest(Path(__file__)),'quality_pass_for_initial_start':False,
       'mechanical_standstill_user_confirmed_before_capture':True,'measured_rpm':None}
    persist(path,s)
    def interrupt(*_):raise KeyboardInterrupt('Standstill capture interrupted; no automatic restart')
    signal.signal(signal.SIGINT,interrupt);signal.signal(signal.SIGTERM,interrupt)
    failure=None
    try:
        with FanPWM(journal_path=journal) as fan:
            try:
                s['initial_readback']=fan.verify(0)
                with connect(odr_hz=200,range_g=2,fifo=True) as bus:
                    s['sensor']=sensor_configuration(bus)
                    metadata={'mounting_id':MOUNTING_ID,'mounting':mounting,'purpose':'pilot',
                      'phase':'standstill','condition_label':'standstill','split':'development_pilot',
                      'fan_pwm_setpoint_percent':0,'fan_pwm_frequency_hz':25000,'detection_controls_fan':False,
                      'user_release':release,'mechanical_standstill_user_confirmed':True,
                      'rpm_measured':None,'sensor_settings_unchanged':True,'old_measurements_pooled':False}
                    s['record_invoked_monotonic_ns']=time.monotonic_ns()
                    s['record_invoked_utc']=utc();s['status']='recording';persist(path,s)
                    print(json.dumps({'event':'standstill_capture_start','utc':utc(),'duration_s':30,'pwm_percent':0}),flush=True)
                    df=record(bus,30,200,output_path=csv,label=0,state='standstill',metadata=metadata)
                    s['recording']=df.attrs['report']
                    s['final_readback']=fan.verify(0)
                    q=s['recording']['summary']
                    s['quality_pass_for_initial_start']=(s['recording']['status']=='completed' and len(df)>1 and
                        q['nonmonotonic_host_intervals']==0 and all(q[k]==0 for k in ['gap_flagged_samples','overrun_flagged_samples','saturated_samples']))
                    if len(df):
                        first,last=int(df.host_monotonic_ns.iloc[0]),int(df.host_monotonic_ns.iloc[-1])
                        s['timing']={'first_xyz_monotonic_ns':first,'last_xyz_monotonic_ns':last,
                          'first_xyz_after_record_invocation_s':(first-s['record_invoked_monotonic_ns'])/1e9,
                          'first_to_last_xyz_s':(last-first)/1e9}
                    s['status']='completed' if s['recording']['status']=='completed' else 'incomplete'
            except BaseException as exc:
                failure=exc;s.update(status='error',error=f'{type(exc).__name__}: {exc}')
                try:
                    s['error_zero_result']=fan.stop();s['final_readback']=fan.verify(0)
                except BaseException as stop_exc:
                    s.update(status='shutdown_error',shutdown_error=str(stop_exc))
                    try:s['actual_state_after_shutdown_error']=fan.read_state()
                    except BaseException as read_exc:s['actual_state_read_error']=str(read_exc)
    except BaseException as exc:
        failure=failure or exc;s.update(status='error',controller_error=str(exc))
    finally:
        s['finished_utc']=utc();persist(path,s)
    print(json.dumps({'event':'standstill_finished','status':s['status'],
        'quality_pass_for_initial_start':s['quality_pass_for_initial_start'],'summary':s.get('recording',{}).get('summary')}),flush=True)
    if failure or not s['quality_pass_for_initial_start']:raise SystemExit(1)


if __name__=='__main__':main()
