        static int log_lkg_2 = 0;
        static float time_acc2 = 0;
        time_acc2 += dt;
        if (time_acc2 > 1.995f && time_acc2 < 2.005f) {
            printf("LKG2: t=%f, kf=%d, obs_th=%f, lkg_th=%f, lkg_om=%f, eA=%f, eB=%f, eC=%f, sep=%f\\n", time_acc2, k_fault, theta, fm->lkg_theta, fm->lkg_omega, fm->err_acc_A, fm->err_acc_B, fm->err_acc_C, separation);
        }
