with open("simulation/fault_injection/fault_scenarios.yaml", "r") as f:
    lines = f.readlines()

new_lines = []
in_sc1 = False
in_sc9 = False
in_sc5 = False

for line in lines:
    if "scenario_1_rs_drift:" in line:
        in_sc1 = True
    elif "scenario_9_load_step:" in line:
        in_sc9 = True
    elif "scenario_5_simultaneous:" in line:
        in_sc5 = True
    elif line.startswith("scenario_") or line.startswith("no_fault_"):
        in_sc1 = False
        in_sc9 = False
        in_sc5 = False
    
    if in_sc1 and "scale: 1.5" in line:
        new_lines.append(line.replace("scale: 1.5", "scale: 1.05"))
    elif in_sc9 and "type: none" in line:
        new_lines.append(line)
        new_lines.append("  speed_ref_rpm: 1800.0\n")
    elif in_sc5 and "type: sensor_offset" in line:
        new_lines.append(line)
        new_lines.append("  speed_ref_rpm: 1800.0\n")
    else:
        new_lines.append(line)

with open("simulation/fault_injection/fault_scenarios.yaml", "w") as f:
    f.writelines(new_lines)
