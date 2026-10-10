import yaml

with open("simulation/fault_injection/fault_scenarios.yaml", "r") as f:
    scenarios = yaml.safe_load(f)

scenarios["scenario_test"] = {
    "type": "sensor_offset",
    "channel": "a",
    "offset": 2.0,
    "onset_time": 1.5000,
    "expected_outcome": scenarios["scenario_2_offset_a_2_0"]["expected_outcome"]
}

with open("simulation/fault_injection/fault_scenarios.yaml", "w") as f:
    yaml.dump(scenarios, f)
