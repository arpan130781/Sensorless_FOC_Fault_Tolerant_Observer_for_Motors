import re

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace('if (fm->fault_isolation_timer == 0.00001f) printf("INIT: ia_pred=%f, ib_pred=%f\\n", fm->i_alpha_pred, fm->i_beta_pred);', 'if (fm->fault_isolation_timer == 0.00001f) printf("INIT: ia_meas=%f, ib_meas=%f\\n", (2.0f/3.0f) * (i_a - 0.5f*i_b - 0.5f*i_c), 0.57735027f * (i_b - i_c));')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
