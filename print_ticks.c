        static int tick_cnt = 0;
        if (fault.unisolated_timer > 0.0f && tick_cnt < 10) {
            printf("TICK: t=%f, id=%f, iq=%f, vd=%f, vq=%f, val=%f, vbe=%f, th=%f\\n", fault.unisolated_timer, id, iq, vd, vq, valpha, vbeta, angle);
            tick_cnt++;
        }
