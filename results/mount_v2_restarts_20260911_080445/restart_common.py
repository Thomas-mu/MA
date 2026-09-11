"""Read-only prerequisites for exactly three individually selected restarts."""
import json
from pathlib import Path
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
PLAN = json.loads((BASE/'plan.json').read_text())
MOUNTING_ID = PLAN['mounting_id']
sys.path.insert(0,str(ROOT/'results/mount_v2_pilot_20260911_072748'))
from pilot_common import validate_safety


def prepare_run(run):
    if run not in (1,2,3):
        raise ValueError('Only three specified runs authorized')
    safety = validate_safety(json.loads((ROOT/PLAN['safety_source']).read_text()), MOUNTING_ID)
    confirmation = json.loads((BASE/f'run{run}_standstill_confirmation.json').read_text())
    required = ('fan_observed_fully_stopped','mounting_unchanged','fan_12v_supply_connected')
    if (confirmation.get('run') != run or confirmation.get('mounting_id') != MOUNTING_ID
            or not confirmation.get('operator_answer') or any(confirmation.get(k) is not True for k in required)):
        raise ValueError('Current explicit standstill confirmation for this run required')
    if confirmation['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        raise ValueError('Confirmation monotonic clock belongs to another boot')
    if confirmation['accepted_monotonic_ns'] > time.monotonic_ns():
        raise ValueError('Confirmation time is in future')
    previous_path = BASE/f'run{run-1}_session.json' if run>1 else ROOT/PLAN['prior_shutdown_source']
    previous = json.loads(previous_path.read_text())
    if previous['status'] != 'completed' or previous['final_readback']['pwm_configuration']['configured_duty_percent'] != 0:
        raise ValueError('Previous run completion and zero readback required; no automatic replacement starts')
    from datetime import datetime
    if datetime.fromisoformat(confirmation['recorded_utc']) <= datetime.fromisoformat(previous['zero_command_completed_utc']):
        raise ValueError('Standstill confirmation must follow previous shutdown')
    return safety,confirmation,previous,previous_path


def mounting_metadata():
    details=json.loads((ROOT/PLAN['mounting_source']).read_text())
    return {'mounting_id':MOUNTING_ID,'mounting':'Two screws at outer stationary fan frame; board oblique; unchanged new mounting',
            'mounting_details_source':PLAN['mounting_source'],
            'attachment_material':details['attachment_material'],'attachment_location':details['location'],
            'attachment_orientation':details['orientation'],
            'safety_confirmation_source':PLAN['safety_source'],'old_measurements_pooled_with_new_reference':False}
