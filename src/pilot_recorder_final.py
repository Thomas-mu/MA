"""Live recorder compatible with execute_capture's injected recorder interface.

Construct the engine before the PWM command; the capture owner MUST use its
existing try/finally zero shutdown. This module never controls the fan.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading

import pandas as pd
from pilot_stream_final import run_stream
from pilot_sensor_source import sensor_rows
import independent_normal_test as frozen


def make_recorder(engine, *, capacity=4):
    def record(bus, duration_seconds, sample_rate_hz, *, output_path, label,
               state, metadata, stop_event=None):
        if (duration_seconds,sample_rate_hz,label,state)!=(300,200,0,'normal'):
            raise ValueError('Live pilot requires 300 s, 200 Hz, normal label')
        if metadata.get('capture_mode')!='sensor_live':
            raise ValueError('Live processing load must be declared before capture')
        from collect_real_data import provenance, recording_summary, FIELDS
        from adxl345 import sensor_configuration
        path=Path(output_path).resolve()
        sidecar=path.with_suffix('.json')
        runtime=path.with_suffix('.runtime')
        if path.exists() or sidecar.exists() or runtime.exists():
            raise FileExistsError('No live capture overwrite')
        path.parent.mkdir(parents=True,exist_ok=True)
        report=dict(metadata,schema_version=1,recording_id=path.stem,path=str(path),
                    configured_duration_seconds=300,label=0,state='normal',
                    started_at_utc=datetime.now(timezone.utc).isoformat(),status='recording',
                    sensor=sensor_configuration(bus),code=provenance(),
                    methods=list(engine.methods),runtime_directory=str(runtime),
                    timestamp_note='Host read completion; nominal sensor time is not a conversion clock')
        with sidecar.open('x') as handle: json.dump(report,handle,indent=2,allow_nan=False)
        stop=stop_event if stop_event is not None else threading.Event()
        failure=None
        try:
            run_stream(sensor_rows(bus,metadata['pwm_command_invocation_monotonic_ns'],stop),
                       metadata['pwm_command_invocation_monotonic_ns'],engine,runtime,
                       capacity=capacity,stop_event=stop,source_mode='sensor_live')
            report['status']='completed'
        except BaseException as exc:
            failure=exc
            report.update(status='error',error=f'{type(exc).__name__}: {exc}')
        finally:
            raw=runtime/'raw.csv'
            if raw.exists():
                # Exclusive hard link: never overwrite an unexpectedly created target.
                os.link(raw,path)
                raw.unlink()
                try: frame=pd.read_csv(path,float_precision='round_trip')
                except pd.errors.EmptyDataError:frame=pd.DataFrame(columns=FIELDS)
                report['csv_sha256']=frozen.sha256(path)
            else: frame=pd.DataFrame(columns=FIELDS)
            report['summary']=recording_summary(frame,200)
            report['finished_at_utc']=datetime.now(timezone.utc).isoformat()
            temp=sidecar.with_suffix('.json.tmp')
            with temp.open('x') as handle:
                json.dump(report,handle,indent=2,allow_nan=False)
                handle.flush();os.fsync(handle.fileno())
            os.replace(temp,sidecar)
        if failure: raise failure
        frame.attrs.update(report=report,recording_path=str(path),metadata_path=str(sidecar))
        return frame
    return record
