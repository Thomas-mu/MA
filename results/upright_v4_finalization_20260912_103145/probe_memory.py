#!/usr/bin/env python3
"""Exploratory memory diagnosis, after timed trials; never uses hardware.
This is deliberately NOT a latency benchmark or new independent test.
"""
from pathlib import Path
import sys,json,gc,time,tracemalloc,hashlib
B=Path(__file__).resolve().parent;ROOT=B.parents[1];sys.path.insert(0,str(ROOT/'src'))
import pandas as pd
import psutil
from pilot_stream_final import WindowAssembler
from pilot_runtime_final import FrozenEngine


def main():
 protocol=json.loads((B/'runtime_evidence/protocol.json').read_text())
 for spec in protocol['trials']:
  assert json.loads((B/'runtime_evidence'/(spec['id']+'_session.json')).read_text())['status']=='completed'
 frame=pd.read_csv(protocol['replay_csv'],float_precision='round_trip');rows=frame.to_dict('records')
 engine=FrozenEngine(protocol['bundle_directory'],['rms']);engine.warmup()
 process=psutil.Process();gc.collect();tracemalloc.start(5)
 snapshots=[];samples=[];started=time.monotonic_ns()
 def sample(label,windows):
  current,peak=tracemalloc.get_traced_memory()
  samples.append(dict(phase=label,elapsed_s=(time.monotonic_ns()-started)/1e9,windows=windows,
                      rss_bytes=process.memory_info().rss,traced_current_bytes=current,traced_peak_bytes=peak,
                      gc_count=gc.get_count(),tracked_objects=len(gc.get_objects())))
 sample('before',0);snapshots.append(tracemalloc.take_snapshot())
 for repeat in range(1,7):
  a=WindowAssembler(protocol['replay_command_ns']);n=0
  for row in rows:
   window=a.push(row)
   if window is not None:
    decisions=engine.score(window);n+=1
    assert len(decisions)==1 and decisions[0]['decision']!='INVALID'
  assert n==194
  del a,window,decisions
  sample('after_pass_'+str(repeat),repeat*n)
  print(samples[-1],flush=True)
 snapshots.append(tracemalloc.take_snapshot())
 collected=gc.collect();sample('after_explicit_gc',6*194);snapshots.append(tracemalloc.take_snapshot())
 diffs={}
 for name,snap in [('before_gc',snapshots[1]),('after_gc',snapshots[2])]:
  diffs[name]=[dict(size_diff=v.size_diff,count_diff=v.count_diff,traceback=[str(x) for x in v.traceback]) for v in snap.compare_to(snapshots[0],'traceback')[:20]]
 result=dict(purpose='exploratory_memory_probe_not_timing_evidence',scope='six unpaced passes through same stored source, WindowAssembler plus RMS engine; excludes queue, journal and actual sensor',
             no_new_sensor_measurement=True,no_model_change=True,tracemalloc_enabled=True,normal_gc_enabled=gc.isenabled(),explicit_gc_collected_objects=collected,
             source_csv=protocol['replay_csv'],source_sha256=protocol['replay_csv_sha256'],samples=samples,top_allocation_differences=diffs,
             warning='Tracemalloc adds CPU/RAM overhead; these values must not be mixed with timed runtime evidence. RSS retention alone cannot prove an unbounded leak.',
             script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
 with (B/'memory_probe.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')


if __name__=='__main__':main()
