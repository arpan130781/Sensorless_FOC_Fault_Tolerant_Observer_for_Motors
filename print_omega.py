import re

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace('fm->omega_foc);', 'omega);')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
