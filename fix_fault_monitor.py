with open("src/fault_monitor.c", "r") as f:
    content = f.read()

# 1. Reset timer when latching
content = content.replace("""                    if (fm->best_channel == 0) fm->fault_latch_a = true;
                    else if (fm->best_channel == 1) fm->fault_latch_b = true;
                    else fm->fault_latch_c = true;
                    fm->ambiguous_fault = false;
                } else if (fm->fault_isolation_timer > 0.020f) {
                    /* After 20ms without confident isolation → ambiguous */
                    fm->ambiguous_fault = true;
                }

                /* Reset accumulators for next window */
                fm->err_acc_A = 0; fm->err_acc_B = 0; fm->err_acc_C = 0;
                fm->E_acc = 0;
                fm->fault_isolation_timer = 0.00001f;""", """                    if (fm->best_channel == 0) fm->fault_latch_a = true;
                    else if (fm->best_channel == 1) fm->fault_latch_b = true;
                    else fm->fault_latch_c = true;
                    fm->ambiguous_fault = false;
                    fm->fault_isolation_timer = 0.0f;
                } else if (fm->fault_isolation_timer > 0.020f) {
                    /* After 20ms without confident isolation → ambiguous */
                    fm->ambiguous_fault = true;
                    fm->fault_isolation_timer = 0.0f;
                } else {
                    fm->fault_isolation_timer = 0.00001f;
                }

                /* Reset accumulators for next window */
                fm->err_acc_A = 0; fm->err_acc_B = 0; fm->err_acc_C = 0;
                fm->E_acc = 0;""")

# 2. i_alpha_clean
content = content.replace("""    if (fm->fault_isolation_timer > 0.0f || fm->ambiguous_fault || fm->fault_latch_a || fm->fault_latch_b || fm->fault_latch_c) {
        fm->status.i_alpha_clean = fm->i_alpha_pred;
        fm->status.i_beta_clean  = fm->i_beta_pred;
    } else {
        fm->status.i_alpha_clean = (2.0f/3.0f) * (i_a - 0.5f*i_b - 0.5f*i_c);
        fm->status.i_beta_clean  = 0.57735027f * (i_b - i_c);
    }""", """    if (fm->fault_isolation_timer > 0.0f) {
        fm->status.i_alpha_clean = fm->i_alpha_pred;
        fm->status.i_beta_clean  = fm->i_beta_pred;
    } else {
        fm->status.i_alpha_clean = (2.0f/3.0f) * (fm->status.i_a_rec - 0.5f*fm->status.i_b_rec - 0.5f*fm->status.i_c_rec);
        fm->status.i_beta_clean  = 0.57735027f * (fm->status.i_b_rec - fm->status.i_c_rec);
    }""")

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
