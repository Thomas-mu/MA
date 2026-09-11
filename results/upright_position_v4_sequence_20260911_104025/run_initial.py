"""Authorized initial block only: standstill, then first normal start, then pause."""
import subprocess
import sys
from sequence_common import BASE,ROOT,initial_gate,release_gate


def main():
    initial_gate()
    # Each subprocess is run once. Failure prevents the normal start, with no retry.
    result=subprocess.run([sys.executable,str(BASE/'run_standstill.py')],cwd=ROOT)
    if result.returncode:raise SystemExit(result.returncode)
    release_gate('normal_before')
    result=subprocess.run([sys.executable,str(BASE/'run_phase.py'),'--phase','normal_before'],cwd=ROOT)
    raise SystemExit(result.returncode)


if __name__=='__main__':main()
