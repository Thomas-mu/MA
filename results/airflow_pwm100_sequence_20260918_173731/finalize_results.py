"""Verify all three captures and summarize their measured differences."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
PHASES = [('normal_before', 'Ohne Platte (vorher)'), ('airflow_modified', 'Mit Platte'),
          ('normal_after', 'Ohne Platte (nachher)')]
METHODS = ['rms', 'isolation_forest', 'tflite_autoencoder']

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    plan = json.loads((BASE/'plan.json').read_text())
    results, previous = {}, None
    all_checks = {'frozen_source_files_unchanged': all(sha(p)==h for p,h in plan['implementation_sha256'].items())}
    for phase, title in PHASES:
        s = json.loads((BASE/f'{phase}_session.json').read_text())
        rows = [json.loads(line) for line in (BASE/f'{phase}_decisions.jsonl').read_text().splitlines()]
        sidecar = json.loads(Path(s['csv']).with_suffix('.json').read_text())
        selected = pd.read_csv(BASE/f'{phase}_physical_rms_5s.csv')
        selected = selected.loc[(selected.start_s>=180) & (selected.start_s<300)]
        clean = selected.loc[~selected.has_sensor_flags]
        conditions = json.loads((BASE/f'{phase}_condition.json').read_text())
        checks = {
            'completed': s['status']=='completed' and sidecar['status']=='completed',
            'correct_physical_condition_report': conditions['plate_present']==(phase=='airflow_modified'),
            'pwm100_before_and_after': all(s[k]['pwm_configuration']['configured_duty_percent']==100
                                          for k in ['setting_result','pwm_after_capture']),
            'final_pwm_zero': s['final_readback']['pwm_configuration']['configured_duty_percent']==0,
            'capture_span_at_least_299_8s': s['quality']['first_to_last_host_span_s']>=299.8,
            'first_sample_within_one_second': 0<=s['quality']['first_xyz_after_command_s']<1,
            'raw_csv_hash_matches_sidecar': sha(s['csv'])==sidecar['csv_sha256'],
            'plan_unchanged': s['plan_sha256']==sha(BASE/'plan.json'),
            'frozen_bundle_unchanged': s['bundle_sha256']==sha(Path(plan['frozen_bundle_directory'])/'pilot_bundle.json'),
            'invalid_windows_not_classified': all(r['decision']=='INVALID' for r in rows if not r['quality_valid']),
            'same_windows_for_all_methods': len({m['total_windows'] for m in s['metrics'].values()})==1,
            'window_count_matches_decisions': len(rows)==3*s['selection']['full_model_windows'],
            'selected_times_in_interval': all(180<=r['start_since_command_s']<=r['last_since_command_s']<300 for r in rows),
            'no_overlapping_phases': previous is None or s['command_invocation_monotonic_ns']>previous['zero_command_completed_monotonic_ns'],
        }
        all_checks[phase] = checks
        results[phase] = dict(title=title, metrics=s['metrics'], quality=s['quality'], selection=s['selection'],
            physical_vector_ac_rms=dict(interval_s=[180,300], block_seconds=5,
                all_blocks=len(selected), blocks_without_sensor_flags=len(clean),
                mean_all_blocks_g=float(selected.vector_ac_rms_g.mean()),
                mean_blocks_without_sensor_flags_g=float(clean.vector_ac_rms_g.mean()),
                min_blocks_without_sensor_flags_g=float(clean.vector_ac_rms_g.min()),
                max_blocks_without_sensor_flags_g=float(clean.vector_ac_rms_g.max())))
        (BASE/f'{phase}_verification_final.json').write_text(json.dumps(checks,indent=2))
        previous=s
    assert all_checks['frozen_source_files_unchanged']
    assert all(all(all_checks[phase].values()) for phase,_ in PHASES), all_checks
    physical={p:r['physical_vector_ac_rms']['mean_blocks_without_sensor_flags_g'] for p,r in results.items()}
    differences={
        'plate_vs_before_percent':100*(physical['airflow_modified']/physical['normal_before']-1),
        'plate_vs_after_percent':100*(physical['airflow_modified']/physical['normal_after']-1),
        'after_vs_before_percent':100*(physical['normal_after']/physical['normal_before']-1)}
    summary=dict(completed_utc=datetime.now(timezone.utc).isoformat(),status='completed',
        pwm_percent=100,duration_s_per_phase=300,model_reference_pwm_percent=75,
        phases=results,physical_rms_differences=differences,verification=all_checks,
        limitations=['One sequence, no independent repetition.',
                     'Frozen model calibrated at 75%, not recalibrated for 100%.',
                     'Plate geometry and mounting equivalence to v4 were not measured in this run.',
                     'Plate-present labels denote operator-reported condition, not defect truth.',
                     'Physical RMS comparison uses unflagged 5-second blocks; flagged data remain stored.',
                     'RPM, electrical waveform and exact sensor losses were not independently measured.'],
        operational_note='First phase-2 attempt stopped at sensor-lock preflight without a PWM start; its records are archived. Conflicting legacy GUI was terminated gracefully before the successful phase-2 start.')
    (BASE/'sequence_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
    lines=['Plattenversuch bei 100 % PWM – abgeschlossen', '',
           'Reihenfolge: ohne Platte → mit Platte → wieder ohne Platte. Je Phase 300 s; danach 0 % PWM. '
           'Alle drei Aufnahmen und die unveränderten Quell-/Modelldateien sind geprüft.', '',
           '| Phase | Gültige Modellfenster | RMS-Alarme | IF-Alarme | AE-Alarme | Vektor-AC-RMS [g] |',
           '|---|---:|---:|---:|---:|---:|']
    for phase,title in PHASES:
        r=results[phase]
        alarms=[f"{r['metrics'][m]['alarm_fraction']*100:.1f} %" for m in METHODS]
        lines.append(f"| {title} | {r['selection']['quality_valid_windows']} / {r['selection']['full_model_windows']} | "
                     +' | '.join(alarms)+f" | {physical[phase]:.6f} |")
    lines += ['', 'Auswertung jeweils [180,300) s seit PWM-Start. Die physische Schwingung ist der Mittelwert '
              'der Vektor-AC-RMS-Werte aus 5-s-Abschnitten ohne gemeldete Sensorflags; alle Originalabschnitte bleiben gespeichert.', '',
              f"Mit Platte verändert sich dieser Schwingungswert gegenüber vorher um {differences['plate_vs_before_percent']:+.2f} % "
              f"und gegenüber nachher um {differences['plate_vs_after_percent']:+.2f} %. "
              f"Die beiden Phasen ohne Platte unterscheiden sich um {differences['after_vs_before_percent']:+.2f} %.", '',
              'Das eingefrorene v4-Modellpaket verwendet seine unveränderte 75-%-Referenz. '
              'Die Alarmanteile müssen daher zusammen mit den Referenzphasen beurteilt werden; '
              'ein Alarm allein weist keinen Platteneffekt oder Defekt nach. Es wurde nicht nachtrainiert oder nachkalibriert.', '',
              'Der erste Startversuch von Phase 2 wurde vor einer PWM-Änderung durch eine parallel laufende GUI blockiert. '
              'Die GUI wurde regulär geschlossen; der Versuch ist separat archiviert. Die anschließende Plattenaufnahme wurde vollständig ausgeführt.', '',
              'Ergebnisse: [Screenshot aller Phasen](screenshot_normal_after.png), [Diagramm](comparison_through_normal_after.png), '
              '[vollständige Kennzahlen und Prüfungen](sequence_summary.json).']
    (BASE/'report.md').write_text('\n'.join(lines)+'\n')
    manifest={str(p.relative_to(BASE)):sha(p) for p in sorted(BASE.rglob('*'))
              if p.is_file() and p.name!='artifact_manifest.json' and '__pycache__' not in p.parts}
    (BASE/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(dict(status='completed',physical_rms_g=physical,differences_percent=differences),indent=2))

if __name__=='__main__':
    main()
