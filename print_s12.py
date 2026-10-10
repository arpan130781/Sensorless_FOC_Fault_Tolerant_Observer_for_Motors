import sys
sys.path.append('.')
from simulation.harness.sil_runner import SILRunner
from simulation.harness.config import SIM_PARAMS
res = SILRunner(SIM_PARAMS, 'scenario_12_ambiguous_fault').run()
fault_idx = int(2.0 * 20000)
for i in range(20):
    idx = fault_idx + i
    print(f"Step {i}: Mode={res.control_mode[idx]}, err={res.angle_error[idx]:.2f}, omega={res.omega_true[idx]:.2f}, omega_hat={res.omega_hat[idx]:.2f}, iq={res.i_q[idx]:.2f}")
