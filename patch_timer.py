with open('src/fault_monitor.c', 'r') as f:
    c_code = f.read()
import re
c_code = re.sub(r"if \(fm->unisolated_timer > 0.020f\)", "if (fm->unisolated_timer > 0.002f)", c_code)
with open('src/fault_monitor.c', 'w') as f:
    f.write(c_code)
