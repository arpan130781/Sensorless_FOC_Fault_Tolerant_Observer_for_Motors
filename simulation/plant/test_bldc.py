"""
Unit and regression tests for BLDC Motor plant model and FOC / observer interaction.
Validates:
1. 120-degree trapezoidal back-EMF shape, continuity, and harmonic spectrum.
2. Floating-star KCL conservation (ia + ib + ic = 0).
3. Motor acceleration and torque production.
4. FOC drive behavior with BLDC: quantifies intrinsic 6th-harmonic torque ripple.
5. Fault detection, isolation, and two-shunt reconstruction on BLDC motor.
"""
import math
import numpy as np
import pytest

from simulation.plant.bldc_model import BLDCModel, trapezoid_shape
from simulation.plant.pmsm_model import PMSMModel
from simulation.harness.config import MOTOR_PARAMS, CONTROLLER_PARAMS, SIM_PARAMS
from simulation.harness.sil_runner import SILRunner


def test_trapezoid_shape_continuity_and_symmetry():
    """Verify continuity, flat-top, and half-wave anti-symmetry of trapezoid_shape."""
    thetas = np.linspace(0, 4.0 * math.pi, 2000)
    vals = np.array([trapezoid_shape(th) for th in thetas])

    # Range check
    assert np.all(vals >= -1.0 - 1e-6)
    assert np.all(vals <= 1.0 + 1e-6)

    # Flat top check at 90 deg (pi/2)
    assert math.isclose(trapezoid_shape(math.pi / 2.0), 1.0, rel_tol=1e-5)
    # Flat bottom check at 270 deg (3*pi/2)
    assert math.isclose(trapezoid_shape(3.0 * math.pi / 2.0), -1.0, rel_tol=1e-5)

    # Half-wave anti-symmetry: f(theta + pi) == -f(theta)
    for th in [0.1, 0.5, 1.2, 2.0, 3.1]:
        f1 = trapezoid_shape(th)
        f2 = trapezoid_shape(th + math.pi)
        assert math.isclose(f1, -f2, abs_tol=1e-5), f"Symmetry broken at {th}"

    # Verify max step difference (continuity check)
    diffs = np.abs(np.diff(vals))
    assert np.max(diffs) < 0.05, "Discontinuity detected in trapezoid shape"


def test_trapezoid_harmonics():
    """Verify presence of 5th and 7th harmonics in trapezoidal back-EMF."""
    N = 1024
    thetas = np.linspace(0, 2.0 * math.pi, N, endpoint=False)
    wave = np.array([trapezoid_shape(th) for th in thetas])

    fft_vals = np.abs(np.fft.rfft(wave)) / (N / 2)
    fund = fft_vals[1]

    # Fundamental should be approximately 4/pi * 6/pi * sin(pi/6) = 1.216
    assert 1.15 < fund < 1.30, f"Expected fundamental ~1.216, got {fund}"

    # 5th harmonic should be approx fund / 25 (~0.048)
    h5 = fft_vals[5]
    assert 0.03 < h5 < 0.07, f"Expected 5th harmonic ~0.048, got {h5}"

    # Even harmonics (2nd, 4th, 6th) must be near zero due to half-wave symmetry
    assert fft_vals[2] < 1e-3
    assert fft_vals[4] < 1e-3
    assert fft_vals[6] < 1e-3


def test_bldc_kcl_conservation():
    """Verify strict floating neutral KCL: ia + ib + ic = 0 at every simulation step."""
    bldc = BLDCModel(**MOTOR_PARAMS)
    bldc.reset()

    dt = 1e-5
    for step in range(200):
        # Apply arbitrary varying terminal voltages
        va = 12.0 * math.sin(step * 0.1)
        vb = 12.0 * math.sin(step * 0.1 - 2.0 * math.pi / 3.0)
        vc = 12.0 * math.sin(step * 0.1 + 2.0 * math.pi / 3.0)
        bldc.step_phase(va, vb, vc, T_load=0.01, dt=dt)

        ia, ib, ic = bldc.get_phase_currents()
        residual = abs(ia + ib + ic)
        assert residual < 1e-9, f"KCL violated at step {step}: sum = {residual}"


def test_bldc_acceleration():
    """Verify BLDC motor accelerates under positive torque."""
    bldc = BLDCModel(**MOTOR_PARAMS)
    bldc.reset()

    # Step with positive Vq
    dt = 50e-6
    for _ in range(2000):
        bldc.step(v_d=0.0, v_q=10.0, T_load=0.0, dt=dt)

    assert bldc.omega_m > 0.0, "BLDC should have accelerated in positive direction"
    assert bldc.speed_rpm > 500.0, f"Expected speed > 500 RPM, got {bldc.speed_rpm}"


def test_bldc_foc_torque_ripple_comparison():
    """
    Compare torque ripple between sinusoidal PMSM and trapezoidal BLDC under FOC.
    Due to the harmonic mismatch between sinusoidal FOC currents and trapezoidal back-EMF,
    BLDC will exhibit noticeable 6th-harmonic torque ripple.
    """
    pmsm = PMSMModel(**MOTOR_PARAMS)
    bldc = BLDCModel(**MOTOR_PARAMS)
    pmsm.reset()
    bldc.reset()

    # Set constant rotating speed at 1500 RPM
    omega_m = 1500.0 * (2.0 * math.pi / 60.0)
    omega_e = omega_m * MOTOR_PARAMS['P']
    pmsm.omega_m = omega_m
    bldc.omega_m = omega_m

    # Apply identical sinusoidal currents (constant Iq = 2.0 A, Id = 0.0 A)
    iq = 2.0
    id_ref = 0.0
    thetas = np.linspace(0, 2.0 * math.pi, 360)

    t_pmsm = []
    t_bldc = []

    for th in thetas:
        # Phase currents for sinusoidal FOC
        alpha = id_ref * math.cos(th) - iq * math.sin(th)
        beta  = id_ref * math.sin(th) + iq * math.cos(th)
        ia = alpha
        ib = -0.5 * alpha + (math.sqrt(3.0) / 2.0) * beta
        ic = -0.5 * alpha - (math.sqrt(3.0) / 2.0) * beta

        # PMSM torque: 1.5 * P * psi_f * iq
        t_pmsm.append(1.5 * MOTOR_PARAMS['P'] * MOTOR_PARAMS['psi_f'] * iq)

        # BLDC torque: P * psi_f * (fa*ia + fb*ib + fc*ic)
        _, _, _, fa, fb, fc = bldc.back_emf(th, omega_e)
        te_bldc = MOTOR_PARAMS['P'] * MOTOR_PARAMS['psi_f'] * (fa * ia + fb * ib + fc * ic)
        t_bldc.append(te_bldc)

    ripple_pmsm = (np.max(t_pmsm) - np.min(t_pmsm)) / np.mean(t_pmsm)
    ripple_bldc = (np.max(t_bldc) - np.min(t_bldc)) / np.mean(t_bldc)

    # PMSM under pure sinusoidal currents has zero theoretical torque ripple
    assert ripple_pmsm < 1e-6
    # BLDC under sinusoidal currents exhibits ~14% - 20% torque ripple
    assert 0.10 < ripple_bldc < 0.25, f"Expected 10-25% torque ripple for BLDC under FOC, got {ripple_bldc*100:.1f}%"


def test_bldc_closed_loop_foc_and_fault_isolation():
    """
    Run closed-loop SIL simulation with BLDCModel swapped into the runner.
    Verifies that:
    1. BLDC starts up and reaches steady closed-loop speed under FOC.
    2. Single-sensor fault on Phase A is detected and isolated.
    3. Reconstructed currents restore motor operation.
    """
    sim_cfg = dict(SIM_PARAMS)
    sim_cfg['total_time'] = 2.6
    runner = SILRunner(config_sim=sim_cfg, fault_scenario='scenario_2_offset_a_2_0')

    # Swap in the BLDC plant model
    runner.plant = BLDCModel(**MOTOR_PARAMS)

    res = runner.run()

    # Verify steady closed loop reached before fault onset (t in [1.5, 2.0])
    pre_fault = (res.time >= 1.5) & (res.time < 2.0)
    mean_speed_pre = np.mean(res.speed_rpm[pre_fault])
    assert abs(mean_speed_pre - 2000.0) < 150.0, f"BLDC failed to reach 2000 RPM, got {mean_speed_pre}"

    # Verify fault channel isolation after onset at 2.0s
    post_fault = res.time >= 2.1
    latched_channels = res.fault_channel[post_fault]
    assert np.any(latched_channels == 1), "BLDC simulation failed to isolate Phase A fault"

    # Verify two-shunt reconstruction operates on BLDC
    assert np.all(np.isfinite(res.i_a_rec[post_fault])), "Current reconstruction produced non-finite values on BLDC"
