import re
with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = re.sub(r'if \(fm->clear_timer > 0.4990f.*?printf\("PRE.*?\\n", .*?\);', '', content)
content = content.replace("fm->i_beta_pred  += 5000.0f * dt * (i_beta_meas  - fm->i_beta_pred);", 'fm->i_beta_pred  += 5000.0f * dt * (i_beta_meas  - fm->i_beta_pred);\n        printf("PRE: ia_meas=%f, iap=%f\\n", i_alpha_meas, fm->i_alpha_pred);')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
