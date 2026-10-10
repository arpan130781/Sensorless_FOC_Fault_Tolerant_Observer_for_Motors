with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("fm->unisolated_timer += dt;\n", "")
content = content.replace("fm->ambiguous_fault = false; fm->unisolated_timer = 0.0f;", "fm->ambiguous_fault = false;")
content = content.replace("if (fm->unisolated_timer > 0.002f)", "if (fm->fault_isolation_timer > 0.002f)")

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
