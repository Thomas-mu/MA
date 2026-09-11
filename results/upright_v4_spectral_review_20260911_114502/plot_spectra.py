"""Read-only plotting of completed spectral tables."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent
OUT = BASE / 'analysis'
NAMES = {'standstill': 'Stillstand', 'normal_before': 'Normal vor Platte',
         'airflow_modified': 'Mit Platte', 'normal_after': 'Normal nach Platte',
         'normal_followup': 'Zusätzlicher Normallauf'}
COLORS = {'standstill': 'gray', 'normal_before': 'tab:blue', 'airflow_modified': 'tab:red',
          'normal_after': 'tab:orange', 'normal_followup': 'tab:green'}
assert not (OUT/'spectral_comparison.png').exists()
fig, axes = plt.subplots(3, 1, figsize=(11, 10), layout='constrained')
for phase, name in NAMES.items():
    d = pd.read_csv(OUT/f'{phase}_spectra.csv')
    f = d.frequency_hz_observed.to_numpy(); p = d.summed_xyz_psd_g2_per_hz.to_numpy()
    axes[0].semilogy(f[1:], p[1:], label=name, color=COLORS[phase], alpha=.85)
    if phase == 'standstill':
        continue
    mask = (f >= 1) & (f < 90)
    axes[1].plot(f[mask], p[mask] / (p[mask].sum() * (f[1]-f[0])), label=name, color=COLORS[phase])
    axes[2].plot(f, p*1e6, label=name, color=COLORS[phase])
axes[0].set(xlim=(0, 104), xlabel='Frequenz [Hz], aus Durchsatz geschätzt', ylabel='Summierte XYZ-PSD [g²/Hz]', title='Absolute Leistung: Betrieb 180–300 s; Stillstand 0–30 s')
axes[1].set(xlim=(30, 60), xlabel='Frequenz [Hz], aus Durchsatz geschätzt', ylabel='Normierte PSD [1/Hz]', title='Auf Gesamtleistung in 1–90 Hz normiert; Ausschnitt 30–60 Hz')
axes[2].set(xlim=(37, 42), xlabel='Frequenz [Hz], aus Durchsatz geschätzt', ylabel='Summierte XYZ-PSD [mg²/Hz]', title='Explorativer Ausschnitt des dominierenden Anteils; kein unabhängiger Test')
for ax in axes:
    ax.legend(); ax.grid(alpha=.25)
fig.suptitle('Aufbauversion v4: vorhandene Aufnahmen, keine neuen Starts\nHann, 1024 XYZ-Punkte, 50 % Überlappung; keine gemessene Drehzahl')
fig.savefig(OUT/'spectral_comparison.png', dpi=160); fig.savefig(OUT/'spectral_comparison.pdf'); plt.close(fig)

fig, axes = plt.subplots(3, 1, figsize=(11, 10), layout='constrained')
for phase, name in NAMES.items():
    if phase == 'standstill':
        continue
    d = pd.read_csv(OUT/f'{phase}_five_second_spectral_bands.csv')
    x = d.start_s + 2.5
    axes[0].plot(x, d.vector_ac_rms_mg, 'o-', markersize=3, label=name, color=COLORS[phase])
    axes[1].plot(x, np.sqrt(d.band_2_power_g2)*1000, 'o-', markersize=3, label=name, color=COLORS[phase])
    axes[2].plot(x, d.band_2_fraction*100, 'o-', markersize=3, label=name, color=COLORS[phase])
for ax in axes:
    ax.axvspan(180, 300, color='gray', alpha=.12)
    ax.set(xlim=(0, 300), xlabel='Zeit seit jeweiligem PWM-Befehlsaufruf [s]')
    ax.legend(); ax.grid(alpha=.25)
axes[0].set(ylabel='Vektor-AC-RMS [mg]', title='Ungewichtete 5-s-AC-RMS-Werte')
axes[1].set(ylabel='Band-RMS [mg]', title='Hann-gewichtete Energie im vorab gewählten Band 30–60 Hz')
axes[2].set(ylabel='Leistungsanteil [%]', title='Band 30–60 Hz relativ zur gesamten positiven Spektralleistung')
fig.suptitle('Zeitlicher Verlauf: eigene Achsenmittelwerte je 5-s-Abschnitt entfernt\nBand-RMS und ungewichteter Gesamt-RMS verwenden unterschiedliche Gewichtungen')
fig.savefig(OUT/'spectral_time_course.png', dpi=160); fig.savefig(OUT/'spectral_time_course.pdf'); plt.close(fig)
print('Four plot files saved.')
