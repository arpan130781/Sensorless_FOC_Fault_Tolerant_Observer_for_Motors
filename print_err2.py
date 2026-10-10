import re

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("fm->err_acc_A += err_A * dt;", 'if (fm->fault_isolation_timer > 0.0f) printf("t=%f, err_A=%f, err_B=%f, err_C=%f, ia_true_diff=%f\\n", fm->fault_isolation_timer, err_A, err_B, err_C, i_a - ia_pred);\n            fm->err_acc_A += err_A * dt;')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
