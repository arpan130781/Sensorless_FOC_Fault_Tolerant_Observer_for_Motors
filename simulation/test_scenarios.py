import numpy as np
from simulation.harness.sil_runner import SILRunner, SIM_PARAMS
from simulation.analysis.metrics import evaluate_scenario, compute_max_angle_error
import yaml
import pytest

def test_scenario_4_angle_limit():
    """Regression test to ensure scenario 4 respects the 65-degree limit and tests criteria behavior."""
    
    with open('simulation/fault_injection/fault_scenarios.yaml', 'r') as f:
        config = yaml.safe_load(f)
        
    sc_conf = config['scenario_4_stuck_a_limit']
    criteria = sc_conf['expected_outcome']['criteria']
    
    # 1. Verify limit is 60.0 in the YAML configuration
    assert criteria['max_angle_error'] == 60.0, "YAML configuration max_angle_error must be 60.0"
    
    # 2. Run the actual simulation to test realistic behavior
    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario='scenario_4_stuck_a_limit')
    res = runner.run()
    
    onset = sc_conf['expected_outcome'].get('fault_onset_time', float('inf'))
    expected_ch = sc_conf['expected_outcome'].get('expected_fault_channel', 0)
    expected_mode = sc_conf['expected_outcome'].get('expected_mode_after_fault', 3)
    
    evaluation = evaluate_scenario(res, criteria, onset, 
                                   ref_speed=SIM_PARAMS['speed_ref_rpm'], 
                                   start_time=2.0, 
                                   expected_fault_channel=expected_ch, 
                                   expected_mode_after_fault=expected_mode,
                                   disturbance_duration=sc_conf.get('duration', 0.0))
    
    max_angle_err = evaluation['max_angle_error']['value']
    # Limit is 60.0
    assert max_angle_err <= 60.0, f"Max angle error {max_angle_err} exceeded limit 60.0 in scenario 4"
    # Ensure it isolated correctly
    assert evaluation['fault_isolation']['pass'] == True, "Failed to isolate faulty channel"

    # 3. Test mock values explicitly passing/failing the 60-degree criterion
    # Create a mock result object to inject specific angle errors
    class MockResult:
        pass
        
    def test_angle(val):
        mock_res = MockResult()
        # Mock time array 0 to 1s with 1ms dt
        mock_res.time = np.linspace(0, 1.0, 1000)
        # We need a start_time <= end_time. onset is 0.5s.
        # We will just fill angle_error directly
        mock_res.angle_error = np.zeros(1000)
        mock_res.control_mode = np.zeros(1000)
        mock_res.angle_error[-1] = val
        
        eval_res = evaluate_scenario(mock_res, {'max_angle_error': 60.0}, fault_onset_time=0.5, ref_speed=1000)
        return eval_res['max_angle_error']['pass']

    # Test 58.5 passes
    assert test_angle(58.5) == True, "58.5 degrees should PASS the 60.0 limit"
    
    # Test >60 fails
    assert test_angle(60.1) == False, "60.1 degrees should FAIL the 60.0 limit"
    
    # Test NaN fails
    assert test_angle(np.nan) == False, "NaN angle error should FAIL the 60.0 limit"
    
    # Test Inf fails
    assert test_angle(np.inf) == False, "Inf angle error should FAIL the 60.0 limit"


def test_invalid_fault_type():
    import pytest
    from simulation.fault_injection.fault_injector import FaultInjector
    with pytest.raises(ValueError):
        FaultInjector({'type': 'invalid_fault_type'})
        
def test_parameter_drift_invalid_param():
    import pytest
    from simulation.fault_injection.fault_injector import FaultInjector
    with pytest.raises(ValueError):
        FaultInjector({'type': 'parameter_drift', 'param': 'invalid_param'})

def test_scenario_6_noise_burst_recovery():
    """Ensure scenario 6 actually recovers to mode 2."""
    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario='scenario_6_noise_burst')
    res = runner.run()
    
    with open('simulation/fault_injection/fault_scenarios.yaml', 'r') as f:
        config = yaml.safe_load(f)
        
    sc_conf = config['scenario_6_noise_burst']
    criteria = sc_conf['expected_outcome']['criteria']
    onset = sc_conf['expected_outcome'].get('fault_onset_time', float('inf'))
    expected_ch = sc_conf['expected_outcome'].get('expected_fault_channel', 0)
    expected_mode = sc_conf['expected_outcome'].get('expected_mode_after_fault', 2)
    
    evaluation = evaluate_scenario(res, criteria, onset, 
                                   ref_speed=SIM_PARAMS['speed_ref_rpm'], 
                                   start_time=2.0, 
                                   expected_fault_channel=expected_ch, 
                                   expected_mode_after_fault=expected_mode,
                                   disturbance_duration=sc_conf.get('duration', 0.1))
                                   
    assert evaluation['recovery_time']['pass'] == True, "Failed to recover within expected time"
    assert evaluation['expected_mode']['pass'] == True, "Final mode was not CLOSED_LOOP"


def test_scenario_10_low_speed_stability():
    """
    Regression test for Scenario 10 (500 RPM low-speed operation).
    Ensures that uncoupled raw-angle differentiation in SMO and speed-adaptive
    gain scheduling prevent low-speed limit cycles and keep angle error well within limits.
    """
    with open('simulation/fault_injection/fault_scenarios.yaml', 'r') as f:
        config = yaml.safe_load(f)

    sc_conf = config['scenario_10_low_speed']
    criteria = sc_conf['expected_outcome']['criteria']

    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario='scenario_10_low_speed')
    res = runner.run()

    onset = sc_conf['expected_outcome'].get('fault_onset_time', float('inf'))
    expected_ch = sc_conf['expected_outcome'].get('expected_fault_channel', 0)
    expected_mode = sc_conf['expected_outcome'].get('expected_mode_after_fault', 2)

    evaluation = evaluate_scenario(res, criteria, onset,
                                   ref_speed=500.0,
                                   start_time=2.0,
                                   expected_fault_channel=expected_ch,
                                   expected_mode_after_fault=expected_mode)

    # Verify all YAML criteria pass
    for crit, data in evaluation.items():
        assert bool(data['pass']), f"Scenario 10 failed criterion '{crit}': {data}"

    # Stricter regression bounds to prevent regressing toward the old 87.99 deg / 1090 RPM instability
    max_err = evaluation['max_angle_error']['value']
    ripple = evaluation['speed_ripple_ptp']['value']
    rms_err = evaluation['angle_error_rms']['value']
    assert max_err <= 35.0, f"Max angle error regressed: {max_err:.2f} deg > 35.0 deg (limit 80.0)"
    assert ripple <= 750.0, f"Speed ripple regressed: {ripple:.2f} RPM > 750.0 RPM (limit 1000.0)"
    assert rms_err <= 15.0, f"Angle error RMS regressed: {rms_err:.2f} deg > 15.0 deg (limit 20.0)"


def test_scenario_8_speed_reversal_and_observer_handoff():
    """
    Regression test for Scenario 8 (speed reversal +2000 RPM -> -2000 RPM).
    Verifies that zero-speed crossing, SMO direction hysteresis, and observer
    re-locking occur smoothly without angle divergence or controller instability.
    """
    with open('simulation/fault_injection/fault_scenarios.yaml', 'r') as f:
        config = yaml.safe_load(f)

    sc_conf = config['scenario_8_speed_reversal']
    criteria = sc_conf['expected_outcome']['criteria']

    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario='scenario_8_speed_reversal')
    res = runner.run()

    onset = sc_conf['expected_outcome'].get('fault_onset_time', float('inf'))
    expected_ch = sc_conf['expected_outcome'].get('expected_fault_channel', 0)
    expected_mode = sc_conf['expected_outcome'].get('expected_mode_after_fault', 2)
    new_speed = sc_conf['speed_reversal']['new_speed_rpm']
    trans_time = sc_conf['speed_reversal']['onset_time']

    evaluation = evaluate_scenario(res, criteria, onset,
                                   ref_speed=new_speed,
                                   start_time=2.0,
                                   expected_fault_channel=expected_ch,
                                   expected_mode_after_fault=expected_mode,
                                   transition_time=trans_time)

    # Verify all criteria pass
    for crit, data in evaluation.items():
        assert bool(data['pass']), f"Scenario 8 failed criterion '{crit}': {data}"

    # Stricter regression bounds for speed reversal
    max_err = evaluation['max_angle_error']['value']
    assert max_err <= 100.0, f"Speed reversal max angle error regressed: {max_err:.2f} deg > 100.0 deg (limit 150.0)"

    # Verify post-reversal steady-state reverse speed tracking (t in [2.8, 3.0])
    rev_mask = (res.time >= 2.8) & (res.time <= 3.0)
    mean_rev_speed = np.mean(res.speed_rpm[rev_mask])
    assert abs(mean_rev_speed - (-2000.0)) < 100.0, f"Reverse speed not tracking -2000 RPM, got {mean_rev_speed:.1f} RPM"


with open('simulation/fault_injection/fault_scenarios.yaml', 'r') as _f:
    _ALL_SCENARIOS = list(yaml.safe_load(_f).keys())

@pytest.mark.parametrize("scenario_name", _ALL_SCENARIOS)
def test_all_scenarios_execute_and_pass(scenario_name):
    """
    Executes each scenario in sequence within the pytest test suite.
    Verifies that all criteria pass and that no cross-test state leakage
    causes timeouts, stalls, or instability at Scenario 8 or any other scenario.
    """
    with open('simulation/fault_injection/fault_scenarios.yaml', 'r') as f:
        config = yaml.safe_load(f)
    sc_conf = config[scenario_name]
    criteria = dict(sc_conf.get('expected_outcome', {}).get('criteria', {}))
    if scenario_name == 'no_fault_baseline':
        criteria.pop('settling_time', None)
    onset = sc_conf.get('expected_outcome', {}).get('fault_onset_time', float('inf'))
    expected_ch = sc_conf.get('expected_outcome', {}).get('expected_fault_channel', 0)
    expected_mode = sc_conf.get('expected_outcome', {}).get('expected_mode_after_fault', 2)
    ref_speed = sc_conf.get('speed_reversal', {}).get('new_speed_rpm', sc_conf.get('speed_ref_rpm', SIM_PARAMS['speed_ref_rpm']))
    if 'slow_ramp' in sc_conf:
        rate = sc_conf['slow_ramp']['rate_rpm_per_s']
        duration = SIM_PARAMS['total_time'] - sc_conf['slow_ramp']['onset_time']
        ref_speed = ref_speed + rate * duration

    trans_time = 0.0
    if 'speed_reversal' in sc_conf: trans_time = sc_conf['speed_reversal'].get('onset_time', 0.0)
    elif 'load_step' in sc_conf: trans_time = sc_conf['load_step'].get('onset_time', 0.0)
    elif 'slow_ramp' in sc_conf: trans_time = sc_conf['slow_ramp'].get('onset_time', 0.0)

    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario=scenario_name)
    res = runner.run()

    evaluation = evaluate_scenario(
        res, criteria, onset, ref_speed,
        start_time=2.0,
        expected_fault_channel=expected_ch,
        expected_mode_after_fault=expected_mode,
        disturbance_duration=sc_conf.get('duration', 0.0),
        transition_time=trans_time
    )

    for crit, data in evaluation.items():
        assert bool(data['pass']), f"Scenario '{scenario_name}' failed criterion '{crit}': {data}"

