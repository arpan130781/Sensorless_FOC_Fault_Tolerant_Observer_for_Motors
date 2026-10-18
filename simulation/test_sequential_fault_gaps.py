import copy
import numpy as np
import pytest
from simulation.harness.sil_runner import SILRunner, SIM_PARAMS
from simulation.fault_injection.fault_injector import FaultInjector


@pytest.mark.parametrize("gap_s", [0.020, 0.050, 0.100])
def test_sequential_second_fault_detected_within_50ms(gap_s):
    """
    Task 4 Regression Test:
    Verify that sequential two-sensor faults with short intervals (gaps of 20 ms, 50 ms, 100 ms)
    are detected and transition the controller to SAFE_STOP (mode 5) within 50 ms of the second fault.

    Replaces the old blanket 200 ms post-latch holdoff (which delayed second-fault detection by ~213 ms)
    with a targeted settling holdoff.
    """
    t1 = 1.800
    t2 = t1 + gap_s

    cfg = copy.deepcopy(SIM_PARAMS)
    cfg['total_time'] = 3.0

    runner = SILRunner(config_sim=cfg)
    runner.scenario_config = {
        'type': 'simultaneous',
        'faults': [
            {'type': 'sensor_offset', 'channel': 'a', 'offset': 2.0, 'onset_time': t1},
            {'type': 'sensor_offset', 'channel': 'b', 'offset': 2.0, 'onset_time': t2}
        ]
    }
    runner.injector = FaultInjector(runner.scenario_config)
    res = runner.run()

    t = np.array(res.time)
    mode = np.array(res.control_mode)

    # 1. Controller must enter SAFE_STOP
    safe_stop_mask = mode == 5.0
    assert np.any(safe_stop_mask), (
        f"Controller did not reach SAFE_STOP (mode 5) for sequential fault gap of {gap_s * 1000:.0f} ms"
    )

    # 2. Time from second fault onset (t2) to SAFE_STOP must be < 50 ms
    t_safe_stop = t[safe_stop_mask][0]
    latency_ms = (t_safe_stop - t2) * 1000.0

    assert latency_ms < 50.0, (
        f"Second-fault detection latency for {gap_s * 1000:.0f} ms gap was {latency_ms:.2f} ms; "
        f"must be < 50.0 ms."
    )
    assert latency_ms >= 0.0, "SAFE_STOP triggered before second fault onset"
