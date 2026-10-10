import re

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("fm->i_beta_pred  += 5000.0f * dt * (i_beta_meas  - fm->i_beta_pred);", 'fm->i_beta_pred  += 5000.0f * dt * (i_beta_meas  - fm->i_beta_pred);\n        if (fm->clear_timer > 0.4999f) printf("TRACKING: ia_meas=%f, ia_pred=%f\\n", i_alpha_meas, fm->i_alpha_pred);')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
