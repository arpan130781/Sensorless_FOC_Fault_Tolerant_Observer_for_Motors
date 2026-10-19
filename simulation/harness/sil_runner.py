import argparse
import numpy as np
import math
from dataclasses import dataclass
import yaml
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from simulation.plant.pmsm_model import PMSMModel
from simulation.plant.inverter_model import duties_to_voltages, phase_to_dq
from simulation.plant.sensor_model import SensorModel
from simulation.fault_injection.fault_injector import FaultInjector, NullFaultInjector
from simulation.harness.config import MOTOR_PARAMS, CONTROLLER_PARAMS, SIM_PARAMS, PATHS
from simulation.harness.c_bridge import FocController
from simulation.analysis.metrics import evaluate_scenario

def get_scenario_evaluation_start_time(sc_conf):
    """
    Returns the evaluation start time for a given scenario:
    scores each scenario from its own fault_onset_time or load/reversal onset.
    """
    if not sc_conf:
        return 2.0
    exp = sc_conf.get('expected_outcome', {})
    if 'fault_onset_time' in exp and exp['fault_onset_time'] < float('inf'):
        return float(exp['fault_onset_time'])
    if 'load_step' in sc_conf:
        return float(sc_conf['load_step'].get('onset_time', 1.5))
    if 'speed_reversal' in sc_conf:
        return float(sc_conf['speed_reversal'].get('onset_time', 2.0))
    return 2.0

@dataclass
class SimulationResult:
    time: np.ndarray
    theta_true: np.ndarray
    theta_hat_smo: np.ndarray
    theta_hat_flux: np.ndarray
    theta_hat: np.ndarray
    omega_true: np.ndarray
    omega_hat: np.ndarray
    i_a: np.ndarray
    i_b: np.ndarray
    i_c: np.ndarray
    i_true_a: np.ndarray
    i_true_b: np.ndarray
    i_true_c: np.ndarray
    i_d: np.ndarray
    i_q: np.ndarray
    duty_a: np.ndarray
    duty_b: np.ndarray
    duty_c: np.ndarray
    health_score: np.ndarray
    control_mode: np.ndarray
    angle_error: np.ndarray
    speed_rpm: np.ndarray
    # new fields
    fault_channel: np.ndarray
    i_a_rec: np.ndarray
    i_b_rec: np.ndarray
    i_c_rec: np.ndarray
    smo_health: np.ndarray
    flux_health: np.ndarray
    observer_disagreement: np.ndarray
    emf_mag: np.ndarray
    confidence_smo: np.ndarray
    confidence_flux: np.ndarray

class SILRunner:
    def __init__(self, config_sim, fault_scenario=None, sensor_model=None, v_dead_plant=None, custom_ctrl_params=None):
        self.config = config_sim
        self.scenario_name = fault_scenario
        self.sensor_model = sensor_model
        self.custom_ctrl_params = custom_ctrl_params
        if v_dead_plant is not None:
            self.v_dead_plant = float(v_dead_plant)
        elif config_sim and 'v_dead_plant' in config_sim:
            self.v_dead_plant = float(config_sim['v_dead_plant'])
        else:
            self.v_dead_plant = 0.5
        
        lib_path = PATHS['lib_path']
        if not os.path.exists(lib_path):
            lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'build', 'libfoc_controller.so')
            if not os.path.exists(lib_path):
                lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'build', 'libfoc_controller.dylib')

        self.controller = FocController(lib_path)
        self.plant = PMSMModel(**MOTOR_PARAMS)
        
        self.scenario_config = None
        if fault_scenario and fault_scenario != 'no_fault_baseline':
            yaml_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fault_injection', 'fault_scenarios.yaml')
            with open(yaml_path, 'r') as f:
                scenarios = yaml.safe_load(f)
            if fault_scenario not in scenarios:
                raise ValueError(f"Scenario {fault_scenario} not found in YAML.")
            self.scenario_config = scenarios[fault_scenario]
            self.injector = FaultInjector(self.scenario_config)
        else:
            self.injector = NullFaultInjector()
            
    def run(self):
        ctrl_p = self.custom_ctrl_params if self.custom_ctrl_params is not None else CONTROLLER_PARAMS
        self.controller.init(MOTOR_PARAMS, ctrl_p)
        speed_ref = self.config['speed_ref_rpm']
        if self.scenario_config and 'speed_ref_rpm' in self.scenario_config:
            speed_ref = self.scenario_config['speed_ref_rpm']
        self.controller.set_speed_ref(speed_ref * (2*math.pi/60) * MOTOR_PARAMS['P'])
        self.plant.reset()
        
        dt_c = self.config['dt_control']
        dt_p = self.config['dt_plant']
        steps = int(self.config['total_time'] / dt_c)
        sub_steps = int(dt_c / dt_p)
        
        N = steps
        res = SimulationResult(
            time = np.zeros(N), theta_true = np.zeros(N), theta_hat_smo = np.zeros(N),
            theta_hat_flux = np.zeros(N), theta_hat = np.zeros(N), omega_true = np.zeros(N),
            omega_hat = np.zeros(N), i_a = np.zeros(N), i_b = np.zeros(N), i_c = np.zeros(N), i_true_a = np.zeros(N), i_true_b = np.zeros(N), i_true_c = np.zeros(N),
            i_d = np.zeros(N), i_q = np.zeros(N), duty_a = np.zeros(N), duty_b = np.zeros(N),
            duty_c = np.zeros(N), health_score = np.zeros(N), control_mode = np.zeros(N),
            angle_error = np.zeros(N), speed_rpm = np.zeros(N), fault_channel = np.zeros(N),
            i_a_rec = np.zeros(N), i_b_rec = np.zeros(N), i_c_rec = np.zeros(N),
            smo_health = np.zeros(N), flux_health = np.zeros(N), observer_disagreement = np.zeros(N),
            emf_mag = np.zeros(N), confidence_smo = np.zeros(N), confidence_flux = np.zeros(N)
        )
        
        for k in range(steps):
            t = k * dt_c
            
            p_state = self.plant.get_state()
            ia, ib, ic = self.plant.get_phase_currents()
            
            # Param drift
            self.plant.Rs_scale = self.injector.get_rs_scale(t)   # plant derives Rs from Rs_nom, temperature and Rs_scale
            self.plant.Ls = MOTOR_PARAMS['Ls'] * self.injector.get_ls_scale(t)
            
            if self.sensor_model is not None:
                ia, ib, ic = self.sensor_model.measure_phases(ia, ib, ic)

            ia_corr, ib_corr, ic_corr = self.injector.corrupt_currents(ia, ib, ic, t)
            vbus = self.injector.corrupt_vbus(MOTOR_PARAMS['Vbus'], t)
            
            # Controller
            out = self.controller.tick(ia_corr, ib_corr, ic_corr, vbus)
            
            gate_en = getattr(out, 'gate_enable', True)
            if not gate_en:
                # High-impedance mode: all inverter switches OFF.
                # Body diodes conduct only when line-to-line back-EMF exceeds DC bus (rectification)
                # or while rapidly quenching existing inductor energy. Otherwise, phase currents are zero.
                omega_e = self.plant.omega_e
                e_ll_pk = math.sqrt(3.0) * self.plant.psi_f * abs(omega_e)
                if e_ll_pk > vbus:
                    # Diode bridge rectifies into bus, clamping terminal voltage opposing rotation
                    vd = 0.0
                    vq = -math.copysign(vbus / math.sqrt(3.0), omega_e)
                else:
                    # Open-circuit back-EMF terminal voltages for logging
                    th = self.plant.theta_e
                    va = -self.plant.psi_f * omega_e * math.sin(th)
                    vb = -self.plant.psi_f * omega_e * math.sin(th - 2.0 * math.pi / 3.0)
                    vc = -self.plant.psi_f * omega_e * math.sin(th + 2.0 * math.pi / 3.0)
            else:
                va, vb, vc = duties_to_voltages(out.duty_a, out.duty_b, out.duty_c, vbus, ia, ib, ic, v_dead=self.v_dead_plant)  # true currents -> dead-time polarity
            
            load = 0.0
            if self.scenario_config and 'load_step' in self.scenario_config:
                if t >= self.scenario_config['load_step']['onset_time']:
                    load = self.scenario_config['load_step']['torque_Nm']
                    
            if self.scenario_config and 'speed_reversal' in self.scenario_config:
                if t >= self.scenario_config['speed_reversal']['onset_time']:
                    self.controller.set_speed_ref(self.scenario_config['speed_reversal']['new_speed_rpm'] * (2*math.pi/60) * MOTOR_PARAMS['P'])
            
            if self.scenario_config and 'slow_ramp' in self.scenario_config:
                if t >= self.scenario_config['slow_ramp']['onset_time']:
                    dt_time = t - self.scenario_config['slow_ramp']['onset_time']
                    rate = self.scenario_config['slow_ramp']['rate_rpm_per_s']
                    base = self.scenario_config.get('speed_ref_rpm', self.config['speed_ref_rpm'])
                    new_speed = base + rate * dt_time
                    self.controller.set_speed_ref(new_speed * (2*math.pi/60) * MOTOR_PARAMS['P'])
            
            for _ in range(sub_steps):
                if not gate_en:
                    omega_e = self.plant.omega_e
                    e_ll_pk = math.sqrt(3.0) * self.plant.psi_f * abs(omega_e)
                    if e_ll_pk > vbus:
                        vd = 0.0
                        vq = -math.copysign(vbus / math.sqrt(3.0), omega_e)
                        self.plant.step(vd, vq, load, dt_p)
                    else:
                        i_mag = math.hypot(self.plant.i_d, self.plant.i_q)
                        if i_mag > 0.02:
                            # Inductor freewheeling quench through body diodes
                            vd = -math.copysign(vbus / math.sqrt(3.0), self.plant.i_d) if abs(self.plant.i_d) > 0.005 else 0.0
                            vq = -math.copysign(vbus / math.sqrt(3.0), self.plant.i_q) if abs(self.plant.i_q) > 0.005 else 0.0
                            self.plant.step(vd, vq, load, dt_p)
                            if (vd * self.plant.i_d > 0.0) or (vq * self.plant.i_q > 0.0):
                                self.plant.i_d = 0.0
                                self.plant.i_q = 0.0
                                if hasattr(self.plant, 'i_a'):
                                    self.plant.i_a = 0.0
                                    self.plant.i_b = 0.0
                                    self.plant.i_c = 0.0
                        else:
                            # Quenched: zero current, pure mechanical coasting
                            self.plant.i_d = 0.0
                            self.plant.i_q = 0.0
                            if hasattr(self.plant, 'i_a'):
                                self.plant.i_a = 0.0
                                self.plant.i_b = 0.0
                                self.plant.i_c = 0.0
                            vd = 0.0
                            vq = omega_e * self.plant.psi_f
                            self.plant.step(vd, vq, load, dt_p)
                            self.plant.i_d = 0.0
                            self.plant.i_q = 0.0
                            if hasattr(self.plant, 'i_a'):
                                self.plant.i_a = 0.0
                                self.plant.i_b = 0.0
                                self.plant.i_c = 0.0
                else:
                    vd, vq = phase_to_dq(va, vb, vc, self.plant.theta_e)
                    self.plant.step(vd, vq, load, dt_p)
                
            # Log
            res.time[k] = t
            res.theta_true[k] = p_state['theta_e']
            res.theta_hat_smo[k] = out.theta_hat_smo
            res.theta_hat_flux[k] = out.theta_hat_flux
            res.theta_hat[k] = out.theta_hat
            res.omega_true[k] = p_state['omega_e']
            res.omega_hat[k] = out.omega_hat
            res.i_a[k] = ia_corr
            res.i_true_a[k] = ia
            res.i_true_b[k] = ib
            res.i_true_c[k] = ic
            res.i_b[k] = ib_corr
            res.i_c[k] = ic_corr
            res.i_d[k] = out.i_d
            res.i_q[k] = out.i_q
            res.duty_a[k] = out.duty_a
            res.duty_b[k] = out.duty_b
            res.duty_c[k] = out.duty_c
            res.health_score[k] = out.health_score
            res.control_mode[k] = out.control_mode
            
            err = p_state['theta_e'] - out.theta_hat
            err = (err + math.pi) % (2*math.pi) - math.pi
            res.angle_error[k] = math.degrees(err)
            res.speed_rpm[k] = p_state['omega_m'] * 60 / (2 * math.pi)
            
            res.fault_channel[k] = out.fault_channel
            res.i_a_rec[k] = out.i_a_rec
            res.i_b_rec[k] = out.i_b_rec
            res.i_c_rec[k] = out.i_c_rec
            res.smo_health[k] = out.smo_health
            res.flux_health[k] = out.flux_health
            res.observer_disagreement[k] = out.observer_disagreement
            res.emf_mag[k] = out.emf_mag
            res.confidence_smo[k] = out.confidence_smo
            res.confidence_flux[k] = out.confidence_flux
            
        return res

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', type=str, default='no_fault_baseline')
    parser.add_argument('--sensor-model', action='store_true', help='Enable realistic ADC sensor model')
    parser.add_argument('--no-plot', action='store_true')
    args = parser.parse_args()
    
    sensor = SensorModel() if args.sensor_model else None
    runner = SILRunner(config_sim=SIM_PARAMS, fault_scenario=args.scenario, sensor_model=sensor)
    res = runner.run()
    
    # Save the scenario parameters
    import json
    with open(f"docs/results/{args.scenario}_metadata.json", "w") as f:
        meta = {
            'motor': MOTOR_PARAMS,
            'controller': CONTROLLER_PARAMS,
            'sim': SIM_PARAMS,
            'scenario': runner.scenario_config or 'no_fault_baseline'
        }
        json.dump(meta, f, indent=2)
    
    if not args.no_plot:
        from simulation.analysis.plotter import plot_fault_response, plot_observer_comparison
        plot_fault_response(res, args.scenario)
        plot_observer_comparison(res, args.scenario)
        
    # Evaluate
    # Extract expected outcomes from YAML
    sc_conf = runner.scenario_config
    if sc_conf and 'expected_outcome' in sc_conf:
        criteria = sc_conf['expected_outcome']['criteria']
        onset = sc_conf['expected_outcome'].get('fault_onset_time', float('inf'))
        expected_ch = sc_conf['expected_outcome'].get('expected_fault_channel', 0)
        expected_mode = sc_conf['expected_outcome'].get('expected_mode_after_fault', 2) # 2=CLOSED_LOOP, 3=DEGRADED, 5=SAFE_STOP
        ref_speed = sc_conf.get('speed_reversal', {}).get('new_speed_rpm', sc_conf.get('speed_ref_rpm', SIM_PARAMS['speed_ref_rpm']))
        if 'slow_ramp' in sc_conf:
            rate = sc_conf['slow_ramp']['rate_rpm_per_s']
            duration = SIM_PARAMS['total_time'] - sc_conf['slow_ramp']['onset_time']
            ref_speed = ref_speed + rate * duration
        
        trans_time = 0.0
        if 'speed_reversal' in sc_conf: trans_time = sc_conf['speed_reversal'].get('onset_time', 0.0)
        elif 'load_step' in sc_conf: trans_time = sc_conf['load_step'].get('onset_time', 0.0)
        elif 'slow_ramp' in sc_conf: trans_time = sc_conf['slow_ramp'].get('onset_time', 0.0)
        
        start_time = get_scenario_evaluation_start_time(sc_conf)
        evaluation = evaluate_scenario(res, criteria, onset, ref_speed, start_time=start_time, 
                                       expected_fault_channel=expected_ch, expected_mode_after_fault=expected_mode, disturbance_duration=sc_conf.get('duration', 0.0), transition_time=trans_time)
        
        all_passed = True
        print(f"\nEvaluation for {args.scenario}:")
        for k, v in evaluation.items():
            print(f"  {k:20s} : {'PASS' if v['pass'] else 'FAIL'} (value={v['value']:.2f})")
            if not v['pass']: all_passed = False
            
        if all_passed:
            print(f"PASS ({args.scenario}): Met all criteria.")
            sys.exit(0)
        else:
            print(f"FAIL ({args.scenario}): Did not meet all criteria.")
            sys.exit(1)
    else:
        # Default baseline criteria
        evaluation = evaluate_scenario(res, {
            'max_angle_error': 15.0,
            'angle_error_rms': 5.0,
            'speed_ripple_ptp': 350.0,
            'mean_speed': 20.0
        }, start_time=get_scenario_evaluation_start_time(None), expected_mode_after_fault=2)
        
        all_passed = True
        print(f"\nEvaluation for {args.scenario}:")
        for k, v in evaluation.items():
            print(f"  {k:20s} : {'PASS' if v['pass'] else 'FAIL'} (value={v['value']:.2f})")
            if not v['pass']: all_passed = False
            
        if all_passed:
            print(f"PASS ({args.scenario}): Maintained stable control.")
            sys.exit(0)
        else:
            print(f"FAIL ({args.scenario}): Did not meet stable baseline criteria.")
            sys.exit(1)
