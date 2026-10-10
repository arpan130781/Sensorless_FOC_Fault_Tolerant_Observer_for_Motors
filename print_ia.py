import re

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace('printf("t=%f, eA=%f, eB=%f, eC=%f, best=%d, conf=%d, sep=%f, E=%f\\n", fm->unisolated_timer, eA, eB, eC, best, confident, separation, fm->E_acc);', 'printf("t=%f, ia=%f, iap=%f, ib=%f, ibp=%f, ic=%f, icp=%f\\n", fm->unisolated_timer, i_a, ia_pred, i_b, ib_pred, i_c, ic_pred);')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
