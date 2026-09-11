"""Offline phase analysis only. Does not import or access fan/sensor control."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
PHASES=('normal_before','airflow_modified','normal_after')


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def describe(values):
    a=np.asarray(values,dtype=float)
    return {'mean_mg':float(a.mean()),'median_mg':float(np.median(a)),
            'std_mg_ddof0':float(a.std()),'min_mg':float(a.min()),'max_mg':float(a.max())}


def analyze(phase):
    out=BASE/'analysis'/phase
    if out.exists():raise FileExistsError('Existing analysis is preserved')
    session_path=BASE/f'{phase}_session.json';s=json.loads(session_path.read_text())
    if s['status']!='completed':raise ValueError('Completed capture required; errors must be reported separately')
    csv=ROOT/s['csv'];sidecar=csv.with_suffix('.json');meta=json.loads(sidecar.read_text())
    assert meta['status']=='completed' and digest(csv)==meta['csv_sha256']
    d=pd.read_csv(csv,dtype={'host_monotonic_ns':'int64','sample_index':'int64'})
    ns=d.host_monotonic_ns.to_numpy();xyz=d[['x_g','y_g','z_g']].to_numpy()
    assert len(d)>1 and np.isfinite(xyz).all()
    assert all(d[k].dtype==bool for k in ('gap','overrun','saturated'))
    assert np.array_equal(d.sample_index,np.arange(len(d)))
    assert (np.diff(ns)>0).all()
    assert (d.anomaly_type==phase).all() and (d.label==(1 if phase=='airflow_modified' else 0)).all()
    assert meta['state']==phase and meta['sensor']==s['sensor']
    origin=s['command_invocation_monotonic_ns'];t=(ns-origin)/1e9
    relative=(ns-ns[0])/1e9;dt=np.diff(ns)/1e9
    assert np.allclose(d.timestamp_s-d.timestamp_s.iloc[0],relative,atol=1e-10,rtol=0)
    odr=meta['sensor']['odr_hz']
    assert np.allclose(d.sensor_time_estimate_s,np.arange(len(d))/odr,atol=1e-10,rtol=0)
    blocks=[]
    for start in range(0,300,5):
        mask=(t>=start)&(t<start+5);a=xyz[mask];q=ns[mask]
        if len(a)<2:raise ValueError('Missing window; no interpolation or silent omission')
        m=a.mean(axis=0);centered=a-m
        rms=float(1000*np.sqrt(np.mean(np.sum(centered**2,axis=1))))
        # Independent algebraic check: vector energy equals sum of axis variances.
        assert np.isclose(rms,1000*np.sqrt(a.var(axis=0).sum()),rtol=1e-12,atol=1e-10)
        blocks.append({'phase':phase,'start_s':start,'end_s':start+5,'xyz_points':len(a),
            'actual_first_s':float(t[mask][0]),'actual_last_s':float(t[mask][-1]),
            'observed_xyz_s':float((len(q)-1)*1e9/int(q[-1]-q[0])),
            'axis_mean_x_g':float(m[0]),'axis_mean_y_g':float(m[1]),'axis_mean_z_g':float(m[2]),
            'vector_ac_rms_mg':rms,
            **{k+'_count':int(d.loc[mask,k].sum()) for k in ('gap','overrun','saturated')}})
    late=blocks[36:60];y=np.array([b['vector_ac_rms_mg'] for b in late]);x=np.arange(182.5,300,5)
    slope,intercept=np.polyfit(x,y,1)
    robust=np.median([(y[j]-y[i])/(x[j]-x[i]) for i in range(24) for j in range(i+1,24)])
    primary={**describe(y),'windows':24,'linear_slope_mg_min':float(slope*60),
        'theil_sen_slope_mg_min':float(robust*60),'fitted_120s_change_mg':float(slope*120),
        'fitted_120s_change_percent':float(100*slope*120/y.mean()),
        'last60_minus_first60_mg':float(y[12:].mean()-y[:12].mean()),
        'four_30s_means_mg':[float(y[i:i+6].mean()) for i in range(0,24,6)],
        'residual_std_mg':float((y-(slope*x+intercept)).std())}
    quality={'xyz_points':len(d),'single_axis_values':3*len(d),'nominal_odr_hz':odr,
        'configured_duration_s':meta['configured_duration_seconds'],
        'first_to_last_host_s':float(relative[-1]),'observed_xyz_s':float((len(d)-1)/relative[-1]),
        'host_interval_mean_ms':float(dt.mean()*1000),'host_interval_p50_ms':float(np.median(dt)*1000),
        'host_interval_p99_ms':float(np.quantile(dt,.99)*1000),'host_interval_max_ms':float(dt.max()*1000),
        'host_intervals_over_10ms':int((dt>.010).sum()),
        'host_intervals_over_10ms_command_times_s':t[1:][dt>.010].tolist(),
        'read_duration_max_ms':float(d.read_duration_ns.max()/1e6),
        'fifo_max':int(d.fifo_depth.max()),'nonmonotonic_host_intervals':int((dt<=0).sum()),
        'software_sample_indices_contiguous':True,'exact_sensor_loss_count':None,
        'max_absolute_axis_g':float(abs(xyz).max()),
        'axis_means_g':xyz.mean(axis=0).tolist(),'axis_std_g_ddof0':xyz.std(axis=0).tolist(),
        **{k+'_count':int(d[k].sum()) for k in ('gap','overrun','saturated')},
        'beyond_300s_from_command_points':int((t>=300).sum()),
        'first_window_note':'starts with first acquired XYZ; missing pre-read interval is not filled',
        'timestamp_note':'host read completion, not independently measured sensor conversion times'}
    events=[json.loads(line) for line in (BASE/f'{phase}_fan.jsonl').read_text().splitlines()]
    commands=[e['requested_percent'] for e in events if e['event']=='transaction_begin']
    assert commands==[75.0,0.0]
    assert s['final_readback']['pwm_configuration']['configured_duty_percent']==0
    paths=[session_path,csv,sidecar,BASE/f'{phase}_fan.jsonl',BASE/f'{phase}_release.json']
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'phase':phase,
        'csv':s['csv'],'mounting_id':s['mounting_id'],'geometry':s['geometry'],
        'sensor':meta['sensor'],'quality':quality,'primary_180_300':primary,
        'full_60_window_summary':describe([b['vector_ac_rms_mg'] for b in blocks]),
        'timing':s['timing'],'additional_off_from_release_actual_s':s['additional_off_from_release_actual_s'],
        'total_off_since_previous_zero_s':s['total_off_since_previous_zero_s'],
        'command_invocation_utc':s['command_invocation_utc'],'zero_command_completed_utc':s['zero_command_completed_utc'],
        'source_sha256':digest(Path(__file__)),'input_sha256':{str(p.relative_to(ROOT)):digest(p) for p in paths},
        'control_transactions':commands,'final_pwm_percent':0,'mechanical_standstill_observed':None,
        'settling_time_validated':False,'models_trained':False,'observations_requested':False,
        'quality_flags_clear':all(quality[k+'_count']==0 for k in ('gap','overrun','saturated'))}
    out.mkdir(parents=True)
    with (out/'summary.json').open('x') as f:json.dump(report,f,indent=2,ensure_ascii=False,allow_nan=False)
    pd.DataFrame(blocks).to_csv(out/'five_second_rms.csv',index=False)
    plot(phase,blocks,primary,t[1:],dt,out)
    assert all(digest(ROOT/p)==h for p,h in report['input_sha256'].items())
    return report


def plot(phase,blocks,primary,t,dt,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(3,1,figsize=(10.5,9),layout='constrained')
    x=np.array([b['start_s']+2.5 for b in blocks]);y=np.array([b['vector_ac_rms_mg'] for b in blocks])
    ax[0].plot(x,y,'o-',markersize=3)
    ax[0].axvspan(180,300,color='gray',alpha=.15)
    ax[0].set(xlim=(0,300),ylabel='Vektor-AC-RMS [mg]',title='Vollständiger Verlauf; eigener Achsenmittelwert je 5-s-Abschnitt entfernt')
    ax[1].plot(x[36:],y[36:],'o-',markersize=3)
    ax[1].plot(x[36:],primary['mean_mg']+(x[36:]-240)*primary['linear_slope_mg_min']/60,'--',label='Linearer Verlauf')
    ax[1].set(xlim=(180,300),ylabel='Vektor-AC-RMS [mg]',title='180–300 s: vorläufiges Auswertefenster');ax[1].legend()
    # Display every host interval; these are read completions, not conversion intervals.
    ax[2].plot(t,dt*1000,'.',markersize=.6,alpha=.5,rasterized=True)
    ax[2].axhline(5,color='gray',lw=.8,label='Nominelle Periode: 5 ms')
    ax[2].set(xlim=(0,300),ylabel='Host-Leseabstand [ms]',title='Hostzeitbasis und Leseabstände');ax[2].legend()
    for a in ax:a.set_xlabel('Zeit seit PWM-Befehlsaufruf [s]');a.grid(alpha=.25)
    fig.suptitle(f'{phase}: 75 % PWM, 25 kHz — eine unabhängige Aufnahme')
    fig.savefig(out/'phase_overview.png',dpi=160);fig.savefig(out/'phase_overview.pdf');plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=PHASES,required=True)
    result=analyze(parser.parse_args().phase)
    print(json.dumps({k:result[k] for k in ('phase','quality','primary_180_300','timing')},indent=2))
