"""Explicit sensor row adapter; import alone does not open sensor or actuate fan.

The caller must hold the bench/controller lock, verify sensor_configuration and
record PWM command_ns before iteration; fan shutdown belongs in its finally.
"""
import math
import time


def sensor_rows(bus, command_ns, stop_event, *, duration_s=300):
    from adxl345 import read_fresh_sample, reset_fifo, sensor_configuration
    from prepare_pilot_dataset import EXPECTED_SENSOR
    config=sensor_configuration(bus)
    if any(config.get(k)!=v for k,v in EXPECTED_SENSOR.items()):
        raise ValueError('Sensor settings differ from frozen v4 package')
    reset_fifo(bus)
    # Capture 300 s since reader start; model selection still uses command time.
    # The delay to the first row is retained explicitly, never replaced by zero.
    start=time.monotonic_ns()
    while time.monotonic_ns()-start < duration_s*1e9 and not stop_event.is_set():
        sample=read_fresh_sample(bus,stop_event=stop_event)
        if sample is None: break
        x,y,z=sample.xyz_g
        yield dict(timestamp_s=(sample.monotonic_ns-start)/1e9,
            signal=math.sqrt(x*x+y*y+z*z),x_g=x,y_g=y,z_g=z,
            label=0,anomaly_type='normal',source='real_fifo',
            sample_index=sample.sample_index,host_monotonic_ns=sample.monotonic_ns,
            sensor_time_estimate_s=sample.sensor_time_estimate_s,
            fifo_depth=sample.fifo_depth,overrun=sample.overrun,gap=sample.gap,
            saturated=sample.saturated,read_duration_ns=sample.read_duration_ns)
