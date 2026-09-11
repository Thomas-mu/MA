"""Descriptive comparison of exactly three new, independent 300-s starts."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
HELPER=ROOT/'results/mount_v2_pilot_20260911_072748/analyze_pilot.py'
spec=importlib.util.spec_from_file_location('prior_pilot_math',HELPER)
math=importlib.util.module_from_spec(spec)
spec.loader.exec_module(math)


def phase_summary(blocks):
    values=[b['vector_ac_rms_g'] for b in blocks]
    return dict(**math.describe(values),
                slope_g_per_minute=float(60*np.polyfit([b['start_s']+2.5 for b in blocks],values,1)[0]),
                flagged_sections=sum(not b['quality_flags_clear'] for b in blocks))


def read_run(number,mounting_id):
    path=BASE/f'run{number}_session.json'
    session=json.loads(path.read_text())
    if session['status']!='completed' or session['run']!=number:
        raise ValueError('Three completed runs required; no replacement by prior pilot data')
    if session['final_readback']['pwm_configuration']['configured_duty_percent']!=0:
        raise ValueError('Zero readback missing')
    record=math.load(f'Lauf_{number}',session['csv'],300,75,mounting_id)
    blocks=record['five_second_sections']
    primary=[b for b in blocks if 180<=b['start_s'] and b['end_s']<=300]
    assert len(blocks)==60 and len(primary)==24
    record['primary_180_300']=phase_summary(primary)
    record['minutes']=[dict(minute=i+1,**phase_summary(blocks[12*i:12*(i+1)])) for i in range(5)]
    record['primary_late_vs_early_percent']=100*(record['minutes'][4]['mean']/record['minutes'][3]['mean']-1)
    record['timing']=session['timing']
    record['controlled_off_to_command_s']=session['controlled_off_actual_to_command_invocation_s']
    record['controlled_off_to_command_completion_s']=session['controlled_off_actual_to_command_completion_s']
    record['total_off_since_previous_zero_s']=session['total_off_since_previous_zero_to_command_s']
    record['command_invocation_utc']=session['command_invocation_utc']
    record['zero_command_completed_utc']=session['zero_command_completed_utc']
    return record,session


def main():
    plan=json.loads((BASE/'plan.json').read_text())
    out=BASE/'analysis'
    if out.exists():raise FileExistsError('Existing analysis must remain unchanged')
    pairs=[read_run(i,plan['mounting_id']) for i in (1,2,3)]
    records=[p[0] for p in pairs]
    if any(r['sensor']!=records[0]['sensor'] for r in records):raise ValueError('Different sensor settings')
    means=np.array([r['primary_180_300']['mean'] for r in records])
    within_variance=float(np.mean([r['primary_180_300']['population_std']**2 for r in records]))
    combined=[b['vector_ac_rms_g'] for r in records for b in r['five_second_sections'] if b['start_s']>=180]
    if not np.isclose(np.var(combined),within_variance+np.var(means),rtol=1e-10):
        raise ValueError('Descriptive variance decomposition inconsistent')
    between=dict(run_means_g=means.tolist(),**math.describe(means),
                 sample_std_of_three_run_means_g=float(means.std(ddof=1)),
                 range_percent_of_grand_mean=float(100*np.ptp(means)/means.mean()),
                 rms_within_run_population_std_g=float(np.sqrt(within_variance)),
                 pooled_72_blocks_are_not_independent_restarts=True)
    differences=[]
    for a,b in ((0,1),(0,2),(1,2)):
        x,y=records[a]['primary_180_300'],records[b]['primary_180_300']
        low,high=max(x['minimum'],y['minimum']),min(x['maximum'],y['maximum'])
        differences.append(dict(runs=[a+1,b+1],mean_difference_g=y['mean']-x['mean'],
                                difference_percent_of_pair_mean=100*(y['mean']-x['mean'])/((x['mean']+y['mean'])/2),
                                observed_ranges_overlap=low<=high,overlap_interval_g=[low,high] if low<=high else None))
    inputs={str(HELPER.relative_to(ROOT)):math.digest(HELPER),str((BASE/'plan.json').relative_to(ROOT)):math.digest(BASE/'plan.json')}
    for i,(r,s) in enumerate(pairs,1):
        csv=ROOT/r['csv']
        for p in (csv,csv.with_suffix('.json'),BASE/f'run{i}_session.json',BASE/f'run{i}_fan.jsonl',BASE/f'run{i}_standstill_confirmation.json'):
            inputs[str(p.relative_to(ROOT))]=math.digest(p)
        events=[json.loads(line) for line in (BASE/f'run{i}_fan.jsonl').read_text().splitlines()]
        commands=[e['requested_percent'] for e in events if e['event']=='transaction_begin']
        if commands!=[75.0,0.0]:raise ValueError('Unexpected control sequence')
        first=r['first_xyz_monotonic_ns']
        intent=next(e for e in events if e['event']=='sysfs_write_intent' and e.get('value')==30000)
        readback=next(e for e in events if e['event']=='sysfs_write_readback' and e.get('expected')==30000)
        r['timing'].update(first_xyz_after_duty_write_intent_s=(first-intent['monotonic_ns'])/1e9,
                          first_xyz_after_duty_write_readback_s=(first-readback['monotonic_ns'])/1e9)
    observations={}
    for i in (1,2,3):
        path=BASE/f'run{i}_observation.json'
        if path.exists():
            observations[str(i)]=json.loads(path.read_text())
            inputs[str(path.relative_to(ROOT))]=math.digest(path)
        else:observations[str(i)]={'status':'not_yet_reported'}
    report=dict(created_utc=datetime.now(timezone.utc).isoformat(),status='three_new_restarts_descriptive_pilot',
                mounting_id=plan['mounting_id'],records=records,between=between,pairwise=differences,
                observations=observations,input_sha256=inputs,source_sha256=math.digest(Path(__file__)),
                primary_window_s=[180,300],primary_window_origin='first acquired XYZ, command offsets reported per run',
                settling_time_validated=False,statistical_generalization_proven=False,
                models_trained=False,anomalies_induced=False,old_measurements_pooled=False,
                final_pwm_percent=0,definitions={'vector_ac_rms':'sqrt(mean(sum((XYZ - own_section_axis_means)**2)))',
                 'within_std':'population std of24 five-second RMS values per run, ddof=0',
                 'between_std':'population and sample std of three run means shown separately',
                 'quality':'no interpolation or silent exclusion; contiguous software indices do not prove exact sensor loss count',
                 'fixed_off_time':'60s after acceptance of each standstill confirmation; total off time varies with reply delay'})
    out.mkdir()
    with (out/'report.json').open('x') as f:json.dump(report,f,indent=2,ensure_ascii=False,allow_nan=False)
    pd.DataFrame([b for r in records for b in r['five_second_sections']]).to_csv(out/'five_second_sections.csv',index=False)
    pd.DataFrame([dict(name=r['name'],**r['quality'],**r['primary_180_300']) for r in records]).to_csv(out/'primary_summary.csv',index=False)
    plot(report,out)
    assert all(math.digest(ROOT/p)==h for p,h in inputs.items())
    print(json.dumps({'primary':[{k:r[k] for k in ('name','primary_180_300','primary_late_vs_early_percent','controlled_off_to_command_s','total_off_since_previous_zero_s')} for r in records],
                      'between':between,'pairwise':differences},indent=2))


def plot(report,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(11.5,10),layout='constrained')
    for i,r in enumerate(report['records']):
        blocks=r['five_second_sections']
        t=[b['start_s']+2.5 for b in blocks]
        v=[1000*b['vector_ac_rms_g'] for b in blocks]
        axes[0].plot(t,v,'o-',markersize=3,label=r['name'])
        primary=[b for b in blocks if b['start_s']>=180]
        axes[1].plot([b['start_s']+2.5 for b in primary],[1000*b['vector_ac_rms_g'] for b in primary],
                     'o-',markersize=4,label=r['name'])
        axes[2].scatter(np.full(24,i+1)+np.linspace(-.12,.12,24),[1000*b['vector_ac_rms_g'] for b in primary],s=22,alpha=.7)
        axes[2].hlines(r['primary_180_300']['mean']*1000,i+.8,i+1.2,color='black',lw=2,
                       label='Mittel je Lauf' if i==0 else None)
    axes[0].set(xlim=(0,300),xlabel='Zeit seit erstem XYZ-Punkt [s]',ylabel='Vektor-AC-RMS [mg]',title='Alle drei Starts: vollständiger Verlauf')
    axes[0].axvspan(180,300,color='gray',alpha=.1)
    axes[1].set(xlim=(180,300),xlabel='Zeit seit erstem XYZ-Punkt [s]',ylabel='Vektor-AC-RMS [mg]',title='Vorab festgelegter Prüfbereich 180–300 s; Einlaufzeit noch nicht validiert')
    axes[2].set(xticks=[1,2,3],xticklabels=['Lauf 1','Lauf 2','Lauf 3'],ylabel='Vektor-AC-RMS [mg]',
                title='Je24 Abschnittswerte im Prüfbereich; Punkte sind keine unabhängigen Starts')
    for ax in axes:ax.grid(alpha=.25);ax.legend(loc='best')
    fig.suptitle('Neue Montage: drei unabhängige Normalstarts bei75% PWM und25kHz\nEigene Achsenmittelwerte in jedem5-s-Abschnitt entfernt')
    fig.savefig(out/'restart_comparison.png',dpi=180)
    fig.savefig(out/'restart_comparison.pdf')
    plt.close(fig)


if __name__=='__main__':main()
