"""Offline comparison gated on all four completed phases of this upright setup."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
PHASES=('standstill','normal_before','airflow_modified','normal_after')


def main():
    out=BASE/'analysis'/'sequence_comparison'
    if out.exists():raise FileExistsError('Preserve completed comparison')
    reports={p:json.loads((BASE/'analysis'/p/'summary.json').read_text()) for p in PHASES}
    tables={p:pd.read_csv(BASE/'analysis'/p/'five_second_rms.csv') for p in PHASES}
    ids={r['mounting_id'] for r in reports.values()}
    assert ids=={json.loads((BASE/'mounting.json').read_text())['mounting_id']}
    assert all(r['sensor']==reports['standstill']['sensor'] for r in reports.values())
    inputs={}
    for p,r in reports.items():
        session=json.loads((BASE/f'{p}_session.json').read_text())
        assert session['status']=='completed'
        assert session['final_readback']['pwm_configuration']['configured_duty_percent']==0
        for path,h in r['input_sha256'].items():
            assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h
            inputs[path]=h
        for name in ('summary.json','five_second_rms.csv'):
            path=BASE/'analysis'/p/name
            inputs[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    late={p:tables[p].loc[tables[p].start_s>=180,'vector_ac_rms_mg'].to_numpy() for p in PHASES[1:]}
    assert all(len(x)==24 for x in late.values())
    before,changed,after=[late[p] for p in PHASES[1:]]
    normal_shift=float(after.mean()-before.mean())
    result={'created_utc':datetime.now(timezone.utc).isoformat(),'mounting_id':next(iter(ids)),
      'independent_recordings_per_operating_condition':1,'primary_time_window_s':[180,300],
      'settling_time_validated':False,'historical_horizontal_reference_used':False,
      'all_quality_flags_clear':all(r['quality_flags_clear'] for r in reports.values()),
      'primary':{p:reports[p]['primary_180_300'] for p in PHASES[1:]},
      'normal_after_minus_before_mg':normal_shift,
      'normal_after_minus_before_percent':float(100*normal_shift/before.mean()),
      'after_windows_inside_observed_before_range':int(((after>=before.min())&(after<=before.max())).sum()),
      'after_windows_total':24,
      'normal_observed_ranges_overlap':bool(max(before.min(),after.min())<=min(before.max(),after.max())),
      'normal_within_rms_std_mg':float(np.sqrt((before.var()+after.var())/2)),
      'altered_contrasts':{},'input_sha256':inputs,'models_trained':False,
      'interpretation_limit':'One N-A-N sequence. Window counts are descriptive, not independent experimental replicates; no defect or detection claim.'}
    for name,n in [('normal_before',before),('normal_after',after)]:
        delta=float(changed.mean()-n.mean())
        result['altered_contrasts'][name]={'mean_difference_mg':delta,
          'percent_of_normal_mean':float(100*delta/n.mean()),
          'absolute_difference_exceeds_observed_normal_mean_shift':bool(abs(delta)>abs(normal_shift)),
          'absolute_difference_exceeds_this_normal_window_range':bool(abs(delta)>np.ptp(n)),
          'absolute_difference_in_this_normal_window_std':float(abs(delta)/n.std()) if n.std()>0 else None,
          'observed_ranges_overlap':bool(max(changed.min(),n.min())<=min(changed.max(),n.max()))}
    out.mkdir()
    with (out/'comparison.json').open('x') as f:json.dump(result,f,indent=2,ensure_ascii=False,allow_nan=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(11,10),layout='constrained')
    for p in PHASES[1:]:
        d=tables[p];x=d.start_s.to_numpy()+2.5;y=d.vector_ac_rms_mg.to_numpy()
        axes[0].plot(x,y,'o-',markersize=3,label=p)
        axes[1].plot(x[36:],y[36:],'o-',markersize=3,label=p)
        axes[2].plot(x[36:],y[36:]-y[36:].mean(),'o-',markersize=3,label=p)
    axes[0].axvspan(180,300,color='gray',alpha=.12)
    axes[0].set(xlim=(0,300),ylabel='Vektor-AC-RMS [mg]',title='Vollständige Betriebsverläufe; separate Aufnahme pro Zustand')
    axes[1].set(xlim=(180,300),ylabel='Vektor-AC-RMS [mg]',title='Prüfkandidat 180–300 s: Niveau und Schwankungen')
    axes[2].axhline(0,color='gray',lw=.7)
    axes[2].set(xlim=(180,300),ylabel='Abweichung vom Laufmittel [mg]',title='Zeitliche Veränderungen nach Abzug des jeweiligen RMS-Laufmittels')
    for a in axes:a.set_xlabel('Zeit seit jeweiligem PWM-Stellbefehl [s]');a.grid(alpha=.25);a.legend()
    fig.suptitle('Aufrechte Aufstellung — 75 % PWM, 25 kHz\nEigene Achsenmittelwerte in jedem 5-s-Fenster entfernt')
    fig.savefig(out/'sequence_comparison.png',dpi=170);fig.savefig(out/'sequence_comparison.pdf');plt.close(fig)
    print(json.dumps({k:result[k] for k in ('normal_after_minus_before_mg','normal_after_minus_before_percent','after_windows_inside_observed_before_range','altered_contrasts')},indent=2))


if __name__=='__main__':main()
