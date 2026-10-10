                static int log_cnt2 = 0;
                if (log_cnt2 < 20) {
                    float E = i_a + i_b + i_c;
                    printf("eA=%f, eB=%f, eC=%f, sep=%f, E_acc=%f, E=%f\\n", fm->err_acc_A, fm->err_acc_B, fm->err_acc_C, separation, fm->E_acc, E);
                    log_cnt2++;
                }
