with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("if (separation > 0.8f * fm->E_acc) {", 'printf("separation=%f, E_acc=%f, best=%d, errA=%f, errB=%f, errC=%f\\n", separation, fm->E_acc, best, eA, eB, eC);\n                if (separation > 0.8f * fm->E_acc) {')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
