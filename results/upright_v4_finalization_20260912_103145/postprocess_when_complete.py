from pathlib import Path
import json,time,subprocess,os,sys
B=Path(__file__).resolve().parent;R=B/'runtime_evidence';ROOT=B.parents[1]
p=json.loads((R/'protocol.json').read_text())
while True:
 states=[]
 for spec in p['trials']:
  f=R/(spec['id']+'_session.json');states.append(json.loads(f.read_text()).get('status') if f.exists() else None)
 if 'error' in states:raise SystemExit('Runtime matrix error; no automatic retry')
 if all(s=='completed' for s in states):break
 time.sleep(2)
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
for name,args in [('analysis',['analyze_runtime_evidence.py','--output',str(B/'runtime_analysis')]),('memory_probe',['probe_memory.py']),('word_figures',['plot_word_figures.py'])]:
 print('START',name,flush=True)
 subprocess.run([str(ROOT/'.venv/bin/python'),str(B/args[0]),*args[1:]],cwd=ROOT,env=env,check=True)
 print('COMPLETE',name,flush=True)
print('Postprocessing complete; Word assembly/review still pending.',flush=True)
