                static int log_cnt2 = 0;
                if (log_cnt2 < 20) {
                    printf("sc12 eA=%f, eB=%f, eC=%f, sep=%f, E_acc=%f, conf=%d\\n", fm->err_acc_A, fm->err_acc_B, fm->err_acc_C, separation, fm->E_acc, confident);
                    log_cnt2++;
                }
