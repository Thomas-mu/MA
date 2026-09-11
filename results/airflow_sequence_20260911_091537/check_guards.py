"""Hardware-free checks of release gates and failure shutdown, not measurement data."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
import pandas as pd
from sequence_common import FIRST_RELEASE, NEXT_RELEASE, release_gate
from run_phase import execute_capture


class Gates(unittest.TestCase):
    def test_missing_release_never_passes(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                release_gate('normal_before', Path(d), 'test_boot')

    def test_release_order_and_consumption(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            release = {'phase':'normal_before','source':'explicit_user_message',
                       'operator_message':FIRST_RELEASE,'released':True,
                       'boot_id':'test_boot','accepted_monotonic_ns':200}
            (base/'normal_before_release.json').write_text(json.dumps(release))
            release_gate('normal_before',base,'test_boot')
            previous={'status':'completed','zero_command_completed_monotonic_ns':300,
                      'final_readback':{'pwm_configuration':{'configured_duty_percent':0}}}
            (base/'normal_before_session.json').write_text(json.dumps(previous))
            with self.assertRaises(FileExistsError):release_gate('normal_before',base,'test_boot')
            release.update(phase='airflow_modified',operator_message=NEXT_RELEASE)
            (base/'airflow_modified_release.json').write_text(json.dumps(release))
            with self.assertRaises(ValueError):release_gate('airflow_modified',base,'test_boot')
            release['accepted_monotonic_ns']=400
            (base/'airflow_modified_release.json').write_text(json.dumps(release))
            release_gate('airflow_modified',base,'test_boot')
            with self.assertRaises(ValueError):release_gate('airflow_modified',base,'other_boot')
            previous['status']='error'
            (base/'normal_before_session.json').write_text(json.dumps(previous))
            with self.assertRaises(ValueError):release_gate('airflow_modified',base,'test_boot')

    def test_failure_and_success_return_to_zero_without_restart(self):
        class FakeFan:
            def __init__(self):self.commands=[]
            def set_percent(self,p):
                self.commands.append(p)
                return {'pwm_configuration':{'configured_duty_percent':p}}
            def stop(self):return self.set_percent(0)
            def verify(self,p):return {'pwm_configuration':{'configured_duty_percent':p}}
        for error in (None, IOError('synthetic recorder failure'), KeyboardInterrupt('synthetic signal')):
            with self.subTest(error=repr(error)):
                fan=FakeFan();session={'phase':'normal_before'}
                def recorder(*args,**kwargs):
                    if error:raise error
                    now=time.monotonic_ns()
                    df=pd.DataFrame({'host_monotonic_ns':[now,now+1]})
                    df.attrs['report']={'status':'completed','simulation_only':True}
                    return df
                with contextlib.redirect_stdout(io.StringIO()):
                    failure=execute_capture(fan,object(),session,Path('NOT_A_REAL_CAPTURE'),{},recorder)
                self.assertEqual(fan.commands,[75,0])
                self.assertEqual(session['final_readback']['pwm_configuration']['configured_duty_percent'],0)
                self.assertIs(failure,error)
                self.assertEqual(session['status'],'completed' if error is None else 'error')


if __name__=='__main__':unittest.main()
