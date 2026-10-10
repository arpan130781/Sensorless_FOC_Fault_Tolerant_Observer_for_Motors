import numpy as np
from simulation.harness.sil_runner import SILRunner, SIM_PARAMS
from simulation.analysis.metrics import evaluate_scenario, compute_max_angle_error
import yaml

def test_scenario_4_angle_limit():
    """Regression test to ensure scenario 4 respects the 65-degree limit and tests criteria behavior."""
    
    with open('simulation/fault_injection/fault_scenarios.yaml', 'r') as f:
        config = yaml.safe_load(f)
        
    sc_conf = config['scenario_4_stuck_a_limit']
    criteria = sc_conf['expected_outcome']['criteria']
    
    # 1. Verify limit is 65.0 in the YAML configuration
    assert criteria['max_angle_error'] == 65.0, "YAML configuration max_angle_error must be 65.0"
    
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
    # Limit is 65.0
    assert max_angle_err <= 65.0, f"Max angle error {max_angle_err} exceeded limit 65.0 in scenario 4"
    # Ensure it isolated correctly
    assert evaluation['fault_isolation']['pass'] == True, "Failed to isolate faulty channel"

    # 3. Test mock values explicitly passing/failing the 65-degree criterion
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
        
        eval_res = evaluate_scenario(mock_res, {'max_angle_error': 65.0}, fault_onset_time=0.5, ref_speed=1000)
        return eval_res['max_angle_error']['pass']

    # Test 62.92 passes
    assert test_angle(62.92) == True, "62.92 degrees should PASS the 65.0 limit"
    
    # Test >65 fails
    assert test_angle(65.1) == False, "65.1 degrees should FAIL the 65.0 limit"
    
    # Test NaN fails
    assert test_angle(np.nan) == False, "NaN angle error should FAIL the 65.0 limit"
    
    # Test Inf fails
    assert test_angle(np.inf) == False, "Inf angle error should FAIL the 65.0 limit"


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
