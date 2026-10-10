with open("src/fault_monitor.c", "r") as f:
    content = f.read()

target = """    fm->status.i_alpha_clean = (2.0f/3.0f) * (fm->status.i_a_rec - 0.5f*fm->status.i_b_rec - 0.5f*fm->status.i_c_rec);
    fm->status.i_beta_clean  = 0.57735027f * (fm->status.i_b_rec - fm->status.i_c_rec);"""

replacement = """    if (fm->fault_isolation_timer > 0.0f && !fm->fault_latch_a && !fm->fault_latch_b && !fm->fault_latch_c && !fm->ambiguous_fault) {
        fm->status.i_alpha_clean = fm->i_alpha_pred;
        fm->status.i_beta_clean = fm->i_beta_pred;
    } else {
        fm->status.i_alpha_clean = (2.0f/3.0f) * (fm->status.i_a_rec - 0.5f*fm->status.i_b_rec - 0.5f*fm->status.i_c_rec);
        fm->status.i_beta_clean  = 0.57735027f * (fm->status.i_b_rec - fm->status.i_c_rec);
    }"""

content = content.replace(target, replacement)

with open("src/fault_monitor.c", "w") as f:
    f.write(content)

