"""Single explicitly authorized follow-up; no hardware access in release gate."""
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
PHASES=('normal_followup',)
MOUNTING_ID='fan_upright_position_v4_20260911_103726'
PREVIOUS=ROOT/'results/upright_position_v4_sequence_20260911_104025'
def utc():return datetime.now(timezone.utc).isoformat()
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def persist(path,content):
    tmp=path.with_suffix('.json.tmp')
    with tmp.open('x',encoding='utf-8') as f:
        json.dump(content,f,indent=2,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def release_gate(phase):
    if phase not in PHASES:raise ValueError('Only this follow-up is authorized')
    if any((BASE/(phase+s)).exists() for s in ('_session.json','_fan.jsonl')):raise FileExistsError('No repeat or overwrite')
    release=json.loads((BASE/(phase+'_release.json')).read_text())
    if (release.get('source')!='explicit_user_message' or release.get('released') is not True or release.get('authorized_phases')!=[phase] or release.get('mounting_id')!=MOUNTING_ID or release.get('boot_id')!=Path('/proc/sys/kernel/random/boot_id').read_text().strip() or not isinstance(release.get('accepted_monotonic_ns'),int)):
        raise ValueError('Current explicit release missing')
    previous=json.loads((PREVIOUS/'normal_after_session.json').read_text())
    if previous['status']!='completed' or previous['mounting_id']!=MOUNTING_ID or previous['final_readback']['pwm_configuration']['configured_duty_percent']!=0:raise ValueError('Prior complete capture and zero required')
    stop=json.loads((ROOT/release['standstill_confirmation_source']).read_text())
    if stop.get('mechanical_standstill_user_confirmed') is not True or stop.get('mounting_id')!=MOUNTING_ID:raise ValueError('Prior user standstill confirmation missing')
    if release['accepted_monotonic_ns']<=previous['zero_command_completed_monotonic_ns']:raise ValueError('Release must follow prior shutdown')
    if release.get('external_supply_and_mounting_unchanged_as_instructed') is not True:raise ValueError('Ready conditions missing')
    return release,previous
