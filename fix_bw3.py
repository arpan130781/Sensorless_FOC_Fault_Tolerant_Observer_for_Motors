with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("10000.0f * dt", "5000.0f * dt")

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
