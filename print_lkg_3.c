    static float time_acc3 = 0;
    time_acc3 += dt;
    if (time_acc3 > 1.995f && time_acc3 < 2.010f && time_acc3 - (int)(time_acc3*1000)/1000.0f < 0.0001f) {
        printf("LKG3: t=%f, kf=%d, obs_th=%f, lkg_th=%f, lkg_om=%f, ial_pred=%f\\n", time_acc3, k_fault, theta, fm->lkg_theta, fm->lkg_omega, fm->i_alpha_pred);
    }
