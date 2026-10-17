import numpy as np
import yaml
import pytest
from simulation.harness.sil_runner import SILRunner, SIM_PARAMS
from simulation.analysis.metrics import evaluate_scenario


def test_baseline_duty_clamped_and_criteria_pass():
    """
    Task 3 regression test:
    Assert that all inverter duty cycles (duty_a, duty_b, duty_c) in the baseline run
    are strictly within [0.0, 1.0] across all simulation time steps,
    and that the baseline run passes all of its original YAML acceptance criteria
    without relaxing the 15.0-degree max angle error limit.
    """
    with open('simulation/fault_injection/fault_scenarios.yaml', 'r') as f:
        config = yaml.safe_load(f)
    sc_conf = config['no_fault_baseline']
    criteria = dict(sc_conf['expected_outcome']['criteria'])
    criteria.pop('settling_time', None)
    expected_mode = sc_conf.get('expected_outcome', {}).get('expected_mode_after_fault', 2)

    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario='no_fault_baseline')
    res = runner.run()

    # 1. Assert duty cycles are strictly clamped to [0.0, 1.0]
    assert np.all(res.duty_a >= 0.0) and np.all(res.duty_a <= 1.0), (
        f"duty_a out of bounds: min={np.min(res.duty_a)}, max={np.max(res.duty_a)}"
    )
    assert np.all(res.duty_b >= 0.0) and np.all(res.duty_b <= 1.0), (
        f"duty_b out of bounds: min={np.min(res.duty_b)}, max={np.max(res.duty_b)}"
    )
    assert np.all(res.duty_c >= 0.0) and np.all(res.duty_c <= 1.0), (
        f"duty_c out of bounds: min={np.min(res.duty_c)}, max={np.max(res.duty_c)}"
    )

    # 2. Evaluate all original baseline criteria
    ev = evaluate_scenario(
        res, criteria, float('inf'),
        ref_speed=SIM_PARAMS['speed_ref_rpm'],
        start_time=2.0,
        expected_mode_after_fault=expected_mode
    )

    for crit_name, data in ev.items():
        assert bool(data['pass']), f"Baseline failed criterion '{crit_name}': {data}"

    # 3. Assert max_angle_error is well below the original 15.0 degree limit
    max_angle_err = ev['max_angle_error']['value']
    assert max_angle_err <= 15.0, f"Max angle error {max_angle_err:.2f} deg exceeded 15.0 deg"
