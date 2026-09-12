#!/usr/bin/env python3
"""Publication-size figures from archived results; no redefinition of scores."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
OUT=BASE/'word_figures'
PLATE=ROOT/'results/upright_v4_frozen_airflow_test_20260912_073015'
DIAG=ROOT/'results/upright_v4_exploratory_diagnosis_20260912_081728'
PWM=ROOT/'results/upright_v4_second_pwm50_20260912_091000/comparison_50_vs_75'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':9.5,'axes.labelsize':9,
                    'legend.fontsize':8,'xtick.labelsize':8,'ytick.labelsize':8,'axes.spines.top':False,
                    'axes.spines.right':False,'savefig.dpi':240})
COLORS=['#0072B2','#D55E00','#009E73'];PHASES=['normal_before','airflow_modified','normal_after']
NAMES=['Normal vorher','Luftstrom verändert','Normal nachher']
inputs={}


def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def read_csv(p):inputs[str(p)]=sha(p);return pd.read_csv(p,float_precision='round_trip')
def read_json(p):inputs[str(p)]=sha(p);return json.loads(p.read_text())
def save(fig,name):
 for ext in ('png','pdf'):fig.savefig(OUT/(name+'.'+ext))
 plt.close(fig)


def main():
 OUT.mkdir(exist_ok=False)
 rms={ph:read_csv(PLATE/f'evaluation_{ph}/rms_5s.csv') for ph in PHASES}
 fig,ax=plt.subplots(2,1,figsize=(6.3,5.5),layout='constrained')
 for j,(left,right) in enumerate([(0,300),(180,300)]):
  for k,ph in enumerate(PHASES):
   d=rms[ph];assert len(d)==60 and d.quality_valid.all()
   f=d[(d.start_since_command_s>=left)&(d.end_since_command_s_exclusive<=right)]
   ax[j].plot(f.midpoint_since_command_s,f.vector_ac_rms_mg,color=COLORS[k],label=NAMES[k],lw=1,marker='.',ms=3)
  ax[j].set(xlim=(left,right),ylabel='Vektor-AC-RMS [mg]',xlabel='Zeit ab Stellbefehl [s]')
  ax[j].grid(alpha=.2);ax[j].set_title('Vollständiger Verlauf' if j==0 else 'Vorab gewählter Abschnitt [180,300) s')
 ax[0].axvline(180,color='#555',ls='--',lw=.9)
 fig.legend(NAMES,loc='outside lower center',ncol=3,frameon=False)
 save(fig,'plate_rms')
 diag=read_csv(DIAG/'window_diagnostics.csv')
 fig,ax=plt.subplots(3,1,figsize=(6.3,6.2),sharex=True,layout='constrained')
 for j,(method,name,threshold) in enumerate([('rms','RMS',1.2747695377144315),('isolation_forest','Isolation Forest',.5045395247064507),('tflite_autoencoder','TFLite-Autoencoder',.544357966122261)]):
  for k,ph in enumerate(PHASES):
   d=diag[diag.name==ph];assert len(d)==194 and d.quality_valid.all()
   mid=(d.start_since_command_s+d.last_since_command_s)/2
   ax[j].plot(mid,d[method],lw=.8,color=COLORS[k],alpha=.9,label=NAMES[k])
  ax[j].axhline(threshold,color='black',ls='--',lw=1,label='eingefrorene Schwelle')
  ax[j].set_title(name);ax[j].set(ylabel='Score [dimensionslos]',xlim=(180,300));ax[j].grid(alpha=.2)
 ax[-1].set_xlabel('Zeit ab Stellbefehl [s]')
 fig.legend(*ax[0].get_legend_handles_labels(),loc='outside lower center',ncol=2,frameon=False)
 save(fig,'plate_scores')
 labels=['Train 1','Train 2','Valid.','Test 1','Test 2','Test 3','N 11.09.','N vorher','Platte','N nachher']
 keys=['train_normal_before','train_normal_after','validation','normal_test_01','normal_test_02','normal_test_03','normal_sep11']+PHASES
 fig,ax=plt.subplots(3,1,figsize=(6.3,6.6),sharex=True,layout='constrained')
 for row in range(3):
  bottom=np.zeros(len(keys));x=np.arange(len(keys))
  for k,axis in enumerate('xyz'):
   value=[]
   for name in keys:
    d=diag[diag.name==name];assert len(d)==194
    value.append(float(np.mean(np.square(d[axis+'_rms_mg']))) if row==0 else float(d[axis+('_standard_energy' if row==1 else '_ae_mse')].mean()/3))
   ax[row].bar(x,value,bottom=bottom,color=COLORS[k],label=axis.upper());bottom+=value
  ax[row].axvline(6.5,color='#888',ls=':',lw=.8);ax[row].grid(axis='y',alpha=.15)
  ax[row].set_ylabel(['Physische Energie\n[mg²]','Standardisierte Energie\n(je Achse / 3)','Beitrag zum AE-Score\n(MSE je Achse / 3)'][row])
 ax[-1].axhline(.544357966122261,color='black',ls='--',lw=1)
 ax[-1].set_xticks(np.arange(len(keys)),labels,rotation=45,ha='right')
 fig.legend(*ax[0].get_legend_handles_labels(),loc='outside upper center',ncol=3,frameon=False)
 save(fig,'axis_decomposition')
 fp=read_csv(PWM/'false_alarm_comparison.csv')
 fig,ax=plt.subplots(1,3,figsize=(6.3,3.25),sharey=True,layout='constrained')
 for j,(method,name) in enumerate([('rms','RMS'),('isolation_forest','Isolation Forest'),('tflite_autoencoder','Autoencoder')]):
  for k,pwm in enumerate((50,75)):
   g=fp[(fp.method==method)&(fp.pwm_percent==pwm)];d=g[g.run!='pooled'];pool=g[g.run=='pooled']
   assert len(d)==(3 if pwm==50 else 6) and len(pool)==1
   ax[j].scatter(k+np.linspace(-.14,.14,len(d)),100*d.false_alarm_rate_among_valid_normal_windows,s=24,color=COLORS[k])
   y=100*float(pool.false_alarm_rate_among_valid_normal_windows.iloc[0]);ax[j].plot([k-.25,k+.25],[y,y],color=COLORS[k],lw=1.5)
  ax[j].set_title(name);ax[j].set(xticks=[0,1],xticklabels=['50 %\n3 Läufe','75 %\n6 Läufe'],xlim=(-.5,1.5),ylim=(-1,32));ax[j].grid(axis='y',alpha=.2)
 ax[0].set_ylabel('Fehlalarmrate [% gültiger Normalfenster]')
 save(fig,'false_alarm_comparison')
 a=read_json(BASE/'runtime_analysis/analysis.json');r=a['trials']
 fig,ax=plt.subplots(2,1,figsize=(6.3,5.3),layout='constrained')
 methods=['rms','isolation_forest','tflite_autoencoder'];names=['RMS','Isolation Forest','Autoencoder']
 for row,mode in enumerate(['sensor_live','offline_replay']):
  for j,m in enumerate(methods):
   group=[x for x in r if x['mode']==mode and x['method']==m]
   for v in group:
    x=j+(v['repeat']-2)*.13;l=v['latency_ms']['complete_to_decision']
    ax[row].plot([x,x],[l['median'],l['maximum']],color=COLORS[j],lw=1)
    ax[row].scatter(x,l['p99'],color=COLORS[j],s=26,zorder=4)
  limit=min(v['window_deadline_ms'] for v in r if v['mode']==mode)
  ax[row].axhline(limit,color='#555',ls='--',lw=1)
  ax[row].set(yscale='log',xticks=[0,1,2],xticklabels=names,ylabel='Gesamtlatenz [ms]')
  ax[row].set_title('Sensor-Livebetrieb' if mode=='sensor_live' else 'Zeitgetreues Offline-Replay');ax[row].grid(axis='y',alpha=.2)
 save(fig,'latency_comparison')
 resource=read_csv(BASE/'runtime_analysis/all_resources.csv');fig,ax=plt.subplots(3,2,figsize=(6.3,6.2),sharex=True,layout='constrained')
 for row,m in enumerate(methods):
  f=resource[(resource['mode']=='sensor_live')&(resource.method==m)]
  for repeat,g in f.groupby('repeat'):
   g=g.sort_values('elapsed_s').copy()
   g['second']=np.floor(g.elapsed_s)
   v=g.groupby('second').agg(rss=('process_rss_bytes','mean'))
   # Time-weight interval-ending CPU measurements over each 1-s bin.
   # The first measurement has no recorded prior boundary and stays in raw
   # data but cannot contribute a known-duration interval to this graphic.
   sums={};durations={}
   times=g.elapsed_s.to_numpy();cpu=g.process_cpu_percent_one_core.to_numpy()
   for i in range(1,len(g)):
    left,right=times[i-1],times[i]
    for sec in range(int(np.floor(left)),int(np.floor(right))+1):
     dt=max(0.,min(right,sec+1)-max(left,sec))
     if dt>0:
      sums[sec]=sums.get(sec,0.)+dt*cpu[i];durations[sec]=durations.get(sec,0.)+dt
   v['cpu']=pd.Series({sec:sums[sec]/durations[sec] for sec in sums})
   ax[row,0].plot(v.index,v.cpu,lw=.9,color=COLORS[repeat-1],label='Lauf '+str(repeat))
   ax[row,1].plot(v.index,v.rss/2**20,lw=.9,color=COLORS[repeat-1])
  ax[row,0].set_ylabel(names[row]+'\nCPU [% Kern]');ax[row,1].set_ylabel('RSS [MiB]')
  for col in range(2):
   ax[row,col].axvline(180,color='#555',ls='--',lw=.8);ax[row,col].grid(alpha=.2)
 for j in range(2):ax[-1,j].set_xlabel('Zeit ab Stellbefehl [s]')
 fig.legend(*ax[0,0].get_legend_handles_labels(),loc='outside upper center',ncol=3,frameon=False)
 save(fig,'sensor_live_resources')
 (OUT/'provenance.json').write_text(json.dumps({'inputs_sha256':inputs,'script_sha256':sha(__file__),'cpu_plot_interval_rule':'Time-weight complete recorded monitor intervals into 1-s bins; first unpaired CPU probe excluded only from graphic, raw data retained.', 'note':'Neu gesetzte Darstellungen aus unveränderten vorhandenen Ergebnissen; keine Neu-Kalibrierung oder Fensterselektion.','outputs_sha256':{p.name:sha(p) for p in OUT.iterdir() if p.is_file()}},ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
