import re
with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = re.sub(r'printf\("PRE.*?\\n", .*?\);', 'printf("PRE: ia_meas=%f, iap=%f, ib_meas=%f, ibp=%f\\n", i_alpha_meas, fm->i_alpha_pred, i_beta_meas, fm->i_beta_pred);', content)

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
