import re

with open("src/foc_core.c", "r") as f:
    content = f.read()

# Remove the old prev_v_alpha = valpha
content = content.replace("    prev_v_alpha = valpha;\n    prev_v_beta = vbeta;\n", "")

# Add it after scale
scale_code = """        scale = v_max_allowed / fmaxf(fabsf(va), fmaxf(fabsf(vb), fabsf(vc)));
    }
    
    prev_v_alpha = valpha * scale;
    prev_v_beta = vbeta * scale;
"""
content = content.replace("""        scale = v_max_allowed / fmaxf(fabsf(va), fmaxf(fabsf(vb), fabsf(vc)));
    }""", scale_code)

with open("src/foc_core.c", "w") as f:
    f.write(content)
