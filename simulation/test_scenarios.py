import numpy as np
from simulation.harness.sil_runner import SILRunner, SIM_PARAMS, get_scenario_evaluation_start_time
from simulation.plant.sensor_model import SensorModel
from simulation.analysis.metrics import evaluate_scenario, compute_max_angle_error
from simulation.fault_injection.fault_injector import NullFaultInjector
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
                                   start_time=get_scenario_evaluation_start_time(sc_conf), 
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

    start_time = get_scenario_evaluation_start_time(sc_conf)
    evaluation = evaluate_scenario(
        res, criteria, onset, ref_speed,
        start_time=start_time,
        expected_fault_channel=expected_ch,
        expected_mode_after_fault=expected_mode,
        disturbance_duration=sc_conf.get('duration', 0.0),
        transition_time=trans_time
    )

    for crit, data in evaluation.items():
        assert bool(data['pass']), f"Scenario '{scenario_name}' failed criterion '{crit}': {data}"


@pytest.mark.parametrize("scenario_name", _ALL_SCENARIOS)
def test_all_scenarios_under_sensor_model(scenario_name):
    """
    Task 6 regression test:
    Verify that all 14 scenarios execute and pass under realistic ADC sensor model
    (quantization, noise, clipping, and offset calibration).
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

    start_time = get_scenario_evaluation_start_time(sc_conf)
    sensor = SensorModel()
    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario=scenario_name, sensor_model=sensor)
    res = runner.run()

    evaluation = evaluate_scenario(
        res, criteria, onset, ref_speed,
        start_time=start_time,
        expected_fault_channel=expected_ch,
        expected_mode_after_fault=expected_mode,
        disturbance_duration=sc_conf.get('duration', 0.0),
        transition_time=trans_time
    )

    for crit, data in evaluation.items():
        assert bool(data['pass']), f"Scenario '{scenario_name}' under sensor model failed criterion '{crit}': {data}"


class SingleSampleSpikeInjector(NullFaultInjector):
    def __init__(self, target_time, phase, offset):
        super().__init__()
        self.target_time = target_time
        self.phase = phase
        self.offset = offset
        self.injected = False

    def corrupt_currents(self, ia, ib, ic, t):
        if not self.injected and t >= self.target_time:
            self.injected = True
            if self.phase == 'a':
                return ia + self.offset, ib, ic
            elif self.phase == 'b':
                return ia, ib + self.offset, ic
            elif self.phase == 'c':
                return ia, ib, ic + self.offset
        return ia, ib, ic


@pytest.mark.parametrize("phase", ['a', 'b', 'c'])
@pytest.mark.parametrize("offset", [0.5, 1.0, 2.0])
def test_single_sample_spike_rejection(phase, offset):
    """
    Task 1 regression test:
    Inject a single corrupted sample (+0.5A, +1.0A, +2.0A on phases A, B, C) at t=2.0s.
    Assert control_mode never leaves 2 (CLOSED_LOOP) and speed never dips more than 3%
    below baseline minimum speed (relative to nominal speed 2000 RPM).
    """
    if not hasattr(test_single_sample_spike_rejection, 'base_res'):
        runner_base = SILRunner(config_sim=SIM_PARAMS, fault_scenario='no_fault_baseline')
        test_single_sample_spike_rejection.base_res = runner_base.run()
    base_res = test_single_sample_spike_rejection.base_res
    base_min = np.min(base_res.speed_rpm[base_res.time >= 2.0])

    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario='no_fault_baseline')
    runner.injector = SingleSampleSpikeInjector(2.0, phase, offset)
    res = runner.run()

    closed_loop_mask = res.time >= 1.5
    modes = set(res.control_mode[closed_loop_mask])
    assert modes == {2.0}, f"Control mode left CLOSED_LOOP (mode 2) on spike {phase} {offset}A: modes={modes}"

    res_min = np.min(res.speed_rpm[res.time >= 2.0])
    extra_dip = max(0.0, base_min - res_min)
    pct_dip = (extra_dip / SIM_PARAMS['speed_ref_rpm']) * 100.0
    assert pct_dip <= 3.0, f"Speed dipped by {pct_dip:.2f}% (> 3.0%) on spike {phase} {offset}A (extra dip {extra_dip:.2f} RPM)"


class BurstSampleSpikeInjector(NullFaultInjector):
    def __init__(self, target_time, phase, offset, burst_len):
        super().__init__()
        self.target_time = target_time
        self.phase = phase
        self.offset = offset
        self.burst_len = burst_len
        self.count = 0

    def corrupt_currents(self, ia, ib, ic, t):
        if t >= self.target_time and self.count < self.burst_len:
            self.count += 1
            if self.phase == 'a':
                return ia + self.offset, ib, ic
            elif self.phase == 'b':
                return ia, ib + self.offset, ic
            elif self.phase == 'c':
                return ia, ib, ic + self.offset
        return ia, ib, ic


_BURST_CASES = [
    (bl, off, ph)
    for bl in [1, 2, 3, 4]
    for off in [0.5, 1.0]
    for ph in ['a', 'b', 'c']
] + [
    (bl, off, ph)
    for bl in [1, 2]
    for off in [2.0, 3.0]
    for ph in ['a', 'b', 'c']
]


@pytest.mark.parametrize("burst_len,offset,phase", _BURST_CASES)
def test_burst_spike_rejection(burst_len, offset, phase):
    """
    Round 3 & Round 4 regression test:
    Verify that noise bursts of 1..4 samples (+0.5A, +1.0A) and 1..2 samples (+2.0A, +3.0A)
    on phases a, b, c cause no false fault latching or mode change.
    Assert control_mode never leaves CLOSED_LOOP (mode 2).
    """
    cfg = dict(SIM_PARAMS)
    cfg['total_time'] = 2.2
    runner = SILRunner(config_sim=cfg, fault_scenario='no_fault_baseline')
    runner.injector = BurstSampleSpikeInjector(2.0, phase, offset, burst_len)
    res = runner.run()

    closed_loop_mask = res.time >= 1.5
    modes = set(res.control_mode[closed_loop_mask])
    assert modes == {2.0}, (
        f"Control mode left CLOSED_LOOP (mode 2) on burst {burst_len} samples on phase {phase} (+{offset}A): modes={modes}"
    )


@pytest.mark.parametrize("burst_len,offset,expected_latched", [
    (1, 5.0, False),  # 1 sample up to 5 A rejected
    (2, 5.0, False),  # 2 samples up to 5 A rejected
    (4, 1.4, False),  # 4 samples at 1.4 A rejected (< KCL_SEVERE_THRESH)
    (5, 0.5, False),  # 5 samples at 0.5 A rejected
    (3, 2.0, True),   # 3 samples at 2.0 A MUST latch fault (> KCL_SEVERE_THRESH & n >= 3)
])
def test_burst_immunity_envelope_boundaries(burst_len, offset, expected_latched):
    """
    Round-5 Task 3 Regression Test:
    Pins the exact boundary envelope of the fault monitor burst-immunity debounce logic:
    - 1-2 samples at any magnitude up to 5.0 A are rejected.
    - 4 samples at 1.4 A and 5 samples at 0.5 A are rejected.
    - 3 samples at 2.0 A MUST latch a fault, derating to DEGRADED mode for 500 ms.
    """
    cfg = dict(SIM_PARAMS)
    cfg['total_time'] = 2.8 if expected_latched else 2.2
    runner = SILRunner(config_sim=cfg, fault_scenario='no_fault_baseline')
    runner.injector = BurstSampleSpikeInjector(2.0, 'a', offset, burst_len)
    res = runner.run()

    closed_loop_mask = res.time >= 1.5
    modes = set(res.control_mode[closed_loop_mask])

    if not expected_latched:
        assert modes == {2.0}, (
            f"Expected burst {burst_len} samples @ {offset} A to be rejected, but modes={modes}"
        )
    else:
        # Must latch DEGRADED (mode 3)
        assert 3.0 in modes, (
            f"Expected burst {burst_len} samples @ {offset} A to latch fault (mode 3), but modes={modes}"
        )
        # Verify 500 ms derate duration: enters at ~2.001s, returns to mode 2 at ~2.501s
        t = np.array(res.time)
        m = np.array(res.control_mode)
        degraded_times = t[m == 3.0]
        derate_duration = degraded_times[-1] - degraded_times[0]
        assert 0.45 <= derate_duration <= 0.55, (
            f"Expected derate duration ~0.50 s, got {derate_duration:.3f} s"
        )
        assert m[-1] == 2.0, f"Expected recovery back to mode 2 after derate, got mode {m[-1]}"


def test_safe_stop_reachable_on_second_fault_and_ambiguous():
    """
    Task 4 regression test:
    Verify that:
    1. Sequential two-sensor fault enters SAFE_STOP (mode 5) with safe_stop_time <= 50 ms.
    2. Persistent ambiguous fault enters SAFE_STOP (mode 5) with safe_stop_time <= 1600 ms.
    3. SAFE_STOP disables gate driver pulses (duty_a=0, duty_b=0, duty_c=0).
    4. Once in SAFE_STOP, control_mode is permanently latched at 5 until foc_reset().
    """
    with open('simulation/fault_injection/fault_scenarios.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # 1. Sequential two-sensor fault
    sc13 = config['scenario_13_sequential_two_sensor']
    runner13 = SILRunner(config_sim=SIM_PARAMS, fault_scenario='scenario_13_sequential_two_sensor')
    res13 = runner13.run()
    ev13 = evaluate_scenario(res13, sc13['expected_outcome']['criteria'], 
                             sc13['expected_outcome']['fault_onset_time'],
                             ref_speed=SIM_PARAMS['speed_ref_rpm'],
                             start_time=sc13['expected_outcome']['fault_onset_time'],
                             expected_mode_after_fault=5)
    assert ev13['expected_mode']['pass'], f"Scenario 13 failed to reach mode 5: {ev13}"
    assert ev13['safe_stop_time']['pass'], f"Scenario 13 safe_stop_time failed: {ev13}"
    safe_idx13 = np.where(res13.control_mode == 5)[0]
    assert np.all(res13.control_mode[safe_idx13[0]:] == 5), "SAFE_STOP unlatched before reset"
    assert np.all(res13.duty_a[safe_idx13[0]:] == 0.0), "duty_a not 0 in SAFE_STOP"
    assert np.all(res13.duty_b[safe_idx13[0]:] == 0.0), "duty_b not 0 in SAFE_STOP"
    assert np.all(res13.duty_c[safe_idx13[0]:] == 0.0), "duty_c not 0 in SAFE_STOP"

    # 2. Persistent ambiguous fault
    sc14 = config['scenario_14_persistent_ambiguous_fault']
    runner14 = SILRunner(config_sim=SIM_PARAMS, fault_scenario='scenario_14_persistent_ambiguous_fault')
    res14 = runner14.run()
    ev14 = evaluate_scenario(res14, sc14['expected_outcome']['criteria'],
                             sc14['expected_outcome']['fault_onset_time'],
                             ref_speed=SIM_PARAMS['speed_ref_rpm'],
                             start_time=sc14['expected_outcome']['fault_onset_time'],
                             expected_mode_after_fault=5)
    assert ev14['expected_mode']['pass'], f"Scenario 14 failed to reach mode 5: {ev14}"
    assert ev14['safe_stop_time']['pass'], f"Scenario 14 safe_stop_time failed: {ev14}"



