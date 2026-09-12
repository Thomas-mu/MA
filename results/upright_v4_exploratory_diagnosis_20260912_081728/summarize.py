"""Descriptive summaries/graphics only; no decision thresholds or model fitting."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

B=Path(__file__).resolve().parent
D=pd.read_csv(B/'window_diagnostics.csv')
S=np.load(B/'spectra_and_reconstruction.npz')
V=json.loads((B/'verification.json').read_text())
plt.rcParams.update({'font.size':10,'axes.grid':True,'grid.alpha':.2})
COLORS=['#3274a1','#e1812c','#3a923a']
NAMES=['train_normal_before','train_normal_after','validation','normal_test_01','normal_test_02','normal_test_03','normal_sep11','normal_before','airflow_modified','normal_after']
SHORT=['Train N1','Train N2','Valid. N','Test N1','Test N2','Test N3','N 11.09.','N vorher','Platte','N nachher']
def save(fig,name):
    fig.savefig(B/(name+'.png'),dpi=160,bbox_inches='tight');fig.savefig(B/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
def write(name,data):
    with (B/name).open('x') as f:json.dump(data,f,indent=2,ensure_ascii=False,allow_nan=False)

fig,axes=plt.subplots(3,1,figsize=(12,11),sharex=True)
for ax,kind,ylabel in zip(axes,['physical','standard','error'],['Physische Achsenenergie / mg²','Standardisierte Achsenenergie / 3','Beitrag zum AE-Score (MSE / 3)']):
    bottom=np.zeros(len(NAMES))
    for a,color in zip('xyz',COLORS):
        values=[]
        for name in NAMES:
            g=D[D.name==name]
            values.append(float((g[a+'_rms_mg']**2).mean()) if kind=='physical' else float(g[a+('_standard_energy' if kind=='standard' else '_ae_mse')].mean()/3))
        ax.bar(np.arange(len(NAMES)),values,bottom=bottom,label=a.upper(),color=color);bottom+=values
    if kind=='error':ax.axhline(V['thresholds']['tflite_autoencoder']['value'],color='black',ls='--',label='Eingefrorene AE-Schwelle')
    ax.set_ylabel(ylabel);ax.legend(loc='upper left',ncol=4);ax.axvline(6.5,color='grey',ls=':')
axes[-1].set_xticks(range(len(NAMES)),SHORT,rotation=25,ha='right')
fig.suptitle('Explorative Zerlegung auf denselben 128er-Fenstern; Balkenmittel je Aufnahme',fontsize=14)
fig.tight_layout();save(fig,'axis_decomposition')

n=D[D.name=='normal_before'];p=D[D.name=='airflow_modified']
fig,axes=plt.subplots(3,1,figsize=(12,10),sharex=True)
axes[0].plot(n.start_since_command_s,n.tflite_autoencoder,label='AE-Score Normal vorher',color='tab:blue')
alarms=n[n.ae_alarm];axes[0].scatter(alarms.start_since_command_s,alarms.tflite_autoencoder,color='crimson',s=15,label='51 Fehlalarme',zorder=3)
axes[0].axhline(V['thresholds']['tflite_autoencoder']['value'],ls='--',color='black',label='eingefrorene Schwelle')
axes[0].set_ylabel('AE-MSE');axes[0].legend(ncol=3)
for a,color in zip('xyz',COLORS):axes[1].plot(n.start_since_command_s,n[a+'_ae_mse']/3,label=a.upper()+'-Beitrag',color=color)
axes[1].set_ylabel('Achsenbeitrag zum AE-Score');axes[1].legend(ncol=3)
axes[2].plot(n.start_since_command_s,n.x_rms_mg,label='X-RMS / mg',color=COLORS[0]);axes[2].plot(n.start_since_command_s,n.y_rms_mg,label='Y-RMS / mg',color=COLORS[1]);axes[2].plot(n.start_since_command_s,n.z_rms_mg,label='Z-RMS / mg',color=COLORS[2]);axes[2].set_ylabel('Physischer Achsen-RMS / mg');axes[2].set_xlabel('Fensterbeginn seit Stellbefehlsaufruf / s');axes[2].legend(ncol=3)
fig.suptitle('Normale Fehlalarme: unveränderte Fenster und vollständiger Bewertungsabschnitt',fontsize=14);fig.tight_layout();save(fig,'normal_false_alarm_timing')

fig,axes=plt.subplots(2,3,figsize=(14,8),sharex=True)
groups=[('Train normal',D.group=='train','#777777'),('Validierung normal',D.name=='validation','#9467bd'),('Normal vorher: Alarm',(D.name=='normal_before')&D.ae_alarm,'#c62828'),('Normal vorher: kein Alarm',(D.name=='normal_before')&~D.ae_alarm,'#3274a1'),('Platte',D.name=='airflow_modified','#e1812c')]
f=S['frequency_hz_nominal']
for row,kind in enumerate(['standard_psd','residual_psd']):
    for j,a in enumerate('XYZ'):
        ax=axes[row,j]
        for label,mask,color in groups:ax.semilogy(f[1:],S[kind][mask.to_numpy(),:,j].mean(axis=0)[1:],label=label,color=color)
        ax.set_title(a+(' – standardisiertes Eingangssignal' if row==0 else ' – Rekonstruktionsrest'))
        ax.set_ylabel('Mittlere Leistungsdichte / Hz⁻¹');ax.set_xlabel('Nominelle Frequenzachse / Hz')
axes[0,0].legend(fontsize=8)
fig.suptitle('Hann-Periodogramm je identischem 128er-Fenster, nominell 200 Hz; keine Drehzahlmessung',fontsize=12);fig.tight_layout();save(fig,'spectral_diagnosis')

fig,axes=plt.subplots(1,2,figsize=(12,5))
for label,mask,color in [('Train/Validierung',D.group.isin(['train','validation']),'#999999'),('Unabhängige Normaltests',D.group=='independent_normal','#9467bd'),('Normal vorher',D.name=='normal_before','#3274a1'),('Platte',D.name=='airflow_modified','#e1812c'),('Normal nachher',D.name=='normal_after','#3a923a')]:
    g=D[mask];axes[0].scatter(g.physical_vector_ac_rms_mg,g.tflite_autoencoder,s=9,alpha=.4,label=label,color=color);axes[1].scatter(g.x_ae_mse,g.y_ae_mse,s=9,alpha=.4,color=color)
axes[0].axhline(V['thresholds']['tflite_autoencoder']['value'],ls='--',color='black');axes[0].set_xlabel('Physischer Vektor-AC-RMS / mg');axes[0].set_ylabel('AE-Score');axes[0].legend(fontsize=8)
axes[1].set_xlabel('X-Achsen-MSE');axes[1].set_ylabel('Y-Achsen-MSE')
fig.suptitle('Explorative Merkmalsüberlappung; Punkte sind abhängige Modellfenster');fig.tight_layout();save(fig,'normal_variability_overlap')

features=['physical_vector_ac_rms_mg','x_rms_mg','y_rms_mg','z_rms_mg','rms','isolation_forest','tflite_autoencoder','x_ae_mse','y_ae_mse','z_ae_mse','standard_high_fraction']
overlap=[]
for label,ref in [('training_only',D[D.group=='train']),('normal_validation',D[D.name=='validation']),('training_and_validation',D[D.group.isin(['train','validation'])]),('earlier_independent_normals',D[D.group=='independent_normal']),('all_preexisting_normal_sources',D[D.group.isin(['train','validation','independent_normal'])])]:
    joint=np.ones(len(p),bool)
    for k in features:
        low,high=ref[k].min(),ref[k].max();inside=p[k].between(low,high);joint &= inside.to_numpy()
        overlap.append({'reference':label,'feature':k,'min':low,'max':high,'p05':ref[k].quantile(.05),'p95':ref[k].quantile(.95),'plate_inside_minmax':int(inside.sum()),'plate_inside_p05_p95':int(p[k].between(ref[k].quantile(.05),ref[k].quantile(.95)).sum()),'plate_N':len(p)})
    overlap.append({'reference':label,'feature':'all_features_axis_aligned_box_NOT_joint_support','plate_inside_minmax':int(joint.sum()),'plate_N':len(p)})
pd.DataFrame(overlap).to_csv(B/'normal_envelope_overlap.csv',index=False,mode='x')
groups=[]
for name,g in [('normal_before_false_alarm',n[n.ae_alarm]),('normal_before_no_alarm',n[~n.ae_alarm]),('plate',p),('training',D[D.group=='train']),('validation',D[D.name=='validation'])]:
    row={'group':name,'windows':len(g)}
    row.update({k:float(g[k].mean()) for k in features+[a+s for a in 'xyz' for s in ['_residual_energy_ratio','_input_reconstruction_corr','_power_fraction_0_20','_power_fraction_20_60','_power_fraction_60_100','_residual_power_fraction_0_20','_residual_power_fraction_20_60','_residual_power_fraction_60_100']]})
    groups.append(row)
pd.DataFrame(groups).to_csv(B/'false_alarm_feature_groups.csv',index=False,mode='x')
time=[]
for name,g in D.groupby('name',sort=False):
    for low in [180,210,240,270]:
        h=g[g.start_since_command_s.between(low,low+30,inclusive='left')]
        time.append({'name':name,'start_s':low,'end_s':low+30,'windows':len(h),'ae_alarms':int(h.ae_alarm.sum()),'mean_ae_score':float(h.tflite_autoencoder.mean())})
pd.DataFrame(time).to_csv(B/'false_alarm_timing_30s.csv',index=False,mode='x')
corr=n[features].corr()['tflite_autoencoder'].drop('tflite_autoencoder').to_dict()
write('descriptive_correlations.json',{'scope':'normal_before same 194 windows; dependent observations, no p-values or causal claim','pearson':corr})
row={}
for name,g in D.groupby('name',sort=False):
    means=np.array([(g[a+'_rms_mg']**2).mean() for a in 'xyz']);mse=np.array([g[a+'_ae_mse'].mean() for a in 'xyz'])
    row[name]={'physical_energy_xyz_mg2':means.tolist(),'physical_energy_share_xyz':(means/means.sum()).tolist(),'ae_mse_axis':mse.tolist(),'ae_error_contribution_fraction_xyz':(mse/mse.sum()).tolist()}
scale=np.array(V['scaler']['scale']);write('axis_algebra.json',{'per_recording':row,'inverse_variance_weights_relative_to_z':((scale[2]/scale)**2).tolist(),'note':'MSE score equals mean of three axis MSE; physical vector RMS sums raw axis energies. Different weighting and reconstruction explain why these need not increase together.'})
print('Summary tables and four graphics saved.')
