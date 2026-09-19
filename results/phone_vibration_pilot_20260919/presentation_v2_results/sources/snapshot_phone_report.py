"""Capture the actual browser-rendered saved report, without a live sensor GUI."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import subprocess
import tempfile


def snapshot(run, report_directory=None):
    run = Path(run).resolve()
    report_directory = Path(report_directory).resolve() if report_directory else run
    metadata = json.loads((run / 'run.json').read_text())
    summary = json.loads((report_directory / 'summary.json').read_text())
    figure = report_directory / 'figures/overview.png'
    if not figure.is_file():
        raise FileNotFoundError(figure)
    output = run / 'report_screenshot'
    output.mkdir(exist_ok=False)
    title = {'tflite_autoencoder': 'Autoencoder', 'isolation_forest': 'Isolation Forest', 'rms': 'RMS'}[metadata['method']]
    with (run / 'decisions.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    cues = [json.loads(line) for line in (run / 'cues.jsonl').read_text().splitlines()]
    starts = [cue['monotonic_ns'] for cue in cues if cue['event'] == 'call_requested']
    ends = [cue['monotonic_ns'] for cue in cues if cue['event'] == 'end_reported']
    phase_html = ''
    if len(starts) == len(ends) == 1:
        for label, selected in (
            ('Vor Freigabe', [r for r in rows if int(r['window_complete_ns']) < starts[0]]),
            ('Freigabe bis Rückmeldung', [r for r in rows if int(r['window_start_ns']) >= starts[0] and int(r['window_complete_ns']) <= ends[0]]),
            ('Nach Rückmeldung', [r for r in rows if int(r['window_start_ns']) >= ends[0]]),
        ):
            phase_html += f'<p><strong>{label}</strong><br>{sum(r["prediction"] == "1" for r in selected)} Alarmfenster / {len(selected)} Fenster</p>'
    page = f'''<!doctype html><html lang="de"><meta charset="utf-8">
<title>{title} – gespeicherter Pilotbericht</title>
<style>body{{margin:0;padding:28px 42px;background:#f3f6fa;color:#183148;font:18px "DejaVu Sans",sans-serif}}
h1{{font-size:34px;margin:8px 0}}small{{color:#53677b}}.grid{{display:grid;grid-template-columns:870px 1fr;gap:24px;margin-top:22px}}
.card{{background:white;padding:20px;border-radius:12px}}img{{width:830px;height:748px;object-fit:contain}}h2{{font-size:22px;margin-top:8px}}
p{{line-height:1.45}}.note{{background:#fff0d9;padding:15px;border-radius:8px;font-size:16px}}footer{{font-size:13px;margin-top:14px;overflow-wrap:anywhere}}</style>
<small>RASPBERRY PI · GESPEICHERTE AUSWERTUNG · {html.escape(metadata['purpose'])}</small>
<h1>{title}: Beobachtungen aus einem Einzelversuch</h1>
<div class="grid"><div class="card"><img src="{figure.as_uri()}" alt="Score, Rechenzeit, CPU und RAM über die Zeit"></div>
<div class="card"><h2>Dokumentierte Daten</h2>
<p>{summary['windows']} Fenster<br>{summary['invalid_windows']} ungültig<br>{metadata['acquisition']['windows_dropped']} verworfen<br>{metadata['pwm_before']['percent']:g} % PWM</p>
<h2>Abschnitte nach Chat-Markierung</h2>{phase_html}
<div class="note">Die Freigabe ist kein gemessener physischer Vibrationsbeginn. Rechenzeit und Fehler-Erkennungsverzögerung sind verschiedene Größen. Ein Anruf belegt keine allgemeine Erkennungsquote.</div>
<p><small>Originaldaten: raw.csv, decisions.csv, cues.jsonl und run.json. Grenzüberlappende Fenster sind in den Phasensummen ausgelassen.</small></p></div></div>
<footer>Browseransicht des nachträglich erzeugten Berichts · keine Live-GUI, kein Aufbau-Foto · Lauf: {html.escape(run.name)}</footer></html>'''
    (output / 'report.html').write_text(page, encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='phone-report-browser-') as profile:
        command = ['chromium', '--headless', '--no-sandbox', '--disable-gpu', '--disable-background-networking',
                   '--no-first-run', f'--user-data-dir={profile}', '--hide-scrollbars', '--window-size=1440,1080',
                   '--virtual-time-budget=1000', f'--screenshot={output / "report.png"}', (output / 'report.html').as_uri()]
        result = subprocess.run(command, capture_output=True, text=True, timeout=45)
        (output / 'browser.log').write_text(result.stdout + result.stderr)
        result.check_returncode()
    evidence = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'type': 'actual_browser_screenshot_of_saved_report',
                'not_live_gui': True, 'source_run': str(run), 'command': command,
                'source_hashes': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                  [run/'run.json', run/'decisions.csv', run/'cues.jsonl', figure, output/'report.html']},
                'screenshot_sha256': hashlib.sha256((output/'report.png').read_bytes()).hexdigest()}
    (output/'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    return output / 'report.png'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--report-directory')
    args = parser.parse_args()
    print(snapshot(args.run, args.report_directory))
