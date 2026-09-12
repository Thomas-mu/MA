#!/usr/bin/env python3
"""Separate frozen 50%-NORMAL evaluation and predeclared six-run 75% comparison.
Run only once all three recordings finished; never changes PWM or sources.
"""
from pathlib import Path
from datetime import datetime,timezone
import json,sys,hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import second_pwm_normal_test as evaluation
import controlled_airflow_test as diagnostic
import pilot_method_comparison as pilot
BASE=Path(__file__).resolve().parent

def read(path):return json.loads(Path(path).read_text())
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False)

def main():
    protocol=BASE/'protocol.json'
    p,phash,bundle,directory=evaluation.load_protocol(protocol)
    sessions=[read(BASE/(phase+'_session.json')) for phase in p['planned_runs']]
    assert all(s['status']=='completed' for s in sessions), 'All three runs must complete first'
    outputs=[BASE/('evaluation_'+phase) for phase in p['planned_runs']]
    assert not any(out.exists() for out in outputs), 'Evaluation already attempted; no overwrite'
    assert not (BASE/'comparison_50_vs_75').exists()
    reports=[]; all_rms=[]; acquisition=[]
    for session,out in zip(sessions,outputs,strict=True):
        csv=Path(session['csv']);sidecar=csv.with_suffix('.json')
        phase=session['phase'];journal=BASE/(phase+'_session.json')
        report=evaluation.evaluate_recording(csv,sidecar,protocol,journal,out)
        recording=evaluation.load_test_recording(csv,sidecar,protocol,journal)
        blocks=diagnostic.rms_5s(recording)
        description=diagnostic.interval_description(blocks)
        all_rms.extend(blocks)
        reports.append(report)
        acquisition.append(dict(phase=phase,recording_id=report['recording_id'],
            command_utc=session['command_invocation_utc'],first_xyz_utc_estimate=session['timing']['first_xyz_utc_estimate'],
            first_xyz_delay_s=session['timing']['first_xyz_after_command_invocation_s'],
            additional_off_from_release_s=session['additional_off_from_release_actual_s'],
            total_off_since_previous_zero_s=session['total_off_since_previous_zero_s'],
            zero_command_completed_utc=session['zero_command_completed_utc'],
            final_readback=session['final_readback'],quality=report['quality'],rms_5s_late=description,
            mechanical_standstill_before_start=session['user_release']['mechanical_standstill_confirmed'],
            release_source=session['user_release']['source'],physical_lost_samples=None))
    combined=evaluation.combine_results(outputs,BASE/'comparison_50_only')
    out=BASE/'comparison_50_vs_75';out.mkdir()
    scores=[];baseline_sources=[];table=[]
    for report in reports:
        own=read(BASE/('evaluation_'+report['phase'])/'scores.json')
        scores.extend(dict(r,pwm_percent=50,display_run=report['phase']) for r in own)
        table.extend(dict(pwm_percent=50,run=report['phase'],recording_id=report['recording_id'],method=m,**stats) for m,stats in report['metrics'].items())
    baseline_rows=[]
    for anchor in p['baseline_75_normal_recordings']:
        assert digest(anchor['csv'])==anchor['csv_sha256'] and digest(anchor['session'])==anchor['session_sha256']
        candidates=[]
        for path in Path(anchor['session']).parent.rglob('summary.json'):
            old=read(path)
            if old.get('recording_id')==anchor['recording_id']:candidates.append((path,old))
        assert len(candidates)==1, 'Ambiguous baseline result'
        path,old=candidates[0]
        assert old['frozen_bundle_sha256']==p['frozen_bundle']['sha256']
        assert old['condition']=='normal' and old['csv_sha256']==anchor['csv_sha256']
        for name,h in old['artifact_sha256'].items():assert digest(path.parent/name)==h
        own=read(path.parent/'scores.json')
        assert all(r['label']==0 and r['recording_id']==anchor['recording_id'] for r in own)
        # Earlier airflow adapter uses a phase name in state, while NORMAL is
        # explicitly confirmed by condition/label. Canonicalize only new report rows.
        own=[dict(r,archived_state=r['state'],state='normal') for r in own]
        metrics=evaluation.normal_metrics(own)
        for m,stats in metrics.items():
            assert stats['valid_windows']==old['metrics'][m]['valid_windows']
            assert stats['false_alarms']==old['metrics'][m]['false_alarms']
        baseline_rows.extend(own)
        display=anchor['name']+' (75 %)'
        scores.extend(dict(r,pwm_percent=75,display_run=display) for r in own)
        table.extend(dict(pwm_percent=75,run=display,recording_id=anchor['recording_id'],method=m,**stats) for m,stats in metrics.items())
        baseline_sources.append(dict(**anchor,summary=str(path),summary_sha256=digest(path),scores_sha256=digest(path.parent/'scores.json')))
    pooled75=evaluation.normal_metrics(baseline_rows)
    for pwm,metrics in ((50,combined['pooled']),(75,pooled75)):
        table.extend(dict(pwm_percent=pwm,run='pooled',recording_id='whole_recordings_pooled',method=m,**stats) for m,stats in metrics.items())
    pd.DataFrame(table).to_csv(out/'false_alarm_comparison.csv',index=False,mode='x')
    pd.DataFrame(scores).to_csv(out/'all_scores.csv',index=False,mode='x')
    pd.DataFrame(all_rms).to_csv(out/'rms_5s.csv',index=False,mode='x')
    write(out/'acquisition_quality.json',acquisition)
    write(out/'baseline_provenance.json',baseline_sources)
    write(out/'comparison.json',dict(pwm50_runs=3,pwm75_historical_runs=6,pooled50=combined['pooled'],pooled75=pooled75,
          no_training=True,no_threshold_change=True,selection_seconds=[180,300],model_window_xyz=128,step_xyz=128,
          physical_losses_unknown=True,mechanical_stop_between_automated_runs_not_observed=True,
          contemporaneous_comparison=False,anomaly_recall_or_f1_evaluated=False))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,4),sharey=True)
    colors={50:'#0072B2',75:'#D55E00'}
    for ax,m in zip(axes,pilot.METHODS,strict=True):
        for x,pwm in enumerate((50,75)):
            sub=[r for r in table if r['method']==m and r['pwm_percent']==pwm and r['run']!='pooled']
            rates=[100*r['false_alarm_rate_among_valid_normal_windows'] if r['false_alarm_rate_among_valid_normal_windows'] is not None else np.nan for r in sub]
            ax.scatter(x+np.linspace(-.12,.12,len(rates)),rates,color=colors[pwm],s=45,label=f'{pwm} %: ganze Läufe')
            pooled=next(r for r in table if r['method']==m and r['pwm_percent']==pwm and r['run']=='pooled')
            rate=pooled['false_alarm_rate_among_valid_normal_windows']
            if rate is not None:ax.hlines(100*rate,x-.2,x+.2,color=colors[pwm],linewidth=2)
        ax.set_xticks([0,1],['50 %\n3 neue Läufe','75 %\n6 frühere Läufe']);ax.set_title(m);ax.grid(axis='y',alpha=.25)
        ax.set_ylim(bottom=-1)
    axes[0].set_ylabel('Fehlalarmrate unter gültigen Normalfenstern (%)')
    fig.suptitle('Eingefrorenes v4-Paket: Punkte = vollständige Läufe, Striche = gepoolte Fenster\nNicht zeitgleicher Vergleich; Fenster sind keine unabhängigen Versuchsreplikate',fontsize=10)
    fig.tight_layout()
    for ext in ('png','pdf'):fig.savefig(out/('false_alarm_comparison.'+ext),dpi=150)
    plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(11,7))
    for phase in p['planned_runs']:
        blocks=[r for r in all_rms if r['phase']==phase]
        x=[r['midpoint_since_command_s'] for r in blocks];y=[r['vector_ac_rms_mg'] for r in blocks]
        for ax in axes:ax.plot(x,y,label=phase)
    axes[0].set_xlim(0,300);axes[0].axvspan(180,300,color='gray',alpha=.12)
    axes[1].set_xlim(180,300)
    for ax in axes:ax.set_ylabel('Vektor-AC-RMS (mg)');ax.set_xlabel('Sekunden seit Stellbefehl');ax.grid(alpha=.25);ax.legend()
    fig.suptitle('50 % PWM: 5-s-Diagnostik mit achsenweiser Mittelwertentfernung\nDiese Werte sind keine 128er-Modellscores')
    fig.tight_layout()
    for ext in ('png','pdf'):fig.savefig(out/('rms_5s.'+ext),dpi=150)
    plt.close(fig)
    write(BASE/'evaluation_completion.json',dict(status='completed',completed_utc=datetime.now(timezone.utc).isoformat(),
        protocol_sha256=phash,script_sha256=digest(__file__),outputs=[str(x) for x in outputs],
        comparison=str(out),artifacts_sha256={str(f.relative_to(BASE)):digest(f) for f in out.iterdir() if f.is_file()}))
    print(json.dumps({'pooled50':combined['pooled'],'pooled75':pooled75,'acquisition':acquisition},indent=2))

if __name__=='__main__':main()
