#!/usr/bin/env python3
"""Read-only analysis of the predeclared runtime matrix. Never actuates hardware."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone

ROOT = Path('/home/malik/masterarbeit-edge-ai')
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
import pandas as pd
import independent_normal_test as frozen
import pilot_method_comparison as pilot


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def write(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write('\n')


def describe(values):
    x = np.asarray(values, np.float64)
    assert x.size and np.isfinite(x).all()
    return dict(n=int(x.size), mean=float(x.mean()), median=float(np.median(x)),
                p95=float(np.percentile(x, 95)), p99=float(np.percentile(x, 99)),
                minimum=float(x.min()), maximum=float(x.max()),
                sd=float(x.std(ddof=1)) if len(x) > 1 else None)


def check_frame(frame):
    index = frozen.preparation.integral_column(frame, 'sample_index')
    host = frozen.preparation.integral_column(frame, 'host_monotonic_ns')
    assert index[0] == 0 and np.all(np.diff(index) == 1)
    assert np.all(np.diff(host) > 0)
    elapsed = frame.timestamp_s.to_numpy(np.float64)
    assert np.isfinite(elapsed).all() and np.all(np.diff(elapsed) > 0)
    assert np.allclose(elapsed-elapsed[0], (host-host[0])/1e9, rtol=0, atol=1e-7)
    nominal = frame.sensor_time_estimate_s.to_numpy(np.float64)
    assert np.allclose(nominal, index/200, rtol=0, atol=1e-7)
    fifo = frozen.preparation.integral_column(frame, 'fifo_depth')
    assert np.all((fifo >= 1) & (fifo <= 32))
    assert frame.label.eq(0).all() and set(frame.anomaly_type) == {'normal'}


def resource_summary(frame):
    assert len(frame) > 100
    t = frame.elapsed_s.to_numpy(np.float64)
    ns = frame.monotonic_ns.to_numpy(np.int64)
    assert np.all(np.diff(ns) > 0)
    rss = frame.process_rss_bytes.to_numpy(np.float64)/2**20
    cpu = frame.process_cpu_percent_one_core.to_numpy(np.float64)
    dt = np.diff(ns)/1e9
    # psutil deltas belong to the interval ending at each row. The first
    # zero-initialization sample is excluded from the time-weighted CPU mean.
    weighted_cpu = float(np.average(cpu[1:], weights=dt))
    return dict(samples=len(frame), span_s=float(t[-1]-t[0]),
                process_cpu_percent_one_core_time_weighted=weighted_cpu,
                process_cpu_percent_one_core=describe(cpu[1:]),
                process_rss_mib=describe(rss),
                lifetime_peak_rss_mib=float(frame.process_lifetime_peak_rss_bytes.max()/2**20),
                rss_first_mib=float(rss[0]), rss_last_mib=float(rss[-1]),
                rss_first_last_change_mib=float(rss[-1]-rss[0]),
                rss_linear_slope_mib_per_min=float(np.polyfit(t, rss, 1)[0]*60),
                monitor_interval_ms=describe(dt*1000),
                queue_sampled_max=int(frame.queue_pending_windows.max()))


def analyze_trial(spec, protocol, protocol_hash, functions, bundle):
    runtime = BASE / 'runtime_evidence'
    session_path = runtime / (spec['id']+'_session.json')
    session = read(session_path)
    assert session['status'] == 'completed', (spec['id'], session.get('error'))
    assert all(session[k] == spec[k] for k in ('id', 'mode', 'method', 'repeat'))
    assert session['protocol_sha256'] == protocol_hash
    assert session['frozen_bundle_sha256'] == protocol['frozen_bundle_sha256']
    assert session['boot_id'] == protocol['boot_id']
    live = spec['mode'] == 'sensor_live'
    if live:
        csv_path = Path(session['csv'])
        output = Path(session['recording']['runtime_directory'])
        command = session['command_invocation_monotonic_ns']
        metadata = read(csv_path.with_suffix('.json'))
        assert metadata == session['recording']
        assert metadata['csv_sha256'] == digest(csv_path)
        assert metadata['mounting_id'] == protocol['mounting_id']
        assert metadata['purpose'] == 'runtime_test' and metadata['split'] == 'runtime_evidence'
        assert metadata['condition_label'] == 'normal' and metadata['detection_controls_fan'] is False
        assert all(metadata['sensor'][k] == v for k, v in protocol['sensor'].items())
        assert all(session['sensor'][k] == v for k, v in protocol['sensor'].items())
        for key, value in [('initial_readback',0), ('precommand_zero',0),
                           ('setting_result',30000), ('after_capture_readback',30000),
                           ('final_readback',0)]:
            frozen.verify_pwm(session[key], value)
        assert session['additional_off_actual_s'] >= 60
        assert session['physical_stop_observed'] is False
        assert metadata['rpm_measured'] is None
    else:
        csv_path = Path(protocol['replay_csv'])
        output = runtime / spec['id']
        command = protocol['replay_command_ns']
        assert digest(csv_path) == protocol['replay_csv_sha256']
        metadata = None
    frame = pd.read_csv(csv_path, float_precision='round_trip')
    check_frame(frame)
    quality = frozen.summarize_quality(frame, command)
    assert quality['first_to_last_host_span_s'] >= 299.8
    assert 0 <= quality['first_xyz_after_command_s'] < 1
    if live:
        assert int(frame.host_monotonic_ns.iloc[-1]) < session['zero_command_completed_monotonic_ns']
        assert metadata['summary']['samples'] == len(frame)
    else:
        # Replay exports must preserve all raw columns and Float64 values.
        replay_raw = pd.read_csv(output/'raw.csv', float_precision='round_trip')
        pd.testing.assert_frame_equal(frame, replay_raw, check_exact=True)
    windows, selected = frozen.build_windows(frame, command)
    summary = read(output / 'summary.json')
    assert summary['status'] == 'completed'
    assert summary['raw_xyz'] == len(frame)
    assert summary['complete_windows'] == len(windows)
    assert summary['selected_xyz'] == selected['xyz_selected']
    assert summary['trailing_selected_xyz'] == selected['trailing_xyz_not_windowed']
    assert summary['source_mode'] == spec['mode']
    assert summary['warmup_invocations'] == 20
    assert summary['physical_lost_samples'] is None
    decisions = pd.DataFrame([json.loads(line) for line in (output/'decisions.jsonl').read_text().splitlines()])
    events = [json.loads(line) for line in (output/'events.jsonl').read_text().splitlines()]
    assert len(decisions) == summary['decision_rows']
    assert set(decisions.method) == {spec['method']}
    assert len(set(decisions.window_index_in_recording)) == len(decisions)
    assert len(windows) == len(decisions) + summary['windows_dropped'] + summary['unprocessed_windows']
    assert len(events) == summary['windows_dropped']
    for event in events:
        assert event['event'] == 'decision_window_dropped_queue_full'
    assert int(decisions.decision.eq('INVALID').sum()) == summary['invalid_decisions']
    differences = []
    for record in decisions.to_dict('records'):
        index = record['window_index_in_recording']
        window = windows[index]
        for key, value in window['metadata'].items():
            assert record[key] == value, (spec['id'], index, key)
        threshold = bundle['thresholds'][spec['method']]['value']
        assert record['threshold'] == threshold
        if not window['metadata']['quality_valid']:
            assert record['decision'] == 'INVALID' and pd.isna(record['score'])
            continue
        if record['decision'] == 'INVALID':
            # Retain valid-input inference errors as invalid, never as normal.
            assert record['error']
            continue
        x = pilot.standardize_ac(window['ac_float32'], bundle['scaler'])
        expected = float(functions[spec['method']](x.copy()))
        difference = abs(record['score']-expected)
        differences.append(difference)
        assert difference == 0, (spec['id'], index, difference)
        expected_prediction = pilot.common.finite_score(expected, threshold)
        assert int(record['prediction']) == expected_prediction
        assert record['decision'] == ('ANOMALY' if expected_prediction else 'NORMAL')
    resource = pd.read_csv(output / 'resources.csv', float_precision='round_trip')
    # For paced replay, the scheduled arrival clock is an affine translation
    # of original host times. Recover it exactly from every decision's timing.
    offsets = (decisions.decision_monotonic_ns-decisions.complete_to_decision_ns-
               decisions.last_host_monotonic_ns).to_numpy(np.int64)
    assert len(set(offsets)) == 1
    offset = int(offsets[0])
    assert (offset == 0) if live else (offset != 0)
    resource['elapsed_s'] = (resource.monotonic_ns.to_numpy(np.int64)-command-offset)/1e9
    late = resource[(resource.elapsed_s >= 180) & (resource.elapsed_s < 300)]
    valid = decisions[decisions.decision.ne('INVALID')].copy()
    invalid_count = int(decisions.decision.eq('INVALID').sum())
    latency_fields = ['complete_to_decision_ns', 'model_core_ns', 'transfer_in_ns',
                      'transfer_out_ns', 'score_and_other_overhead_ns',
                      'standardization_ns', 'scorer_call_ns', 'dequeue_to_decision_ns',
                      'assembly_ns', 'queue_wait_ns']
    for field in latency_fields:
        assert np.all(valid[field].to_numpy() >= 0), field
    assert np.all(decisions.logging_monotonic_ns >= decisions.decision_monotonic_ns)
    assert np.all(decisions.decision_monotonic_ns >= decisions.dequeue_monotonic_ns)
    deadline_ms = 128/quality['observed_xyz_per_second']*1000
    over = int((valid.complete_to_decision_ns/1e6 >= deadline_ms).sum())
    # Across all complete source windows, not merely adjacent output rows:
    # a dropped decision must not hide a data-boundary interval.
    first_hosts=np.array([w['metadata']['start_host_monotonic_ns'] for w in windows],dtype=np.int64)
    last_hosts=np.array([w['metadata']['last_host_monotonic_ns'] for w in windows],dtype=np.int64)
    boundary=(first_hosts[1:]-last_hosts[:-1])/1e6
    assert np.all(boundary>0)
    result = {**spec, 'source_csv':str(csv_path),
              'inter_window_host_sample_gap_ms':describe(boundary),
              'inter_window_host_sample_gaps_over_10ms':int((boundary>10).sum()),
              'inter_window_host_sample_gaps_over_160ms':int((boundary>160).sum()),
              'complete_window_arrival_interval_ms':describe(np.diff(last_hosts)/1e6), 'source_csv_sha256':digest(csv_path),
              'runtime_directory':str(output), 'session_sha256':digest(session_path),
              'quality':quality, 'selected':selected, 'pipeline':summary,
              'valid_decisions':len(valid), 'invalid_decisions':invalid_count,
              'normal_alarms':int(valid.prediction.eq(1).sum()),
              'source_to_reference_score_max_abs_difference':max(differences,default=None),
              'scores_compared':len(differences),
              'window_deadline_ms':deadline_ms, 'deadline_exceedances':over,
              'deadline_exceedance_fraction':over/len(valid) if len(valid) else None,
              'latency_ms':{f[:-3]:describe(valid[f]/1e6) for f in latency_fields},
              'resource_whole_capture':resource_summary(resource),
              'resource_primary_180_300':resource_summary(late),
              'environment_before':session['environment_before'],
              'environment_after':session['environment_after'],
              'model_load_ms':session['model_load_ns']/1e6,
              'model_warmup_ms':session['model_warmup_ns']/1e6,
              'process_entry_to_ready_ms':session['process_entry_to_ready_ns']/1e6,
              'replay_clock_offset_ns':offset,
              'command_utc':session.get('command_invocation_utc'),
              'command_ns':command if live else None,
              'zero_command_completed_ns':session.get('zero_command_completed_monotonic_ns'),
              'additional_off_actual_s':session.get('additional_off_actual_s'),
              'total_previous_commanded_off_s':None,
              'mechanical_off_duration_s':None,
              'artifact_sha256':{p.name:digest(p) for p in output.iterdir() if p.is_file()}}
    decisions['trial'] = spec['id']; decisions['mode'] = spec['mode']; decisions['repeat'] = spec['repeat']
    resource['trial'] = spec['id']; resource['mode'] = spec['mode']; resource['method'] = spec['method']; resource['repeat'] = spec['repeat']
    return result, decisions, resource


def plot(trials, resources, decisions, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names={'rms':'RMS','isolation_forest':'Isolation Forest','tflite_autoencoder':'TFLite-Autoencoder'}
    colors={'rms':'#0072B2','isolation_forest':'#D55E00','tflite_autoencoder':'#009E73'}
    plt.rcParams.update({'font.size':10, 'axes.spines.top':False, 'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(11,4.3),layout='constrained')
    for j,mode in enumerate(('sensor_live','offline_replay')):
        for i,method in enumerate(pilot.METHODS):
            group=[r for r in trials if r['mode']==mode and r['method']==method]
            for r in group:
                x=i+(r['repeat']-2)*.11
                axes[j].scatter(x,r['latency_ms']['complete_to_decision']['p99'],color=colors[method],s=52,zorder=4)
                axes[j].plot([x,x],[r['latency_ms']['complete_to_decision']['median'],r['latency_ms']['complete_to_decision']['maximum']],color=colors[method],alpha=.6)
        deadline=min(r['window_deadline_ms'] for r in trials if r['mode']==mode)
        axes[j].axhline(deadline,color='#555555',ls='--',label='kleinstes Fensterintervall')
        axes[j].set(xticks=range(3),xticklabels=[names[m] for m in pilot.METHODS],yscale='log',
                    ylabel='Latenz [ms], logarithmische Achse',title='Sensor-Livebetrieb' if j==0 else 'Offline-Replay mit Originalzeitabständen')
        axes[j].tick_params(axis='x',labelsize=8);axes[j].grid(axis='y',alpha=.2);axes[j].legend(fontsize=8)
    fig.suptitle('Je drei Prozesse: Punkt = P99; Linie = Median bis Maximum\nVollständiges Fenster bis verfügbare Entscheidung, Abschnitt [180,300) s',fontsize=11)
    for ext in ('png','pdf'):fig.savefig(output/f'latency_comparison.{ext}',dpi=180)
    plt.close(fig)
    for mode in ('sensor_live','offline_replay'):
        fig,axes=plt.subplots(2,3,figsize=(11,6),sharex=True,layout='constrained')
        for col,method in enumerate(pilot.METHODS):
            f=resources[(resources['mode']==mode)&(resources.method==method)]
            for repeat,g in f.groupby('repeat'):
                # Display one-second arithmetic means only; reported CPU uses
                # original 100-ms intervals and time weighting.
                s=g.assign(second=np.floor(g.elapsed_s).astype(int)).groupby('second').agg(
                    cpu=('process_cpu_percent_one_core','mean'),rss=('process_rss_bytes','mean'))
                axes[0,col].plot(s.index,s.cpu,label=f'Lauf {repeat}',lw=.9)
                axes[1,col].plot(s.index,s.rss/2**20,lw=.9)
            axes[0,col].set_title(names[method]);axes[0,col].legend(fontsize=8)
            for row in range(2):
                axes[row,col].axvline(180,color='#555555',ls='--',lw=.8)
                axes[row,col].grid(alpha=.2)
            axes[1,col].set_xlabel('Zeit ab Stellbefehl bzw. Replay-Ursprung [s]')
        axes[0,0].set_ylabel('Prozess-CPU [% eines Kerns]');axes[1,0].set_ylabel('RSS [MiB]')
        fig.suptitle(('Sensor-Livebetrieb' if mode=='sensor_live' else 'Offline-Replay')+': Ressourcen über den vollständigen Lauf\nModellbewertung erst ab 180 s; je Verfahren drei getrennte Prozesse',fontsize=11)
        for ext in ('png','pdf'):fig.savefig(output/f'{mode}_resources.{ext}',dpi=180)
        plt.close(fig)


def report(trials, output, protocol_hash):
    lines=['# Abschließender Nachweis des lokalen Datenwegs für Aufbau v4', '',
           'Die Laufzeitprüfung verwendet das unveränderte, eingefrorene Pilotpaket. Sie ergänzt die Erkennungstests um Sensor-Livebetrieb und zeitgetreues Offline-Replay. Sie ist kein Nachtraining und keine neue Bewertung einer Defektklasse.', '',
           f'Protokoll-SHA-256: `{protocol_hash}`. Protokoll vor dem ersten Lauf fixiert; vollständige Artefakthashes in `analysis.json`.', '',
           '## Messumfang und Grenzen', '',
           'Je Methode und Betriebsart wurden drei eigene Prozesse vorgesehen. Die Methodenreihenfolge ist über die drei Wiederholungen rotiert. Sensorläufe verwenden unveränderten Aufbau v4 ohne Platte, 75 % PWM bei 25 kHz und nominell 200 Hz. Je Start werden 300 s Rohdaten gespeichert. Nach jeweils mindestens 60 s zusätzlicher Vorgabe 0 % folgt ein einzelner Start; gesamte Auszeiten werden gesondert angegeben. Neue mechanische Sichtprüfungen wurden im ausdrücklich freigegebenen unbeaufsichtigten Ablauf nicht behauptet.', '',
           'Die Modellbewertung beginnt gemäß eingefrorenem Vertrag bei 180 s und endet vor 300 s. Damit werden je Prozess nur 120 s aktiver Modellverarbeitung gemessen. Der gesamte Anlauf wird erfasst, jedoch nicht vom Modell bewertet. 180 s bleiben eine vorläufige Messabschnittswahl. 20 synthetische Modellaufrufe zum Aufwärmen erfolgen vor dem Lüfterstart; sie passen keine Parameter an.', '',
           'Offline-Replay verwendet in allen neun Prozessen dieselbe bereits vorhandene Aufnahme und ihre ursprünglichen Host-Abstände. Es sind keine neuen physikalischen Replikate. Die Sensorläufe verwenden eigene neue Rohdaten. Für den Aufwand je Methode laufen die anderen beiden Methoden jeweils nicht im selben Prozess. Diese neuen Läufe sind deshalb kein Vergleich ihrer Erkennungsleistung auf identischen neuen Signalen.', '',
           'Beim Replay wird die gesamte Quelldatei vor Beginn in einen DataFrame und eine Liste von Datensätzen geladen. Dieser belegte Zusatzspeicher gehört zur Replay-Implementierung; er ist keine Modelldateigröße und kein direkter Maßstab für die stromweise Sensorerfassung. Der kontinuierliche Ressourcenmonitor umfasst die Erfassung/Wiedergabe; Modellstart und abschließendes Laden der gespeicherten Sensor-CSV liegen außerhalb dieses Verlaufs und sind durch getrennte Umgebungssnapshots beziehungsweise Ladezeiten dokumentiert.', '',
           'Keine grafische Oberfläche war beteiligt. Die optionale frühere GUI ist damit nicht als Teil dieses validierten Datenwegs nachgewiesen. Hintergrund: gewöhnliche Betriebssystemdienste sowie kurze lesende Statusabfragen und leichte Dokumentvorbereitung; keine parallel absichtlich laufenden Trainings-, Test- oder Rendering-Benchmarks. Der Rechner ist kein abgeschottetes Echtzeitsystem.', '',
           '## Ergebnisse je vollständigem Prozess', '',
           '| Modus / Methode / Lauf | gültig / ungültig | verworfen / unverarbeitet | P99 gesamt [ms] | P99 Rechenkern [ms] | Fristüberschreitungen | CPU aktiv [% Kern] | max. RSS aktiv [MiB] |',
           '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in trials:
        lines.append(f"| {r['mode']} / {r['method']} / {r['repeat']} | {r['valid_decisions']} / {r['invalid_decisions']} | {r['pipeline']['windows_dropped']} / {r['pipeline']['unprocessed_windows']} | {r['latency_ms']['complete_to_decision']['p99']:.3f} | {r['latency_ms']['model_core']['p99']:.3f} | {r['deadline_exceedances']} | {r['resource_primary_180_300']['process_cpu_percent_one_core_time_weighted']:.2f} | {r['resource_primary_180_300']['process_rss_mib']['maximum']:.2f} |")
    lines += ['', '![Latenzvergleich](latency_comparison.png)', '',
              'CPU: 100 % entspricht einem vollständig ausgelasteten logischen Kern, nicht dem gesamten Vierkernrechner. RSS ist Prozessspeicher einschließlich Python, Bibliotheken, Erfassung und Protokollierung; er ist keine reine Modellgröße. Die zeitgewichtete CPU-Auslastung bezieht sich auf [180,300) s. Die vollständigen Ressourcenreihen werden separat erhalten.', '',
              'Rechenkern: RMS-Berechnung, `IsolationForest.score_samples` oder ausschließlich `Interpreter.invoke`. Tensorübertragung sowie AE-Fehlerberechnung sind außerhalb des AE-Rechenkerns separat gemessen. Die gesamte Latenz beginnt beim Host-Abschluss des letzten XYZ-Punkts im Fenster und umfasst Rohdatenübergabe, Fensteraufbau, Qualitätsprüfung, Float64-Mittelwertentfernung, Queue, gespeicherte Standardisierung und Entscheidung. Sie endet vor dem Schreiben der Entscheidung ins Journal. Die Fensterfüllzeit und noch nicht am Host sichtbare Sensor-/FIFO-Zeit sind nicht enthalten.', '',
              '## Zeitbasis, Datenqualität und Auszeiten', '',
              '| Sensorlauf | XYZ | beobachtet [XYZ/s] | erster Punkt nach Befehl [ms] | längster Host-Abstand [ms] | Gap / Overrun / Sättigung | gesamte vorherige 0-%-Zeit [s] |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for r in trials:
        if r['mode']!='sensor_live':continue
        q=r['quality'];off=r['total_previous_commanded_off_s'];off_text='unbekannt' if off is None else f'{off:.3f}'
        lines.append(f"| {r['id']} | {q['xyz_points']} | {q['observed_xyz_per_second']:.6f} | {q['first_xyz_after_command_s']*1000:.3f} | {q['host_interval_max_ms']:.3f} | {q['gap_flagged_xyz']} / {q['overrun_flagged_xyz']} / {q['saturated_flagged_xyz']} | {off_text} |")
    lines += ['', 'Nominelle Sensor-ODR: 200 Hz. Beobachteter Durchsatz: (XYZ-Punkte − 1) / Zeit zwischen erstem und letztem Host-Zeitstempel. Ein XYZ-Punkt enthält drei einzelne Achsenwerte. Sampleindex/200 ist nur eine rechnerische Sensorzeit. Die monotone Host-Zeit und die daraus abgeleitete relative CSV-Zeit werden getrennt geprüft. Die Abweichung von ungefähr 3,5 % ist nicht durch das Zählen der drei Achsen erklärbar. Ein unbekannter Sensortakt und unbekannte physische Verluste werden nicht nachträglich durch eine korrigierte Sollrate ersetzt.', '',
              'Zwischen vollständigen Fenstern wurden zusätzlich der Abstand vom letzten XYZ-Punkt zum ersten Punkt des Folgefensters sowie die Zeit zwischen zwei vollständigen Fensterankünften geprüft. Diese Host-Abstände stehen je Lauf in analysis.json. Ein solcher Abstand ist kein unabhängig gemessener Stillstand der Sensorwandlung; verworfene Entscheidungen werden bei der Prüfung der Rohfenstergrenzen nicht übergangen.', '',
              'Die dargestellten Auszeiten beginnen bei der vorigen abgeschlossenen 0-%-Rückstellung. Sie sind softwareseitige Auszeiten, keine gemessene mechanische Stillstandsdauer. PWM-Rücklesung und mechanischer Zustand sind verschiedene Nachweise; die Drehzahl bleibt unbekannt.', '',
              '## Ressourcenverlauf und numerische Konsistenz', '',
              '![Sensor-Ressourcen](sensor_live_resources.png)', '',
              '![Replay-Ressourcen](offline_replay_resources.png)', '',
              f"Für {sum(r['scores_compared'] for r in trials)} ausgegebene gültige Scores wurde der identische eingefrorene Offline-Datenweg erneut auf genau denselben Rohfenstern angewendet. Die maximale absolute Scoreabweichung beträgt {max(r['source_to_reference_score_max_abs_difference'] for r in trials):.1f}; auch die Entscheidungen stimmen überein. Dies ist eine Software-Konsistenzprüfung, keine unabhängige Erkennungsvalidierung.", '',
              'Die begrenzte Queue fasst vier vollständige Fenster; bei Überlast wird das neue Entscheidungsfenster mit Ereignisprotokoll verworfen, während die Rohdaten erhalten bleiben. Bereits vor der Hardwareprüfung wurden Qualitätsfehler, Queue-Überlast, Quellenfehler, Float64/Float32-Gleichheit und die 0-%-Rückstellung bei Fehler beziehungsweise Unterbrechung mit Softwaretests geprüft. Reale Nullbefunde der Flags beweisen keine physikalische Verlustfreiheit.', '',
              '## Schlussfolgerung und verbleibender Umfang', '']
    live=[r for r in trials if r['mode']=='sensor_live']
    h2=all(r['latency_ms']['complete_to_decision']['p99']<r['window_deadline_ms'] for r in live)
    deltas=[r['resource_primary_180_300']['rss_first_last_change_mib'] for r in live]
    lines += [f"Der RSS-Unterschied zwischen erster und letzter Ressourcenprobe in [180,300) s beträgt im Sensorbetrieb {min(deltas):.3f} bis {max(deltas):.3f} MiB. Ein positiver Verlauf wird ausdrücklich erhalten. Null Rückstand und kein Speicherabbruch in 300 s belegen für sich keinen stationären Speicherbedarf; eine Speicherleck-Ursache wird aus RSS allein nicht abgeleitet. Eine gegebenenfalls anschließende instrumentierte Speicherdiagnose ist vom Benchmark getrennt und verändert seine Messwerte nicht.", '']
    lines += [f"H2 ist im definierten Sensor-Liveumfang {'erfüllt' if h2 else 'nicht durchgängig erfüllt'}: Maßstab ist das empirische P99 gegenüber dem pro Lauf beobachteten Fensterintervall. Insgesamt wurden {sum(r['deadline_exceedances'] for r in live)} Überschreitungen unter {sum(r['valid_decisions'] for r in live)} gültigen Entscheidungen gezählt. Eine harte Echtzeitgarantie oder ein Nachweis über industriellen Dauerbetrieb folgt daraus nicht.", '',
              f"Die Sensorläufe meldeten insgesamt {sum(r['pipeline']['windows_dropped'] for r in live)} verworfene Entscheidungsfenster, {sum(r['pipeline']['unprocessed_windows'] for r in live)} unverarbeitete Fenster und {sum(r['invalid_decisions'] for r in live)} ungültige Entscheidungen. Speicher- und Rückstandsverläufe werden für die gemessene Dauer beurteilt; ein endlicher Lauf beweist keine allgemeine Speicherobergrenze über unbegrenzte Laufzeiten.", '',
              'Die bisherigen Fehlalarme und die schwache Erkennung des Plattenzustands bleiben unverändert gültige Ergebnisse. Für eine gesicherte Defekterkennung fehlen weiterhin passende unabhängige Defektaufnahmen. Die fehlende Drehzahlmessung und nicht vollständig geklärte physische Zeitbasis begrenzen die Interpretation. Diese Punkte werden als nicht oder nur teilweise erfüllte Nachweise in der Arbeit ausgewiesen. Ein erneut geändertes Modell benötigte eine neue Version und neue, zuvor ungenutzte Tests.', '',
              'Empfehlung: Das unveränderte Pilotpaket mit diesen Grenzen abschließend dokumentieren. Keine weitere Wiederholung derselben Normalaufnahme zur Verbesserung von Kennzahlen. Ein späterer Defektversuch oder ein genauer Drehzahl-/Sensortaktnachweis ist ein eigener, vorher festzulegender Messauftrag mit geeigneter zusätzlicher physischer Vorbereitung.']
    (output/'runtime_report.md').write_text('\n'.join(lines)+'\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    runtime=BASE/'runtime_evidence';p=read(runtime/'protocol.json');ph=digest(runtime/'protocol.json')
    assert (runtime/'protocol.sha256').read_text().strip()==ph
    assert len(p['trials'])==18
    for path,expected in p['implementation_sha256'].items():assert digest(path)==expected,path
    bundle=pilot.load_bundle(p['bundle_directory'])
    assert digest(Path(p['bundle_directory'])/'pilot_bundle.json')==p['frozen_bundle_sha256']
    for spec in p['trials']:
        assert read(runtime/(spec['id']+'_session.json'))['status']=='completed'
    args.output.mkdir(parents=True,exist_ok=False)
    functions,_=pilot.model_scorers(bundle,p['bundle_directory'])
    trials=[];all_decisions=[];all_resources=[];previous_zero=None
    for spec in p['trials']:
        result,decisions,resources=analyze_trial(spec,p,ph,functions,bundle)
        if result['mode']=='sensor_live':
            if previous_zero is not None:result['total_previous_commanded_off_s']=(result['command_ns']-previous_zero)/1e9
            previous_zero=result['zero_command_completed_ns']
        trials.append(result);all_decisions.append(decisions);all_resources.append(resources)
        print(spec['id'],result['valid_decisions'],'valid; exact scores verified',flush=True)
    decisions=pd.concat(all_decisions,ignore_index=True);resources=pd.concat(all_resources,ignore_index=True)
    decisions.to_csv(args.output/'all_decisions.csv',index=False);resources.to_csv(args.output/'all_resources.csv',index=False)
    flattened=[]
    for r in trials:
        flattened.append({**{k:r[k] for k in ['id','mode','method','repeat','valid_decisions','invalid_decisions','normal_alarms','window_deadline_ms','deadline_exceedances','model_load_ms','model_warmup_ms','process_entry_to_ready_ms']},
                          'windows_dropped':r['pipeline']['windows_dropped'],'unprocessed_windows':r['pipeline']['unprocessed_windows'],
                          **{f'{field}_{stat}_ms':v[stat] for field,v in r['latency_ms'].items() for stat in ['median','p95','p99','maximum']},
                          'cpu_primary_percent_one_core':r['resource_primary_180_300']['process_cpu_percent_one_core_time_weighted'],
                          'rss_primary_max_mib':r['resource_primary_180_300']['process_rss_mib']['maximum'],
                          'rss_primary_slope_mib_per_min':r['resource_primary_180_300']['rss_linear_slope_mib_per_min'],
                          'queue_high_watermark':r['pipeline']['queue_high_watermark']})
    pd.DataFrame(flattened).to_csv(args.output/'trial_comparison.csv',index=False)
    write(args.output/'analysis.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),protocol_sha256=ph,
              frozen_bundle_sha256=p['frozen_bundle_sha256'],trials=trials,
              artifact_sizes_bytes={name:(Path(p['bundle_directory'])/name).stat().st_size for name in ['autoencoder_float32.tflite','isolation_forest.joblib','scaler.joblib','pilot_bundle.json']},
              analysis_source_sha256=digest(__file__),GUI_included=False,physical_losses=None,measured_rpm=None))
    plot(trials,resources,decisions,args.output);report(trials,args.output,ph)
    write(args.output/'artifact_inventory.json',{p.name:digest(p) for p in args.output.iterdir() if p.is_file()})


if __name__=='__main__':main()
