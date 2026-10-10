import re

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

# Replace lkg_theta with theta, and lkg_omega with omega
content = content.replace("fm->lkg_theta", "theta")
content = content.replace("fm->lkg_omega", "omega")

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
