with open("src/foc_core.c", "r") as f:
    content = f.read()

# 1. Remove the old observer block
content = content.replace("""    static float frozen_theta = 0.0f;
    static float frozen_omega = 0.0f;

    if (fault.fault_isolation_timer == 0.0f) {
        obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, i_alpha, i_beta, speed_est, dt_curr);
        frozen_theta = obs_mgr_get_theta(&obs_mgr);
        frozen_omega = obs_mgr_get_omega(&obs_mgr);
    } else {
        frozen_theta += frozen_omega * dt_curr;
        if (frozen_theta > M_PI) frozen_theta -= 2.0f * M_PI;
        if (frozen_theta < -M_PI) frozen_theta += 2.0f * M_PI;
    }

    float obs_omega = frozen_omega;
    speed_est = obs_omega;
    
    float angle = frozen_theta;""", "")

# 2. Add it at the top, right before fault_update
obs_top = """
    // Raw Clarke for observer (before fault_update)
    float raw_i_alpha = (2.0f/3.0f) * (input->i_a - 0.5f*input->i_b - 0.5f*input->i_c);
    float raw_i_beta  = (2.0f/3.0f) * ((sqrtf(3.0f)/2.0f)*input->i_b - (sqrtf(3.0f)/2.0f)*input->i_c);

    static float frozen_theta = 0.0f;
    static float frozen_omega = 0.0f;

    if (fault.fault_isolation_timer == 0.0f) {
        obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, raw_i_alpha, raw_i_beta, speed_est, dt_curr);
        frozen_theta = obs_mgr_get_theta(&obs_mgr);
        frozen_omega = obs_mgr_get_omega(&obs_mgr);
    } else {
        frozen_theta += frozen_omega * dt_curr;
        if (frozen_theta > M_PI) frozen_theta -= 2.0f * M_PI;
        if (frozen_theta < -M_PI) frozen_theta += 2.0f * M_PI;
    }

    float obs_omega = frozen_omega;
    speed_est = obs_omega;
    float angle = frozen_theta;

    FaultStatus fs = fault_update(&fault, input->i_a, input->i_b, input->i_c, prev_v_alpha, prev_v_beta, angle, obs_omega, dt_curr);"""

content = content.replace("""    float obs_theta = obs_mgr_get_theta(&obs_mgr);
    FaultStatus fs = fault_update(&fault, input->i_a, input->i_b, input->i_c, prev_v_alpha, prev_v_beta, obs_theta, speed_est, dt_curr);""", obs_top)

with open("src/foc_core.c", "w") as f:
    f.write(content)
