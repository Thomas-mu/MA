from pathlib import Path
import subprocess,sys,json,time,os
from datetime import datetime,timezone
base=Path(__file__).resolve().parent
protocol=base/'protocol.json';p=json.loads(protocol.read_text())
root=Path(p['bundle_directory']).parents[3]
# Resolve by this project, not by model-directory parent counting.
root=Path('/home/malik/masterarbeit-edge-ai')
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
for spec in p['trials']:
    name=spec['id'];session=base/(name+'_session.json')
    if session.exists():raise RuntimeError('No automatic resume/retry of attempted runtime sequence')
    print(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'event':'trial_begin',**spec}),flush=True)
    with (base/(name+'_console.log')).open('x') as log:
        child=subprocess.Popen([sys.executable,str(root/'src/run_final_runtime_evidence.py'),'--protocol',str(protocol),'--trial',name],stdout=log,stderr=subprocess.STDOUT,env=env)
        while child.poll() is None:
            time.sleep(20)
            state=json.loads(session.read_text()) if session.exists() else {}
            print(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'trial':name,'status':state.get('status','loading'),
                'elapsed_command_s':(time.monotonic_ns()-state['command_invocation_monotonic_ns'])/1e9 if spec['mode']=='sensor_live' and 'command_invocation_monotonic_ns' in state else None}),flush=True)
    if child.returncode!=0:
        print(json.dumps({'event':'sequence_stopped_on_error','trial':name,'exit_code':child.returncode}),flush=True)
        raise SystemExit(child.returncode)
    state=json.loads(session.read_text());assert state['status']=='completed'
    print(json.dumps({'event':'trial_complete','trial':name,'final_zero_readback':state.get('final_readback',{}).get('pwm_configuration',{}).get('duty_cycle_ns')}),flush=True)
print(json.dumps({'status':'completed','planned_trials':len(p['trials'])}),flush=True)
