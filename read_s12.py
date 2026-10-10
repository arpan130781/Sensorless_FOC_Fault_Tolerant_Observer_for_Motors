import numpy as np
data = np.load('docs/results/scenario_12_ambiguous_fault.npz')
print("Keys:", data.files)
mode = data['control_mode']
fault_onset = int(2.0 * 20000)
print("Mode at onset:", mode[fault_onset:fault_onset+5])
print("Mode 20ms later:", mode[fault_onset+400:fault_onset+405])
print("Mode at end:", mode[-10:])
print("Max mode:", np.max(mode))
