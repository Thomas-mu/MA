#!/usr/bin/env python3
"""Recompute source integrity and model decisions for the Word evidence audit."""
from pathlib import Path
import sys
import hashlib
import json
from collections import Counter
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import common_comparison as common
from replay_phone_pilot import read_rows, extract_windows, phase_of, RUNS

SOURCE=ROOT/'results/phone_vibration_pilot_20260919'
OUT=ROOT/'results/phone_vibration_word_revision_20260919'


def main():
    plan=common.read_json(SOURCE/'plan.json')
    directory=SOURCE/'bundle'
    assert common.sha256(directory/'bundle.json')==plan['bundle_sha256']
    bundle=common.load_bundle(directory)
    scorers={m:common.scorer(m,bundle,directory,runtime='litert',threads=1)[0] for m in common.METHODS}
    replay=common.read_json(SOURCE/'replay_v1/summary.json')
    jointsummary=common.read_json(SOURCE/'presentation_v3_joint/joint_summary.json')
    report={'bundle_sha256':plan['bundle_sha256'],'source_sha256':{},'trials':{},'hardware_access':False,'thresholds_changed':False}
    for trial in (*RUNS,'all_methods_01'):
        joint=trial=='all_methods_01'
        path=SOURCE/('joint_trials' if joint else 'trials')/trial
        meta=common.read_json(path/'run.json')
        assert meta['status'] in ['stopped','completed'] and not meta.get('cleanup_errors')
        assert meta['bundle_sha256']==plan['bundle_sha256']
        for filename,digest in meta['file_sha256'].items():
            assert common.sha256(path/filename)==digest,(trial,filename)
            report['source_sha256'][str((path/filename).relative_to(ROOT))]=digest
        rows=read_rows(path/'decisions.csv')
        base=[r for r in rows if r['method']=='tflite_autoencoder'] if joint else rows
        windows,partial=extract_windows(read_rows(path/'raw.csv'),base,bundle['window_size'])
        assert partial==meta['acquisition']['partial_samples_saved']
        cues=[json.loads(s) for s in (path/'cues.jsonl').read_text().splitlines()]
        starts=[c['monotonic_ns'] for c in cues if c['event']=='call_requested']
        ends=[c['monotonic_ns'] for c in cues if c['event']=='end_reported']
        assert len(starts)==len(ends)==1
        entry={'windows':len(windows),'partial_samples':partial,'phases':dict(Counter(phase_of(r,starts[0],ends[0]) for r in base)),'methods':{}}
        for method,function in scorers.items():
            compared=0; maximum=0.; alarms=[]
            rr=[r for r in rows if r['method']==method] if joint else base
            for raw,row in zip(windows,rr):
                if joint:assert hashlib.sha256(raw.tobytes()).hexdigest()==row['input_sha256']
                score,prediction=common.classify_raw(raw,bundle['scaler'],function,bundle['thresholds'][method]['value'])
                if joint or method==meta['method']:
                    delta=abs(score-float(row['score']));maximum=max(maximum,delta)
                    assert delta==0 and prediction==int(row['prediction'])
                    compared+=1
                if prediction:alarms.append(int(row['window']))
            expected=jointsummary['methods'][method] if joint else replay['recordings'][trial]['methods'][method]
            assert alarms[0]==expected['first_alarm_window_between_cues']
            assert len(alarms)==expected['alarm_windows' if joint else 'alarm_windows_total']
            result={'first_alarm_window':alarms[0],'alarm_windows':len(alarms),'original_decisions_reproduced':compared,'maximum_score_difference':maximum if compared else None}
            if joint:
                times=np.array([float(r['window_to_decision_ms']) for r in rr])
                first=min(int(r['decision_ns']) for r in rr if r['prediction']=='1')
                assert first==expected['first_alarm_decision_ns']
                result.update(first_alarm_decision_ns=first,window_to_decision_p99_ms=float(np.percentile(times,99)),window_to_decision_maximum_ms=float(max(times)))
            entry['methods'][method]=result
        if joint:
            earliest=min(v['first_alarm_decision_ns'] for v in entry['methods'].values())
            for method,result in entry['methods'].items():
                lag=(result['first_alarm_decision_ns']-earliest)/1e6
                assert lag==jointsummary['methods'][method]['first_alarm_output_after_earliest_ms']
                result['relative_first_output_ms']=lag
        report['trials'][trial]=entry
    # Preserve all attempts; count rather than silently omit invalid windows.
    report['all_attempts']={}
    for path in sorted((SOURCE/'trials').iterdir()):
        if not (path/'decisions.csv').is_file():continue
        rows=read_rows(path/'decisions.csv')
        report['all_attempts'][path.name]={'windows':len(rows),'alarm_windows':sum(r['prediction']=='1' for r in rows),'invalid_windows':sum(r['prediction'] not in ['0','1'] for r in rows)}
    report['total_original_decisions_reproduced']=sum(m['original_decisions_reproduced'] for t in report['trials'].values() for m in t['methods'].values())
    assert report['total_original_decisions_reproduced']==1205
    report['status']='passed'
    (OUT/'evidence_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'decisions_reproduced':report['total_original_decisions_reproduced'],'joint':report['trials']['all_methods_01']},indent=2))


if __name__=='__main__':main()
