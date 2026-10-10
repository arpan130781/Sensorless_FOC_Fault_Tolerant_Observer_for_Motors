import re

with open('src/fault_monitor.c', 'r') as f:
    c_code = f.read()

c_code = c_code.replace("                              && (second_err > min_err * 1.3f);", ";")

with open('src/fault_monitor.c', 'w') as f:
    f.write(c_code)
