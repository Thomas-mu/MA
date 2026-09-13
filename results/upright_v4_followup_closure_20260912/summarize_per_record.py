"""Post-hoc descriptive per-record counts from unchanged archived decisions."""
from pathlib import Path
import csv,json,hashlib,math
B=Path(__file__).resolve().parent;ROOT=B.parents[1]
SOURCE=ROOT/'results/upright_v4_frozen_airflow_test_20260912_073015'
METHODS=['rms','isolation_forest','tflite_autoencoder']
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 rows=[];sources={}
 for phase,label in [('normal_before',0),('airflow_modified',1),('normal_after',0)]:
  p=SOURCE/f'evaluation_{phase}/scores.csv';sources[str(p.relative_to(ROOT))]=sha(p)
  data=list(csv.DictReader(p.open()));identities=[]
  for method in METHODS:
   group=[r for r in data if r['method']==method];ids=[(r['source_start_index'],r['source_end_index_exclusive'],r['quality_valid']) for r in group];identities.append(ids)
   valid=[r for r in group if r['quality_valid']=='True' and r['decision'] in ['NORMAL','ANOMALY']]
   counts={'tp':0,'fn':0,'fp':0,'tn':0}
   for r in valid:
    assert int(r['label'])==label and r['phase']==phase
    score=float(r['score']);threshold=float(r['threshold']);prediction=int(r['prediction'])
    assert math.isfinite(score) and math.isfinite(threshold) and prediction==int(score>threshold)
    assert r['frozen_bundle_sha256']=='cec1859bfb354bafef77a619e6d2c1ffd85b50787c87595aba9a1e20a80cdae5'
    counts[{(1,1):'tp',(1,0):'fn',(0,1):'fp',(0,0):'tn'}[(label,prediction)]]+=1
   numerator=counts['fp'] if label==0 else counts['tp'];denominator=len(valid)
   rows.append(dict(phase=phase,method=method,recording_id=group[0]['recording_id'],label=label,valid=denominator,invalid=len(group)-denominator,**counts,
       primary_quantity='false_alarm_rate_normal' if label==0 else 'marked_fraction_controlled_changed_state',primary_rate=numerator/denominator if denominator else None,
       precision=None,recall=None,f1=None,accuracy=None,single_class_metrics_note='Only the class-specific primary rate is reported for this homogeneous recording. No general detection score is inferred from a single class. Combined two-class descriptive metrics remain in the unchanged earlier appendix.'))
  assert identities[0]==identities[1]==identities[2]
 expected={'rms':(7,187,1,387),'isolation_forest':(4,190,0,388),'tflite_autoencoder':(0,194,55,333)}
 for m in METHODS:assert tuple(sum(r[k] for r in rows if r['method']==m) for k in ['tp','fn','fp','tn'])==expected[m]
 result=dict(status='explorative_report_completion_no_new_measurement',positive_label='airflow_modified: controlled change, not a proven defect',source_sha256=sources,records=rows,script_sha256=sha(Path(__file__)))
 with (B/'per_record_metrics.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
 with (B/'per_record_metrics.csv').open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 print('Nine per-record method rows; archived combined counts and window identities verified.')
if __name__=='__main__':main()
