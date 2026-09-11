"""Read-only final control check plus preservation of all pre-existing files."""
from datetime import datetime,timezone
from pathlib import Path
import json
import hashlib
import subprocess
import sys

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fan_pwm import FanPWM


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    output=BASE/'final_verification.json'
    if output.exists():raise FileExistsError(output)
    report=json.loads((BASE/'analysis/report.json').read_text())
    baseline=json.loads((BASE/'baseline.json').read_text())['preserved_file_sha256']
    changed=[name for name,h in baseline.items() if not (ROOT/name).is_file() or digest(ROOT/name)!=h]
    if changed:raise ValueError('Pre-existing files changed: '+repr(changed))
    if any(digest(ROOT/name)!=h for name,h in report['input_sha256'].items()):
        raise ValueError('Analysis input changed')
    if digest(BASE/'analyze_restarts.py')!=report['source_sha256']:raise ValueError('Analysis source changed')
    sessions=[json.loads((BASE/f'run{i}_session.json').read_text()) for i in (1,2,3)]
    for s in sessions:
        assert s['status']=='completed'
        assert s['runner_sha256']==digest(BASE/'run_restart.py')
        assert s['common_source_sha256']==digest(BASE/'restart_common.py')
        assert s['controlled_off_actual_to_command_invocation_s']>=60
    holders=subprocess.run(['fuser','-v','/dev/i2c-1','/dev/gpiochip0','/dev/gpiomem0'],capture_output=True,text=True)
    if holders.returncode!=1 or holders.stdout or holders.stderr:raise RuntimeError('Device use unclear')
    with FanPWM(journal_path=BASE/'final_fan_readback.jsonl') as fan:
        state=fan.verify(0)
    result={'recorded_utc':datetime.now(timezone.utc).isoformat(),'preexisting_files_checked':len(baseline),
            'changed_or_missing':changed,'word_sha256':digest(ROOT/'docs/Akz_Masterarbeit_Bericht(3).docx'),
            'three_completed_recordings':True,'identical_controller_source_for_all_runs':True,
            'identical_nominal_60s_off_time':True,'actual_controlled_off_s':[s['controlled_off_actual_to_command_invocation_s'] for s in sessions],
            'source_and_input_hashes_match':True,'final_control_readback':state,
            'mechanical_standstill_confirmation_file':'final_standstill_confirmation.json' if (BASE/'final_standstill_confirmation.json').exists() else None,
            'device_holders_after_completion':[],'models_trained':False,'anomalies_induced':False}
    with output.open('x') as f:json.dump(result,f,indent=2,ensure_ascii=False)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
