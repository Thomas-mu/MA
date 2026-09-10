"""Two announced final standstill references after unavailable original session.

No PWM writes and no rewriting of the original, unfinished session journal.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from fan_pwm import FanPWM
from adxl345 import connect
from collect_real_data import record


def utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    original=OUT/'sequence_20260910_074455.json'
    previous=json.loads(original.read_text())
    if len(previous['recordings'])!=6 or previous['phases'][-1]['phase']!='standstill_after':
        raise ValueError('Expected six completed recordings and pending final reference phase')
    confirmation=json.loads((OUT/'final_standstill_confirmation_recovery.json').read_text())
    if confirmation.get('fan_observed_fully_stopped') is not True:
        raise ValueError('Fresh positive standstill confirmation required')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    session_path=OUT/f'closing_references_{stamp}.json'
    with session_path.open('x') as handle:handle.write('{}\n')
    journal=OUT/f'closing_references_{stamp}_fan.jsonl'
    report={'started_utc':utc(),'status':'running','recordings':[],
            'original_session':str(original.relative_to(ROOT)),
            'original_session_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
            'fan_journal':str(journal.relative_to(ROOT)), 'operator_confirmation':confirmation,
            'pwm_writes_requested':False,'interruption':'Original tool session65289 unavailable; no Python controller process found. Termination cause and exact time unknown. Original journal remains unchanged.',
            'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    def persist():
        tmp=session_path.with_suffix('.json.tmp')
        with tmp.open('w') as handle:
            json.dump(report,handle,indent=2,ensure_ascii=False,allow_nan=False)
            handle.flush();os.fsync(handle.fileno())
        os.replace(tmp,session_path)
    def interrupt(*_):raise KeyboardInterrupt('Closing references interrupted')
    signal.signal(signal.SIGTERM,interrupt)
    try:
        with FanPWM(journal_path=journal) as fan:
            report['initial_readback']=fan.verify(0)
            for repeat in (1,2):
                path=Path('data/pwm50_75_sequence_20260910')/(
                    f'standstill_after_r{repeat}_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'.csv')
                before=fan.verify(0)
                meta={'purpose':'pilot','sequence_id':original.stem,'sequence_phase':'standstill_after',
                      'phase_repeat':repeat,'continuation_of_session':str(original.relative_to(ROOT)),
                      'mounting':'ADXL345 with intended I2C wiring attached to a corner of ARCTIC P12 Pro PST frame; fan control GPIO18',
                      'mounting_id':'fan_frame_corner_adxl345_gpio18_v1','mounting_unchanged_user_instruction':True,
                      'fan_pwm_setpoint_percent':0.0,'fan_pwm_frequency_hz':25000,
                      'fan_pwm_source':'verified_existing_zero_hardware_pwm_no_writes_in_continuation',
                      'fan_control_journal':report['fan_journal'],'physical_state_source':'new_operator_visual_full_standstill_confirmation',
                      'operator_confirmation':confirmation,'elapsed_since_phase_pwm_command_s':None,
                      'last_documented_zero_command_utc':previous['phases'][-1]['setting_completed_utc'],
                      'control_session_interrupted':True,'rpm_measured':None,'rpm_method':None,'rpm_source':'not_measured',
                      'detection_controls_fan':False,'induced_anomaly':False,
                      'repeat_design':'two files at unchanged confirmed standstill;5s gap'}
                with connect(odr_hz=200,range_g=2,fifo=True) as bus:
                    print(json.dumps({'event':'capture_start','utc':utc(),'repeat':repeat,'pwm_percent':0,'seconds':30,'csv':str(path)}),flush=True)
                    df=record(bus,30,200,output_path=path,label=-1,state='controlled_standstill_after_pilot',metadata=meta)
                after=fan.verify(0)
                item={'phase':'standstill_after','repeat':repeat,'csv':str(path),'before':before,'after':after,'report':df.attrs['report']}
                report['recordings'].append(item);persist()
                summary=item['report']['summary']
                print(json.dumps({'event':'capture_completed','utc':utc(),'repeat':repeat,'summary':summary}),flush=True)
                if item['report']['status']!='completed' or any(summary[k] for k in ('gap_flagged_samples','overrun_flagged_samples','saturated_samples')):
                    raise RuntimeError('Incomplete or flagged reference')
                if repeat==1:time.sleep(5)
            report['final_readback']=fan.verify(0)
            report['final_mechanical_state']='operator_confirmed_full_standstill_before_closing_pair; no subsequent PWM change'
            report['status']='completed'
    except BaseException as exc:
        report.update(status='error',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        report['finished_utc']=utc();persist()
    print(json.dumps({'event':'closing_references_finished','session':str(session_path.relative_to(ROOT)),'status':report['status']}),flush=True)


if __name__=='__main__':main()
