import re

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

shield_code = """    else if (fm->fault_isolation_timer > 0.0f) {
        fm->status.i_a_rec = fm->i_alpha_pred;
        fm->status.i_b_rec = -0.5f*fm->i_alpha_pred + 0.8660254f*fm->i_beta_pred;
        fm->status.i_c_rec = -0.5f*fm->i_alpha_pred - 0.8660254f*fm->i_beta_pred;
        fm->status.degradation_state = CLOSED_LOOP;
    }
    else {"""

content = content.replace("    else {", shield_code)

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
