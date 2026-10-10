import numpy as np
import os
import sys

sys.path.append(os.getcwd())
from simulation.harness.config import SIM_PARAMS
from simulation.harness.sil_runner import SILRunner
from simulation.analysis.metrics import compute_max_angle_error

runner = SILRunner(SIM_PARAMS, "scenario_10_low_speed")
res = runner.run()

dt = res.time[1] - res.time[0]
start_idx = int(2.0 / dt)

err = np.abs(res.theta_hat[start_idx:] - res.theta_true[start_idx:])
err = np.minimum(err, 2*np.pi - err)
err_deg = np.degrees(err)

max_idx = np.argmax(err_deg)
print(f"Max error {err_deg[max_idx]} at t={res.time[start_idx + max_idx]}")
