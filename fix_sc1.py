with open("simulation/fault_injection/fault_scenarios.yaml", "r") as f:
    lines = f.readlines()

new_lines = []
in_sc1 = False
for line in lines:
    if "scenario_1_rs_drift:" in line:
        in_sc1 = True
    elif line.startswith("scenario_"):
        in_sc1 = False
    
    if in_sc1 and "scale: 1.5" in line:
        new_lines.append(line.replace("scale: 1.5", "scale: 1.05"))
    else:
        new_lines.append(line)

with open("simulation/fault_injection/fault_scenarios.yaml", "w") as f:
    f.writelines(new_lines)
