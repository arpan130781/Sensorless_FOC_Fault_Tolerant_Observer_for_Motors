import os
import sys
import re

# ============================================================================
# SINGLE SOURCE OF TRUTH: Load from src/motor_params.h
# ============================================================================
_header_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'motor_params.h'))

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

# Explicit SIL simulation dead-time (compensating the simulator's 0.5 V plant distortion: 0.5 / (20000 * 24) = 1.0416667e-6 s)
SIM_DEAD_TIME = 1.0416667e-6

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
    'ctrl_rate_spd': 1000.0,
    'dead_time': SIM_DEAD_TIME
}

if os.path.exists(_header_path):
    with open(_header_path, 'r') as _f:
        _content = _f.read()
    _defines = dict(re.findall(r'#define\s+([A-Za-z0-9_]+)\s+([^\s/]+)', _content))
    if 'MOTOR_PARAM_RS' in _defines:
        MOTOR_PARAMS['Rs'] = float(_defines['MOTOR_PARAM_RS'].rstrip('f'))
        MOTOR_PARAMS['Ls'] = float(_defines['MOTOR_PARAM_LS'].rstrip('f'))
        MOTOR_PARAMS['psi_f'] = float(_defines['MOTOR_PARAM_PSI_F'].rstrip('f'))
        MOTOR_PARAMS['P'] = int(_defines['MOTOR_PARAM_POLE_PAIRS'])
        MOTOR_PARAMS['J'] = float(_defines['MOTOR_PARAM_J'].rstrip('f'))
        MOTOR_PARAMS['B'] = float(_defines['MOTOR_PARAM_B'].rstrip('f'))
        MOTOR_PARAMS['Vbus'] = float(_defines['MOTOR_PARAM_VBUS'].rstrip('f'))
        MOTOR_PARAMS['In'] = float(_defines['MOTOR_PARAM_IN'].rstrip('f'))

    if 'CTRL_PARAM_ID_KP' in _defines:
        CONTROLLER_PARAMS['id_kp'] = float(_defines['CTRL_PARAM_ID_KP'].rstrip('f'))
        CONTROLLER_PARAMS['id_ki'] = float(_defines['CTRL_PARAM_ID_KI'].rstrip('f'))
        CONTROLLER_PARAMS['iq_kp'] = float(_defines['CTRL_PARAM_IQ_KP'].rstrip('f'))
        CONTROLLER_PARAMS['iq_ki'] = float(_defines['CTRL_PARAM_IQ_KI'].rstrip('f'))
        CONTROLLER_PARAMS['spd_kp'] = float(_defines['CTRL_PARAM_SPD_KP'].rstrip('f'))
        CONTROLLER_PARAMS['spd_ki'] = float(_defines['CTRL_PARAM_SPD_KI'].rstrip('f'))
        CONTROLLER_PARAMS['smo_k'] = float(_defines['CTRL_PARAM_SMO_K'].rstrip('f'))
        CONTROLLER_PARAMS['smo_h'] = float(_defines['CTRL_PARAM_SMO_H'].rstrip('f'))
        CONTROLLER_PARAMS['smo_lpf'] = float(_defines['CTRL_PARAM_SMO_LPF'].rstrip('f'))
        CONTROLLER_PARAMS['flux_wc'] = float(_defines['CTRL_PARAM_FLUX_WC'].rstrip('f'))
        CONTROLLER_PARAMS['observer_select'] = int(_defines['CTRL_PARAM_OBS_SELECT'])
        CONTROLLER_PARAMS['pwm_freq'] = float(_defines['CTRL_PARAM_PWM_FREQ'].rstrip('f'))
        CONTROLLER_PARAMS['ctrl_rate_curr'] = float(_defines['CTRL_PARAM_CTRL_CURR'].rstrip('f'))
        CONTROLLER_PARAMS['ctrl_rate_spd'] = float(_defines['CTRL_PARAM_CTRL_SPD'].rstrip('f'))
    if 'CTRL_PARAM_DEAD_TIME' in _defines:
        # Note: Do NOT overwrite SIL simulation dead-time with the uncommissioned firmware default (0.0).
        # SIL simulation explicitly uses SIM_DEAD_TIME to match the simulated 0.5V inverter plant.
        pass

SIM_PARAMS = {
    'dt_control': 1.0 / CONTROLLER_PARAMS['pwm_freq'],
    'dt_plant': 1.0 / 100000.0,
    'total_time': 3.0,
    'speed_ref_rpm': 2000.0
}

_build_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'build'))
_lib_ext = 'dylib' if sys.platform == 'darwin' else 'so'
_lib_path = os.path.join(_build_dir, f'libfoc_controller.{_lib_ext}')
if not os.path.exists(_lib_path):
    _alt_ext = 'so' if _lib_ext == 'dylib' else 'dylib'
    _alt_path = os.path.join(_build_dir, f'libfoc_controller.{_alt_ext}')
    if os.path.exists(_alt_path):
        _lib_path = _alt_path

PATHS = {
    'lib_path': _lib_path,
    'faults_yaml': os.path.join(os.path.dirname(__file__), '..', 'fault_injection', 'fault_scenarios.yaml')
}
