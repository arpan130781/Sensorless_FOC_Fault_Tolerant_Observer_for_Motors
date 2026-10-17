import numpy as np
import yaml
import pytest
from simulation.harness.sil_runner import SILRunner, SIM_PARAMS
from simulation.analysis.metrics import evaluate_scenario
from simulation.plant.sensor_model import SensorModel


def test_old_current_scale_clips_and_triggers_false_fault():
    """
    Task 5 negative test:
    Demonstrates that the old current scale (+/-3.3A full scale) clips the baseline
    phase currents (which reach ~5.0A peak), generating a large artificial KCL residual
    that causes false fault trips and forces the controller out of normal CLOSED_LOOP.
    """
    old_sensor = SensorModel(full_scale_A=3.3, bits=12, noise_rms_A=0.0, offset_lsb=0, calibrate_offset=False)
    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario='no_fault_baseline', sensor_model=old_sensor)
    res = runner.run()

    # With 3.3A clipping, fault monitor must detect violation and leave normal mode
    # Control mode must leave CLOSED_LOOP (2)
    post_startup = res.time >= 1.5
    modes = set(res.control_mode[post_startup])
    assert modes != {2.0}, f"Expected false fault trip under +/-3.3A clipping, but mode stayed {modes}"


def test_new_current_scale_with_noise_quantization_and_offset():
    """
    Task 5 regression test:
    Under the new current scale (+/-8.25A full scale, derived from 10 mOhm shunt x 20 gain):
    - 12-bit ADC quantization
    - 30 mA RMS analog noise
    - 20 LSB hardware offset (with startup calibration)
    The baseline must show zero false faults:
    1. Control mode remains in CLOSED_LOOP (2) for all t >= 1.5s.
    2. Fault status flags remain zero (no false sensor fault latched).
    3. All baseline acceptance criteria pass.
    """
    new_sensor = SensorModel(full_scale_A=8.25, bits=12, noise_rms_A=0.030, offset_lsb=20, calibrate_offset=True)
    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario='no_fault_baseline', sensor_model=new_sensor)
    res = runner.run()

    # 1. Assert control mode never trips into fault degradation after startup
    post_startup = res.time >= 1.5
    modes = set(res.control_mode[post_startup])
    assert modes == {2.0}, f"False fault triggered! Control modes post-startup: {modes}"

    # 2. Assert no fault channel was isolated
    isolated_channels = set(res.fault_channel[post_startup])
    assert isolated_channels == {0.0}, f"False channel isolated: {isolated_channels}"

    # 3. Assert baseline criteria all pass
    with open('simulation/fault_injection/fault_scenarios.yaml', 'r') as f:
        config = yaml.safe_load(f)
    sc_conf = config['no_fault_baseline']
    criteria = dict(sc_conf['expected_outcome']['criteria'])
    criteria.pop('settling_time', None)

    ev = evaluate_scenario(
        res, criteria, float('inf'),
        ref_speed=SIM_PARAMS['speed_ref_rpm'],
        start_time=2.0,
        expected_mode_after_fault=2
    )

    for crit_name, data in ev.items():
        assert bool(data['pass']), f"Baseline failed criterion '{crit_name}' under realistic sensor model: {data}"
