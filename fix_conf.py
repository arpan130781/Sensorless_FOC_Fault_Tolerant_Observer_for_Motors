with open("src/fault_monitor.c", "r") as f:
    content = f.read()
content = content.replace("if (fm->consecutive_confident >= 2) {", "if (fm->consecutive_confident >= 10) {")
with open("src/fault_monitor.c", "w") as f:
    f.write(content)
