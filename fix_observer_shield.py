import re

# 1. Add i_alpha_clean and i_beta_clean to FocApi and FaultStatus
with open("src/fault_monitor.h", "r") as f:
    content = f.read()
content = content.replace("    float i_c_rec;\n    ControlMode degradation_state;", "    float i_c_rec;\n    float i_alpha_clean;\n    float i_beta_clean;\n    ControlMode degradation_state;")
with open("src/fault_monitor.h", "w") as f:
    f.write(content)

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

# Replace the previous full shield in `fault_update` with just populating i_alpha_clean
shield_code_old = """    else if (fm->fault_isolation_timer > 0.0f) {
        fm->status.i_a_rec = fm->i_alpha_pred;
        fm->status.i_b_rec = -0.5f*fm->i_alpha_pred + 0.8660254f*fm->i_beta_pred;
        fm->status.i_c_rec = -0.5f*fm->i_alpha_pred - 0.8660254f*fm->i_beta_pred;
        fm->status.degradation_state = CLOSED_LOOP;
    }
    else {"""

shield_code_new = """    else {
        fm->status.i_a_rec = i_a;
        fm->status.i_b_rec = i_b;
        fm->status.i_c_rec = i_c;
        fm->status.degradation_state = CLOSED_LOOP;
    }"""
content = content.replace(shield_code_old, shield_code_new)

# Now add i_alpha_clean logic
clean_logic = """
    if (fm->fault_isolation_timer > 0.0f || fm->ambiguous_fault || fm->fault_latch_a || fm->fault_latch_b || fm->fault_latch_c) {
        fm->status.i_alpha_clean = fm->i_alpha_pred;
        fm->status.i_beta_clean  = fm->i_beta_pred;
    } else {
        fm->status.i_alpha_clean = (2.0f/3.0f) * (i_a - 0.5f*i_b - 0.5f*i_c);
        fm->status.i_beta_clean  = 0.57735027f * (i_b - i_c);
    }
    
    return fm->status;
}"""
content = content.replace("    return fm->status;\n}", clean_logic)

# Remove the print statements
content = re.sub(r'if \(fm->fault_isolation_timer > 0.0f\) printf\("t=%f, err_A=.*?\\n", .*?\);\n\s*', '', content)

with open("src/fault_monitor.c", "w") as f:
    f.write(content)

# 3. Update foc_core.c to use i_alpha_clean
with open("src/foc_core.c", "r") as f:
    content = f.read()

obs_code_old = """    // Observers
    obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, i_alpha, i_beta, speed_est, dt_curr);"""

obs_code_new = """    // Observers
    obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, fs.i_alpha_clean, fs.i_beta_clean, speed_est, dt_curr);"""
content = content.replace(obs_code_old, obs_code_new)

with open("src/foc_core.c", "w") as f:
    f.write(content)
