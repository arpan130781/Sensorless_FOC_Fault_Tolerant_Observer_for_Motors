import re

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace('printf("t=%f, eA=%f, eB=%f, eC=%f, best=%d, conf=%d\\n", fm->unisolated_timer, eA, eB, eC, best, confident);', 'printf("t=%f, eA=%f, eB=%f, eC=%f, best=%d, conf=%d, sep=%f, E=%f\\n", fm->unisolated_timer, eA, eB, eC, best, confident, separation, fm->E_acc);')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
