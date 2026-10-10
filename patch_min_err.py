with open('src/fault_monitor.c', 'r') as f:
    c_code = f.read()
import re
confident_section = r"                bool confident = \(separation > 0.3f \* fm->E_acc\)\s+&& \(fm->E_acc > 0.0001f\)\s+&& \(min_err > 0.0f\);"
replacement = """                bool confident = (separation > 0.3f * fm->E_acc)
                              && (fm->E_acc > 0.0001f)
                              && (min_err < 0.3f * fm->E_acc);"""
c_code = re.sub(confident_section, replacement, c_code)
with open('src/fault_monitor.c', 'w') as f:
    f.write(c_code)
