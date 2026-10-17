
import ctypes
import os
import sys

class FocInput(ctypes.Structure):
    _fields_ = [
        ("i_a", ctypes.c_float),
        ("i_b", ctypes.c_float),
        ("i_c", ctypes.c_float),
        ("v_bus", ctypes.c_float)
    ]

class FocOutput(ctypes.Structure):
    _fields_ = [
        ("duty_a", ctypes.c_float),
        ("duty_b", ctypes.c_float),
        ("duty_c", ctypes.c_float),
        ("gate_enable", ctypes.c_bool),
        ("theta_hat", ctypes.c_float),
        ("omega_hat", ctypes.c_float),
        ("health_score", ctypes.c_float),
        ("control_mode", ctypes.c_int),
        ("i_d", ctypes.c_float),
        ("i_q", ctypes.c_float),
        ("emf_alpha", ctypes.c_float),
        ("emf_beta", ctypes.c_float),
        ("theta_hat_smo", ctypes.c_float),
        ("theta_hat_flux", ctypes.c_float),
        ("fault_channel", ctypes.c_int),
        ("i_a_rec", ctypes.c_float),
        ("i_b_rec", ctypes.c_float),
        ("i_c_rec", ctypes.c_float),
        ("smo_health", ctypes.c_float),
        ("flux_health", ctypes.c_float),
        ("observer_disagreement", ctypes.c_float),
        ("emf_mag", ctypes.c_float),
        ("confidence_smo", ctypes.c_float),
        ("confidence_flux", ctypes.c_float)
    ]

class MotorParams(ctypes.Structure):
    _fields_ = [
        ("Rs", ctypes.c_float),
        ("Ls", ctypes.c_float),
        ("psi_f", ctypes.c_float),
        ("P", ctypes.c_int),
        ("J", ctypes.c_float),
        ("B", ctypes.c_float),
        ("Vbus", ctypes.c_float),
        ("In", ctypes.c_float)
    ]

class ControllerParams(ctypes.Structure):
    _fields_ = [
        ("id_kp", ctypes.c_float), ("id_ki", ctypes.c_float),
        ("iq_kp", ctypes.c_float), ("iq_ki", ctypes.c_float),
        ("spd_kp", ctypes.c_float), ("spd_ki", ctypes.c_float),
        ("smo_k", ctypes.c_float), ("smo_h", ctypes.c_float), ("smo_lpf", ctypes.c_float),
        ("flux_wc", ctypes.c_float),
        ("observer_select", ctypes.c_int),
        ("pwm_freq", ctypes.c_float),
        ("ctrl_rate_curr", ctypes.c_float),
        ("ctrl_rate_spd", ctypes.c_float)
    ]

class FocController:
    def __init__(self, lib_path):
        if not os.path.exists(lib_path):
            raise FileNotFoundError(f"CRITICAL: C library not found at {lib_path}. Run 'make lib' first.")
        
        self.lib = ctypes.CDLL(lib_path)
        
        self.lib.foc_init.argtypes = [ctypes.POINTER(MotorParams), ctypes.POINTER(ControllerParams)]
        self.lib.foc_tick.argtypes = [ctypes.POINTER(FocInput)]
        self.lib.foc_tick.restype = FocOutput
        self.lib.foc_reset.argtypes = []
        self.lib.foc_set_speed_ref.argtypes = [ctypes.c_float]
        self.lib.foc_set_torque_ref.argtypes = [ctypes.c_float]
        
    def init(self, motor_dict, ctrl_dict):
        m = MotorParams(**motor_dict)
        c = ControllerParams(**ctrl_dict)
        self.lib.foc_init(ctypes.byref(m), ctypes.byref(c))
        
    def tick(self, i_a, i_b, i_c, v_bus):
        inp = FocInput(i_a, i_b, i_c, v_bus)
        return self.lib.foc_tick(ctypes.byref(inp))
        
    def reset(self):
        self.lib.foc_reset()
        
    def set_speed_ref(self, omega_ref):
        self.lib.foc_set_speed_ref(omega_ref)
        
    def set_torque_ref(self, iq_ref):
        self.lib.foc_set_torque_ref(iq_ref)
