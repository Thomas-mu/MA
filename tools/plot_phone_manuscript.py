#!/usr/bin/env python3
"""Read archived measurements; generate publication-sized figures, never acquire data."""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'results/phone_vibration_pilot_20260919'
OUT = ROOT / 'results/phone_vibration_word_revision_20260919'
METHODS = ['tflite_autoencoder', 'isolation_forest', 'rms']
NAMES = ['Autoencoder', 'Isolation Forest', 'RMS']
COLORS = ['#007c83', '#b26713', '#684da2']
TRIALS = ['autoencoder_awaiting_call_03', 'isolation_forest_awaiting_call_02', 'rms_awaiting_call_01']


def read_csv(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def values(rows, key):
    return np.array([float(x[key]) for x in rows])


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def box(ax, xy, width, height, text, color='#e7f3f3'):
    ax.add_patch(FancyBboxPatch(xy, width, height, boxstyle='round,pad=0.01',
                              linewidth=1, edgecolor='#536570', facecolor=color))
    ax.text(xy[0]+width/2, xy[1]+height/2, text, ha='center', va='center', fontsize=10)


def arrow(ax, a, b):
    ax.annotate('', b, a, arrowprops={'arrowstyle': '->', 'color': '#536570', 'lw': 1.4})


def main():
    (OUT/'figures').mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.5,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titlesize': 11, 'axes.labelsize': 10.5,
                         'savefig.dpi': 230, 'pdf.fonttype': 42})
    manifest = {'source_root': str(SOURCE.relative_to(ROOT)), 'figures': {}, 'source_sha256': {}}

    def save(fig, name, sources):
        for ext in ('png', 'pdf'):
            fig.savefig(OUT/'figures'/f'{name}.{ext}', bbox_inches='tight', facecolor='white')
        plt.close(fig)
        manifest['figures'][name] = [str(p.relative_to(ROOT)) for p in sources]
        for p in sources:
            manifest['source_sha256'][str(p.relative_to(ROOT))] = digest(p)

    joint = SOURCE/'joint_trials/all_methods_01'
    jp = SOURCE/'presentation_v3_joint/joint_summary.json'
    summary = json.loads(jp.read_text())
    run = json.loads((joint/'run.json').read_text())
    rows = read_csv(joint/'decisions.csv')
    resources = read_csv(joint/'resources.csv')
    grouped = {m: [r for r in rows if r['method'] == m] for m in METHODS}
    assert len(rows) == 591 and all(len(grouped[m]) == 197 for m in METHODS)
    for triple in zip(*(grouped[m] for m in METHODS)):
        assert len({r['input_sha256'] for r in triple}) == 1
        assert len({r['window'] for r in triple}) == 1
    for m in METHODS:
        alarms = [r for r in grouped[m] if r['prediction'] == '1']
        sm = summary['methods'][m]
        assert len(alarms) == sm['alarm_windows']
        assert int(alarms[0]['window']) == sm['first_alarm_window_between_cues']
        assert int(alarms[0]['decision_ns']) == sm['first_alarm_decision_ns']
    start = run['start_monotonic_ns']
    cue0, cue1 = summary['cue_start_s'], summary['cue_end_s']
    single = [read_csv(SOURCE/'trials'/t/'decisions.csv') for t in TRIALS]

    fig, ax = plt.subplots(figsize=(7.1, 3.9))
    ax.set(xlim=(0,1), ylim=(0,1)); ax.axis('off')
    box(ax, (.02,.64), .26,.23, 'Handy\nAnruf → Vibration')
    box(ax, (.39,.64), .27,.23, 'Lüfter / ADXL345\n75 % PWM, 25 kHz')
    box(ax, (.75,.64), .23,.23, 'Raspberry Pi 5\nlokale Auswertung')
    ax.plot([.015,.66], [.53,.53], color='#536570', lw=3)
    ax.text(.34,.46,'Tisch: mechanischer Übertragungsweg',ha='center')
    arrow(ax,(.15,.64),(.15,.54)); arrow(ax,(.52,.54),(.52,.64))
    arrow(ax,(.66,.76),(.75,.76)); ax.text(.705,.82,'I²C',ha='center',fontsize=9)
    box(ax, (.40,.12), .25,.18, 'externe 12-V-\nVersorgung', '#f2f0ed')
    arrow(ax,(.52,.30),(.52,.43))
    ax.text(.015,.03,'Schema, kein Foto und nicht maßstäblich. Handyposition und Stärke nicht vermessen.',fontsize=8.6)
    save(fig,'setup',[SOURCE/'plan.json',joint/'run.json',SOURCE/'bundle/source_profile.json'])

    fig, ax = plt.subplots(figsize=(7.1,3.5))
    ax.set(xlim=(0,1),ylim=(0,1)); ax.axis('off')
    box(ax,(.01,.36),.22,.3,'ADXL345\n128 XYZ-Punkte\npro Rohfenster')
    box(ax,(.30,.36),.22,.3,'gemeinsame Queue\nidentischer Input\nSHA-256 geprüft')
    arrow(ax,(.23,.51),(.30,.51))
    for y,m,n in zip([.77,.43,.09], METHODS,NAMES):
        box(ax,(.63,y),.35,.20,n+'\nScore + Entscheidung')
        arrow(ax,(.52,.51),(.63,y+.10))
    ax.text(.015,1.05,'Gemeinsamer Live-Lauf: ein Prozess, drei Worker-Threads',weight='bold',fontsize=11,transform=ax.transAxes)
    ax.text(.015,.03,'Einzelbetrieb: jeweils nur ein Verfahren. Replay: gespeicherte Rohfenster erneut auswerten.',fontsize=8.7)
    save(fig,'pipeline',[joint/'run.json',joint/'decisions.csv'])

    raw = read_csv(joint/'raw.csv')
    fig, axs = plt.subplots(2,1,figsize=(7.1,5.6),sharex=True,layout='constrained')
    t=(values(raw,'host_monotonic_ns')-start)/1e9
    for k,c in zip(['x_g','y_g','z_g'],['#546c87','#b26713','#007c83']):
        axs[0].plot(t,values(raw,k),lw=.6,label=k[0].upper(),color=c)
    axs[0].set(ylabel='Beschleunigung [g]',title='a) Gespeicherte Rohwerte, gleicher Sensor für alle Verfahren')
    axs[0].legend(ncol=3,loc='upper right',fontsize=9)
    for m,n,c in zip(METHODS,NAMES,COLORS):
        r=grouped[m]; axs[1].plot(values(r,'elapsed_s'),values(r,'score')/values(r,'threshold'),label=n,color=c,lw=1)
    axs[1].axhline(1,color='#333',ls='--',lw=1)
    axs[1].set(yscale='log',ylabel='Score / eigene Schwelle',xlabel='Zeit seit Aufnahmestart [s]',title='b) Schwelle = 1; unterschiedliche Scoredefinitionen')
    axs[1].legend(ncol=3,fontsize=9,loc='upper right')
    for ax in axs:
        ax.axvspan(cue0,cue1,color='#dddddd',alpha=.35,zorder=-1)
        for cue in [cue0,cue1]: ax.axvline(cue,color='#777',ls=':',lw=1)
        ax.grid(alpha=.15)
    save(fig,'joint_signals',[joint/'raw.csv',joint/'decisions.csv',joint/'run.json',jp])

    fig, axs=plt.subplots(1,2,figsize=(7.1,3.25),gridspec_kw={'width_ratios':[1.35,1]},layout='constrained')
    lags=[summary['methods'][m]['first_alarm_output_after_earliest_ms'] for m in METHODS]
    axs[0].hlines(range(3),0,lags,color=COLORS,lw=2)
    axs[0].scatter(lags,range(3),c=COLORS,s=65,zorder=3)
    for i,v in enumerate(lags): axs[0].annotate(f'Rang {i+1}: {v:.2f} ms'.replace('.',','),(v,i),xytext=(5,9),textcoords='offset points',fontsize=9)
    axs[0].set(yticks=range(3),yticklabels=NAMES,ylim=(2.6,-.6),xlim=(-25,1030),xlabel='Abstand zur ersten Alarmausgabe [ms]',title='a) Ausgabezeitpunkte')
    axs[0].grid(axis='x',alpha=.2)
    first=[summary['methods'][m]['first_alarm_window_between_cues'] for m in METHODS]
    axs[1].scatter(first,range(3),c=COLORS,s=65)
    for i,v in enumerate(first): axs[1].annotate(str(v),(v,i),xytext=(7,0),textcoords='offset points',va='center')
    axs[1].set(yticks=range(3),yticklabels=[],ylim=(2.6,-.6),xticks=[108,109],xlim=(107.7,109.7),xlabel='Erstes Alarmfenster',title='b) AE und IF: gleiches Fenster')
    axs[1].grid(axis='x',alpha=.2)
    save(fig,'alarm_order',[jp,joint/'decisions.csv'])

    fig,ax=plt.subplots(figsize=(7.1,3.3),layout='constrained')
    x=np.arange(3); width=.23
    for i,(m,n,c) in enumerate(zip(METHODS,NAMES,COLORS)):
        ratios=[float(r['score'])/float(r['threshold']) for r in grouped[m] if int(r['window']) in [107,108,109]]
        bars=ax.bar(x+(i-1)*width,ratios,width,color=c,label=n)
        for b,v in zip(bars,ratios): ax.text(b.get_x()+width/2,v+.05,f'{v:.3f}'.replace('.',','),ha='center',fontsize=9)
    ax.axhline(1,color='#333',ls='--',lw=1,label='jeweilige Schwelle')
    ax.set(xticks=x,xticklabels=['107','108','109'],xlabel='Gemeinsames Fenster',ylabel='Score / eigene Schwelle',ylim=(0,9.5))
    ax.legend(ncol=2,fontsize=9,loc='upper left')
    save(fig,'threshold_crossing',[joint/'decisions.csv'])

    rp=SOURCE/'replay_v1/summary.json'; replay=json.loads(rp.read_text())
    fig,ax=plt.subplots(figsize=(7.1,3.4),layout='constrained')
    for i,(m,n,c) in enumerate(zip(METHODS,NAMES,COLORS)):
        wins=[replay['recordings'][t]['methods'][m]['first_alarm_window_between_cues'] for t in TRIALS]
        minima=[min(v['first_alarm_window_between_cues'] for v in replay['recordings'][t]['methods'].values()) for t in TRIALS]
        d=np.array(wins)-minima
        ax.scatter(np.arange(3)+(i-1)*.15,d,c=c,label=n,s=75,marker=['o','s','^'][i])
        for j,w in enumerate(wins): ax.annotate(str(w),(j+(i-1)*.15,d[j]),xytext=(0,9+10*(i==1)),textcoords='offset points',ha='center',fontsize=9)
    ax.set(xticks=range(3),xticklabels=['Aufnahme AE03','Aufnahme IF02','Aufnahme RMS01'],yticks=[0,1],ylim=(-.25,1.75),ylabel='Fenster hinter dem jeweils ersten Alarm',title='Offline-Replay: Zahlen bezeichnen den Fensterindex')
    ax.grid(axis='y',alpha=.2); ax.legend(loc='upper left',ncol=3,fontsize=9)
    save(fig,'replay_onsets',[rp])

    process_stats={}
    for m,r in zip(METHODS,single):
        process_stats[m]={'cpu_median':float(np.median(values(r,'process_cpu_percent_one_core'))),'rss_max_mib':float(max(values(r,'process_rss_bytes'))/2**20),'processing_median_ms':float(np.median(values(r,'processing_ms'))),'processing_p95_ms':float(np.percentile(values(r,'processing_ms'),95)),'temperature_range':[float(min(values(r,'temperature_c'))),float(max(values(r,'temperature_c')))],'frequency_khz_range':[float(min(values(r,'cpu_frequency_khz'))),float(max(values(r,'cpu_frequency_khz')))]}
    process_stats['joint']={'cpu_median':float(np.median(values(resources,'process_cpu_percent_one_core'))),'rss_max_mib':float(max(values(resources,'process_rss_bytes'))/2**20),'temperature_range':[float(min(values(resources,'temperature_c'))),float(max(values(resources,'temperature_c')))],'frequency_khz_range':[float(min(values(resources,'cpu_frequency_khz'))),float(max(values(resources,'cpu_frequency_khz')))]}
    fig,ax=plt.subplots(figsize=(7.1,3.5),layout='constrained')
    for i,(m,n,c) in enumerate(zip(METHODS,NAMES,COLORS)):
        a=process_stats[m]; b=summary['methods'][m]
        for off,key,stats,marker in [(-.14,'single',a,'o'),(.14,'joint',b,'s')]:
            median=stats['processing_median_ms']; p95=stats['processing_p95_ms']
            ax.plot([median,p95],[i+off,i+off],color=c,lw=2)
            ax.scatter(median,i+off,color=c,marker=marker,s=50,label=('Einzelprozess' if key=='single' else 'Gemeinsamer Prozess') if i==0 else None)
            ax.scatter(p95,i+off,color=c,marker='|',s=110)
    ax.set(yscale='linear',xscale='log',yticks=range(3),yticklabels=NAMES,ylim=(2.6,-.7),xlabel='Verarbeitungszeit [ms, logarithmische Achse]',title='Symbol: Median; rechter Strich: P95')
    ax.legend(fontsize=9);ax.grid(axis='x',alpha=.2)
    save(fig,'processing',[*(SOURCE/'trials'/t/'decisions.csv' for t in TRIALS),joint/'decisions.csv',jp])

    fig,axs=plt.subplots(1,2,figsize=(7.1,3.7),layout='constrained')
    keys=METHODS+['joint']; labels=['AE allein','IF allein','RMS allein','alle drei']; colors=COLORS+['#52616f']
    for ax,key,title,ylabel in zip(axs,['cpu_median','rss_max_mib'],['a) CPU-Median','b) Größter abgetasteter RSS'],['% eines logischen Kerns','Prozessspeicher [MiB]']):
        vals=[process_stats[k][key] for k in keys]
        bars=ax.bar(range(4),vals,color=colors)
        for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,v,f'{v:.2f}'.replace('.',','),ha='center',va='bottom',fontsize=9)
        ax.set(xticks=range(4),xticklabels=labels,ylabel=ylabel,title=title,ylim=(0,max(vals)*1.23))
        ax.tick_params(axis='x',labelrotation=35);ax.grid(axis='y',alpha=.15)
    save(fig,'resources',[*(SOURCE/'trials'/t/'decisions.csv' for t in TRIALS),joint/'resources.csv'])

    fig,axs=plt.subplots(3,1,figsize=(7.1,5.6),sharex=True,layout='constrained')
    rt=values(resources,'elapsed_s')
    axs[0].plot(rt,values(resources,'process_cpu_percent_one_core'),color='#52616f',lw=1)
    axs[0].set(ylabel='CPU [% eines Kerns]')
    axs[1].plot(rt,values(resources,'process_rss_bytes')/2**20,color='#007c83',lw=1)
    axs[1].set(ylabel='RSS [MiB]')
    axs[2].plot(rt,values(resources,'temperature_c'),color='#b26713',lw=1,label='Temperatur')
    axs[2].set(ylabel='Temperatur [°C]',xlabel='Zeit seit Aufnahmestart [s]',ylim=(48,64))
    twin=axs[2].twinx();twin.step(rt,values(resources,'cpu_frequency_khz')/1e6,color='#684da2',alpha=.65,lw=1,where='mid');twin.set(ylabel='CPU-Takt [GHz]',ylim=(1.2,2.8))
    for ax in axs:
        ax.axvspan(cue0,cue1,color='#ddd',alpha=.35,zorder=-1);ax.grid(alpha=.15)
    save(fig,'joint_operating',[joint/'resources.csv',jp,joint/'run.json'])
    (OUT/'figure_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    (OUT/'derived_metrics.json').write_text(json.dumps({'process_resources':process_stats,'shared_windows':197,'decisions':591,'source_summary':str(jp.relative_to(ROOT))},indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(process_stats,indent=2))


if __name__=='__main__':
    main()
