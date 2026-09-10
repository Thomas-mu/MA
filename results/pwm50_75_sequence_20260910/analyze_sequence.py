"""Compare only the eight files of the new bracketed50/75% pilot sequence.

No training, anomaly generation or historical-file edits. Shared numerical
definitions are reused from the preceding pilot analysis without running its
main function or writing into its output directory.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
OUT = BASE / 'comparison'
HELPER = ROOT / 'results/pwm50_investigation_20260910/analyze_conditions.py'
spec = importlib.util.spec_from_file_location('prior_pilot_numerics', HELPER)
numerics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(numerics)
AXES = ['x_g', 'y_g', 'z_g']
PHASES = ['standstill_before', 'operating50', 'operating75', 'standstill_after']
PREFIXES = ['PRE', 'PWM50', 'PWM75', 'POST']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary(values):
    return {'mean': float(np.mean(values)), 'min': float(np.min(values)),
            'max': float(np.max(values)), 'range': float(np.ptp(values))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,help='Explicit assembly manifest for documented controller continuation')
    args=parser.parse_args()
    if OUT.exists():
        raise FileExistsError('Completed analysis must not be overwritten')
    paths = [args.manifest] if args.manifest is not None else list(BASE.glob('sequence_*.json'))
    if len(paths) != 1:
        raise ValueError('Exactly one completed acquisition sequence required')
    session = json.loads(paths[0].read_text())
    if session.get('status') != 'completed' or len(session.get('recordings', [])) != 8:
        raise ValueError('Eight completed recordings required')
    if session['final_readback']['pwm_configuration']['configured_duty_percent'] != 0:
        raise ValueError('Final0% not verified')
    records, spectral_rows = {}, []
    for index, item in enumerate(session['recordings']):
        phase, prefix, repeat = PHASES[index//2], PREFIXES[index//2], index%2+1
        if item['phase'] != phase or item['repeat'] != repeat:
            raise ValueError('Recording order differs from protocol')
        name = f'{prefix}_{repeat}'
        r, spectra = numerics.load(name, ROOT / item['csv'])
        r['phase'] = phase
        r['phase_repeat'] = repeat
        r['elapsed_since_phase_pwm_command_s'] = item['report']['elapsed_since_phase_pwm_command_s']
        records[name] = r
        spectral_rows.extend(spectra)
    sensor_keys = ['odr_hz', 'range_g', 'full_resolution', 'acquisition_mode', 'register_readback', 'i2c_clock_configured_hz']
    config = {k: records['PRE_1']['sensor'][k] for k in sensor_keys}
    if any({k:r['sensor'][k] for k in sensor_keys} != config for r in records.values()):
        raise ValueError('Sensor configuration changed')
    if len({r['mounting_id'] for r in records.values()}) != 1:
        raise ValueError('Mounting identifiers differ')
    keys = ['mean_'+a for a in AXES]+['std_'+a for a in AXES]+['vector_ac_rms_g','magnitude_ac_rms_g']
    phase_stats = {}
    for phase, prefix in zip(PHASES, PREFIXES):
        names = [f'{prefix}_1', f'{prefix}_2']
        stats = {}
        for key in keys:
            vals = [records[n]['statistics'][key] for n in names]
            blocks = [s[key] for n in names for s in records[n]['five_second_sections']]
            result = summary(vals)
            result['repeat_difference_absolute'] = abs(vals[1]-vals[0])
            result['repeat_difference_signed'] = vals[1]-vals[0]
            result['relative_repeat_difference_percent'] = 100*abs(vals[1]-vals[0])/abs(result['mean']) if result['mean'] else None
            result['five_second_sections'] = summary(blocks)
            result['five_second_sections']['descriptive_cv_percent'] = float(100*np.std(blocks)/abs(np.mean(blocks))) if np.mean(blocks) else None
            stats[key] = result
        phase_stats[phase] = {'recordings': names, 'metrics': stats}
    contrasts = []
    for a,b in [('standstill_before','standstill_after'),('standstill_before','operating50'),
                ('standstill_after','operating50'),('standstill_before','operating75'),
                ('standstill_after','operating75'),('operating50','operating75')]:
        for key in keys:
            left,right=phase_stats[a]['metrics'][key],phase_stats[b]['metrics'][key]
            difference=right['mean']-left['mean']
            denom=max(left['repeat_difference_absolute'],right['repeat_difference_absolute'])
            contrasts.append({'a':a,'b':b,'metric':key,'difference_b_minus_a':difference,
                              'largest_within_phase_repeat_difference':denom,
                              'difference_to_repeat_range_ratio':abs(difference)/denom if denom else None,
                              'recording_ranges_overlap':max(left['min'],right['min'])<=min(left['max'],right['max']),
                              'five_second_ranges_overlap':max(left['five_second_sections']['min'],right['five_second_sections']['min'])<=min(left['five_second_sections']['max'],right['five_second_sections']['max'])})
    metric='vector_ac_rms_g'
    pre=phase_stats['standstill_before']['metrics'][metric]
    post=phase_stats['standstill_after']['metrics'][metric]
    comparisons={}
    for phase in ('operating50','operating75'):
        op=phase_stats[phase]['metrics'][metric]
        background_max=max(pre['max'],post['max'])
        reference_variation=max(pre['repeat_difference_absolute'],post['repeat_difference_absolute'],abs(post['mean']-pre['mean']))
        comparisons[phase]={
            'mean_vector_ac_rms_g':op['mean'],
            'mean_increase_over_pre_g':op['mean']-pre['mean'],
            'mean_increase_over_post_g':op['mean']-post['mean'],
            'minimum_operating_minus_maximum_background_recording_g':op['min']-background_max,
            'repeat_difference_g':op['repeat_difference_absolute'],
            'relative_repeat_difference_percent':op['relative_repeat_difference_percent'],
            'five_second_rms_range_g':op['five_second_sections'],
            'minimum_operating_minus_maximum_background_section_g':op['five_second_sections']['min']-max(pre['five_second_sections']['max'],post['five_second_sections']['max']),
            'observed_background_change_or_repeat_difference_g':reference_variation,
            'meaning':'Descriptive margins and variability; no automatic pass threshold or PWM selection.'}
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'status':'completed_pilot_analysis_no_training',
            'sequence':str(paths[0].relative_to(ROOT)),'sequence_sha256':digest(paths[0]),
            'analysis_source_sha256':digest(Path(__file__)),'numerical_helper':str(HELPER.relative_to(ROOT)),
            'numerical_helper_sha256':digest(HELPER),'records':records,'phase_statistics':phase_stats,
            'contrasts':contrasts,'operating_point_comparison':comparisons,'sensor_configuration':config,
            'background_vector_rms_change_post_minus_pre_g':post['mean']-pre['mean'],
            'final_setpoint_percent':0,'final_mechanical_state':session['final_mechanical_state'],
            'controller_execution_uninterrupted':session.get('controller_execution_uninterrupted',True),
            'controller_interruption':session.get('interruption'),
            'source_sessions':session.get('source_sessions',[]),
            'capture_sequence_elapsed_s':session.get('first_capture_start_to_last_capture_end_s'),
            'definitions':{'axis_std':'population std(ddof=0), equal to AC-RMS after own axis mean removal',
                           'vector_ac_rms_g':'sqrt(mean(sum((XYZ-mean(XYZ,axis=0))^2,axis=1)))',
                           'time_rate':'(N-1)/(last-first host read-completion time); nominal sensor time is not independently measured',
                           'sections':'six non-overlapping5-s host-time sections per recording; own axis mean removed in each section',
                           'repeats':'two separate30-s files in one continuously held state; not independent state re-establishments',
                           'aggregation':'each complete recording receives equal weight; pre/post background kept separate'},
            'limitations':['Two repetitions per phase support descriptive assessment, not robust statistical inference.',
                           'Short sections share one recording and must not be treated as independent experimental replications.',
                           'Fixed ordering leaves time/order effects possible; pre/post references reveal only observed drift.',
                           'Long confirmation waits and an unavailable controller session before closing references interrupt temporal continuity; actual waits and recovery are documented.',
                           'No tachometer or independent sensor conversion timestamps; no alias-freedom or anomaly detection proof.',
                           'No model training or artificial anomaly; normal/anomalous comparison at identical PWM remains future work.']}
    OUT.mkdir()
    (OUT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    rows,blocks=[],[]
    for name,r in records.items():
        rows.append({k:v for k,v in r.items() if not isinstance(v,(dict,list))}|r['statistics'])
        blocks.extend({'name':name,'phase':r['phase'],'pwm_percent':r['pwm_percent']}|s for s in r['five_second_sections'])
    pd.DataFrame(rows).to_csv(OUT/'recording_metrics.csv',index=False)
    pd.DataFrame(blocks).to_csv(OUT/'five_second_metrics.csv',index=False)
    pd.DataFrame(contrasts).to_csv(OUT/'phase_contrasts.csv',index=False)
    pd.DataFrame(spectral_rows).to_csv(OUT/'spectra.csv',index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(13,5),constrained_layout=True)
    colors=['#35648a']*2+['#c96322']*2+['#45894b']*2+['#35648a']*2
    for i,((name,r),color) in enumerate(zip(records.items(),colors)):
        vals=[s['vector_ac_rms_g']*1000 for s in r['five_second_sections']]
        axes[0].plot([i]*len(vals),vals,'o',color=color,alpha=.35,markersize=5)
        axes[0].plot(i,r['statistics']['vector_ac_rms_g']*1000,'D',color=color,markersize=8)
        axes[1].plot(i,r['host_observed_rate_xyz_per_s'],'D',color=color)
    axes[0].set(ylabel='Vektor-AC-RMS / mg',title='Raute: 30 s; Kreise: sechs 5-s-Abschnitte')
    axes[1].axhline(200,color='gray',linestyle='--',label='Soll-ODR 200 Hz')
    axes[1].set(ylabel='XYZ-Messpunkte / s',title='Beobachteter FIFO-Durchsatz aus Hostzeit')
    axes[1].legend()
    for ax in axes:
        ax.set_xticks(range(8),list(records),rotation=30)
        ax.grid(alpha=.25)
    fig.suptitle('Stillstand → 50 % → 75 % → Stillstand\nJe zwei getrennte 30-s-Aufnahmen; unveränderte Sensoreinstellungen')
    fig.savefig(OUT/'comparison.png',dpi=180)
    fig.savefig(OUT/'comparison.pdf')
    plt.close(fig)
    for r in records.values():
        p=ROOT/r['csv']
        if digest(p)!=r['csv_sha256'] or digest(p.with_suffix('.json'))!=r['sidecar_sha256']:
            raise ValueError('Input changed during analysis')
    print(json.dumps({'output':str(OUT.relative_to(ROOT)),'operating_comparison':comparisons,
                      'background_change_g':report['background_vector_rms_change_post_minus_pre_g']},ensure_ascii=False))


if __name__=='__main__':
    main()
