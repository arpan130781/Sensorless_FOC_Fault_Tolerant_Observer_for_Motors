with open("src/foc_core.c", "r") as f:
    content = f.read()

content = content.replace("valpha * scale, vbeta * scale", "prev_v_alpha, prev_v_beta")

with open("src/foc_core.c", "w") as f:
    f.write(content)
