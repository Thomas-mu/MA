#!/usr/bin/env python3
"""Three preauthorized starts, abort on first failure, no automatic replacement.

A current initial physical readiness release must already exist. Later off
intervals use read-back software zero, not an invented visual confirmation.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone
from second_pwm_release import PHASES, POLICY
from run_second_pwm_normal_test import confirmed_zero, digest


def run_sequence(protocol_path, *, run_process=subprocess.run):
    protocol_path=Path(protocol_path).resolve()
    base=protocol_path.parent
    p=json.loads(protocol_path.read_text())
    if p.get('release_policy')!=POLICY or digest(protocol_path)!=protocol_path.with_suffix('.sha256').read_text().strip():
        raise ValueError('Explicit, frozen unattended protocol required')
    # Never resume an attempted sequence automatically (including a failed start).
    if any((base/(phase+suffix)).exists() for phase in PHASES for suffix in ('_session.json','_fan.jsonl')):
        raise ValueError('Sequence already attempted; no automatic replacement')
    for i,phase in enumerate(PHASES):
        release_path=base/(phase+'_release.json')
        if i:
            previous=json.loads((base/(PHASES[i-1]+'_session.json')).read_text())
            if previous.get('status')!='completed' or not confirmed_zero(previous.get('final_readback',{})):
                raise ValueError('Predecessor incomplete or zero unverified; sequence aborted')
            initial=json.loads((base/(PHASES[0]+'_release.json')).read_text())
            release=dict(initial,phase=phase,authorized_phases=[phase],
                source='authorized_sequence_continuation',mechanical_standstill_confirmed=None,
                software_zero_confirmed=True,accepted_utc=datetime.now(timezone.utc).isoformat(),
                accepted_monotonic_ns=time.monotonic_ns(),
                sequence_initial_release_sha256=digest(base/(PHASES[0]+'_release.json')),
                observation_note='No new physical observation; unchanged setup under explicit unattended authorization')
            with release_path.open('x') as handle:json.dump(release,handle,indent=2)
        result=run_process([sys.executable,str(Path(__file__).with_name('run_second_pwm_normal_test.py')),
            '--protocol',str(protocol_path),'--phase',phase,'--release',str(release_path)],check=False)
        if result.returncode!=0:
            raise RuntimeError(f'{phase} failed; no further start or retry')
        previous=json.loads((base/(phase+'_session.json')).read_text())
        if previous.get('status')!='completed' or not confirmed_zero(previous.get('final_readback',{})):
            raise RuntimeError('Successful exit without completed capture/zero evidence; abort')
    return {'status':'completed','runs':PHASES,'mechanical_stop_observed_at_end':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',required=True)
    print(json.dumps(run_sequence(parser.parse_args().protocol)))
