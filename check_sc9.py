import numpy as np
import os
import sys

sys.path.append(os.getcwd())
from simulation.harness.config import SIM_PARAMS
from simulation.harness.sil_runner import SILRunner

runner = SILRunner(SIM_PARAMS, "scenario_9_load_step")
res = runner.run()

print(f"End speed: {res.speed_rpm[-1]}")
