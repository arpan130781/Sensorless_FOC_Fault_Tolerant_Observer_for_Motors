import os

MOTOR_PARAMS = {
    'Rs': 0.5,
    'Ls': 1.0e-3,
    'psi_f': 0.015,
    'P': 4,
    'J': 0.0001,
    'B': 0.001,
    'Vbus': 24.0,
    'In': 5.0
}

CONTROLLER_PARAMS = {
    'id_kp': 6.28,
    'id_ki': 3142.0,
    'iq_kp': 6.28,
    'iq_ki': 3142.0,
    'spd_kp': 0.194,
    'spd_ki': 17.4,
    'smo_k': 20.0,
    'smo_h': 0.5,
    'smo_lpf': 50.0,
    'flux_wc': 125.6,
    'observer_select': 0,
    'pwm_freq': 20000.0,
    'ctrl_rate_curr': 20000.0,
    'ctrl_rate_spd': 1000.0
}

SIM_PARAMS = {
    'dt_control': 1 / 20000.0,
    'dt_plant': 1 / 100000.0,
    'total_time': 3.0,
    'speed_ref_rpm': 2000.0
}

PATHS = {
    'lib_path': os.path.join(os.path.dirname(__file__), '..', '..', 'build', 'libfoc_controller.so'),
    'faults_yaml': os.path.join(os.path.dirname(__file__), '..', 'fault_injection', 'fault_scenarios.yaml')
}
