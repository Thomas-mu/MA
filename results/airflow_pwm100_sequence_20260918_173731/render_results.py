"""Display recorded phase results and capture the actual Tk results window."""
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import time

BASE = Path(__file__).resolve().parent
os.environ.update(DISPLAY=':99', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                  MPLCONFIGDIR='/tmp/masterarbeit_matplotlib')
PHASES = [('normal_before', '1 · Ohne Platte', '#176b9f'),
          ('airflow_modified', '2 · Mit Platte', '#d26a19'),
          ('normal_after', '3 · Wieder ohne Platte', '#29814d')]
METHODS = [('rms', 'RMS-Modell'), ('isolation_forest', 'Isolation Forest'),
           ('tflite_autoencoder', 'TFLite-Autoencoder')]

def main():
    import numpy as np
    import pandas as pd
    completed = {}
    for phase, title, color in PHASES:
        path = BASE / f'{phase}_session.json'
        if path.exists():
            session = json.loads(path.read_text())
            if session['status'] == 'completed':
                rows = [json.loads(line) for line in (BASE / f'{phase}_decisions.jsonl').read_text().splitlines()]
                frame = pd.read_csv(session['csv'], float_precision='round_trip')
                seconds = (frame.host_monotonic_ns-session['command_invocation_monotonic_ns'])/1e9
                blocks = []
                for start in range(0, 300, 5):
                    block = frame.loc[(seconds >= start) & (seconds < start+5)]
                    if block.empty:
                        continue
                    raw = block[['x_g','y_g','z_g']].to_numpy(np.float64)
                    centered = raw-raw.mean(axis=0)
                    flags = any(block[k].astype(str).str.lower().isin(['true','1','1.0']).any()
                                for k in ['gap','overrun','saturated'])
                    blocks.append(dict(start_s=start, center_s=start+2.5, samples=len(block),
                        vector_ac_rms_g=float(np.sqrt(np.mean(np.sum(centered**2, axis=1)))),
                        has_sensor_flags=bool(flags)))
                rms_path = BASE / f'{phase}_physical_rms_5s.csv'
                if not rms_path.exists():
                    pd.DataFrame(blocks).to_csv(rms_path,index=False)
                completed[phase] = dict(session=session, decisions=rows, blocks=blocks)
    if not completed:
        raise RuntimeError('No completed phase results to display')
    latest = list(completed)[-1]
    screenshot = BASE / f'screenshot_{latest}.png'
    figure_path = BASE / f'comparison_through_{latest}.png'
    if screenshot.exists() or figure_path.exists():
        raise FileExistsError('Result images already exist; no overwrite')
    if Path('/tmp/.X11-unix/X99').exists():
        raise RuntimeError('Display :99 already occupied')
    server = subprocess.Popen(['/tmp/edge-ai-screenshot-xvfb/usr/bin/Xvfb', ':99',
                               '-screen', '0', '1440x1080x24', '-nolisten', 'tcp'],
                               stdout=(BASE / f'{latest}_display.log').open('w'), stderr=subprocess.STDOUT)
    try:
        for _ in range(100):
            if server.poll() is not None:
                raise RuntimeError('Virtual display failed')
            if Path('/tmp/.X11-unix/X99').exists():
                break
            time.sleep(.05)
        import matplotlib
        matplotlib.use('TkAgg')
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        import tkinter as tk
        from PIL import ImageGrab
        root = tk.Tk()
        root.title('Plattenversuch bei 100 % PWM – Messergebnisse')
        root.geometry('1440x1080+0+0')
        root.configure(bg='#f3f6f9')
        tk.Label(root, text='100 % PWM · Ohne Platte → Mit Platte → Wieder ohne Platte',
                 font=('Helvetica', 23, 'bold'), bg='#17354d', fg='white', pady=16).pack(fill='x')
        tk.Label(root, text=f'{len(completed)} von 3 Phasen abgeschlossen | 300 s je Phase | Sensor-ODR 200 Hz | PWM nach Messung: 0 %',
                 font=('Helvetica', 13), bg='#e7eff5', fg='#17354d', pady=10).pack(fill='x')
        table = tk.Frame(root, bg='white', padx=20, pady=12)
        table.pack(fill='x', padx=20, pady=(12, 0))
        headings = ['Messphase', 'Zustand', 'RMS: Alarme', 'IF: Alarme', 'AE: Alarme', 'Gültige Fenster']
        for column, heading in enumerate(headings):
            table.grid_columnconfigure(column, weight=1)
            tk.Label(table, text=heading, font=('Helvetica', 12, 'bold'), bg='white', fg='#364f63').grid(row=0,column=column,sticky='w',padx=7,pady=5)
        for index,(phase,title,color) in enumerate(PHASES,1):
            if phase in completed:
                session=completed[phase]['session']
                metrics=session['metrics']
                alarm_values=[f"{100*metrics[m]['alarm_fraction']:.1f} %" if metrics[m]['alarm_fraction'] is not None else 'ungültig' for m,_ in METHODS]
                selection=session['selection']
                values=[title,'Abgeschlossen',*alarm_values,f"{selection['quality_valid_windows']} / {selection['full_model_windows']}"]
            else:
                values=[title,'Ausstehend','–','–','–','–']
            for column,value in enumerate(values):
                tk.Label(table,text=value,font=('Helvetica',12),bg='white',fg=color if column==0 else '#223344').grid(row=index,column=column,sticky='w',padx=7,pady=5)
        fig=Figure(figsize=(13.8,6),dpi=100,facecolor='#f3f6f9')
        axes=fig.subplots(2,2)
        for ax,(method,title) in zip(axes.flat,METHODS):
            for phase,label,color in PHASES:
                if phase not in completed:
                    continue
                rows=[r for r in completed[phase]['decisions'] if r['method']==method]
                ax.plot([r['start_since_command_s'] for r in rows],
                        [r['score']/r['threshold'] if r['score'] is not None else np.nan for r in rows],
                        color=color,label=label,linewidth=1.3)
            ax.axhline(1,color='#b23838',linestyle='--',linewidth=1,label='P99-Schwelle')
            ax.set_title(title,loc='left',fontweight='bold')
            ax.set_xlabel('Sekunden seit PWM-Start')
            ax.set_ylabel('Modellscore / P99-Schwelle')
            ax.set_xlim(180,300)
            ax.grid(alpha=.2)
            ax.legend(fontsize=8,loc='best')
        ax=axes.flat[3]
        for phase,label,color in PHASES:
            if phase in completed:
                blocks=completed[phase]['blocks']
                ax.plot([b['center_s'] for b in blocks],[b['vector_ac_rms_g'] for b in blocks],color=color,label=label,linewidth=1.5)
                flagged=[b for b in blocks if b['has_sensor_flags']]
                if flagged:
                    ax.scatter([b['center_s'] for b in flagged], [b['vector_ac_rms_g'] for b in flagged],
                               color=color, marker='x', s=45, zorder=4, label='Sensorflags · '+label)
        ax.axvspan(180,300,color='#17354d',alpha=.05)
        ax.set_title('Gemessene Schwingung · Vektor-AC-RMS',loc='left',fontweight='bold')
        ax.set_xlabel('Sekunden seit PWM-Start · 5-s-Abschnitte')
        ax.set_ylabel('Beschleunigung [g]')
        ax.set_xlim(0,300)
        ax.grid(alpha=.2)
        ax.legend(fontsize=8,loc='best')
        fig.tight_layout(pad=2.3)
        fig.savefig(figure_path,dpi=150)
        canvas=FigureCanvasTkAgg(fig,master=root)
        canvas.draw()
        quality=completed[latest]['session']['quality']
        details=f"Letzte Phase: {quality['xyz_points']:,} XYZ-Punkte | Lückenflags {quality['gap_flagged_xyz']} | Überlaufflags {quality['overrun_flagged_xyz']} | Sättigungsflags {quality['saturated_flagged_xyz']}"
        tk.Label(root,text=details,font=('Helvetica',11),bg='#f3f6f9',fg='#223344',pady=3).pack(side='bottom',fill='x')
        tk.Label(root,text='Eingefrorenes v4-Modell (Referenz: 75 % PWM). Auswertung: 180–300 s. Alarmanteile sind kein Defektnachweis.',
                 font=('Helvetica',11),bg='#fff1cb',fg='#554322',pady=7).pack(side='bottom',fill='x')
        canvas.get_tk_widget().pack(fill='both',expand=True,padx=12)
        def capture():
            root.update_idletasks()
            ImageGrab.grab(xdisplay=':99').save(screenshot)
            root.destroy()
        root.after(700,capture)
        root.mainloop()
        print(screenshot)
    finally:
        server.terminate()
        server.wait(timeout=5)

if __name__=='__main__':
    main()
