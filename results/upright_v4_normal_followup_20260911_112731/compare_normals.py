"""Offline comparison of three complete normal records from mounting v4."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
PREVIOUS = ROOT / 'results/upright_position_v4_sequence_20260911_104025'
SOURCES = {'normal_before': PREVIOUS, 'normal_after': PREVIOUS, 'normal_followup': BASE}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = BASE / 'analysis/normal_comparison'
    if out.exists():
        raise FileExistsError('Existing analysis must be preserved')
    reports, frames, inputs = {}, {}, {}
    for phase, folder in SOURCES.items():
        report = json.loads((folder / 'analysis' / phase / 'summary.json').read_text())
        session = json.loads((folder / f'{phase}_session.json').read_text())
        assert session['status'] == 'completed'
        assert report['mounting_id'] == 'fan_upright_position_v4_20260911_103726'
        assert report['control_transactions'] == [75.0, 0.0]
        for name, expected in report['input_sha256'].items():
            assert digest(ROOT / name) == expected
            inputs[name] = expected
        reports[phase] = report
        frames[phase] = pd.read_csv(folder / 'analysis' / phase / 'five_second_rms.csv')
        for name in ['summary.json', 'five_second_rms.csv']:
            path = folder / 'analysis' / phase / name
            inputs[str(path.relative_to(ROOT))] = digest(path)
    assert all(r['sensor'] == reports['normal_before']['sensor'] for r in reports.values())
    late = {p: f.loc[f.start_s >= 180, 'vector_ac_rms_mg'].to_numpy() for p, f in frames.items()}
    assert all(len(values) == 24 for values in late.values())
    means = np.array([values.mean() for values in late.values()])
    result = {'created_utc': datetime.now(timezone.utc).isoformat(),
              'mounting_id': reports['normal_before']['mounting_id'],
              'records': list(SOURCES), 'full_normal_recordings': 3,
              'primary_interval_s': [180, 300], 'window_length_s': 5,
              'windows_are_independent_replicates': False, 'settling_time_validated': False,
              'primary': {p: r['primary_180_300'] for p, r in reports.items()},
              'normal_run_mean_range_mg': float(np.ptp(means)),
              'normal_run_means_sd_mg_ddof1': float(means.std(ddof=1)),
              'within_run_pooled_sd_mg_ddof0': float(np.sqrt(np.mean([v.var() for v in late.values()]))),
              'followup_contrasts': {}, 'input_sha256': inputs,
              'source_sha256': digest(Path(__file__)), 'models_trained': False,
              'interpretation': 'Three pilot normal starts; different total off times; descriptive comparison, no calibrated normal distribution or detection proof.'}
    new = late['normal_followup']
    for phase in ['normal_before', 'normal_after']:
        reference = late[phase]
        result['followup_contrasts'][phase] = {
            'mean_difference_mg': float(new.mean() - reference.mean()),
            'percent_of_reference_mean': float(100 * (new.mean() - reference.mean()) / reference.mean()),
            'observed_ranges_overlap': bool(max(new.min(), reference.min()) <= min(new.max(), reference.max())),
            'followup_windows_inside_reference_range': int(((new >= reference.min()) & (new <= reference.max())).sum())}
    out.mkdir(parents=True)
    with (out / 'comparison.json').open('x') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, allow_nan=False)
    plot(frames, out)
    assert all(digest(ROOT / p) == h for p, h in inputs.items())
    print(json.dumps({k: result[k] for k in ['normal_run_mean_range_mg', 'normal_run_means_sd_mg_ddof1', 'within_run_pooled_sd_mg_ddof0', 'followup_contrasts']}, indent=2))


def plot(frames, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), layout='constrained')
    names = {'normal_before': 'Normal vor Platte', 'normal_after': 'Normal nach Platte', 'normal_followup': 'Zusätzlicher Normallauf'}
    for phase, frame in frames.items():
        x, y = frame.start_s.to_numpy() + 2.5, frame.vector_ac_rms_mg.to_numpy()
        axes[0].plot(x, y, 'o-', markersize=3, label=names[phase])
        axes[1].plot(x[36:], y[36:], 'o-', markersize=3, label=names[phase])
        axes[2].plot(x[36:], y[36:] - y[36:].mean(), 'o-', markersize=3, label=names[phase])
    axes[0].axvspan(180, 300, color='gray', alpha=.12)
    axes[0].set(xlim=(0, 300), ylabel='Vektor-AC-RMS [mg]', title='Vollständige Normalläufe: eigene Achsenmittelwerte je 5-s-Fenster entfernt')
    axes[1].set(xlim=(180, 300), ylabel='Vektor-AC-RMS [mg]', title='180–300 s: Niveau und Schwankungen')
    axes[2].axhline(0, color='gray', linewidth=.7)
    axes[2].set(xlim=(180, 300), ylabel='Abweichung vom Laufmittel [mg]', title='Zeitlicher Verlauf nach Abzug des jeweiligen späten RMS-Laufmittels')
    for ax in axes:
        ax.set_xlabel('Zeit seit jeweiligem PWM-Befehlsaufruf [s]')
        ax.legend(); ax.grid(alpha=.25)
    fig.suptitle('Aufbauversion v4: drei Normalaufnahmen ohne Platte\n75 % PWM, 25 kHz; drei Starts, keine unabhängigen Fensterreplikate')
    fig.savefig(out / 'comparison.png', dpi=160)
    fig.savefig(out / 'comparison.pdf'); plt.close(fig)


if __name__ == '__main__':
    main()
