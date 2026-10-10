import numpy as np
import os
import sys

sys.path.append(os.getcwd())
from simulation.harness.config import SIM_PARAMS
from simulation.harness.sil_runner import SILRunner

runner = SILRunner(SIM_PARAMS, "scenario_9_load_step")
res = runner.run()

print(f"End i_q: {res.i_q[-1]}")
print(f"End omega_hat: {res.omega_hat[-1]} rad/s")
print(f"End speed true: {res.speed_rpm[-1]}")
