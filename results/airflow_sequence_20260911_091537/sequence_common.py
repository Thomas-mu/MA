"""Session-local definitions and explicit release gates; importing does not access hardware."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
PHASES = ('normal_before', 'airflow_modified', 'normal_after')
FIRST_RELEASE = 'Normalaufbau bereit, Versorgung angeschlossen, erster Lauf freigegeben.'
NEXT_RELEASE = 'Umbau fertig, nächster Lauf freigegeben.'
MOUNTING_ID = 'adxl345_mount_v2_provisional_20260911_072748'


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def persist(path, content):
    """Update this attempt's new journal only, never an earlier attempt."""
    temp = path.with_suffix('.json.tmp')
    with temp.open('x', encoding='utf-8') as f:
        json.dump(content, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def release_gate(phase, base=BASE, boot_id=None):
    if phase not in PHASES:
        raise ValueError('Unknown phase')
    i = PHASES.index(phase)
    if (base/f'{phase}_session.json').exists() or (base/f'{phase}_fan.jsonl').exists():
        raise FileExistsError('An attempt exists; no automatic repeat or overwrite')
    release_path = base/f'{phase}_release.json'
    release = json.loads(release_path.read_text())
    expected = FIRST_RELEASE if i == 0 else NEXT_RELEASE
    if (release.get('phase') != phase or release.get('source') != 'explicit_user_message'
            or release.get('operator_message') != expected or release.get('released') is not True):
        raise ValueError('Explicit user release for this phase is missing')
    if boot_id is None:
        boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if release.get('boot_id') != boot_id:
        raise ValueError('Host reboot: monotonic release time requires review, never auto-start')
    if not isinstance(release.get('accepted_monotonic_ns'), int):
        raise ValueError('Release acceptance time missing')
    previous = None
    if i:
        previous = json.loads((base/f'{PHASES[i-1]}_session.json').read_text())
        if (previous.get('status') != 'completed' or
                previous.get('final_readback', {}).get('pwm_configuration', {}).get('configured_duty_percent') != 0):
            raise ValueError('Preceding capture and zero readback must be complete')
        if release['accepted_monotonic_ns'] <= previous['zero_command_completed_monotonic_ns']:
            raise ValueError('Release must follow the preceding shutdown')
    return release, previous
