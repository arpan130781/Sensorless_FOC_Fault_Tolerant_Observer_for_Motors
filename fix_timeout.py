with open("src/fault_monitor.c", "r") as f:
    content = f.read()
content = content.replace("if (fm->unisolated_timer > 0.002f) {", "if (fm->unisolated_timer > 0.010f) {")
with open("src/fault_monitor.c", "w") as f:
    f.write(content)
