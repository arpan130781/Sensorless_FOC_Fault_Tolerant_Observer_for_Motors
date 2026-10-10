with open("src/fault_monitor.c", "r") as f:
    content = f.read()

replacement = """    if (fm->fault_isolation_timer > 0.0f && !fm->fault_latch_a && !fm->fault_latch_b && !fm->fault_latch_c && !fm->ambiguous_fault) {
        fm->status.i_alpha_clean = fm->i_alpha_pred;
        fm->status.i_beta_clean = fm->i_beta_pred;
    } else {
        fm->status.i_alpha_clean = (2.0f/3.0f) * (fm->status.i_a_rec - 0.5f*fm->status.i_b_rec - 0.5f*fm->status.i_c_rec);
        fm->status.i_beta_clean  = 0.57735027f * (fm->status.i_b_rec - fm->status.i_c_rec);
    }
    return fm->status;"""

content = content.replace("""    fm->status.i_alpha_clean = (2.0f/3.0f) * (fm->status.i_a_rec - 0.5f*fm->status.i_b_rec - 0.5f*fm->status.i_c_rec);
    fm->status.i_beta_clean  = 0.57735027f * (fm->status.i_b_rec - fm->status.i_c_rec);
    return fm->status;""", replacement)

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
    
with open("src/foc_core.c", "r") as f:
    content = f.read()

# Remove observer freeze!
content = content.replace("""    if (fault.fault_isolation_timer == 0.0f) {
        obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, fs.i_alpha_clean, fs.i_beta_clean, speed_est, dt_curr);
        frozen_theta = obs_mgr_get_theta(&obs_mgr);
        frozen_omega = obs_mgr_get_omega(&obs_mgr);
    } else {
        frozen_theta += frozen_omega * dt_curr;
        if (frozen_theta > M_PI) frozen_theta -= 2.0f * M_PI;
        if (frozen_theta < -M_PI) frozen_theta += 2.0f * M_PI;
    }""", """    obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, fs.i_alpha_clean, fs.i_beta_clean, speed_est, dt_curr);
    frozen_theta = obs_mgr_get_theta(&obs_mgr);
    frozen_omega = obs_mgr_get_omega(&obs_mgr);""")

with open("src/foc_core.c", "w") as f:
    f.write(content)

