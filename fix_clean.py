with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("    return fm->status;", """    fm->status.i_alpha_clean = (2.0f/3.0f) * (fm->status.i_a_rec - 0.5f*fm->status.i_b_rec - 0.5f*fm->status.i_c_rec);
    fm->status.i_beta_clean  = 0.57735027f * (fm->status.i_b_rec - fm->status.i_c_rec);
    return fm->status;""")

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
