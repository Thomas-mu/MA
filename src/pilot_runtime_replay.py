#!/usr/bin/env python3
"""Replay existing raw data through frozen streaming adapter, no hardware imports."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import signal
import threading

import pandas as pd
import independent_normal_test as frozen
from pilot_live_adapter import FrozenEngine, run_stream


def replay(csv_path, session_path, bundle, output, *, method='all', paced=False, capacity=4):
    csv_path, session_path = Path(csv_path).resolve(), Path(session_path).resolve()
    session=json.loads(session_path.read_text())
    if session.get('status')!='completed' or Path(session['csv']).resolve()!=csv_path:
        raise ValueError('Completed matching source session required')
    digest=frozen.sha256(csv_path)
    if session['recording']['csv_sha256']!=digest:
        raise ValueError('Raw source hash differs from completed recording')
    engine=FrozenEngine(bundle, None if method=='all' else [method])
    # Exact round-trip Float64 parser is shared with the independent test import.
    frame=pd.read_csv(csv_path,float_precision='round_trip')
    command=session['command_invocation_monotonic_ns']
    host=frame.host_monotonic_ns.to_numpy()
    if len(frame)<2 or not (host[1:]>host[:-1]).all():
        raise ValueError('Nonmonotonic source rejected before replay')
    quality=frozen.summarize_quality(frame,command)
    stop=threading.Event()
    def halt(*_): stop.set()
    signal.signal(signal.SIGTERM,halt)
    signal.signal(signal.SIGINT,halt)
    result=run_stream(frame.to_dict('records'),command,engine,output,capacity=capacity,
                      paced=paced,stop_event=stop,source_mode='offline_replay')
    if frozen.sha256(csv_path)!=digest:
        raise ValueError('Source changed during replay')
    result.update(source_csv=str(csv_path),source_csv_sha256=digest,
                  source_session=str(session_path),source_session_sha256=frozen.sha256(session_path),
                  source_quality=quality, replay_finished_utc=datetime.now(timezone.utc).isoformat(),
                  sensor_live_measured=False, pwm_access=False, fresh_process_methods=engine.methods,
                  machine=platform.platform(),deadline_s=128/quality['observed_xyz_per_second'],
                  nominal_deadline_s=128/200,
                  note='Unpaced replay is throughput evidence only. Paced replay uses mapped host arrival times; neither measures a live sensor or GUI load.')
    decisions=[json.loads(line) for line in (Path(output)/'decisions.jsonl').read_text().splitlines()]
    import numpy as np
    result['per_method']={}
    for m in engine.methods:
        rows=[r for r in decisions if r['method']==m]
        valid=[r for r in rows if r['decision']!='INVALID']
        latency=np.array([r['complete_to_decision_ns']/1e6 for r in valid])
        call=np.array([r['scorer_call_ns']/1e6 for r in valid])
        result['per_method'][m]=dict(valid_windows=len(valid),invalid_windows=len(rows)-len(valid),
            false_alarms=sum(r['decision']=='ANOMALY' for r in valid),
            false_alarm_rate=sum(r['decision']=='ANOMALY' for r in valid)/len(valid) if valid else None,
            complete_to_decision_ms=dict(zip(['p50','p95','p99','max'],map(float,np.r_[np.percentile(latency,[50,95,99]),latency.max()]))) if len(latency) else None,
            scorer_call_ms=dict(zip(['p50','p95','p99','max'],map(float,np.r_[np.percentile(call,[50,95,99]),call.max()]))) if len(call) else None,
            deadline_misses=int((latency>=result['deadline_s']*1000).sum()))
    result['implementation_sha256']={str(Path(p).resolve()):frozen.sha256(p) for p in [__file__,Path(__file__).with_name('pilot_live_adapter.py')]}
    result['artifacts_sha256']={p.name:frozen.sha256(p) for p in Path(output).iterdir() if p.is_file()}
    (Path(output)/'replay_report.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('csv','session','bundle','output'): parser.add_argument('--'+arg,required=True)
    parser.add_argument('--method',choices=['all',*frozen.METHODS],default='all')
    parser.add_argument('--paced',action='store_true')
    parser.add_argument('--capacity',type=int,default=4)
    a=parser.parse_args()
    print(json.dumps(replay(a.csv,a.session,a.bundle,a.output,method=a.method,paced=a.paced,capacity=a.capacity),indent=2))
if __name__=='__main__': main()
