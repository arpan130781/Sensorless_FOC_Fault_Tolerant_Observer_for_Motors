        static int log_pred = 0;
        if (fm->fault_isolation_timer > 0.0f && log_pred < 20) {
            printf("PRED: t=%f, v_al=%f, e_al=%f, i_al_pred=%f, lkg_th=%f\\n", fm->unisolated_timer, v_alpha, e_alpha, fm->i_alpha_pred, fm->lkg_theta);
            log_pred++;
        }
