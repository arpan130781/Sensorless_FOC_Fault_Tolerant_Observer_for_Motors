with open("src/fault_monitor.c", "r") as f:
    content = f.read()
content = content.replace('printf("AMBIGUOUS FAULT at t=%f, ia=%f, ib=%f, ic=%f\\n", fm->unisolated_timer, i_a, i_b, i_c);\n', '')
content = content.replace('printf("LATCHED: a=%d, b=%d, c=%d at t=%f\\n", fm->fault_latch_a, fm->fault_latch_b, fm->fault_latch_c, fm->unisolated_timer);\n', '')
content = content.replace('printf("UNLATCHED at clear_timer=%f\\n", fm->clear_timer);\n', '')
content = content.replace("        theta = theta;\n", "")
content = content.replace("        omega = omega;\n", "")
with open("src/fault_monitor.c", "w") as f:
    f.write(content)
