import numpy as np
import copy
import pytest
from simulation.harness.sil_runner import SILRunner
from simulation.harness.config import SIM_PARAMS
from simulation.fault_injection.fault_injector import FaultInjector


@pytest.mark.parametrize("target_rpm", [1000, 500, -2000])
def test_single_fault_deceleration_stays_degraded(target_rpm):
    """
    Regression test for sensor fault + rapid deceleration/reversal:
    Inject single sensor fault (ia +2.0 A offset) at t=1.8 s.
    Step speed reference from 2000 RPM to target_rpm at t=2.5 s.
    
    Verifies:
    1. Controller transitions to and remains in DEGRADED mode (mode 3),
       never falsely tripping SAFE_STOP (mode 5) due to braking transients.
    2. Observer maintains lock: max angle error across fault and decel is < 30.0 degrees.
    3. Motor tracks the new speed reference.
    """
    cfg = copy.deepcopy(SIM_PARAMS)
    cfg['total_time'] = 3.5

    runner = SILRunner(config_sim=cfg)
    runner.scenario_config = {
        'type': 'sensor_offset',
        'channel': 'a',
        'offset': 2.0,
        'onset_time': 1.8,
        'speed_reversal': {
            'onset_time': 2.5,
            'new_speed_rpm': float(target_rpm)
        }
    }
    runner.injector = FaultInjector(runner.scenario_config)
    res = runner.run()

    # 1. Controller mode check after fault onset (t >= 1.85 s)
    post_fault_mask = res.time >= 1.85
    modes_seen = set(res.control_mode[post_fault_mask])
    assert 5 not in modes_seen, (
        f"Controller falsely latched SAFE_STOP (mode 5) during decel to {target_rpm} RPM. "
        f"Modes seen: {modes_seen}"
    )
    assert res.control_mode[-1] == 3, (
        f"Expected final control mode DEGRADED (3), got {res.control_mode[-1]}"
    )

    # 2. Maximum angle error must stay under 30.0 degrees after fault onset and throughout decel
    eval_mask = res.time >= 2.0
    max_angle_err = float(np.max(np.abs(res.angle_error[eval_mask])))
    assert max_angle_err < 30.0, (
        f"Observer lost lock during decel to {target_rpm} RPM: "
        f"max angle error {max_angle_err:.2f} deg >= 30.0 deg"
    )

    # 3. Speed tracking verification (within 10% or 100 RPM at steady-state)
    settled_mask = res.time >= 3.2
    mean_speed = float(np.mean(res.speed_rpm[settled_mask]))
    speed_tol = max(100.0, 0.10 * abs(target_rpm))
    assert abs(mean_speed - target_rpm) < speed_tol, (
        f"Speed did not settle at {target_rpm} RPM: mean speed {mean_speed:.1f} RPM"
    )
