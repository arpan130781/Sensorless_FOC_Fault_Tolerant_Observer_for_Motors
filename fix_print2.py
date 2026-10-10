with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("if (fm->best_channel == 0) fm->fault_latch_a = true; printf(\"LATCH A!\\n\");", "if (fm->best_channel == 0) { fm->fault_latch_a = true; printf(\"LATCH A!\\n\"); }")

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
