    static int log_cnt = 0;
    if (fault.fault_isolation_timer > 0.0f && log_cnt < 20) {
        printf("lkg_th=%f, E_al=%f, obs_angle=%f, v_al=%f\\n", fault.lkg_theta, -fault.psi_f*fault.lkg_omega*sinf(fault.lkg_theta), angle, valpha);
        log_cnt++;
    }
