import re
with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("bool confident =", 'printf("separation=%f, E_acc=%f, best=%d, eA=%f, eB=%f, eC=%f, min_err=%f, sec_err=%f\\n", separation, fm->E_acc, best, eA, eB, eC, min_err, second_err);\n                bool confident =')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
