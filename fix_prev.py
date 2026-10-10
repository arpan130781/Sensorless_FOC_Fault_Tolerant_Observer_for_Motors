import re
with open("src/foc_core.c", "r") as f:
    content = f.read()

content = content.replace("vc *= scale;", "vc *= scale;\n    prev_v_alpha = valpha * scale;\n    prev_v_beta = vbeta * scale;")

with open("src/foc_core.c", "w") as f:
    f.write(content)
