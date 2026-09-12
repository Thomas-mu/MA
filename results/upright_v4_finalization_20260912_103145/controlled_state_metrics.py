#!/usr/bin/env python3
"""Supplementary descriptive metrics of EXISTING labels, no model execution.
Positive label is controlled airflow modification, never a demonstrated defect.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import csv,json,hashlib
B=Path(__file__).resolve().parent
S=B.parent/'upright_v4_frozen_airflow_test_20260912_073015'
source={};all_rows=[]
for phase in ['normal_before','airflow_modified','normal_after']:
 path=S/f'evaluation_{phase}/scores.csv'
 source[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
 rows=list(csv.DictReader(path.open()))
 assert len(rows)==582
 assert {r['phase'] for r in rows}=={phase}
 assert {r['label'] for r in rows}==({'1'} if phase=='airflow_modified' else {'0'})
 assert all(r['quality_valid']=='True' and r['decision'] in ['NORMAL','ANOMALY'] for r in rows)
 assert {r['protocol_sha256'] for r in rows}=={'5375fda6aff23f8f3c7651ac25e638a0dbbfbb52b49a33611e528bade3644a5d'}
 all_rows+=rows
results=[]
for method in ['rms','isolation_forest','tflite_autoencoder']:
 rows=[r for r in all_rows if r['method']==method];assert len(rows)==582
 assert len({(r['recording_id'],r['window_index_in_recording']) for r in rows})==582
 counts=Counter((int(r['label']),int(r['prediction'])) for r in rows)
 tp,fn,fp,tn=counts[1,1],counts[1,0],counts[0,1],counts[0,0]
 assert tp+fn==194 and fp+tn==388
 result=dict(method=method,true_positive=tp,false_negative=fn,false_positive=fp,true_negative=tn,
             valid_windows=582,invalid_windows=0,positive_windows=194,negative_windows=388,
             precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn),f1=2*tp/(2*tp+fp+fn),
             false_positive_rate=fp/(fp+tn),accuracy=(tp+tn)/582)
 results.append(result)
out=dict(created_utc=datetime.now(timezone.utc).isoformat(),analysis_status='post_hoc_descriptive_state_label_counts',
         positive_class='airflow_modified, a controlled changed operating condition, NOT a proven defect',
         negative_class='normal, before and after from the SAME complete sequence',
         independent_positive_recordings=1,independent_sequence_replicates=1,
         note='Existing labels, predictions, thresholds and [180,300) selection unchanged. No new inference, calibration or exclusion. Dependent windows are not independent replicates. These are descriptive metrics of this one sequence; no general defect recall/F1 is claimed.',
         source_sha256=source,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),results=results)
with (B/'controlled_state_descriptive_metrics.json').open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
with (B/'controlled_state_descriptive_metrics.csv').open('x') as f:
 w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
print(json.dumps(results,indent=2))
