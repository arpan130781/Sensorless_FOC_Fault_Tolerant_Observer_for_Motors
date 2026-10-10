with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("fm->fault_isolation_timer = 0.00001f;", "fm->fault_isolation_timer = 0.00001f; printf(\"Starting timer\\n\");")
content = content.replace("fm->ambiguous_fault = true;", "fm->ambiguous_fault = true; printf(\"AMBIGUOUS!\\n\");")
content = content.replace("fm->fault_latch_a = true;", "fm->fault_latch_a = true; printf(\"LATCH A!\\n\");")
content = content.replace("fm->fault_latch_b = true;", "fm->fault_latch_b = true; printf(\"LATCH B!\\n\");")
content = content.replace("fm->fault_latch_c = true;", "fm->fault_latch_c = true; printf(\"LATCH C!\\n\");")

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
