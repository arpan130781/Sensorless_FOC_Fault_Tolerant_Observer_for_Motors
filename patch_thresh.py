with open('src/fault_monitor.c', 'r') as f:
    c_code = f.read()
import re
c_code = re.sub(r"min_err < 0.3f \* fm->E_acc", "min_err < 1.0f * fm->E_acc", c_code)
with open('src/fault_monitor.c', 'w') as f:
    f.write(c_code)
