import re

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("float E = i_a + i_b + i_c;", 'float E = i_a + i_b + i_c;\n    if (fm->fault_isolation_timer > 0.0f) printf("E=%f, ia=%f, ib=%f, ic=%f\\n", E, i_a, i_b, i_c);')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
