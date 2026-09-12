"""Optional unattended continuation policy; never invent a mechanical observation.

Activated only by a protocol that records the user's explicit permission for
all three planned starts/stops. Initial physical readiness remains required.
"""
PHASES=['normal_pwm50_01','normal_pwm50_02','normal_pwm50_03']
POLICY='initial_readiness_then_authorized_software_off_timer'

def readiness_fields(protocol, release):
    automated = protocol.get('release_policy') == POLICY
    first = release.get('phase') == PHASES[0]
    if automated:
        auth=protocol.get('automation_authorization',{})
        if auth.get('source')!='explicit_user_message' or auth.get('authorized_phases')!=PHASES or not auth.get('verbatim_message'):
            raise ValueError('Explicit sequence authorization is missing')
    source='authorized_sequence_continuation' if automated and not first else 'explicit_user_message'
    if release.get('source')!=source:
        raise ValueError('Release source does not match authorization policy')
    expected={'ready_normal_no_plate':True,'external_supply_connected':True,'mounting_unchanged':True}
    if automated and not first:
        expected.update(mechanical_standstill_confirmed=None,software_zero_confirmed=True)
    else:
        expected['mechanical_standstill_confirmed']=True
    return expected
