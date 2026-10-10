import yaml
with open("simulation/fault_injection/fault_scenarios.yaml", "r") as f:
    config = yaml.safe_load(f)

config['scenario_1_rs_drift']['scale'] = 1.05

with open("simulation/fault_injection/fault_scenarios.yaml", "w") as f:
    yaml.dump(config, f)
