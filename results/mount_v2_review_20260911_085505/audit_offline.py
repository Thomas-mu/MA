"""Supplementary offline checks; no sensor or controller imports or writes."""
import hashlib
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
import time
import numpy as np
import pandas as pd
from smbus2 import SMBus

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
SOURCE = ROOT / 'results/mount_v2_restarts_20260911_080445'
review = json.loads((BASE / 'review.json').read_text())
rows = []
for r in review['records']:
    s = json.loads((SOURCE / f"run{r['run']}_session.json").read_text())
    d = pd.read_csv(ROOT / r['csv'], dtype={'host_monotonic_ns': 'int64'})
    ns = d.host_monotonic_ns.to_numpy()
    xyz = d[['x_g', 'y_g', 'z_g']].to_numpy()
    origins = {'first_xyz': int(ns[0]), 'command_invocation': s['command_invocation_monotonic_ns'],
               'command_completion': s['command_completed_monotonic_ns']}
    for name, origin in origins.items():
        t = (ns - origin) / 1e9
        values = []
        for start in range(180, 300, 5):
            a = xyz[(t >= start) & (t < start + 5)]
            assert len(a) > 1000
            values.append(float(1000 * np.sqrt(np.mean(np.sum((a-a.mean(axis=0))**2, axis=1)))))
        y = np.array(values)
        slope = float(np.polyfit(np.arange(182.5, 300, 5), y, 1)[0]*60)
        rows.append({'run': r['run'], 'time_origin': name, 'mean_mg': float(y.mean()),
                     'ols_slope_mg_min': slope,
                     'sign_matches_primary': bool(np.sign(slope) == np.sign(r['trend']['ols_mg_per_min']))})
    dt = np.diff(ns)/1e6
    r['supplemental'] = {'host_intervals_over_10ms': int((dt > 10).sum()),
        'over_10ms_times_since_first_xyz_s': ((ns[1:][dt > 10] - ns[0])/1e9).tolist(),
        'max_absolute_axis_g': float(np.abs(xyz).max()),
        'first_xyz_after_command_invocation_s': float((ns[0] - origins['command_invocation'])/1e9),
        'controlled_off_s': s['controlled_off_actual_to_command_invocation_s'],
        'total_off_since_previous_zero_s': s['total_off_since_previous_zero_to_command_s'],
        'command_invocation_utc': s['command_invocation_utc']}

clock = time.get_clock_info('monotonic')
audit = {'created_utc': datetime.now(timezone.utc).isoformat(), 'hardware_access': False,
         'boundary_sensitivity': rows,
         'per_run_supplemental': [{'run': r['run'], **r['supplemental']} for r in review['records']],
         'current_host_clock_snapshot': {'implementation': clock.implementation, 'monotonic': clock.monotonic,
             'adjustable': clock.adjustable, 'resolution_s': clock.resolution,
             'clocksource': Path('/sys/devices/system/clocksource/clocksource0/current_clocksource').read_text().strip(),
             'independent_clock_calibration': False},
         'software_sha256': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
             for p in ['src/adxl345.py', 'src/collect_real_data.py', 'src/fan_pwm.py']},
         'smbus2_read_i2c_block_data_source': inspect.getsource(SMBus.read_i2c_block_data),
         'sources': [{'url': 'https://www.analog.com/media/en/technical-documentation/data-sheets/adxl345.pdf',
             'edition': 'Rev. G', 'consulted_date': '2026-09-11', 'pages': [13, 14, 17, 20, 21, 27]},
             {'url': 'https://ez.analog.com/mems/f/q-a/86236/adxl345-tolerance',
              'author': 'ADIApproved / Venkat', 'answer_date': '2015-06-05',
              'consulted_date': '2026-09-11', 'use': 'original verified employee reply, not AI thread summary'},
             {'url': 'https://support.arctic.de/de/p12-pro-pst', 'consulted_date': '2026-09-11'}]}
with (BASE / 'software_timebase_audit.json').open('x') as f:
    json.dump(audit, f, indent=2, ensure_ascii=False, allow_nan=False)
print(json.dumps({'boundary_sensitivity': rows, 'per_run_supplemental': audit['per_run_supplemental']}, indent=2))
