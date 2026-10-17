import ctypes
import numpy as np
import math
import pytest
from simulation.harness.c_bridge import FocController
from simulation.harness.config import MOTOR_PARAMS, CONTROLLER_PARAMS, PATHS
from simulation.plant.pmsm_model import PMSMModel
from simulation.plant.inverter_model import duties_to_voltages, phase_to_dq


class HandoffCtypes(ctypes.Structure):
    _fields_ = [
        ("current_mode", ctypes.c_int),
        ("time_in_state", ctypes.c_float),
        ("blend_timer", ctypes.c_float),
        ("lkg_theta", ctypes.c_float),
        ("lkg_omega", ctypes.c_float),
        ("stall_timer", ctypes.c_float),
        ("pending_fault_state", ctypes.c_int)
    ]


def test_fault_during_align_mode_sequence_unit():
    """
    Task 2 unit test:
    Inject a fault (DEGRADED mode 3) during ALIGN via ctypes handoff_update.
    Assert the sequence of modes is strictly ALIGN (0) -> OPEN_LOOP (1) -> CLOSED_LOOP (2) -> DEGRADED (3),
    never skipping any intermediate startup stages.
    """
    lib = ctypes.CDLL(PATHS['lib_path'])
    lib.handoff_init.argtypes = [ctypes.POINTER(HandoffCtypes)]
    lib.handoff_update.argtypes = [
        ctypes.POINTER(HandoffCtypes),
        ctypes.c_float, ctypes.c_float, ctypes.c_float,
        ctypes.c_bool, ctypes.c_int, ctypes.c_float
    ]
    lib.handoff_update.restype = ctypes.c_int

    h = HandoffCtypes()
    lib.handoff_init(ctypes.byref(h))

    dt = 0.00005
    modes = []
    t = 0.0

    # 1. ALIGN phase (t < 0.5s): inject DEGRADED (3) at t = 0.05s
    while t < 0.5:
        fault_req = 3 if t >= 0.05 else 2
        m = lib.handoff_update(ctypes.byref(h), 0.8, 0.1, 0.0, False, fault_req, dt)
        modes.append(m)
        t += dt

    # 2. OPEN_LOOP phase (0.5s <= t < 1.0s)
    while t < 1.0:
        m = lib.handoff_update(ctypes.byref(h), 0.8, 0.1, 100.0, False, 3, dt)
        modes.append(m)
        t += dt

    # 3. Startup completes at t = 1.0s: handoff tick to CLOSED_LOOP, then following tick to DEGRADED
    m_handoff = lib.handoff_update(ctypes.byref(h), 0.8, 0.1, 100.0, True, 3, dt)
    modes.append(m_handoff)
    m_next = lib.handoff_update(ctypes.byref(h), 0.8, 0.1, 100.0, True, 3, dt)
    modes.append(m_next)

    unique_sequence = []
    for m in modes:
        if not unique_sequence or m != unique_sequence[-1]:
            unique_sequence.append(m)

    assert unique_sequence == [0, 1, 2, 3], (
        f"Mode sequence skipped stages: expected [0, 1, 2, 3] (ALIGN -> OPEN_LOOP -> CLOSED_LOOP -> DEGRADED), "
        f"got {unique_sequence}"
    )


def test_fault_during_align_full_controller():
    """
    Task 2 integration test with plant and C controller:
    Inject sensor fault during ALIGN at t=0.05s.
    Verify mode sequence is ALIGN (0) -> OPEN_LOOP (1) -> CLOSED_LOOP (2) -> DEGRADED (3).
    """
    controller = FocController(PATHS['lib_path'])
    controller.init(MOTOR_PARAMS, CONTROLLER_PARAMS)
    controller.set_speed_ref(2000.0 * (2 * math.pi / 60) * MOTOR_PARAMS['P'])
    plant = PMSMModel(**MOTOR_PARAMS)

    dt_c = 1.0 / CONTROLLER_PARAMS['pwm_freq']
    dt_p = 1e-6
    sub_steps = int(dt_c / dt_p)

    modes = []
    for k in range(int(1.5 / dt_c)):
        t = k * dt_c
        ia, ib, ic = plant.get_phase_currents()
        if t >= 0.05:
            ia += 2.0  # Massive sensor fault injected during ALIGN
        out = controller.tick(ia, ib, ic, MOTOR_PARAMS['Vbus'])
        modes.append(out.control_mode)
        va, vb, vc = duties_to_voltages(out.duty_a, out.duty_b, out.duty_c, MOTOR_PARAMS['Vbus'], ia, ib, ic)
        for _ in range(sub_steps):
            vd, vq = phase_to_dq(va, vb, vc, plant.theta_e)
            plant.step(vd, vq, 0.0, dt_p)

    seq = []
    for m in modes:
        if not seq or m != seq[-1]:
            seq.append(m)

    assert seq == [0, 1, 2, 3], (
        f"Full controller mode sequence failed: expected [0, 1, 2, 3], got {seq}"
    )


def test_stall_fallback_unit():
    """
    Task 2 unit test:
    Verify stall fallback in handoff_update:
    When in CLOSED_LOOP (2), sustained low speed (|obs_omega| < 10 rad/s) for > 300 ms
    must transition to OPEN_LOOP (1).
    """
    lib = ctypes.CDLL(PATHS['lib_path'])
    lib.handoff_init.argtypes = [ctypes.POINTER(HandoffCtypes)]
    lib.handoff_update.argtypes = [
        ctypes.POINTER(HandoffCtypes),
        ctypes.c_float, ctypes.c_float, ctypes.c_float,
        ctypes.c_bool, ctypes.c_int, ctypes.c_float
    ]
    lib.handoff_update.restype = ctypes.c_int

    h = HandoffCtypes()
    lib.handoff_init(ctypes.byref(h))
    h.current_mode = 2  # CLOSED_LOOP

    dt = 0.00005
    modes = []
    t = 0.0
    while t < 0.35:
        m = lib.handoff_update(ctypes.byref(h), 0.8, 0.1, 5.0, True, 2, dt)
        modes.append(m)
        t += dt

    seq = []
    for m in modes:
        if not seq or m != seq[-1]:
            seq.append(m)

    assert seq == [2, 1], f"Expected stall fallback sequence [2, 1], got {seq}"
    assert h.stall_timer == 0.0, "Stall timer must be reset on fallback to OPEN_LOOP"


@pytest.mark.parametrize("fault_amp", [0.5, 1.0, 2.0])
@pytest.mark.parametrize("stage,inject_time", [("align", 0.05), ("open_loop", 0.6)])
def test_fault_during_startup_stages(fault_amp, stage, inject_time):
    """
    Round 2 Audit Task 1 Regression Test:
    Inject sensor fault of 0.5A, 1.0A, 2.0A during ALIGN (0.05s) and OPEN_LOOP (0.6s).
    Assert:
    1. Observers report 0.0 rad/s during ALIGN (standstill).
    2. Full mode sequence is strictly ALIGN (0) -> OPEN_LOOP (1) -> CLOSED_LOOP (2) -> DEGRADED (3).
    3. Controller NEVER prematurely jumps to SAFE_STOP (5).
    """
    controller = FocController(PATHS['lib_path'])
    controller.init(MOTOR_PARAMS, CONTROLLER_PARAMS)
    controller.set_speed_ref(2000.0 * (2 * math.pi / 60) * MOTOR_PARAMS['P'])
    plant = PMSMModel(**MOTOR_PARAMS)

    dt_c = 1.0 / CONTROLLER_PARAMS['pwm_freq']
    dt_p = 1e-5
    sub_steps = int(dt_c / dt_p)

    modes = []
    align_omegas = []
    for k in range(int(1.5 / dt_c)):
        t = k * dt_c
        ia, ib, ic = plant.get_phase_currents()
        if t >= inject_time:
            ia += fault_amp
        out = controller.tick(ia, ib, ic, MOTOR_PARAMS['Vbus'])
        modes.append(out.control_mode)
        if t < 0.5:
            align_omegas.append(abs(out.omega_hat))
        va, vb, vc = duties_to_voltages(out.duty_a, out.duty_b, out.duty_c, MOTOR_PARAMS['Vbus'], ia, ib, ic)
        for _ in range(sub_steps):
            vd, vq = phase_to_dq(va, vb, vc, plant.theta_e)
            plant.step(vd, vq, 0.0, dt_p)

    seq = []
    for m in modes:
        if not seq or m != seq[-1]:
            seq.append(m)

    assert max(align_omegas) == 0.0, f"Observer must report 0.0 rad/s during ALIGN, got max {max(align_omegas)}"
    assert seq == [0, 1, 2, 3], (
        f"Fault of {fault_amp}A in {stage} failed mode sequence: expected [0, 1, 2, 3], got {seq}"
    )

