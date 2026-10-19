"""
SIL Tests for Inverter Dead-Time Parameterization and Sensitivity Sweep.

Evaluates controller performance across plant dead-times:
- Plant v_dead = 0.5 V (matched): baseline max angle error < 1.0 deg (well within 15 deg limit).
- Plant v_dead = 0.25 V: max angle error ~6.5 deg (within 15 deg limit).
- Plant v_dead = 1.0 V: max angle error ~3.5 deg (within 15 deg limit).
- Plant v_dead = 1.5 V: max angle error ~7.1 deg (within 15 deg limit).
- Plant v_dead = 0.0 V: with controller assuming 0.5 V, max angle error degrades to ~19.3 deg
  due to uncompensated 0.5V over-compensation ripple at zero-crossings.
- Plant v_dead = 0.0 V with controller dead_time = 0.0: max angle error recovers to < 1.0 deg.
"""

import pytest
import numpy as np
from simulation.harness.sil_runner import SILRunner
from simulation.harness.config import SIM_PARAMS, MOTOR_PARAMS, CONTROLLER_PARAMS


def test_matched_dead_time_baseline():
    """Verify default matched dead-time (0.5V plant and 0.5V controller compensation) achieves < 1.0 deg error."""
    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario='no_fault_baseline', v_dead_plant=0.5)
    res = runner.run()
    mask = res.time >= 1.5
    max_err = float(np.max(np.abs(res.angle_error[mask])))
    assert max_err < 1.0, f"Matched dead-time error unexpectedly high: {max_err:.2f} deg"


@pytest.mark.parametrize("v_dead_plant, expected_max_err_bound, expected_pass_15deg", [
    (0.50, 1.0, True),    # Matched (0.5V vs 0.5V)
    (0.25, 10.0, True),   # 0.25V mismatch
    (1.00, 10.0, True),   # 0.5V plant dead-time
    (1.50, 12.0, True),   # 1.0V plant dead-time
    (0.00, 22.0, False),  # 0.0V plant: uncompensated 0.5V over-compensation -> ~19.3 deg error
])
def test_dead_time_mismatch_sweep(v_dead_plant, expected_max_err_bound, expected_pass_15deg):
    """
    Sweep plant dead-time against fixed controller assumption (0.5V).
    Documents and verifies measured degradation:
    - 0.25V, 0.5V, 1.0V, 1.5V meet the 15 deg baseline criterion.
    - 0.0V plant degrades to ~19.3 deg (fails 15 deg criterion) due to 0.5V compensation mismatch.
    """
    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario='no_fault_baseline', v_dead_plant=v_dead_plant)
    res = runner.run()
    mask = res.time >= 1.5
    max_err = float(np.max(np.abs(res.angle_error[mask])))

    assert max_err < expected_max_err_bound, (
        f"Plant v_dead={v_dead_plant}V: max angle error {max_err:.2f} deg exceeded bound {expected_max_err_bound} deg"
    )

    if expected_pass_15deg:
        assert max_err < 15.0, (
            f"Plant v_dead={v_dead_plant}V: expected < 15.0 deg, got {max_err:.2f} deg"
        )
    else:
        # Documented degradation for 0.0V plant with 0.5V compensation
        assert max_err >= 15.0, (
            f"Plant v_dead={v_dead_plant}V: expected degradation >= 15.0 deg, got {max_err:.2f} deg"
        )
        assert 18.0 <= max_err <= 21.0, (
            f"Plant v_dead=0.0V degradation out of expected range [18, 21] deg: {max_err:.2f} deg"
        )


def test_dead_time_parameter_configuration_zero_recovery():
    """
    Verify that when controller dead_time parameter is configured to 0.0 s
    to match a 0.0 V plant, angle error recovers from 19.3 deg back to < 1.0 deg.
    """
    # Configure controller dead_time = 0.0
    custom_ctrl = dict(CONTROLLER_PARAMS)
    custom_ctrl['dead_time'] = 0.0
    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario='no_fault_baseline', v_dead_plant=0.0, custom_ctrl_params=custom_ctrl)

    res = runner.run()
    mask = res.time >= 1.5
    max_err = float(np.max(np.abs(res.angle_error[mask])))
    assert max_err < 1.0, f"Angle error with zero dead-time compensation failed to recover: {max_err:.2f} deg"
