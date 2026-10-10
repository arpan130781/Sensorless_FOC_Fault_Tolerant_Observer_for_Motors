with open("src/foc_core.c", "r") as f:
    content = f.read()

content = content.replace("""    if (fault.fault_isolation_timer == 0.0f) {
        if (fault.unresolved_fault_timer == 0.0f) {
            // Unfrozen and normal! But if it just unfroze, sync it!
            // Wait, we don't have a sync function. I can just update the observer.
            // Actually, we can just sync the SMO internal state directly if we have access, but we don't.
            // I will add a sync function!
        }
        obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, fs.i_alpha_clean, fs.i_beta_clean, speed_est, dt_curr);""", """    static bool was_frozen = false;
    if (fault.fault_isolation_timer == 0.0f) {
        if (was_frozen) {
            obs_mgr_sync_current(&obs_mgr, fs.i_alpha_clean, fs.i_beta_clean);
            was_frozen = false;
        }
        obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, fs.i_alpha_clean, fs.i_beta_clean, speed_est, dt_curr);""")

content = content.replace("""    } else {
        frozen_theta += frozen_omega * dt_curr;""", """    } else {
        was_frozen = true;
        frozen_theta += frozen_omega * dt_curr;""")

with open("src/foc_core.c", "w") as f:
    f.write(content)
