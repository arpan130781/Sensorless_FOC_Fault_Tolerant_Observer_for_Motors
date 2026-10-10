        static int log_pred_f = 0;
        if (fm->fault_isolation_timer > 0.0f && log_pred_f % 20 == 0 && fm->unisolated_timer < 0.010f) {
            printf("FULL: t=%f, v_al=%f, e_al=%f, i_al_pred=%f, lkg_th=%f\\n", fm->unisolated_timer, v_alpha, e_alpha, fm->i_alpha_pred, fm->lkg_theta);
        }
        if (fm->fault_isolation_timer > 0.0f) log_pred_f++;
