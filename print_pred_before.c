        static int log_pred_b = 0;
        if (fm->unisolated_timer == 0.0f && log_pred_b < 5) {
            printf("BEFORE: v_al=%f, e_al=%f, i_al_pred=%f, lkg_th=%f\\n", v_alpha, e_alpha, fm->i_alpha_pred, fm->lkg_theta);
            log_pred_b++;
        }
