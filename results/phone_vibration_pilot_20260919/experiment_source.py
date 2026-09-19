"""Headless, operator-managed phone-vibration pilot; never controls the fan.

One method per process. Call cues are not physical ground-truth timestamps.
Figures are generated after capture so plotting does not load the measured Pi.
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import json
import math
import os
from pathlib import Path
import shutil
import signal
import threading
import time
from datetime import datetime, timezone

import numpy as np

import common_comparison as common
from live_pipeline import BufferedAcquisition, ProcessMetrics, Sample


def utc():
    return datetime.now(timezone.utc).isoformat()


def pwm_readback():
    root = Path('/sys/class/pwm/pwmchip0/pwm2')
    values = {key: int((root / key).read_text()) for key in ('period', 'duty_cycle', 'enable')}
    values['percent'] = 100 * values['duty_cycle'] / values['period']
    return values


def prepare(bundle_path, output, pwm):
    bundle_path, output = Path(bundle_path).resolve(), Path(output).resolve()
    bundle = common.load_bundle(bundle_path)
    output.mkdir(parents=True, exist_ok=False)
    # Freeze a private copy before any trial; source profiles stay untouched.
    shutil.copytree(bundle_path, output / 'bundle')
    shutil.copy2(__file__, output / 'experiment_source.py')
    plan = {
        'created_utc': utc(), 'status': 'awaiting_final_phone_setup',
        'pwm_percent': pwm, 'methods': list(common.METHODS),
        'events_per_method': 1, 'normal_lead_in_seconds': 30,
        'suggested_vibration_seconds': 5, 'minimum_rest_seconds': 15,
        'bundle_sha256': common.sha256(output / 'bundle/bundle.json'),
        'thresholds': bundle['thresholds'],
        'sampling_rate_hz': bundle['sampling_rate_hz'],
        'window_size': bundle['window_size'],
        'ground_truth': 'Call cues only; actual physical onset/end not measured.',
        'evidence_scope': 'pilot_only_until_final_setup_calibration_and_independent_onset_reference',
        'setup_confirmed': False, 'phone_description': None,
        'limitations': bundle.get('limitations', []),
        'operator_tasks': ['record cues', 'capture raw data', 'single-method resources',
                           'export figures', 'archive provenance and failures'],
    }
    common.write_json(output / 'plan.json', plan)
    protocol = f'''# Versuchsprotokoll: Handyvibration auf dem Tisch

Status: VORBEREITET, noch keine wissenschaftliche Messreihe durchgeführt.
Betriebspunkt: {pwm:g} % PWM (zuletzt gewählter Betriebspunkt).
Methoden: Autoencoder, Isolation Forest und RMS, jeweils einzeln im Prozess.
Geplant: ein Anruf/Vibrationsereignis pro Methode; insgesamt drei Anrufe.

## Aufbau und Kalibrierung
Handyposition, Befestigung, Vibrationsmuster, Sensorposition und Lüfteraufstellung
vor Beginn dokumentieren. Das Handy bleibt auch in Normalphasen am gleichen Ort.
Der endgültige Aufbau ist noch nicht bestätigt. Das kopierte Vergleichsbündel
ist deshalb vorerst nur für technische Pilotprüfungen freigegeben. Bei geändertem
Aufbau neue normale Trainings-/Validierungsaufnahmen und Kalibrierung erstellen.
Keine Anpassung der Schwellen an die späteren Störungsversuche.

## Ablauf je Methode
Mindestens 30 s ungestörte Vorlaufphase. Der Operator protokolliert die Aufforderung
zum Anrufen. Vorgesehen sind etwa 5 s Vibration, danach mindestens 15 s Ruhe.
Einmal je Methode durchführen. Der Operator protokolliert auch das gemeldete Ende und
Abweichungen. Alle Bedienung, Aufzeichnung und Auswertung übernimmt der Assistent.
Die Person am Aufbau befestigt das Handy und löst die Vibration nach Signal aus.

## Auswertung und Grenzen
Rohdaten und Entscheidungen vollständig speichern. CPU (100 % = ein Kern),
Prozess-RAM, Rechenzeit, Fensterlatenz, Sensorausfälle und verworfene Fenster
protokollieren. Temperatur und Takt dienen als Betriebsdiagnose.
Diagramme erst nach der Aufnahme als PNG/PDF exportieren; keine Live-GUI nötig.
Exporte sind Diagramme, keine angeblichen Screenshots einer unbeobachteten GUI.
Fotos des tatsächlichen Aufbaus sind nur mit realer Kameraaufnahme möglich.

Anrufaufforderung und Rückmeldung sind keine gemessenen physischen Anfangs-/Endzeiten.
Deshalb ohne unabhängige Referenz keine echte Fehler-Erkennungsverzögerung oder
bestätigte Erkennungs-/Fehlalarmrate behaupten. Alarmzahlen zunächst deskriptiv.
Jede Vibrationsphase zählt als ein Versuch, nicht jeder Schlag oder Alarmwechsel.
Einzelanrufe zwischen Methoden liefern ähnliche, aber nicht identische Signale.
Ein späterer Replay-Vergleich derselben Rohaufnahme ermöglicht identische Eingaben.
Die Reihenfolge der Methoden bei Wiederholungen wechseln, um Reihenfolgeeffekte
zu prüfen. Ein Ereignis je Methode ist ein Funktionstest, keine belastbare Statistik.
Eine Erkennungsquote von 0/1 oder 1/1 belegt keine allgemeine Zuverlässigkeit.

## Dateien
plan.json und bundle/: eingefrorene Planung und Modellartefakte.
Je Lauf: raw.csv, decisions.csv, cues.jsonl, run.json, summary.json,
report.md und figures/overview.png sowie overview.pdf.
technical_check-Läufe dienen ausschließlich der Funktionsprüfung.
'''
    (output / 'protocol.md').write_text(protocol, encoding='utf-8')
    return output


def mark(run, event, number, note):
    run = Path(run)
    # A separate operator command timestamps the cue even while inference runs.
    if not (run / 'started.json').is_file() or (run / 'run.json').exists():
        raise ValueError('Markierungen benötigen einen laufenden Versuch.')
    record = dict(event=event, number=number, note=note, utc=utc(),
                  monotonic_ns=time.monotonic_ns(), physical_onset_verified=False)
    with (run / 'cues.jsonl').open('a', encoding='utf-8') as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(record, ensure_ascii=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    return record


def capture(plan_directory, method, output, seconds, *, technical_check=False):
    from adxl345 import connect, read_fresh_sample, reset_fifo, sensor_configuration
    plan_directory, output = Path(plan_directory).resolve(), Path(output).resolve()
    plan = common.read_json(plan_directory / 'plan.json')
    directory = plan_directory / 'bundle'
    if common.sha256(directory / 'bundle.json') != plan['bundle_sha256']:
        raise ValueError('Bündel wurde seit der Planung verändert.')
    bundle = common.load_bundle(directory)
    before_pwm = pwm_readback()
    if before_pwm['enable'] != 1 or not math.isclose(before_pwm['percent'], plan['pwm_percent']):
        raise ValueError('Aktuelle PWM widerspricht dem Versuchsplan.')
    output.mkdir(parents=True, exist_ok=False)
    stop = threading.Event()
    handlers = {s: signal.signal(s, lambda *_: stop.set()) for s in (signal.SIGINT, signal.SIGTERM)}
    report = dict(method=method, started_utc=utc(), status='starting',
                  purpose='technical_check' if technical_check else 'exploratory_phone_pilot',
                  gui_enabled=False, methods_active=[method], pwm_before=before_pwm,
                  plan_sha256=common.sha256(plan_directory / 'plan.json'),
                  bundle_sha256=plan['bundle_sha256'], provenance=common.provenance(),
                  implementation_sha256=common.sha256(Path(__file__)),
                  requested_seconds=seconds, ground_truth_verified=False,
                  threshold=bundle['thresholds'][method], warmup_windows=20)
    bus = acquisition = None
    try:
        function, runtime = common.scorer(method, bundle, directory, runtime='litert', threads=1)
        report['runtime'] = runtime
        threshold = bundle['thresholds'][method]['value']
        warmup = np.load(directory / 'validation_raw.npy', mmap_mode='r')
        for i in range(20):
            common.classify_raw(warmup[i % len(warmup)], bundle['scaler'], function, threshold)
        bus = connect(odr_hz=bundle['sampling_rate_hz'], range_g=2, fifo=True)
        report['sensor'] = sensor_configuration(bus)
        reset_fifo(bus)
        start = time.monotonic_ns()
        report['start_monotonic_ns'] = start
        common.write_json(output / 'started.json', report)
        (output / 'cues.jsonl').touch(exist_ok=False)

        def read(event):
            if time.monotonic_ns() - start >= seconds * 1e9:
                return None
            sample = read_fresh_sample(bus, stop_event=event)
            if sample is None:
                return None
            return Sample(sample.xyz_g, sample.monotonic_ns, time.time_ns(),
                          sample.gap, sample.overrun, sample.saturated,
                          {'sensor_sample_index': sample.sample_index})

        metrics = ProcessMetrics()
        acquisition = BufferedAcquisition(read, output / 'raw.csv', window_size=bundle['window_size'],
                                          capacity=4, stop_event=stop).start()
        fields = ['window', 'window_start_ns', 'window_complete_ns', 'decision_ns',
                  'elapsed_s', 'score', 'threshold', 'prediction', 'error',
                  'processing_ms', 'window_to_decision_ms', 'process_cpu_percent_one_core',
                  'process_rss_bytes', 'process_lifetime_peak_rss_bytes',
                  'temperature_c', 'cpu_frequency_khz', 'windows_dropped']
        with (output / 'decisions.csv').open('x', newline='', buffering=1) as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            while not stop.is_set():
                window = acquisition.get(timeout=.1)
                if window is None:
                    if acquisition.done.is_set():
                        break
                    continue
                score, prediction, error = None, None, ''
                ready = time.monotonic_ns()
                try:
                    if window.gap_count or window.overrun_count or window.saturated_count:
                        raise ValueError('Ungültiges Sensorfenster')
                    score, prediction = common.classify_raw(window.values, bundle['scaler'], function, threshold)
                except Exception as exc:
                    error = f'{type(exc).__name__}: {exc}'
                decision = time.monotonic_ns()
                writer.writerow(dict(window=window.index, window_start_ns=window.first_sample_ns,
                    window_complete_ns=window.complete_ns, decision_ns=decision,
                    elapsed_s=(decision-start)/1e9, score=score, threshold=threshold,
                    prediction=prediction, error=error, processing_ms=(decision-ready)/1e6,
                    window_to_decision_ms=(decision-window.complete_ns)/1e6,
                    **metrics.sample(), temperature_c=read_number('/sys/class/thermal/thermal_zone0/temp', 1000),
                    cpu_frequency_khz=read_number('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq'),
                    windows_dropped=acquisition.snapshot()['windows_dropped']))
            handle.flush()
            os.fsync(handle.fileno())
        report['status'] = 'stopped' if stop.is_set() else 'completed'
    except BaseException as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        try:
            if acquisition:
                acquisition.stop()
                report['acquisition'] = acquisition.snapshot()
        finally:
            try:
                if bus:
                    bus.close()
            finally:
                for s, handler in handlers.items():
                    signal.signal(s, handler)
                report['finished_utc'] = utc()
                report['pwm_after'] = pwm_readback()
                report['file_sha256'] = {p.name: common.sha256(p) for p in output.iterdir() if p.is_file()}
                common.write_json(output / 'run.json', report)
    return output


def read_number(path, divisor=1):
    try:
        return float(Path(path).read_text()) / divisor
    except (OSError, ValueError):
        return None


def summarize(rows):
    valid = [row for row in rows if row['prediction'] in ('0', '1') and not row['error']]
    times = [float(row['processing_ms']) for row in valid]
    return dict(windows=len(rows), invalid_windows=len(rows)-len(valid),
                alarm_windows=sum(row['prediction'] == '1' for row in valid),
                processing_median_ms=float(np.median(times)) if times else None,
                processing_p95_ms=float(np.percentile(times, 95)) if times else None,
                sampled_peak_rss_mib=max((float(r['process_rss_bytes'])/2**20 for r in rows), default=None),
                true_detection_delay_ms=None, detection_rate=None, false_alarm_rate=None,
                reason='Kein unabhängig gemessener physischer Störungsbeginn/-ende vorhanden.')


def render_report(run):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    run = Path(run)
    metadata = common.read_json(run / 'run.json')
    with (run / 'decisions.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    summary = summarize(rows)
    cues = [json.loads(line) for line in (run / 'cues.jsonl').read_text().splitlines()]
    calls = [cue for cue in cues if cue['event'] == 'call_requested']
    summary['call_requests'] = len(calls)
    summary['one_call_request'] = len(calls) == 1 and calls[0]['number'] == 1
    summary['purpose'] = metadata['purpose']
    common.write_json(run / 'summary.json', summary)
    (run / 'figures').mkdir(exist_ok=False)
    figure, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    x = [float(r['elapsed_s']) for r in rows]
    axes[0].plot(x, [float(r['score']) if r['score'] else np.nan for r in rows], label='Score')
    axes[0].axhline(metadata['threshold']['value'], color='red', linestyle='--', label='Threshold')
    axes[0].set_ylabel('Score'); axes[0].legend()
    axes[1].plot(x, [float(r['processing_ms']) for r in rows]); axes[1].set_ylabel('Berechnung [ms]')
    axes[2].plot(x, [float(r['process_cpu_percent_one_core']) for r in rows], label='CPU [% eines Kerns]')
    axes[2].plot(x, [float(r['process_rss_bytes'])/2**20 for r in rows], label='RAM [MiB]')
    axes[2].legend(); axes[2].set_xlabel('Zeit seit Aufnahmestart [s]')
    for axis in axes:
        axis.grid(alpha=.25)
        for cue in calls:
            axis.axvline((cue['monotonic_ns']-metadata['start_monotonic_ns'])/1e9,
                         color='gray', linestyle=':', alpha=.6)
    figure.suptitle(f"{metadata['method']} — {metadata['purpose']}\nGrau: Anrufaufforderung, kein verifizierter Fehlerbeginn")
    figure.tight_layout()
    for suffix in ('png', 'pdf'):
        figure.savefig(run / 'figures' / f'overview.{suffix}', dpi=160)
    plt.close(figure)
    text = f'''# Einzelmessung: {metadata['method']}

Zweck: {metadata['purpose']}; Status: {metadata['status']}.
PWM vorher/nachher: {metadata['pwm_before']['percent']} / {metadata['pwm_after']['percent']} %.
Fenster: {summary['windows']}; ungültig: {summary['invalid_windows']}; Alarmfenster: {summary['alarm_windows']}.
Berechnungszeit Median: {summary['processing_median_ms']} ms; P95: {summary['processing_p95_ms']} ms.
Abgetasteter maximaler Prozess-RAM: {summary['sampled_peak_rss_mib']} MiB.
Anrufaufforderungen: {summary['call_requests']}; genau eine Aufforderung: {summary['one_call_request']}.

Die CPU-/RAM-Werte umfassen den gesamten Einzelprozess inklusive Erfassung und Logging.
Ein Anrufsignal ist kein gemessener Vibrationsbeginn. Echte Erkennungsverzögerung,
Erkennungsrate und Fehlalarmrate sind daher noch nicht bestimmt.
Ein kurzer technical_check ist kein Ressourcenvergleich und kein Störungsversuch.
PNG/PDF sind nachträglich erzeugte Diagramme; kein Screenshot und kein Aufbau-Foto.
Die unveränderten Rohdaten ermöglichen spätere unabhängige Auswertungen.
'''
    (run / 'report.md').write_text(text, encoding='utf-8')
    return run / 'report.md'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--bundle', required=True); prep.add_argument('--output', required=True)
    prep.add_argument('--pwm', type=float, default=75)
    record = sub.add_parser('record')
    record.add_argument('--plan', required=True); record.add_argument('--output', required=True)
    record.add_argument('--method', choices=common.METHODS, required=True)
    record.add_argument('--seconds', type=float, default=180)
    record.add_argument('--technical-check', action='store_true')
    marker = sub.add_parser('mark')
    marker.add_argument('--run', required=True)
    marker.add_argument('--event', choices=('call_requested', 'end_reported', 'note'), required=True)
    marker.add_argument('--number', type=int, choices=(1,), default=1)
    marker.add_argument('--note', default='')
    report = sub.add_parser('report'); report.add_argument('--run', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        if not math.isfinite(args.pwm) or not 0 <= args.pwm <= 100:
            parser.error('PWM muss zwischen 0 und 100 liegen.')
        print(prepare(args.bundle, args.output, args.pwm))
    elif args.command == 'record':
        if not math.isfinite(args.seconds) or not 0 < args.seconds <= 600:
            parser.error('Dauer muss endlich und zwischen 0 und 600 s sein.')
        print(capture(args.plan, args.method, args.output, args.seconds, technical_check=args.technical_check))
    elif args.command == 'mark':
        print(json.dumps(mark(args.run, args.event, args.number, args.note)))
    else:
        print(render_report(args.run))


if __name__ == '__main__':
    main()
