"""Read-only pure-function checks; never imports GUI/sensor/model runtimes.

Extract selected functions by AST from the reviewed source; test configuration
validation and numerical preprocessing using synthetic values and saved scaler.
This is not an end-to-end GUI test or performance benchmark.
"""
from pathlib import Path
import ast
import hashlib
import json
import re
from types import SimpleNamespace
import numpy as np
import joblib

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BUNDLE = ROOT / 'results/upright_v4_training_pilot_20260911_130614/run_001/frozen'

def extract(relative, names, globals_):
    path=ROOT/relative
    tree=ast.parse(path.read_text())
    nodes=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]+nodes,type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module,str(path),'exec'),globals_)
    return {n.name: {'file':relative,'lines':[n.lineno,n.end_lineno]} for n in nodes}

def check(condition, message):
    if not condition: raise ValueError(message)

gui={'np':np,'Path':Path,'json':json,'hashlib':hashlib,'re':re,'Any':object,
     'LiveConfiguration':lambda **kwargs:SimpleNamespace(**kwargs),'AXIS_COUNT':3,'WINDOW_SHAPE':(128,3),
     'PROJECT_ROOT':ROOT,'PROFILES_DIRECTORY':ROOT/'profiles','DEFAULT_LOG_PATH':ROOT/'results/live_runs/live_tflite_log.csv',
     'PROFILE_NAME_PATTERN':re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')}
functions=extract('src/live_tflite_monitor.py', ['sha256_file','validate_profile_name','verify_profile_hash','resolve_live_configuration','validate_acquisition_options','scale_window'],gui)
canonical={'np':np,'preparation':SimpleNamespace(check=check)}
functions.update(extract('src/pilot_method_comparison.py',['center_raw_window'],canonical))
common={'np':np}
functions.update(extract('src/common_comparison.py',['standardize'],common))
bundle=json.loads((BUNDLE/'pilot_bundle.json').read_text())
scaler=joblib.load(BUNDLE/'scaler.joblib')
assert np.array_equal(scaler.mean_,np.array(bundle['scaler']['mean']))
assert np.array_equal(scaler.scale_,np.array(bundle['scaler']['scale']))
profile_results=[]
for p in sorted((ROOT/'profiles').glob('*/profile.json')):
    c=gui['resolve_live_configuration'](p.parent.name)
    result={'path':str(p.relative_to(ROOT)),'profile_name':c.profile_name,'profile_hz':c.profile_sampling_rate_hz,'resolved':True,'model_sha256':gui['sha256_file'](c.model_path),'scaler_sha256':gui['sha256_file'](c.scaler_path),'threshold':c.threshold}
    opts=dict(sensor_odr=200,sensor_range=2,buffer_windows=4,allow_sampling_mismatch=False,fan_pwm_setpoint=None,measured_rpm=None,rpm_source=None)
    try:gui['validate_acquisition_options'](c,**opts)
    except ValueError as error:result['default_200hz_rejected']=True;result['reason']=str(error)
    else:raise AssertionError('Expected old 500-Hz profile to reject 200-Hz default')
    opts['allow_sampling_mismatch']=True
    gui['validate_acquisition_options'](c,**opts)
    result['explicit_development_override_passes_configuration_check']=True
    profile_results.append(result)

# Exactly representable constants isolate DC handling, without sensor or model inference.
raw=np.tile(np.array([0.125,-0.25,-1.0],dtype=np.float64),(128,1))
old=gui['scale_window'](raw,scaler)
ac=canonical['center_raw_window'](raw)
new=common['standardize'](ac,bundle['scaler'])
assert old.dtype==new.dtype==np.float32
assert not np.array_equal(old,new)
assert np.max(np.abs(new))<1e-6
numerical={'input':'synthetic constant XYZ in g, 128 repetitions of [0.125, -0.25, -1.0]; no measurement',
           'saved_scaler_matches_bundle':True,'both_output_dtype':str(new.dtype),'both_output_shape':list(new.shape),
           'legacy_standardized_axis_mean':[float(v) for v in old.astype(np.float64).mean(axis=0)],
           'v4_standardized_axis_mean':[float(v) for v in new.astype(np.float64).mean(axis=0)],
           'outputs_identical':False,'maximum_absolute_output_difference':float(np.max(np.abs(old-new))),
           'model_scores_computed':False}
result={'status':'passed','scope':'Extracted pure configuration/preprocessing functions only; synthetic input; no complete GUI/runtime/inference/hardware test',
        'checks':['all four existing legacy profiles resolve with stored artifact hashes','all four reject nominal 200-Hz acquisition without explicit development override','saved frozen scaler matches bundle','GUI and v4 preprocessing differ for the same raw synthetic XYZ window'],
        'functions':functions,'profiles':profile_results,'preprocessing_counterexample':numerical,
        'frozen_bundle_sha256':hashlib.sha256((BUNDLE/'pilot_bundle.json').read_bytes()).hexdigest(),
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'src/live_tflite_monitor.py',ROOT/'src/pilot_method_comparison.py',ROOT/'src/common_comparison.py']}}
(OUT/'gui_contract_check.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':result['status'],'profile_count':len(profile_results),'preprocessing':numerical},indent=2))
