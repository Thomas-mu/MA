"""Explicit release gates for the upright setup; no hardware access on import."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
PHASES=('normal_before','airflow_modified','normal_after')
MOUNTING_ID='fan_upright_position_v4_20260911_103726'
NEXT_RELEASE='Umbau fertig, nächster Lauf freigegeben.'


def utc():return datetime.now(timezone.utc).isoformat()


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def persist(path, content):
    tmp=path.with_suffix('.json.tmp')
    with tmp.open('x',encoding='utf-8') as f:
        json.dump(content,f,indent=2,ensure_ascii=False,allow_nan=False)
        f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)


def require_no_attempt(phase,base=BASE):
    if (base/f'{phase}_session.json').exists() or (base/f'{phase}_fan.jsonl').exists():
        raise FileExistsError('Phase already attempted; no repeat or overwrite')


def require_current_release(release,phase,boot_id=None):
    boot_id=boot_id or Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if (release.get('source')!='explicit_user_message' or release.get('released') is not True
            or release.get('mounting_id')!=MOUNTING_ID or release.get('boot_id')!=boot_id
            or not isinstance(release.get('accepted_monotonic_ns'),int)):
        raise ValueError('Explicit current-setup release with valid host time missing')
    if phase not in release.get('authorized_phases',[]):
        raise ValueError('This phase is not released')


def initial_gate(base=BASE,boot_id=None):
    require_no_attempt('standstill',base)
    release=json.loads((base/'initial_release.json').read_text())
    require_current_release(release,'standstill',boot_id)
    if (release.get('mechanical_standstill_user_confirmed') is not True
            or release.get('external_12v_supply_connected') is not True):
        raise ValueError('Current standstill and connected supply must be explicit before initial sequence')
    return release


def release_gate(phase,base=BASE,boot_id=None):
    if phase not in PHASES:raise ValueError('Unknown phase')
    require_no_attempt(phase,base)
    i=PHASES.index(phase)
    if i==0:
        release=json.loads((base/'initial_release.json').read_text())
        require_current_release(release,phase,boot_id)
        previous=json.loads((base/'standstill_session.json').read_text())
        if release.get('mechanical_standstill_user_confirmed') is not True or release.get('external_12v_supply_connected') is not True:
            raise ValueError('Initial conditions missing')
        if not previous.get('quality_pass_for_initial_start',False):
            raise ValueError('Stillstand reference must pass quality before first start')
    else:
        release=json.loads((base/f'{phase}_release.json').read_text())
        require_current_release(release,phase,boot_id)
        if release.get('operator_message')!=NEXT_RELEASE or release.get('phase')!=phase:
            raise ValueError('New manual-change release for this phase missing')
        previous=json.loads((base/f'{PHASES[i-1]}_session.json').read_text())
        if release['accepted_monotonic_ns']<=previous['zero_command_completed_monotonic_ns']:
            raise ValueError('Release must follow previous shutdown')
    if (previous.get('mounting_id')!=MOUNTING_ID or previous.get('status')!='completed' or
            previous.get('final_readback',{}).get('pwm_configuration',{}).get('configured_duty_percent')!=0):
        raise ValueError('Completed same-setup preceding phase and zero readback required')
    return release,previous
