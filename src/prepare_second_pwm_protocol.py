#!/usr/bin/env python3
"""Freeze a new 50% protocol and history inventory, without bench access/release."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import time
import independent_normal_test as frozen
import prepare_pilot_dataset as preparation
from second_pwm_release import POLICY, PHASES

ROOT=Path(__file__).resolve().parents[1]
DESIGN=ROOT/'results/upright_v4_exploratory_diagnosis_20260912_081728/second_pwm_protocol_design.json'


def prepare(output, data_directory, authorization_text):
    output, data_directory=Path(output).resolve(), Path(data_directory).resolve()
    if output.exists() or data_directory.exists(): raise FileExistsError('No overwrite')
    p=json.loads(DESIGN.read_text())
    old=json.loads((ROOT/'results/upright_v4_frozen_airflow_test_20260912_073015/protocol.json').read_text())
    p.update(status='frozen_awaiting_current_initial_readiness',protocol_id=output.name,
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        frozen_at_utc=datetime.now(timezone.utc).isoformat(),frozen_at_monotonic_ns=time.monotonic_ns(),
        mounting=old['mounting'],planned_runs=PHASES,data_directory=str(data_directory),
        evaluator_sha256=frozen.sha256(ROOT/'src/second_pwm_normal_test.py'),
        release_policy=POLICY,manual_readiness_per_run_required=False,
        current_initial_readiness_required=True,new_runtime_adapter_required=False,
        automation_authorization=dict(source='explicit_user_message',authorized_phases=PHASES,
                                      verbatim_message=authorization_text),
        off_time_note='60 additional seconds from initial readiness, then at least 60 seconds from each software-zero continuation. No new mechanical standstill observation between automated runs; total intervals are measured separately.',
        source_design_sha256=frozen.sha256(DESIGN))
    p['implementation_sha256']={str(q.resolve()):frozen.sha256(q) for q in sorted((ROOT/'src').glob('*.py'))}
    paths=sorted((ROOT/'data').rglob('*.csv'))
    p['excluded_recordings']=dict(csv_paths=[str(q.resolve()) for q in paths],
                                  csv_sha256=[frozen.sha256(q) for q in paths],recording_ids=[q.stem for q in paths])
    p['new_capture_authorized']='sequence_permission_given_but_initial_readiness_pending'
    output.mkdir(parents=True,exist_ok=False)
    (output/'protocol.json').write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n')
    (output/'protocol.sha256').write_text(frozen.sha256(output/'protocol.json')+'\n')
    from second_pwm_normal_test import load_protocol
    load_protocol(output/'protocol.json')
    return p

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True);parser.add_argument('--data-directory',required=True)
    parser.add_argument('--authorization-file',required=True)
    a=parser.parse_args()
    p=prepare(a.output,a.data_directory,Path(a.authorization_file).read_text())
    print(json.dumps({'protocol_id':p['protocol_id'],'status':p['status']}))
