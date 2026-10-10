                if (fm->unisolated_timer > 0.004f && log_cnt2 < 20) {
                    float ia_rec = -(i_b + i_c);
                    printf("T=5ms: i_a=%f, i_b=%f, i_c=%f\\n", i_a, i_b, i_c);
                    printf("       ia_pred=%f, ib_pred=%f, ic_pred=%f\\n", ia_pred, ib_pred, ic_pred);
                    printf("       ia_rec=%f\\n", ia_rec);
                    printf("       eB terms: |%f| + |%f| + |%f|\\n", i_a - ia_pred, -(i_a+i_c) - ib_pred, i_c - ic_pred);
                    log_cnt2 += 100; // print once
                }
