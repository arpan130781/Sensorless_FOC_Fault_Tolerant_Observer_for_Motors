with open("src/fault_monitor.c", "r") as f:
    content = f.read()

# Revert i_alpha_clean to always use i_a_rec
content = content.replace("""    if (fm->fault_isolation_timer > 0.0f && !fm->fault_latch_a && !fm->fault_latch_b && !fm->fault_latch_c && !fm->ambiguous_fault) {
        fm->status.i_alpha_clean = fm->i_alpha_pred;
        fm->status.i_beta_clean = fm->i_beta_pred;
    } else {
        fm->status.i_alpha_clean = (2.0f/3.0f) * (fm->status.i_a_rec - 0.5f*fm->status.i_b_rec - 0.5f*fm->status.i_c_rec);
        fm->status.i_beta_clean  = 0.57735027f * (fm->status.i_b_rec - fm->status.i_c_rec);
    }""", """    fm->status.i_alpha_clean = (2.0f/3.0f) * (fm->status.i_a_rec - 0.5f*fm->status.i_b_rec - 0.5f*fm->status.i_c_rec);
    fm->status.i_beta_clean  = 0.57735027f * (fm->status.i_b_rec - fm->status.i_c_rec);""")

with open("src/fault_monitor.c", "w") as f:
    f.write(content)

with open("src/foc_core.c", "r") as f:
    content = f.read()

# Restore observer freeze!
content = content.replace("""    obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, fs.i_alpha_clean, fs.i_beta_clean, speed_est, dt_curr);
    frozen_theta = obs_mgr_get_theta(&obs_mgr);
    frozen_omega = obs_mgr_get_omega(&obs_mgr);""", """    if (fault.fault_isolation_timer == 0.0f) {
        if (fault.unresolved_fault_timer == 0.0f) {
            // Unfrozen and normal! But if it just unfroze, sync it!
            // Wait, we don't have a sync function. I can just update the observer.
            // Actually, we can just sync the SMO internal state directly if we have access, but we don't.
            // I will add a sync function!
        }
        obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, fs.i_alpha_clean, fs.i_beta_clean, speed_est, dt_curr);
        frozen_theta = obs_mgr_get_theta(&obs_mgr);
        frozen_omega = obs_mgr_get_omega(&obs_mgr);
    } else {
        frozen_theta += frozen_omega * dt_curr;
        if (frozen_theta > M_PI) frozen_theta -= 2.0f * M_PI;
        if (frozen_theta < -M_PI) frozen_theta += 2.0f * M_PI;
    }""")

with open("src/foc_core.c", "w") as f:
    f.write(content)

with open("src/smo.h", "r") as f:
    content = f.read()

content = content.replace("float smo_get_emf_magnitude(const SMO* obs);", "float smo_get_emf_magnitude(const SMO* obs);\nvoid smo_sync_current(SMO* obs, float i_alpha, float i_beta);")
with open("src/smo.h", "w") as f:
    f.write(content)

with open("src/smo.c", "r") as f:
    content = f.read()

content += """
void smo_sync_current(SMO* obs, float i_alpha, float i_beta) {
    obs->i_alpha_hat = i_alpha;
    obs->i_beta_hat = i_beta;
}
"""
with open("src/smo.c", "w") as f:
    f.write(content)
    
with open("src/observer_manager.h", "r") as f:
    content = f.read()

content = content.replace("float obs_mgr_get_emf_mag(const ObserverManager* mgr);", "float obs_mgr_get_emf_mag(const ObserverManager* mgr);\nvoid obs_mgr_sync_current(ObserverManager* mgr, float i_alpha, float i_beta);")
with open("src/observer_manager.h", "w") as f:
    f.write(content)

with open("src/observer_manager.c", "r") as f:
    content = f.read()
    
content += """
void obs_mgr_sync_current(ObserverManager* mgr, float i_alpha, float i_beta) {
    smo_sync_current(&mgr->smo, i_alpha, i_beta);
}
"""
with open("src/observer_manager.c", "w") as f:
    f.write(content)

