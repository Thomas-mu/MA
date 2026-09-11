"""Offline review: within-run trends and independent recomputation of timebase."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
SOURCE=ROOT/'results/mount_v2_restarts_20260911_080445'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    if (BASE/'review.json').exists():raise FileExistsError('Preserve existing analysis')
    records=[]; inputs={}; all_blocks=[]; trend_rows=[]; rate_rows=[]
    for run in (1,2,3):
        session_path=SOURCE/f'run{run}_session.json';session=json.loads(session_path.read_text())
        csv=ROOT/session['csv'];meta_path=csv.with_suffix('.json');meta=json.loads(meta_path.read_text())
        assert session['status']==meta['status']=='completed' and digest(csv)==meta['csv_sha256']
        for p in (session_path,csv,meta_path):inputs[str(p.relative_to(ROOT))]=digest(p)
        d=pd.read_csv(csv,dtype={'host_monotonic_ns':'int64','sample_index':'int64'})
        xyz=d[['x_g','y_g','z_g']].to_numpy();ns=d.host_monotonic_ns.to_numpy();t=(ns-ns[0])/1e9
        assert np.isfinite(xyz).all() and (np.diff(ns)>0).all()
        assert np.array_equal(d.sample_index,np.arange(len(d)))
        assert np.allclose(d.timestamp_s-d.timestamp_s.iloc[0],t,rtol=0,atol=1e-10)
        assert np.allclose(d.sensor_time_estimate_s,np.arange(len(d))/200,rtol=0,atol=1e-12)
        assert all(d[k].dtype==bool for k in ('gap','overrun','saturated'))
        blocks=[]
        for start in range(0,300,5):
            mask=(t>=start)&(t<start+5);a=xyz[mask];v=a-a.mean(axis=0)
            block={'run':run,'start_s':start,'end_s':start+5,'xyz_points':int(mask.sum()),
                   'vector_ac_rms_mg':float(np.sqrt(np.mean(np.sum(v*v,axis=1)))*1000),
                   'gap':int(d.gap[mask].sum()),'overrun':int(d.overrun[mask].sum()),'saturated':int(d.saturated[mask].sum())}
            blocks.append(block)
        all_blocks+=blocks
        selected=blocks[36:60];x=np.array([b['start_s']+2.5 for b in selected]);y=np.array([b['vector_ac_rms_mg'] for b in selected])
        slope,intercept=np.polyfit(x,y,1);res=y-(slope*x+intercept)
        pair_slopes=[(y[j]-y[i])/(x[j]-x[i]) for i in range(24) for j in range(i+1,24)]
        loo=[float(60*np.polyfit(np.delete(x,i),np.delete(y,i),1)[0]) for i in range(24)]
        trend={'run':run,'mean_mg':float(y.mean()),'std_mg':float(y.std()),'ols_mg_per_min':float(slope*60),
               'theil_sen_mg_per_min':float(np.median(pair_slopes)*60),'fitted_change_120s_mg':float(slope*120),
               'fitted_change_percent':float(100*slope*120/y.mean()),'r2':float(1-np.var(res)/np.var(y)),
               'residual_std_mg':float(res.std()),'residual_lag1_correlation':float(np.corrcoef(res[:-1],res[1:])[0,1]),
               'loo_slope_min':min(loo),'loo_slope_max':max(loo),'four_30s_means_mg':[float(y[i:i+6].mean()) for i in range(0,24,6)],
               'last60_minus_first60_mg':float(y[12:].mean()-y[:12].mean()),
               'last60_vs_first60_percent':float(100*(y[12:].mean()/y[:12].mean()-1)),
               'positive_steps':int((np.diff(y)>0).sum()),'negative_steps':int((np.diff(y)<0).sum())}
        trend_rows.append(trend)
        index=np.arange(len(d));slope_t,intercept_t=np.polyfit(index,t,1);time_res=t-(slope_t*index+intercept_t)
        for start in range(0,300,30):
            mask=(t>=start)&(t<start+30);q=ns[mask]
            rate_rows.append({'run':run,'start_s':start,'end_s':start+30,'rate_xyz_s':float((len(q)-1)*1e9/int(q[-1]-q[0]))})
        rate=(len(d)-1)/t[-1]
        timing={'xyz_points':len(d),'axis_values':3*len(d),'nominal_odr':meta['sensor']['odr_hz'],
                'host_span_s':float(t[-1]),'observed_rate_xyz_s':float(rate),'linear_fit_rate_xyz_s':float(1/slope_t),
                'rate_difference_percent':float(100*(rate/200-1)),'nominal_minus_host_duration_s':float((len(d)-1)/200-t[-1]),
                'host_interval_mean_ms':float(np.diff(ns).mean()/1e6),'host_interval_median_ms':float(np.median(np.diff(ns))/1e6),
                'fit_time_residual_max_ms':float(abs(time_res).max()*1000),'fifo_max':int(d.fifo_depth.max()),
                'host_interval_max_ms':float(np.diff(ns).max()/1e6),'read_duration_max_ms':float(d.read_duration_ns.max()/1e6),
                'quality_flags':{k:int(d[k].sum()) for k in ('gap','overrun','saturated')},
                'consecutive_equal_xyz':int((np.diff(xyz,axis=0)==0).all(axis=1).sum()),
                'maximum_initial_fifo_contribution_xyz_s':float(32/t[-1]),
                'utc_journal_elapsed_s':(datetime.fromisoformat(meta['finished_at_utc'])-datetime.fromisoformat(meta['started_at_utc'])).total_seconds()}
        records.append({'run':run,'csv':session['csv'],'sensor':meta['sensor'],'trend':trend,'timebase':timing,
                        'recording_source_matches_current':{p:digest(ROOT/p)==h for p,h in meta['code']['source_sha256'].items()},
                        'command_offset_s':session['timing']['first_xyz_after_command_completion_s']})
    assert all(r['sensor']==records[0]['sensor'] for r in records)
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'records':records,'input_sha256':inputs,
            'source_sha256':digest(Path(__file__)),'definitions':{'trend':'OLS and median pairwise slopes, descriptive only',
              'robustness':'leave one section out; not confidence interval','time_origin':'first XYZ host timestamp',
              'inference':'no independent-window p-values or pooled significance test'},'new_measurements':False}
    with (BASE/'review.json').open('x') as f:json.dump(report,f,indent=2,allow_nan=False)
    pd.DataFrame(all_blocks).to_csv(BASE/'five_second_rms.csv',index=False)
    pd.DataFrame(trend_rows).to_csv(BASE/'trends.csv',index=False)
    pd.DataFrame(rate_rows).to_csv(BASE/'thirty_second_rates.csv',index=False)
    plot(all_blocks,trend_rows,rate_rows)
    assert all(digest(ROOT/p)==h for p,h in inputs.items())
    print(json.dumps({'trends':trend_rows,'timebase':[r['timebase'] for r in records]},indent=2))

def plot(blocks,trends,rates):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(10.5,7.5),layout='constrained')
    for run in (1,2,3):
        b=[x for x in blocks if x['run']==run and x['start_s']>=180];tr=trends[run-1]
        t=np.array([x['start_s']+2.5 for x in b]);v=np.array([x['vector_ac_rms_mg'] for x in b])-tr['mean_mg']
        axes[0].plot(t,v,'o-',markersize=3,label=f'Lauf {run}')
        axes[0].plot(t,(t-t.mean())*tr['ols_mg_per_min']/60,'--',color=f'C{run-1}')
        p=[x for x in rates if x['run']==run]
        axes[1].plot([x['start_s']+15 for x in p],[x['rate_xyz_s'] for x in p],'o-',label=f'Lauf {run}')
    axes[0].axhline(0,color='gray',lw=.7)
    axes[0].set(xlabel='Zeit seit erstem XYZ-Punkt [s]',ylabel='Abweichung vom jeweiligen Laufmittel [mg]',
                title='Trends innerhalb der Läufe: Mittelwertunterschiede entfernt\nVektor-AC-RMS aus 5-s-Fenstern; gestrichelt: linearer Verlauf')
    axes[1].set(xlabel='Zeit seit erstem XYZ-Punkt [s]',ylabel='Beobachteter Durchsatz [XYZ/s]',
                title='Durchsatz in 30-s-Abschnitten; nominelle Sensoreinstellung: 200 Hz')
    for ax in axes:ax.grid(alpha=.25);ax.legend()
    fig.savefig(BASE/'trends_and_timebase.png',dpi=180);fig.savefig(BASE/'trends_and_timebase.pdf')
    plt.close(fig)

if __name__=='__main__':main()
