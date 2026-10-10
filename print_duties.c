        static float time_acc2 = 0;
        time_acc2 += dt_curr;
        if (time_acc2 > 1.995f && time_acc2 < 2.005f) {
            printf("WIN2: t=%f, deg=%d, da=%f, db=%f, dc=%f\\n", time_acc2, fs.degradation_state, out.duty_a, out.duty_b, out.duty_c);
        }
