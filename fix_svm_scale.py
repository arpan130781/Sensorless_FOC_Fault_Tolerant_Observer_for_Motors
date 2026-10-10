with open("src/foc_core.c", "r") as f:
    content = f.read()

old_svm = """    va += vcom; vb += vcom; vc += vcom;
    
    out.duty_a = (va / input->v_bus) + 0.5f;"""

new_svm = """    va += vcom; vb += vcom; vc += vcom;

    float v_max_allowed = input->v_bus * 0.5f;
    float scale = 1.0f;
    if (fmaxf(fabsf(va), fmaxf(fabsf(vb), fabsf(vc))) > v_max_allowed) {
        scale = v_max_allowed / fmaxf(fabsf(va), fmaxf(fabsf(vb), fabsf(vc)));
    }
    
    va *= scale;
    vb *= scale;
    vc *= scale;

    prev_v_alpha = valpha * scale;
    prev_v_beta = vbeta * scale;
    
    out.duty_a = (va / input->v_bus) + 0.5f;"""

content = content.replace(old_svm, new_svm)

with open("src/foc_core.c", "w") as f:
    f.write(content)
