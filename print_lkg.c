        static int log_lkg = 0;
        if (log_lkg < 5 && fm->unisolated_timer == 0.0f) {
            printf("LKG: k_fault=%d, uniso=%f, theta=%f, lkg_theta=%f\\n", k_fault, fm->unisolated_timer, theta, fm->lkg_theta);
            log_lkg++;
        }
