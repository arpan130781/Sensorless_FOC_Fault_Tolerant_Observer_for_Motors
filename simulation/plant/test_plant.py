import math
import pytest
import numpy as np
from simulation.plant.pmsm_model import PMSMModel
from simulation.plant.inverter_model import abc_to_alpha_beta, alpha_beta_to_dq, phase_to_dq, duties_to_voltages

@pytest.fixture
def motor():
    return PMSMModel(Rs=0.5, Ls=1.0e-3, psi_f=0.015, P=4, J=0.0001, B=0.001, Vbus=24.0)

def test_standstill(motor):
    motor.step(v_d=0.0, v_q=0.0, T_load=0.0, dt=1e-4)
    assert math.isclose(motor.omega_m, 0.0, abs_tol=1e-6)
    assert math.isclose(motor.i_q, 0.0, abs_tol=1e-6)

def test_acceleration(motor):
    motor.step(v_d=0.0, v_q=5.0, T_load=0.0, dt=1e-4)
    assert motor.omega_m > 0.0
    assert motor.i_q > 0.0

def test_steady_state(motor):
    for _ in range(20000):
        motor.step(v_d=0.0, v_q=5.0, T_load=0.0, dt=1e-4)
    speed_1 = motor.omega_m
    for _ in range(100):
        motor.step(v_d=0.0, v_q=5.0, T_load=0.0, dt=1e-4)
    speed_2 = motor.omega_m
    assert math.isclose(speed_1, speed_2, rel_tol=1e-2)

def test_transforms_known_angles():
    a, b, c = 1.0, -0.5, -0.5
    alpha, beta = abc_to_alpha_beta(a, b, c)
    assert math.isclose(alpha, 1.0, abs_tol=1e-6)
    assert math.isclose(beta, 0.0, abs_tol=1e-6)
    
    d, q = alpha_beta_to_dq(alpha, beta, 0.0)
    assert math.isclose(d, 1.0, abs_tol=1e-6)
    assert math.isclose(q, 0.0, abs_tol=1e-6)
    
    d, q = alpha_beta_to_dq(alpha, beta, math.pi/2)
    assert math.isclose(d, 0.0, abs_tol=1e-6)
    assert math.isclose(q, -1.0, abs_tol=1e-6)

def test_round_trip():
    theta = math.pi / 3
    i_d_orig, i_q_orig = 2.0, 3.0
    alpha = i_d_orig * math.cos(theta) - i_q_orig * math.sin(theta)
    beta = i_d_orig * math.sin(theta) + i_q_orig * math.cos(theta)
    i_a = alpha
    i_b = -0.5 * alpha + (math.sqrt(3.0) / 2.0) * beta
    i_c = -0.5 * alpha - (math.sqrt(3.0) / 2.0) * beta
    
    d_res, q_res = phase_to_dq(i_a, i_b, i_c, theta)
    assert math.isclose(i_d_orig, d_res, abs_tol=1e-6)
    assert math.isclose(i_q_orig, q_res, abs_tol=1e-6)
