with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("separation > 0.3f * fm->E_acc", "separation > 0.6f * fm->E_acc")

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
