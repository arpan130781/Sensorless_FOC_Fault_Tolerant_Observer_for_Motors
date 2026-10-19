#include "fault_monitor.h"
#include "foc_api.h"
#include <math.h>
#include <stdio.h>

#define KCL_THRESH 0.3f
#define KCL_CONSECUTIVE_EXCEED_LIMIT 5  /* Require 5 consecutive exceedances (250 us @ 20 kHz) to reject noise bursts up to 4 samples */
#define KCL_SEVERE_THRESH 1.5f          /* Severe residual threshold for fast track (2 consecutive samples) */
#define ISOLATION_WINDOW 0.001f   /* 1 ms accumulation window */
#define RECOVERY_WINDOW 0.500f   /* 500 ms sustained healthy before clearing */

void fault_init(FaultMonitor* fm, float Rs, float Ls, float psi_f) {
    fm->Rs = Rs; fm->Ls = Ls; fm->psi_f = psi_f;
    fault_reset(fm);
}

void fault_reset(FaultMonitor* fm) {
    fm->status.sensor_fault_a = false;
    fm->status.sensor_fault_b = false;
    fm->status.sensor_fault_c = false;
    fm->status.i_a_rec = 0; fm->status.i_b_rec = 0; fm->status.i_c_rec = 0;
    fm->status.degradation_state = CLOSED_LOOP;
    fm->fault_latch_a = false; fm->fault_latch_b = false; fm->fault_latch_c = false;
    fm->clear_timer = 0; fm->fault_isolation_timer = 0; fm->unresolved_fault_timer = 0;
    fm->healthy_residual_timer = 0;
    fm->kcl_exceed_count = 0;
    fm->candidate_onset_channel = -1;
    fm->ambiguous_fault = false;
    fm->safe_stop_latched = false;
    fm->ambiguous_timer = 0.0f;
    fm->second_fault_timer = 0.0f;
    fm->post_latch_settling_timer = 0.0f;
    fm->consecutive_confident = 0; fm->best_channel = -1;
    fm->err_acc_A = 0; fm->err_acc_B = 0; fm->err_acc_C = 0; fm->err_acc_Amb = 0; fm->E_acc = 0;
    fm->i_alpha_pred = 0; fm->i_beta_pred = 0;
    fm->lkg_theta = 0.0f; fm->lkg_omega = 0.0f;
    fm->prev_i_a = 0; fm->prev_i_b = 0; fm->prev_i_c = 0;
    fm->stuck_count_a = 0; fm->stuck_count_b = 0; fm->stuck_count_c = 0;
    fm->onset_channel = -1;
}

IRAM_ATTR FaultStatus fault_update(FaultMonitor* fm, float i_a, float i_b, float i_c,
                         float v_alpha, float v_beta,
                         float theta, float omega,
                         int controller_mode, bool transient_inhibit, float dt)
{
    /* ---- Step / onset changes from previous healthy sample ---- */
    float dia = fabsf(i_a - fm->prev_i_a);
    float dib = fabsf(i_b - fm->prev_i_b);
    float dic = fabsf(i_c - fm->prev_i_c);

    /* ---- Stuck-sensor detection (only in closed-loop / degraded / limp modes) ---- */
    bool is_closed_mode = (controller_mode == CLOSED_LOOP || controller_mode == DEGRADED || controller_mode == LIMP);
    if (is_closed_mode) {
        if (dia < 0.0001f) fm->stuck_count_a++; else fm->stuck_count_a = 0;
        if (dib < 0.0001f) fm->stuck_count_b++; else fm->stuck_count_b = 0;
        if (dic < 0.0001f) fm->stuck_count_c++; else fm->stuck_count_c = 0;
    } else {
        fm->stuck_count_a = 0;
        fm->stuck_count_b = 0;
        fm->stuck_count_c = 0;
    }

    /* Post-latch transient settling countdown */
    if (fm->post_latch_settling_timer > 0.0f) {
        fm->post_latch_settling_timer -= dt;
        fm->second_fault_timer = 0.0f;
    }

    /* ---- KCL residual and debounce ---- */
    float E = i_a + i_b + i_c;
    bool k_sample_exceed = fabsf(E) > KCL_THRESH;
    if (k_sample_exceed) {
        fm->kcl_exceed_count++;
        if (fm->kcl_exceed_count == 1) {
            /* Record candidate single-sensor jump at initial exceedance tick */
            if (dia > 1.4f * dib && dia > 1.4f * dic && dia > 0.25f && dib < 0.35f && dic < 0.35f) {
                fm->candidate_onset_channel = 0;
            } else if (dib > 1.4f * dia && dib > 1.4f * dic && dib > 0.25f && dia < 0.35f && dic < 0.35f) {
                fm->candidate_onset_channel = 1;
            } else if (dic > 1.4f * dia && dic > 1.4f * dib && dic > 0.25f && dia < 0.35f && dib < 0.35f) {
                fm->candidate_onset_channel = 2;
            } else {
                fm->candidate_onset_channel = -1;
            }
        }
    } else {
        fm->kcl_exceed_count = 0;
        fm->candidate_onset_channel = -1;
    }
    bool k_fault = (fm->kcl_exceed_count >= KCL_CONSECUTIVE_EXCEED_LIMIT) ||
                   (fabsf(E) > KCL_SEVERE_THRESH && fm->kcl_exceed_count >= 2);

    /* ---- Last-known-good kinematics ---- */
    if (!k_sample_exceed && !fm->fault_latch_a && !fm->fault_latch_b && !fm->fault_latch_c && !fm->ambiguous_fault) {
        fm->lkg_theta = theta;
        fm->lkg_omega = omega;
    } else {
        fm->lkg_theta += fm->lkg_omega * dt;
        while (fm->lkg_theta > (float)M_PI)  fm->lkg_theta -= 2.0f * (float)M_PI;
        while (fm->lkg_theta < -(float)M_PI) fm->lkg_theta += 2.0f * (float)M_PI;
    }

    /* ---- Independent current predictor (open-loop observer) ---- */
    float e_alpha = -fm->psi_f * omega * sinf(theta);
    float e_beta  =  fm->psi_f * omega * cosf(theta);

    fm->i_alpha_pred += (dt / fm->Ls) * (v_alpha - fm->Rs * fm->i_alpha_pred - e_alpha);
    fm->i_beta_pred  += (dt / fm->Ls) * (v_beta  - fm->Rs * fm->i_beta_pred  - e_beta);

    int num_latched = (fm->fault_latch_a ? 1 : 0) +
                      (fm->fault_latch_b ? 1 : 0) +
                      (fm->fault_latch_c ? 1 : 0);

    /* Stabilise predictor with measured currents when healthy */
    if (num_latched == 0 && !k_sample_exceed && !fm->ambiguous_fault) {
        float i_alpha_meas = (2.0f/3.0f) * (i_a - 0.5f*i_b - 0.5f*i_c);
        float i_beta_meas  = 0.57735027f * (i_b - i_c);
        fm->i_alpha_pred += 5000.0f * dt * (i_alpha_meas - fm->i_alpha_pred);
        fm->i_beta_pred  += 5000.0f * dt * (i_beta_meas  - fm->i_beta_pred);
    } else if (num_latched == 1 && !fm->safe_stop_latched) {
        /* Track reconstructed currents in degraded mode while residual is healthy */
        float ia_v = fm->fault_latch_a ? -(i_b + i_c) : i_a;
        float ib_v = fm->fault_latch_b ? -(i_a + i_c) : i_b;
        float ic_v = fm->fault_latch_c ? -(i_a + i_b) : i_c;
        float i_alpha_rec = (2.0f/3.0f) * (ia_v - 0.5f*ib_v - 0.5f*ic_v);
        float i_beta_rec  = 0.57735027f * (ib_v - ic_v);
        float da = i_alpha_rec - fm->i_alpha_pred;
        float db = i_beta_rec - fm->i_beta_pred;
        float r_pred = sqrtf(da * da + db * db);
        float gain = 2000.0f;
        if (r_pred > 1.0f) {
            gain = 2000.0f / r_pred;
        }
        fm->i_alpha_pred += gain * dt * da;
        fm->i_beta_pred  += gain * dt * db;
    }

    /* ---- Clear fault-status flags for this tick ---- */
    fm->status.sensor_fault_a = false;
    fm->status.sensor_fault_b = false;
    fm->status.sensor_fault_c = false;

    /* If SAFE_STOP is latched, it remains permanently latched until foc_reset() */
    if (fm->safe_stop_latched) {
        fm->status.sensor_fault_a = fm->fault_latch_a;
        fm->status.sensor_fault_b = fm->fault_latch_b;
        fm->status.sensor_fault_c = fm->fault_latch_c;
        fm->status.i_a_rec = i_a; fm->status.i_b_rec = i_b; fm->status.i_c_rec = i_c;
        fm->status.degradation_state = SAFE_STOP;
        return fm->status;
    }

    /* ==== 1. Recovery / Clearing ==== */
    if (!fm->safe_stop_latched && (fm->fault_latch_a || fm->fault_latch_b || fm->fault_latch_c || fm->ambiguous_fault)) {
        if (k_sample_exceed) {
            fm->clear_timer = 0;
        } else {
            fm->clear_timer += dt;
            if (fm->clear_timer > RECOVERY_WINDOW) {
                fm->fault_latch_a = false;
                fm->fault_latch_b = false;
                fm->fault_latch_c = false;
                fm->ambiguous_fault = false;
                fm->clear_timer = 0;
                fm->consecutive_confident = 0;
                fm->best_channel = -1;
                fm->fault_isolation_timer = 0;
                fm->unresolved_fault_timer = 0;
                fm->healthy_residual_timer = 0;
                fm->ambiguous_timer = 0.0f;
                fm->second_fault_timer = 0.0f;
            }
        }
    }

    /* ==== 2. Fault Isolation ==== */
    if (!fm->fault_latch_a && !fm->fault_latch_b && !fm->fault_latch_c && !fm->ambiguous_fault) {
        /* Cancel isolation plus reset unresolved_fault_timer when the residual stays below threshold for a full window */
        if (fm->fault_isolation_timer > 0.0f) {
            if (!k_sample_exceed) {
                fm->healthy_residual_timer += dt;
                if (fm->healthy_residual_timer >= ISOLATION_WINDOW) {
                    /* Abort isolation */
                    fm->fault_isolation_timer = 0.0f;
                    fm->unresolved_fault_timer = 0.0f;
                    fm->healthy_residual_timer = 0.0f;
                    fm->consecutive_confident = 0;
                    fm->best_channel = -1;
                    fm->onset_channel = -1;
                    fm->candidate_onset_channel = -1;
                    fm->err_acc_A = 0; fm->err_acc_B = 0; fm->err_acc_C = 0; fm->err_acc_Amb = 0;
                    fm->E_acc = 0;
                }
            } else {
                fm->healthy_residual_timer = 0.0f;
            }
        }

        if (k_fault && fm->fault_isolation_timer == 0.0f) {
            /* Start a new isolation window */
            fm->fault_isolation_timer = 0.00001f;
            fm->unresolved_fault_timer = 0.00001f;
            fm->healthy_residual_timer = 0.0f;
            fm->err_acc_A = 0; fm->err_acc_B = 0; fm->err_acc_C = 0; fm->err_acc_Amb = 0;
            fm->E_acc = 0;

            /* Check for abrupt single-sensor jump at onset.
             * In an offset fault, only ONE channel jumps, while the other two have normal slew < 0.20 A.
             * In a stuck fault, the stuck channel does not jump, but the other channels rotate. */
            if (fm->stuck_count_a >= 8) {
                fm->onset_channel = 0;
            } else if (fm->stuck_count_b >= 8) {
                fm->onset_channel = 1;
            } else if (fm->stuck_count_c >= 8) {
                fm->onset_channel = 2;
            } else if (fm->candidate_onset_channel >= 0) {
                fm->onset_channel = fm->candidate_onset_channel;
            } else if (dia > 1.4f * dib && dia > 1.4f * dic && dia > 0.25f && dib < 0.35f && dic < 0.35f) {
                fm->onset_channel = 0;
            } else if (dib > 1.4f * dia && dib > 1.4f * dic && dib > 0.25f && dia < 0.35f && dic < 0.35f) {
                fm->onset_channel = 1;
            } else if (dic > 1.4f * dia && dic > 1.4f * dib && dic > 0.25f && dia < 0.35f && dib < 0.35f) {
                fm->onset_channel = 2;
            } else {
                fm->onset_channel = -1;
            }
        }


        if (fm->fault_isolation_timer > 0.0f) {
            fm->fault_isolation_timer += dt;
            fm->unresolved_fault_timer += dt;

            float ialph_meas = (2.0f/3.0f) * (i_a - 0.5f*i_b - 0.5f*i_c);
            float ibet_meas  = 0.57735027f * (i_b - i_c);

            /* Four hypotheses in alpha-beta space:
             * H_A: ia is faulty -> reconstruct ia = -(ib+ic)
             * H_B: ib is faulty -> reconstruct ib = -(ia+ic)
             * H_C: ic is faulty -> reconstruct ic = -(ia+ib)
             * H_Amb: common mode -> alpha-beta is unaffected
             */
            float ialph_A = -(i_b + i_c);
            float ibet_A  = ibet_meas;

            float ialph_B = i_a;
            float ibet_B  = 0.57735027f * (-(i_a + i_c) - i_c);

            float ialph_C = i_a;
            float ibet_C  = 0.57735027f * (i_b - (-(i_a + i_b)));

            float ialph_Amb = ialph_meas;
            float ibet_Amb  = ibet_meas;

            float da_A = ialph_A - fm->i_alpha_pred;
            float db_A = ibet_A  - fm->i_beta_pred;
            float err_A = sqrtf(da_A * da_A + db_A * db_A);

            float da_B = ialph_B - fm->i_alpha_pred;
            float db_B = ibet_B  - fm->i_beta_pred;
            float err_B = sqrtf(da_B * da_B + db_B * db_B);

            float da_C = ialph_C - fm->i_alpha_pred;
            float db_C = ibet_C  - fm->i_beta_pred;
            float err_C = sqrtf(da_C * da_C + db_C * db_C);

            float da_Amb = ialph_Amb - fm->i_alpha_pred;
            float db_Amb = ibet_Amb  - fm->i_beta_pred;
            float err_Amb = sqrtf(da_Amb * da_Amb + db_Amb * db_Amb);

            fm->err_acc_A += err_A * dt;
            fm->err_acc_B += err_B * dt;
            fm->err_acc_C += err_C * dt;
            fm->err_acc_Amb += err_Amb * dt;
            fm->E_acc += fabsf(E) * dt;
            float iso_win = (fm->stuck_count_a >= 10 || fm->stuck_count_b >= 10 || fm->stuck_count_c >= 10) ? 0.0005f : ISOLATION_WINDOW;
            if (fm->fault_isolation_timer >= iso_win) {
                float eA = fm->err_acc_A;
                float eB = fm->err_acc_B;
                float eC = fm->err_acc_C;
                float eAmb = fm->err_acc_Amb;

                /* Check if Ambiguous common-mode hypothesis is best (only when no authoritative single fault) */
                float min_single = fminf(eA, fminf(eB, eC));
                bool is_ambiguous = (eAmb < min_single * 0.7f) && (fm->E_acc > 0.0001f)
                                 && (fm->onset_channel < 0)
                                 && (fm->stuck_count_a < 10 && fm->stuck_count_b < 10 && fm->stuck_count_c < 10);

                int best = -1;
                bool confident = false;

                if (is_ambiguous) {
                    fm->ambiguous_fault = true;
                } else {
                    /* Authoritative identification:
                     * 1. Stuck sensor: >= 10 consecutive identical samples (0.5 ms)
                     * 2. Onset jump: clear single-channel jump matching KCL residual
                     */
                    if (fm->stuck_count_a >= 10) { best = 0; confident = true; }
                    else if (fm->stuck_count_b >= 10) { best = 1; confident = true; }
                    else if (fm->stuck_count_c >= 10) { best = 2; confident = true; }
                    else if (fm->onset_channel >= 0 && fm->E_acc > 0.0001f) {
                        best = fm->onset_channel;
                        confident = true;
                    } else {
                        best = 0;
                        float min_err = eA;
                        if (eB < min_err) { min_err = eB; best = 1; }
                        if (eC < min_err) { min_err = eC; best = 2; }

                        float second_err = 1e9f;
                        if (best == 0) second_err = fminf(eB, eC);
                        else if (best == 1) second_err = fminf(eA, eC);
                        else second_err = fminf(eA, eB);

                        float separation = second_err - min_err;
                        confident = (separation > 0.15f * fm->E_acc) && (fm->E_acc > 0.0001f);
                    }

                    /* Debounce: require 2 consecutive confident windows
                     * agreeing on the same channel before latching */
                    if (confident) {
                        if (best == fm->best_channel) {
                            fm->consecutive_confident++;
                        } else {
                            fm->best_channel = best;
                            fm->consecutive_confident = 1;
                        }
                    } else {
                        fm->consecutive_confident = 0;
                        fm->best_channel = -1;
                    }

                    int required_consecutive = (fm->onset_channel >= 0 ||
                                                fm->stuck_count_a >= 10 ||
                                                fm->stuck_count_b >= 10 ||
                                                fm->stuck_count_c >= 10) ? 1 : 2;

                    if (fm->consecutive_confident >= required_consecutive) {
                        /* Latch the identified faulty channel */
                        if (fm->best_channel == 0) fm->fault_latch_a = true;
                        else if (fm->best_channel == 1) fm->fault_latch_b = true;
                        else fm->fault_latch_c = true;
                        fm->ambiguous_fault = false;
                        fm->post_latch_settling_timer = 0.010f;
                    } else if (fm->unresolved_fault_timer > 0.015f) {
                        /* After 15ms without confident single isolation -> ambiguous */
                        fm->ambiguous_fault = true;
                    }
                }

                /* Reset accumulators for next window */
                fm->err_acc_A = 0; fm->err_acc_B = 0; fm->err_acc_C = 0; fm->err_acc_Amb = 0;
                fm->E_acc = 0;
                fm->fault_isolation_timer = 0.00001f;
            }
        }
    }

    /* Count currently latched channels */
    num_latched = (fm->fault_latch_a ? 1 : 0) +
                  (fm->fault_latch_b ? 1 : 0) +
                  (fm->fault_latch_c ? 1 : 0);

    /* Monitor remaining healthy channels for a second sensor fault when 1 channel is already degraded */
    if (num_latched == 1 && !fm->safe_stop_latched && fm->post_latch_settling_timer <= 0.0f && is_closed_mode) {
        if (transient_inhibit) {
            fm->second_fault_timer = 0.0f;
        } else {
            float ia_v = fm->fault_latch_a ? -(i_b + i_c) : i_a;
            float ib_v = fm->fault_latch_b ? -(i_a + i_c) : i_b;
            float ic_v = fm->fault_latch_c ? -(i_a + i_b) : i_c;
            float i_alpha_rec = (2.0f/3.0f) * (ia_v - 0.5f*ib_v - 0.5f*ic_v);
            float i_beta_rec  = 0.57735027f * (ib_v - ic_v);
            float da = i_alpha_rec - fm->i_alpha_pred;
            float db = i_beta_rec - fm->i_beta_pred;
            float r_pred = sqrtf(da * da + db * db);

            bool second_fault = false;
            int second_channel = -1;
            bool is_jump_or_stuck = false;

            if (fm->fault_latch_a) {
                bool stuck = (fm->stuck_count_b >= 10 || fm->stuck_count_c >= 10);
                bool jump = (dib > 1.0f || dic > 1.0f);
                bool res_bad = (r_pred > 1.2f);
                if (stuck || jump || res_bad) {
                    second_fault = true;
                    is_jump_or_stuck = (stuck || jump);
                    second_channel = (fm->stuck_count_b >= 10 || dib > 1.0f) ? 1 : 2;
                }
            } else if (fm->fault_latch_b) {
                bool stuck = (fm->stuck_count_a >= 10 || fm->stuck_count_c >= 10);
                bool jump = (dia > 1.0f || dic > 1.0f);
                bool res_bad = (r_pred > 1.2f);
                if (stuck || jump || res_bad) {
                    second_fault = true;
                    is_jump_or_stuck = (stuck || jump);
                    second_channel = (fm->stuck_count_a >= 10 || dia > 1.0f) ? 0 : 2;
                }
            } else if (fm->fault_latch_c) {
                bool stuck = (fm->stuck_count_a >= 10 || fm->stuck_count_b >= 10);
                bool jump = (dia > 1.0f || dib > 1.0f);
                bool res_bad = (r_pred > 1.2f);
                if (stuck || jump || res_bad) {
                    second_fault = true;
                    is_jump_or_stuck = (stuck || jump);
                    second_channel = (fm->stuck_count_a >= 10 || dia > 1.0f) ? 0 : 1;
                }
            }

            if (second_fault) {
                fm->second_fault_timer += dt;
                float required_time = is_jump_or_stuck ? 0.005f : 0.015f;
                if (fm->second_fault_timer >= required_time) {
                    if (second_channel == 0) fm->fault_latch_a = true;
                    else if (second_channel == 1) fm->fault_latch_b = true;
                    else fm->fault_latch_c = true;
                    fm->safe_stop_latched = true;
                }
            } else {
                fm->second_fault_timer = 0.0f;
            }
        }
    }

    /* Ambiguous fault timeout -> SAFE_STOP (persisting longer than 1.5 s) */
    if (fm->ambiguous_fault && !fm->safe_stop_latched) {
        fm->ambiguous_timer += dt;
        if (fm->ambiguous_timer >= 1.5f) {
            fm->safe_stop_latched = true;
        }
    } else if (!fm->ambiguous_fault) {
        fm->ambiguous_timer = 0.0f;
    }

    num_latched = (fm->fault_latch_a ? 1 : 0) +
                  (fm->fault_latch_b ? 1 : 0) +
                  (fm->fault_latch_c ? 1 : 0);

    /* ==== 3. Output Reconstruction & Mode ==== */
    if (fm->safe_stop_latched || num_latched >= 2) {
        fm->safe_stop_latched = true;
        fm->status.sensor_fault_a = fm->fault_latch_a;
        fm->status.sensor_fault_b = fm->fault_latch_b;
        fm->status.sensor_fault_c = fm->fault_latch_c;
        fm->status.i_a_rec = i_a; fm->status.i_b_rec = i_b; fm->status.i_c_rec = i_c;
        fm->status.degradation_state = SAFE_STOP;
    }
    else if (fm->fault_latch_a) {
        fm->status.sensor_fault_a = true;
        fm->status.i_a_rec = -(i_b + i_c);
        fm->status.i_b_rec = i_b;
        fm->status.i_c_rec = i_c;
        fm->status.degradation_state = DEGRADED;
    }
    else if (fm->fault_latch_b) {
        fm->status.sensor_fault_b = true;
        fm->status.i_a_rec = i_a;
        fm->status.i_b_rec = -(i_a + i_c);
        fm->status.i_c_rec = i_c;
        fm->status.degradation_state = DEGRADED;
    }
    else if (fm->fault_latch_c) {
        fm->status.sensor_fault_c = true;
        fm->status.i_a_rec = i_a;
        fm->status.i_b_rec = i_b;
        fm->status.i_c_rec = -(i_a + i_b);
        fm->status.degradation_state = DEGRADED;
    }
    else if (fm->ambiguous_fault) {
        fm->status.i_a_rec = i_a;
        fm->status.i_b_rec = i_b;
        fm->status.i_c_rec = i_c;
        fm->status.degradation_state = LIMP;
    }
    else {
        fm->status.i_a_rec = i_a;
        fm->status.i_b_rec = i_b;
        fm->status.i_c_rec = i_c;
        fm->status.degradation_state = CLOSED_LOOP;
    }

    fm->prev_i_a = i_a;
    fm->prev_i_b = i_b;
    fm->prev_i_c = i_c;

    return fm->status;
}
