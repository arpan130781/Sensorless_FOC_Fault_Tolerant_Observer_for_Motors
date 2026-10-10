with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("fm->i_alpha_pred += 50000.0f * dt", "fm->i_alpha_pred += 5000.0f * dt")
content = content.replace("fm->i_beta_pred  += 50000.0f * dt", "fm->i_beta_pred  += 5000.0f * dt")

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
