import sys
sys.path.append('.')
from simulation.harness.sil_runner import SILRunner
from simulation.harness.config import SIM_PARAMS
res = SILRunner(SIM_PARAMS, 'scenario_12_ambiguous_fault').run()
print(f"t=0.5s: {res.omega_true[int(0.5*20000)]}")
print(f"t=1.0s: {res.omega_true[int(1.0*20000)]}")
print(f"t=1.5s: {res.omega_true[int(1.5*20000)]}")
print(f"t=2.0s: {res.omega_true[int(2.0*20000)]}")
