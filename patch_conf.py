import re
with open('src/fault_monitor.c', 'r') as f:
    c_code = f.read()
c_code = re.sub(r"bool confident = \(separation > 0.3f \* fm->E_acc\) && \(fm->E_acc > 0.0001f\) && \(min_err < 1.0f \* fm->E_acc\);", "bool confident = (separation > 0.3f * fm->E_acc) && (fm->E_acc > 0.0001f);", c_code)
with open('src/fault_monitor.c', 'w') as f:
    f.write(c_code)
