"""Versioned instrumentation for the unchanged frozen v4 model package.

No actuation or sensor imports. Previous pilot runtime and historical protocols
remain untouched. Model scores are checked against the frozen scorer in tests.
"""
from pathlib import Path
import time
import numpy as np
import pilot_method_comparison as pilot
import independent_normal_test as frozen


class TimedScorer:
    def __init__(self, method, bundle, directory):
        self.method=method
        self.last_timing={}
        if method=='isolation_forest':
            import joblib
            self.model=joblib.load(Path(directory)/'isolation_forest.joblib')
        elif method=='tflite_autoencoder':
            self.interpreter,self.incoming,self.outgoing,self.runtime=pilot.common.load_interpreter(
                Path(directory)/'autoencoder_float32.tflite','auto',1)
            if tuple(self.incoming['shape'])!=(1,128,3):raise ValueError('Wrong input shape')

    def __call__(self,x):
        start=time.monotonic_ns()
        transfer_in=transfer_out=0
        if self.method=='tflite_autoencoder':
            self.interpreter.set_tensor(self.incoming['index'],x[np.newaxis,...])
            core_start=time.monotonic_ns();transfer_in=core_start-start
            self.interpreter.invoke()
            core_end=time.monotonic_ns()
            reconstruction=self.interpreter.get_tensor(self.outgoing['index'])[0]
            transferred=time.monotonic_ns();transfer_out=transferred-core_end
            if reconstruction.shape!=x.shape or not np.isfinite(reconstruction).all():raise ValueError('Invalid AE reconstruction')
            value=float(np.mean(np.square(x-reconstruction),dtype=np.float64))
        elif self.method=='isolation_forest':
            values=x.reshape(1,-1)
            core_start=time.monotonic_ns()
            raw=self.model.score_samples(values)
            core_end=time.monotonic_ns()
            value=float(-raw[0])
        elif self.method=='rms':
            core_start=time.monotonic_ns()
            value=pilot.common.rms_score(x)
            core_end=time.monotonic_ns()
        else:raise ValueError('Unknown method')
        end=time.monotonic_ns()
        self.last_timing=dict(model_core_ns=core_end-core_start,transfer_in_ns=transfer_in,
                              transfer_out_ns=transfer_out,score_and_other_overhead_ns=end-start-(core_end-core_start)-transfer_in-transfer_out)
        return value


class FrozenEngine:
    def __init__(self,bundle_directory,methods=None):
        started=time.monotonic_ns()
        self.directory=Path(bundle_directory)
        self.bundle=pilot.load_bundle(self.directory)
        if frozen.sha256(self.directory/'pilot_bundle.json')!=frozen.FROZEN_BUNDLE_SHA256:raise ValueError('Wrong frozen package')
        self.methods=list(pilot.METHODS if methods is None else methods)
        if not self.methods or len(set(self.methods))!=len(self.methods) or not set(self.methods)<=set(pilot.METHODS):raise ValueError('Unknown/duplicate method')
        self.functions={m:TimedScorer(m,self.bundle,self.directory) for m in self.methods}
        self.runtimes={m:getattr(f,'runtime','numpy' if m=='rms' else 'sklearn.score_samples') for m,f in self.functions.items()}
        self.load_ns=time.monotonic_ns()-started
        self.warmup_ns=None

    def warmup(self):
        start=time.monotonic_ns()
        x=pilot.standardize_ac(np.zeros((128,3),np.float32),self.bundle['scaler'])
        for _ in range(20):
            for scorer in self.functions.values():scorer(x.copy())
        self.warmup_ns=time.monotonic_ns()-start

    def score(self,window):
        start=time.monotonic_ns()
        meta=window['metadata'];shared=None
        if meta['quality_valid']:shared=pilot.standardize_ac(window['ac_float32'],self.bundle['scaler'])
        prepared=time.monotonic_ns();rows=[]
        for method in self.methods:
            threshold=self.bundle['thresholds'][method]['value']
            row=dict(meta,method=method,threshold=threshold,score=None,prediction=None,decision='INVALID',error=None)
            score_start=time.monotonic_ns()
            if shared is None:row['error']=', '.join(meta['quality_reasons'])
            else:
                try:
                    scorer=self.functions[method]
                    value=float(scorer(shared.copy()))
                    prediction=pilot.common.finite_score(value,threshold)
                    row.update(score=value,prediction=prediction,decision='ANOMALY' if prediction else 'NORMAL',**getattr(scorer,'last_timing',{}))
                except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
            finish=time.monotonic_ns()
            row.update(standardization_ns=prepared-start,scorer_call_ns=finish-score_start,decision_monotonic_ns=finish,
                       dequeue_to_decision_ns=finish-start,dequeue_monotonic_ns=start)
            rows.append(row)
        return rows
