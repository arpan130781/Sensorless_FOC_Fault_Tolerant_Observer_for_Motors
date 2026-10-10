import yaml

with open("simulation/fault_injection/fault_scenarios.yaml", "r") as f:
    config = yaml.safe_load(f)

config['scenario_5_simultaneous']['type'] = 'sensor_offset'
config['scenario_5_simultaneous']['offset'] = 2.0

with open("simulation/fault_injection/fault_scenarios.yaml", "w") as f:
    yaml.dump(config, f)
