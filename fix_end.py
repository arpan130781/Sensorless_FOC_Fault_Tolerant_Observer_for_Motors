with open("src/foc_core.c", "r") as f:
    content = f.read()

obs_block = """    // Observers
    if (fault.fault_isolation_timer == 0.0f) {
        obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, fs.i_alpha_clean, fs.i_beta_clean, speed_est, dt_curr);
        frozen_theta = obs_mgr_get_theta(&obs_mgr);
        frozen_omega = obs_mgr_get_omega(&obs_mgr);
    } else {
        frozen_theta += frozen_omega * dt_curr;
        if (frozen_theta > M_PI) frozen_theta -= 2.0f * M_PI;
        if (frozen_theta < -M_PI) frozen_theta += 2.0f * M_PI;
    }
    speed_est = frozen_omega;

    
    
    speed_est = obs_omega;"""

content = content.replace(obs_block, "")

content = content.replace("    return out;", """    // Observers
    if (fault.fault_isolation_timer == 0.0f) {
        obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, fs.i_alpha_clean, fs.i_beta_clean, speed_est, dt_curr);
        frozen_theta = obs_mgr_get_theta(&obs_mgr);
        frozen_omega = obs_mgr_get_omega(&obs_mgr);
    } else {
        frozen_theta += frozen_omega * dt_curr;
        if (frozen_theta > M_PI) frozen_theta -= 2.0f * M_PI;
        if (frozen_theta < -M_PI) frozen_theta += 2.0f * M_PI;
    }
    speed_est = frozen_omega;

    return out;""")

with open("src/foc_core.c", "w") as f:
    f.write(content)
