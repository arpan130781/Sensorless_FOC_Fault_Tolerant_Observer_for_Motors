with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("fm->fault_isolation_timer > 0.020f", "fm->unresolved_fault_timer > 0.020f")
content = content.replace("fm->fault_isolation_timer += dt;", "fm->fault_isolation_timer += dt;\n    if (fm->fault_isolation_timer > 0.0f) fm->unresolved_fault_timer += dt;")
content = content.replace("fm->ambiguous_fault = false;", "fm->ambiguous_fault = false;\n                    fm->unresolved_fault_timer = 0.0f;")
content = content.replace("fm->fault_isolation_timer = 0.0f;", "fm->fault_isolation_timer = 0.0f;\n                    fm->unresolved_fault_timer = 0.0f;")

with open("src/fault_monitor.c", "w") as f:
    f.write(content)

with open("src/fault_monitor.h", "r") as f:
    content = f.read()

content = content.replace("float fault_isolation_timer;", "float fault_isolation_timer;\n    float unresolved_fault_timer;")

with open("src/fault_monitor.h", "w") as f:
    f.write(content)

