from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, subprocess, sys
ROOT=Path(__file__).resolve().parents[2]; BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from fan_pwm import FanPWM
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,d):
 with p.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2);f.write('\n')
s=json.loads((BASE/'normal_after_session.json').read_text());assert s['status']=='completed',s.get('error')
csv=Path(s['csv'])
commands=[['evaluate','--csv',str(csv),'--sidecar',str(csv.with_suffix('.json')),'--protocol',str(BASE/'protocol.json'),'--session',str(BASE/'normal_after_session.json'),'--output',str(BASE/'evaluation_normal_after'),'--threads','1'],['combine','--results',*[str(BASE/('evaluation_'+p)) for p in ['normal_before','airflow_modified','normal_after']],'--output',str(BASE/'comparison_complete')]]
for name,args in zip(['evaluation_normal_after_console.log','comparison_complete_console.log'],commands):
 with (BASE/name).open('x') as out:r=subprocess.run([sys.executable,str(ROOT/'src/controlled_airflow_test.py'),*args],stdout=out,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError((BASE/name).read_text()[-4000:])
p=json.loads((BASE/'protocol.json').read_text());inv=json.loads((BASE/'preservation_inventory.json').read_text())['files'];before=json.loads((BASE/'normal_after_preflight.json').read_text())['existing_sequence_files_sha256']
changed=[f for f,h in inv.items() if not (ROOT/f).is_file() or sha(ROOT/f)!=h]
phase_changes=[f for f,h in before.items() if not (BASE/f).is_file() or sha(BASE/f)!=h]
source_changes=[f for f,h in p['implementation_sha256'].items() if sha(f)!=h]
assert not changed and not phase_changes and not source_changes,(changed,phase_changes,source_changes)
assert sha(Path(p['frozen_bundle']['directory'])/'pilot_bundle.json')==p['frozen_bundle']['sha256']
assert sha(BASE/'protocol.json')==(BASE/'protocol.sha256').read_text().strip()
with FanPWM(journal_path=BASE/'final_complete_fan_readonly.jsonl') as fan:state=fan.verify(0)
reports=[json.loads((BASE/('evaluation_'+phase)/'summary.json').read_text()) for phase in ['normal_before','airflow_modified','normal_after']]
for report in reports:
 for path,key in [('csv','csv_sha256'),('sidecar','sidecar_sha256'),('session','session_sha256')]:assert sha(report[path])==report[key]
 for name,h in report['artifact_sha256'].items():assert sha(BASE/('evaluation_'+report['phase'])/name)==h
comp=json.loads((BASE/'comparison_complete/comparison.json').read_text());assert comp['status']=='complete'
for f,h in comp['artifact_sha256'].items():assert sha(BASE/'comparison_complete'/f)==h
v={'checked_utc':datetime.now(timezone.utc).isoformat(),'protected_existing_file_count':len(inv),'protected_existing_files_changed':changed,'previous_phase_files_changed':phase_changes,'frozen_implementation_changed':source_changes,'protocol_sha256':sha(BASE/'protocol.json'),'frozen_bundle_sha256':p['frozen_bundle']['sha256'],'final_readback':state,'word_sha256':sha(ROOT/'docs/Akz_Masterarbeit_Bericht(3).docx'),'mechanical_state_after_capture':'not_observed','sequence_status':'three_phases_completed_and_evaluated','no_further_start_planned':True,'automatic_restart':False,'source_and_result_hashes_verified':True,'recordings':[{'phase':r['phase'],'recording_id':r['recording_id'],'csv_sha256':r['csv_sha256'],'summary_sha256':sha(BASE/('evaluation_'+r['phase'])/'summary.json')} for r in reports]}
dump(BASE/'final_complete_verification.json',v)
print(json.dumps({'metrics':{r['phase']:r['metrics'] for r in reports},'rms_comparison':comp['rms_comparison'],'quality':{r['phase']:r['quality'] for r in reports},'pwm':state['pwm_configuration']},ensure_ascii=False,indent=2))
