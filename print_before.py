import re

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("float ia_pred = fm->i_alpha_pred;", 'float ia_pred = fm->i_alpha_pred;\n    if (fm->fault_isolation_timer == 0.00001f) printf("INIT: ia_pred=%f, ib_pred=%f\\n", fm->i_alpha_pred, fm->i_beta_pred);')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
