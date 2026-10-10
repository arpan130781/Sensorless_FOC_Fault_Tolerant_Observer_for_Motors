import re

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace('printf("AMBIGUOUS FAULT at t=%f\\n", fm->unisolated_timer);',
                          'printf("AMBIGUOUS FAULT at t=%f, ia=%f, ib=%f, ic=%f\\n", fm->unisolated_timer, i_a, i_b, i_c);')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
