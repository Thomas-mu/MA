"""Shared bookkeeping and fail-closed start gate for the new mounting pilot."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
MOUNTING_ID = json.loads((BASE / 'mounting_version_initial.json').read_text())['mounting_id']
SAFETY_FIELDS = ('power_disconnected_during_checks', 'rotor_clear', 'cables_safely_routed',
                 'no_electrical_short_circuits', 'sensor_board_firm', 'sensor_board_not_bent')


def utc():
    return datetime.now(timezone.utc).isoformat()


def persist(path, obj):
    temporary = path.with_suffix('.json.tmp')
    with temporary.open('x', encoding='utf-8') as handle:
        json.dump(obj, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def validate_safety(confirmation, mounting_id=MOUNTING_ID):
    if confirmation.get('mounting_id') != mounting_id or not confirmation.get('operator_answer'):
        raise ValueError('Explicit safety confirmation for this mounting version required')
    missing = [key for key in SAFETY_FIELDS if confirmation.get(key) is not True]
    if missing:
        raise ValueError('Incomplete power-disconnected safety checks: ' + ', '.join(missing))
    return confirmation


def require_safety():
    return validate_safety(json.loads((BASE / 'safety_confirmation.json').read_text()))


def require_standstill(phase):
    obj = json.loads((BASE / f'{phase}_standstill_confirmation.json').read_text())
    if (obj.get('mounting_id') != MOUNTING_ID or obj.get('fan_observed_fully_stopped') is not True
            or not obj.get('operator_answer')):
        raise ValueError('Current full mechanical standstill confirmation for this mounting required')
    if obj.get('fan_12v_supply_connected') is not True:
        raise ValueError('Reference requires documented connected12V supply at verified0% for comparable before/after conditions')
    return obj


def mounting_metadata():
    details_path = BASE / 'mounting_details.json'
    details = json.loads(details_path.read_text()) if details_path.exists() else {}
    return {'mounting_id': MOUNTING_ID,
            'mounting': 'New provisional ADXL345 attachment changed by user; separate from previous mounting version.',
            'mounting_details': details,
            'mounting_version_initial': str((BASE / 'mounting_version_initial.json').relative_to(ROOT)),
            'mounting_unchanged_user_instruction': True,
            'old_measurements_pooled_with_new_reference': False}
