import numpy as np
import math

class PMSMModel:
    """
    Surface Permanent Magnet Synchronous Motor (SPMSM) model.
    Uses Runge-Kutta 4th order integration for stepping.
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
        
        # New Detailed Physics Parameters
        self.T_cog_mag = kwargs.get('T_cog_mag', 0.005) # Nm of cogging torque
        self.R_th = kwargs.get('R_th', 2.5)            # Thermal resistance K/W
        self.C_th = kwargs.get('C_th', 50.0)           # Thermal capacitance J/K
        self.alpha_cu = 0.00393                        # Copper temp coefficient
        self.T_amb = 25.0
        self.temp_c = 25.0                             # Internal winding temp
        self.Rs_scale = 1.0                            # Fault injection scale
        
        # State variables
        self.i_d = 0.0
        self.i_q = 0.0
        self.omega_m = 0.0
        self.theta_e = 0.0
        
    def reset(self):
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
        return self.omega_m * 60.0 / (2 * math.pi)

    def _derivatives(self, state, v_d, v_q, T_load):
        i_d, i_q, omega_m, theta_e, temp_c = state
        omega_e = self.P * omega_m
        
        # Thermal Drift of Resistance
        Rs_active = self.Rs_nom * (1.0 + self.alpha_cu * (temp_c - 25.0)) * self.Rs_scale
        
        di_d = (1.0 / self.Ls) * (v_d - Rs_active * i_d + omega_e * self.Ls * i_q)
        di_q = (1.0 / self.Ls) * (v_q - Rs_active * i_q - omega_e * self.Ls * i_d - omega_e * self.psi_f)
        
        # Electro-magnetic Torque + Cogging Torque (Harmonics)
        T_e = 1.5 * self.P * self.psi_f * i_q
        T_cog = self.T_cog_mag * math.sin(6.0 * theta_e)
        domega_m = (1.0 / self.J) * (T_e - T_load - T_cog - self.B * omega_m)
        dtheta_e = omega_e
        
        # Thermal Physics: P_loss heats up the motor, R_th dissipates to ambient
        P_loss = 1.5 * Rs_active * (i_d**2 + i_q**2)
        dTemp = (P_loss - (temp_c - self.T_amb) / self.R_th) / self.C_th
        
        return np.array([di_d, di_q, domega_m, dtheta_e, dTemp])

    def step(self, v_d: float, v_q: float, T_load: float, dt: float):
        state = np.array([self.i_d, self.i_q, self.omega_m, self.theta_e, self.temp_c])
        
        k1 = self._derivatives(state, v_d, v_q, T_load)
        k2 = self._derivatives(state + 0.5 * dt * k1, v_d, v_q, T_load)
        k3 = self._derivatives(state + 0.5 * dt * k2, v_d, v_q, T_load)
        k4 = self._derivatives(state + dt * k3, v_d, v_q, T_load)
        
        new_state = state + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)
        
        self.i_d = new_state[0]
        self.i_q = new_state[1]
        self.omega_m = new_state[2]
        self.theta_e = new_state[3] % (2 * math.pi)
        self.temp_c = new_state[4]
        self.Rs = self.Rs_nom * (1.0 + self.alpha_cu * (self.temp_c - 25.0)) * self.Rs_scale

    def get_phase_currents(self):
        # Inverse Park
        alpha = self.i_d * math.cos(self.theta_e) - self.i_q * math.sin(self.theta_e)
        beta = self.i_d * math.sin(self.theta_e) + self.i_q * math.cos(self.theta_e)
        
        # Inverse Clarke
        i_a = alpha
        i_b = -0.5 * alpha + (math.sqrt(3.0) / 2.0) * beta
        i_c = -0.5 * alpha - (math.sqrt(3.0) / 2.0) * beta
        
        return i_a, i_b, i_c

    def get_state(self) -> dict:
        return {
            'i_d': self.i_d,
            'i_q': self.i_q,
            'omega_m': self.omega_m,
            'theta_e': self.theta_e,
            'omega_e': self.omega_e,
            'T_e': 1.5 * self.P * self.psi_f * self.i_q
        }
