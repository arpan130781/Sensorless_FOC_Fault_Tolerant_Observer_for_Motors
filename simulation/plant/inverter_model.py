import math

def abc_to_alpha_beta(a: float, b: float, c: float):
    alpha = (2.0 / 3.0) * (a - 0.5 * b - 0.5 * c)
    beta = (2.0 / 3.0) * (math.sqrt(3.0) / 2.0 * (b - c))
    return alpha, beta

def alpha_beta_to_dq(alpha: float, beta: float, theta: float):
    d = alpha * math.cos(theta) + beta * math.sin(theta)
    q = -alpha * math.sin(theta) + beta * math.cos(theta)
    return d, q

def phase_to_dq(v_a: float, v_b: float, v_c: float, theta_e: float):
    alpha, beta = abc_to_alpha_beta(v_a, v_b, v_c)
    return alpha_beta_to_dq(alpha, beta, theta_e)

def duties_to_voltages(duty_a: float, duty_b: float, duty_c: float, v_bus: float, i_a: float = 0.0, i_b: float = 0.0, i_c: float = 0.0, v_dead: float = 0.5):
    """ Converts PWM duty cycles [0, 1] to phase voltages relative to neutral. Includes dead-time distortion. """
    import numpy as np
    duty_a = float(np.clip(duty_a, 0.0, 1.0))
    duty_b = float(np.clip(duty_b, 0.0, 1.0))
    duty_c = float(np.clip(duty_c, 0.0, 1.0))
    # Apply dead-time voltage drop based on current polarity
    v_a_gnd = duty_a * v_bus - np.sign(i_a) * v_dead
    v_b_gnd = duty_b * v_bus - np.sign(i_b) * v_dead
    v_c_gnd = duty_c * v_bus - np.sign(i_c) * v_dead
    
    v_neutral = (v_a_gnd + v_b_gnd + v_c_gnd) / 3.0
    
    v_a = v_a_gnd - v_neutral
    v_b = v_b_gnd - v_neutral
    v_c = v_c_gnd - v_neutral
    return v_a, v_b, v_c
