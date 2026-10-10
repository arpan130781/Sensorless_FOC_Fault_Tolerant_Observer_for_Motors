with open('src/fault_monitor.c', 'r') as f:
    c_code = f.read()

import re
replacement = """                float separation = second_err - min_err;
                if (fm->E_acc > 0.005f && separation > 0.3f * fm->E_acc) {
                    printf("CONFIDENT ISOLATION: A=%f, B=%f, C=%f, sep=%f, E_acc=%f, time=%f\\n", fm->err_acc_A, fm->err_acc_B, fm->err_acc_C, separation, fm->E_acc, fm->unisolated_timer);
                }
                bool confident = (separation > 0.3f * fm->E_acc)"""

c_code = re.sub(r"                float separation = second_err - min_err;\n                bool confident = \(separation > 0.3f \* fm->E_acc\)", replacement, c_code)

if "<stdio.h>" not in c_code:
    c_code = "#include <stdio.h>\n" + c_code

with open('src/fault_monitor.c', 'w') as f:
    f.write(c_code)
