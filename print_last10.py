with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("fm->i_beta_pred  += 5000.0f * dt * (i_beta_meas  - fm->i_beta_pred);", 'fm->i_beta_pred  += 5000.0f * dt * (i_beta_meas  - fm->i_beta_pred);\n        if (fm->clear_timer > 0.4990f && fm->clear_timer < 0.5005f) printf("PRE: t=%f, ia_meas=%f, iap=%f\\n", fm->clear_timer, i_alpha_meas, fm->i_alpha_pred);')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
