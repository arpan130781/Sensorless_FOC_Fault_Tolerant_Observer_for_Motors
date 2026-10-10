import re
with open("src/foc_core.c", "r") as f:
    content = f.read()

content = content.replace("out.control_mode = mode;", 'out.control_mode = mode;\n    if (fs.degradation_state == DEGRADED) printf("fs.degraded=1, mode=%d\\n", mode);')

with open("src/foc_core.c", "w") as f:
    f.write(content)
