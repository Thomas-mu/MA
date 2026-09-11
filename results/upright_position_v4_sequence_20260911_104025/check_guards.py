"""Hardware-free release/order/cleanup checks; synthetic fixtures are not measurements."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from sequence_common import MOUNTING_ID,NEXT_RELEASE,initial_gate,release_gate
from run_phase import execute_capture


class Gates(unittest.TestCase):
    def fixture(self):
        return {'source':'explicit_user_message','released':True,'mounting_id':MOUNTING_ID,
          'boot_id':'test_boot','accepted_monotonic_ns':100,
          'authorized_phases':['standstill','normal_before'],'mechanical_standstill_user_confirmed':True,
          'external_12v_supply_connected':True}

    def test_missing_conditions_and_disconnected_supply_block_initial(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            with self.assertRaises(FileNotFoundError):initial_gate(base,'test_boot')
            release=self.fixture()
            for field in ['mechanical_standstill_user_confirmed','external_12v_supply_connected']:
                bad={**release,field:False}
                (base/'initial_release.json').write_text(json.dumps(bad))
                with self.assertRaises(ValueError):initial_gate(base,'test_boot')
            (base/'initial_release.json').write_text(json.dumps(release))
            initial_gate(base,'test_boot')
            with self.assertRaises(FileNotFoundError):release_gate('normal_before',base,'test_boot')

    def test_quality_mounting_order_and_no_repeats(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);release=self.fixture()
            (base/'initial_release.json').write_text(json.dumps(release))
            still={'status':'completed','mounting_id':MOUNTING_ID,'quality_pass_for_initial_start':False,
                'final_readback':{'pwm_configuration':{'configured_duty_percent':0}}}
            (base/'standstill_session.json').write_text(json.dumps(still))
            with self.assertRaises(ValueError):release_gate('normal_before',base,'test_boot')
            still['quality_pass_for_initial_start']=True
            (base/'standstill_session.json').write_text(json.dumps(still))
            release_gate('normal_before',base,'test_boot')
            before={**still,'zero_command_completed_monotonic_ns':200}
            (base/'normal_before_session.json').write_text(json.dumps(before))
            with self.assertRaises(FileExistsError):release_gate('normal_before',base,'test_boot')
            with self.assertRaises(FileNotFoundError):release_gate('airflow_modified',base,'test_boot')
            next_release={**release,'phase':'airflow_modified','operator_message':NEXT_RELEASE,
                'authorized_phases':['airflow_modified'],'accepted_monotonic_ns':150}
            (base/'airflow_modified_release.json').write_text(json.dumps(next_release))
            with self.assertRaises(ValueError):release_gate('airflow_modified',base,'test_boot')
            next_release['accepted_monotonic_ns']=250
            (base/'airflow_modified_release.json').write_text(json.dumps(next_release))
            release_gate('airflow_modified',base,'test_boot')
            before['mounting_id']='old_horizontal_setup'
            (base/'normal_before_session.json').write_text(json.dumps(before))
            with self.assertRaises(ValueError):release_gate('airflow_modified',base,'test_boot')

    def test_recorder_failure_returns_to_zero_without_restart(self):
        class FakeFan:
            def __init__(self):self.calls=[]
            def set_percent(self,p):self.calls.append(p);return {}
            def stop(self):return self.set_percent(0)
            def verify(self,p):return {'pwm_configuration':{'configured_duty_percent':p}}
        def fail(*args,**kwargs):raise IOError('synthetic capture failure')
        for phase in ('normal_before','airflow_modified','normal_after'):
            fan=FakeFan();session={'phase':phase}
            with contextlib.redirect_stdout(io.StringIO()):
                failure=execute_capture(fan,object(),session,Path('NOT_A_CAPTURE'),{},fail)
            self.assertIsInstance(failure,IOError);self.assertEqual(fan.calls,[75,0])
            self.assertEqual(session['status'],'error')
            self.assertEqual(session['final_readback']['pwm_configuration']['configured_duty_percent'],0)


if __name__=='__main__':unittest.main()
