"""
Brushless DC (BLDC) Motor Plant Model with 120-degree trapezoidal back-EMF.
Includes 4th-order Runge-Kutta integration, phase coordinate dynamics,
thermal drift, cogging torque, and strict Kirchoff's Current Law (KCL) conservation.
"""
import math
import numpy as np


def trapezoid_shape(theta: float) -> float:
    """
    Standard normalized 120-degree flat-top trapezoidal waveform, period 2*pi.
    Peak = +1.0 for [pi/6, 5*pi/6] (120 deg flat top)
    Ramp down from +1 to -1 for [5*pi/6, 7*pi/6] (60 deg transition)
    Flat bottom = -1.0 for [7*pi/6, 11*pi/6] (120 deg flat bottom)
    Ramp up from -1 to +1 for [11*pi/6, 13*pi/6] (60 deg transition)
    """
    th = theta % (2.0 * math.pi)
    if th < math.pi / 6.0:
        return (6.0 / math.pi) * th
    elif th < 5.0 * math.pi / 6.0:
        return 1.0
    elif th < 7.0 * math.pi / 6.0:
        return 1.0 - (6.0 / math.pi) * (th - 5.0 * math.pi / 6.0)
    elif th < 11.0 * math.pi / 6.0:
        return -1.0
    else:
        return -1.0 + (6.0 / math.pi) * (th - 11.0 * math.pi / 6.0)


class BLDCModel:
    """
    3-Phase Brushless DC (BLDC) Motor model with trapezoidal back-EMF.
    Solves electrical differential equations in phase coordinates (ia, ib, ic)
    with isolated star neutral point and mechanical dynamics.
    """
    def __init__(self, Rs: float, Ls: float, psi_f: float, P: int, J: float, B: float, Vbus: float, **kwargs):
        self.Rs_nom = Rs
        self.Rs = Rs
        self.Ls = Ls
        self.psi_f = psi_f
        self.P = P
        self.J = J
        self.B = B
        self.Vbus = Vbus

        # Physical & Thermal Parameters
        self.T_cog_mag = kwargs.get('T_cog_mag', 0.005) # Nm cogging torque amplitude
        self.R_th = kwargs.get('R_th', 2.5)             # Thermal resistance K/W
        self.C_th = kwargs.get('C_th', 50.0)            # Thermal capacitance J/K
        self.alpha_cu = 0.00393                         # Copper temperature coefficient
        self.T_amb = 25.0
        self.temp_c = 25.0
        self.Rs_scale = 1.0

        # Phase currents
        self.i_a = 0.0
        self.i_b = 0.0
        self.i_c = 0.0

        # Equivalent dq currents (derived via Clarke & Park)
        self.i_d = 0.0
        self.i_q = 0.0

        # Mechanical state
        self.omega_m = 0.0
        self.theta_e = 0.0

    def reset(self):
        self.i_a = 0.0
        self.i_b = 0.0
        self.i_c = 0.0
        self.i_d = 0.0
        self.i_q = 0.0
        self.omega_m = 0.0
        self.theta_e = 0.0
        self.temp_c = 25.0
        self.Rs_scale = 1.0
        self.Rs = self.Rs_nom

    @property
    def omega_e(self) -> float:
        return self.P * self.omega_m

    @property
    def speed_rpm(self) -> float:
        return self.omega_m * 60.0 / (2.0 * math.pi)

    def back_emf(self, theta_e: float, omega_e: float):
        """Returns back-EMF voltages (e_a, e_b, e_c) for given angle and speed."""
        # Align with FOC convention where fundamental EMF opposes rotation along -sin(theta)
        fa = -trapezoid_shape(theta_e)
        fb = -trapezoid_shape(theta_e - 2.0 * math.pi / 3.0)
        fc = -trapezoid_shape(theta_e + 2.0 * math.pi / 3.0)
        ea = self.psi_f * omega_e * fa
        eb = self.psi_f * omega_e * fb
        ec = self.psi_f * omega_e * fc
        return ea, eb, ec, fa, fb, fc

    def _derivatives(self, state, v_a, v_b, v_c, T_load):
        i_a, i_b, i_c, omega_m, theta_e, temp_c = state
        omega_e = self.P * omega_m

        Rs_active = self.Rs_nom * (1.0 + self.alpha_cu * (temp_c - 25.0)) * self.Rs_scale

        ea, eb, ec, fa, fb, fc = self.back_emf(theta_e, omega_e)

        # Isolated star neutral voltage:
        # Summing (v_k - e_k - v_n = Rs*i_k + Ls*di_k/dt) under sum(i_k) = 0
        v_n = ((v_a + v_b + v_c) - (ea + eb + ec)) / 3.0

        # Phase current derivatives
        di_a = (1.0 / self.Ls) * (v_a - ea - v_n - Rs_active * i_a)
        di_b = (1.0 / self.Ls) * (v_b - eb - v_n - Rs_active * i_b)
        di_c = (1.0 / self.Ls) * (v_c - ec - v_n - Rs_active * i_c)

        # Electromagnetic Torque: Te = P * psi_f * (fa*ia + fb*ib + fc*ic)
        T_e = self.P * self.psi_f * (fa * i_a + fb * i_b + fc * i_c)
        T_cog = self.T_cog_mag * math.sin(6.0 * theta_e)
        domega_m = (1.0 / self.J) * (T_e - T_load - T_cog - self.B * omega_m)
        dtheta_e = omega_e

        # Thermal dissipation
        P_loss = Rs_active * (i_a**2 + i_b**2 + i_c**2)
        dTemp = (P_loss - (temp_c - self.T_amb) / self.R_th) / self.C_th

        return np.array([di_a, di_b, di_c, domega_m, dtheta_e, dTemp])

    def step(self, v_d: float, v_q: float, T_load: float, dt: float):
        """
        Step the motor using dq voltages (from FOC controller).
        Converts dq voltages to abc terminal voltages, integrates with RK4,
        and projects phase currents to dq for telemetry.
        """
        # Inverse Park
        c = math.cos(self.theta_e)
        s = math.sin(self.theta_e)
        v_alpha = v_d * c - v_q * s
        v_beta  = v_d * s + v_q * c

        # Inverse Clarke
        v_a = v_alpha
        v_b = -0.5 * v_alpha + (math.sqrt(3.0) / 2.0) * v_beta
        v_c = -0.5 * v_alpha - (math.sqrt(3.0) / 2.0) * v_beta

        self.step_phase(v_a, v_b, v_c, T_load, dt)

    def step_phase(self, v_a: float, v_b: float, v_c: float, T_load: float, dt: float):
        """Step the BLDC model using direct phase voltages."""
        state = np.array([self.i_a, self.i_b, self.i_c, self.omega_m, self.theta_e, self.temp_c])

        k1 = self._derivatives(state, v_a, v_b, v_c, T_load)
        k2 = self._derivatives(state + 0.5 * dt * k1, v_a, v_b, v_c, T_load)
        k3 = self._derivatives(state + 0.5 * dt * k2, v_a, v_b, v_c, T_load)
        k4 = self._derivatives(state + dt * k3, v_a, v_b, v_c, T_load)

        new_state = state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

        self.i_a = new_state[0]
        self.i_b = new_state[1]
        self.i_c = new_state[2]
        self.omega_m = new_state[3]
        self.theta_e = new_state[4] % (2.0 * math.pi)
        self.temp_c = new_state[5]
        self.Rs = self.Rs_nom * (1.0 + self.alpha_cu * (self.temp_c - 25.0)) * self.Rs_scale

        # Enforce strict floating star KCL: ia + ib + ic = 0
        residual = (self.i_a + self.i_b + self.i_c) / 3.0
        self.i_a -= residual
        self.i_b -= residual
        self.i_c -= residual

        # Update dq currents
        c = math.cos(self.theta_e)
        s = math.sin(self.theta_e)
        alpha = (2.0 / 3.0) * (self.i_a - 0.5 * self.i_b - 0.5 * self.i_c)
        beta  = 0.5773502691896258 * (self.i_b - self.i_c)
        self.i_d =  alpha * c + beta * s
        self.i_q = -alpha * s + beta * c

    def get_phase_currents(self):
        return self.i_a, self.i_b, self.i_c

    def get_state(self) -> dict:
        ea, eb, ec, fa, fb, fc = self.back_emf(self.theta_e, self.omega_e)
        t_e = self.P * self.psi_f * (fa * self.i_a + fb * self.i_b + fc * self.i_c)
        return {
            'i_a': self.i_a,
            'i_b': self.i_b,
            'i_c': self.i_c,
            'i_d': self.i_d,
            'i_q': self.i_q,
            'omega_m': self.omega_m,
            'theta_e': self.theta_e,
            'omega_e': self.omega_e,
            'T_e': t_e
        }
