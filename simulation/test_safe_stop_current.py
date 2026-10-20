import numpy as np
import pytest
from simulation.harness.sil_runner import SILRunner, SIM_PARAMS
from simulation.harness.config import MOTOR_PARAMS


def test_safe_stop_peak_current_below_limit():
    """
    Task 3 Regression Test:
    Verify that when the inverter gate enable is disabled (SAFE_STOP mode 5),
    the plant is modeled as high-impedance (body-diode freewheeling/coasting)
    rather than a 3-phase short circuit (va=vb=vc=0).

    Peak phase current after SAFE_STOP onset at 2000 RPM must stay below 1.2 * In (6.0 A),
    preventing the ~12.5 A short-circuit surge.
    """
    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario='scenario_13_sequential_two_sensor')
    res = runner.run()

    t = np.array(res.time)
    mode = np.array(res.control_mode)
    safe_stop_mask = mode == 5.0

    assert np.any(safe_stop_mask), "Controller must enter SAFE_STOP (mode 5) in scenario 13"

    t_onset = t[safe_stop_mask][0]
    # Allow 1 control cycle (50 us) for initial inductor current to quench
    quench_mask = t >= (t_onset + 0.0005)

    # Check peak current across all three physical phases in SAFE_STOP
    peak_ia = float(np.max(np.abs(res.i_true_a[safe_stop_mask])))
    peak_ib = float(np.max(np.abs(res.i_true_b[safe_stop_mask])))
    peak_ic = float(np.max(np.abs(res.i_true_c[safe_stop_mask])))
    peak_current = max(peak_ia, peak_ib, peak_ic)

    in_limit = 1.2 * MOTOR_PARAMS['In']  # 1.2 * 5.0 A = 6.0 A
    assert peak_current < in_limit, (
        f"Peak phase current after SAFE_STOP was {peak_current:.2f} A, "
        f"exceeding 1.2*In ({in_limit:.2f} A). Gate disable must not behave as a 3-phase short."
    )

    # After initial quenching (0.5 ms), currents should remain near zero since back-EMF < Vbus
    if np.any(quench_mask):
        quenched_peak = max(
            float(np.max(np.abs(res.i_true_a[quench_mask]))),
            float(np.max(np.abs(res.i_true_b[quench_mask]))),
            float(np.max(np.abs(res.i_true_c[quench_mask])))
        )
        assert quenched_peak < 0.5, (
            f"Quenched phase current after SAFE_STOP was {quenched_peak:.2f} A; expected near zero."
        )

    # Task 5: Verify DC bus voltage rise from inductive freewheeling into Cbus
    assert res.v_bus is not None, "SimulationResult must record v_bus"
    vbus_nominal = MOTOR_PARAMS['Vbus']
    vbus_peak = float(np.max(res.v_bus[safe_stop_mask]))
    vbus_rise = vbus_peak - vbus_nominal
    assert vbus_rise > 0.1, (
        f"Expected bus voltage rise during SAFE_STOP quenching, but got {vbus_rise:.3f} V."
    )
    # Bus voltage must bleed back down toward nominal via bleeder resistor (RC = 50 ohm * 470 uF = 23.5 ms).
    # Verify quantitative decay by stated margins after stated times:
    t_peak_idx = np.where(safe_stop_mask)[0][np.argmax(res.v_bus[safe_stop_mask])]
    t_peak = t[t_peak_idx]

    # At t = t_peak + 50 ms (~2 RC time constants), bus voltage must have decayed by at least 50% of the rise
    t_50ms_idx = np.searchsorted(t, t_peak + 0.050)
    assert t_50ms_idx < len(t), "Simulation must extend at least 50 ms beyond peak bus voltage"
    vbus_at_50ms = float(res.v_bus[t_50ms_idx])
    decay_50ms = vbus_peak - vbus_at_50ms
    assert decay_50ms >= 0.50 * vbus_rise, (
        f"Bus voltage after 50 ms did not decay sufficiently: decayed {decay_50ms:.3f} V, "
        f"expected >= {0.50 * vbus_rise:.3f} V (50% of {vbus_rise:.3f} V rise). Current Vbus: {vbus_at_50ms:.3f} V."
    )

    # At simulation end (t > t_peak + 200 ms, >8 RC time constants), bus voltage must return to within 0.05 V of nominal
    vbus_final = float(res.v_bus[-1])
    assert vbus_final <= vbus_nominal + 0.05, (
        f"Bus voltage at end of simulation ({vbus_final:.3f} V) did not fully bleed to nominal ({vbus_nominal:.1f} V)."
    )
