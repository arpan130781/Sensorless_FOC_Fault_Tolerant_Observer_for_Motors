        static int log_window = 0;
        if (tick_counter == 0 && current_omega_ref > 0) { // Just to not trigger at start
            static float time_acc = 0;
            time_acc += dt_curr * 20; // tick_counter is 20
            if (time_acc > 1.995f && time_acc < 2.005f) {
                printf("WIN: t=%f, ia=%f, ib=%f, ic=%f, ial=%f, ibe=%f, val=%f, vbe=%f, vd=%f, vq=%f\\n", time_acc, ia, ib, ic, i_alpha, i_beta, valpha, vbeta, vd, vq);
            }
        }
