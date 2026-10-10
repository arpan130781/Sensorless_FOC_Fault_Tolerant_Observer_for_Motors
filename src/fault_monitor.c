#include "fault_monitor.h"
#include "foc_api.h"
#include <math.h>
#include <stdio.h>

#define KCL_THRESH 0.3f
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
    fm->clear_timer = 0; fm->fault_isolation_timer = 0;
    fm->ambiguous_fault = false;
    fm->consecutive_confident = 0; fm->best_channel = -1;
    fm->err_acc_A = 0; fm->err_acc_B = 0; fm->err_acc_C = 0; fm->E_acc = 0;
    fm->i_alpha_pred = 0; fm->i_beta_pred = 0;
    fm->prev_i_a = 0; fm->prev_i_b = 0; fm->prev_i_c = 0;
    fm->stuck_count_a = 0; fm->stuck_count_b = 0; fm->stuck_count_c = 0;
}

FaultStatus fault_update(FaultMonitor* fm, float i_a, float i_b, float i_c,
                         float v_alpha, float v_beta,
                         float theta, float omega, float dt)
{
    /* ---- Stuck-sensor detection ---- */
    if (fabsf(i_a - fm->prev_i_a) < 0.0001f) fm->stuck_count_a++; else fm->stuck_count_a = 0;
    if (fabsf(i_b - fm->prev_i_b) < 0.0001f) fm->stuck_count_b++; else fm->stuck_count_b = 0;
    if (fabsf(i_c - fm->prev_i_c) < 0.0001f) fm->stuck_count_c++; else fm->stuck_count_c = 0;
    fm->prev_i_a = i_a; fm->prev_i_b = i_b; fm->prev_i_c = i_c;

    /* ---- KCL residual ---- */
    float E = i_a + i_b + i_c;
    bool k_fault = fabsf(E) > KCL_THRESH;

    /* ---- Last-known-good kinematics ---- */
    if (!k_fault && !fm->fault_latch_a && !fm->fault_latch_b && !fm->fault_latch_c && !fm->ambiguous_fault) {
        fm->lkg_theta = theta;
        fm->lkg_omega = omega;
    } else {
        fm->lkg_theta += fm->lkg_omega * dt;
        if (fm->lkg_theta > M_PI)  fm->lkg_theta -= 2.0f * (float)M_PI;
        if (fm->lkg_theta < -M_PI) fm->lkg_theta += 2.0f * (float)M_PI;
    }

    /* ---- Independent current predictor (open-loop observer) ---- */
    float e_alpha = -fm->psi_f * fm->lkg_omega * sinf(fm->lkg_theta);
    float e_beta  =  fm->psi_f * fm->lkg_omega * cosf(fm->lkg_theta);

    fm->i_alpha_pred += (dt / fm->Ls) * (v_alpha - fm->Rs * fm->i_alpha_pred - e_alpha);
    fm->i_beta_pred  += (dt / fm->Ls) * (v_beta  - fm->Rs * fm->i_beta_pred  - e_beta);

    /* Stabilise predictor with measured currents only when healthy */
    if (!k_fault && !fm->fault_latch_a && !fm->fault_latch_b && !fm->fault_latch_c) {
        float i_alpha_meas = (2.0f/3.0f) * (i_a - 0.5f*i_b - 0.5f*i_c);
        float i_beta_meas  = 0.57735027f * (i_b - i_c);
        fm->i_alpha_pred += 5000.0f * dt * (i_alpha_meas - fm->i_alpha_pred);
        fm->i_beta_pred  += 5000.0f * dt * (i_beta_meas  - fm->i_beta_pred);
    }

    /* Predicted abc from predictor */
    float ia_pred = fm->i_alpha_pred;
    float ib_pred = -0.5f * fm->i_alpha_pred + 0.8660254f * fm->i_beta_pred;
    float ic_pred = -0.5f * fm->i_alpha_pred - 0.8660254f * fm->i_beta_pred;

    /* ---- Clear fault-status flags for this tick ---- */
    fm->status.sensor_fault_a = false;
    fm->status.sensor_fault_b = false;
    fm->status.sensor_fault_c = false;

    /* ==== 1. Recovery / Clearing ==== */
    if (fm->fault_latch_a || fm->fault_latch_b || fm->fault_latch_c || fm->ambiguous_fault) {
        if (k_fault) {
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
            }
        }
    }

    /* ==== 2. Fault Isolation ==== */
    if (!fm->fault_latch_a && !fm->fault_latch_b && !fm->fault_latch_c) {
        if (k_fault && fm->fault_isolation_timer == 0.0f) {
            /* Start a new isolation window */
            fm->fault_isolation_timer = 0.00001f;
            fm->err_acc_A = 0; fm->err_acc_B = 0; fm->err_acc_C = 0;
            fm->E_acc = 0;
        }

        if (fm->fault_isolation_timer > 0.0f) {
            fm->fault_isolation_timer += dt;

            /*
             * Three fault hypotheses:
             *   H_A: sensor A faulty → reconstruct ia = -(ib+ic)
             *   H_B: sensor B faulty → reconstruct ib = -(ia+ic)
             *   H_C: sensor C faulty → reconstruct ic = -(ia+ib)
             *
             * For each hypothesis, compute the reconstruction error vs predictor.
             * The correct hypothesis should produce the best match because the
             * reconstructed current removes the fault offset/bias.
             *
             * To reduce sensitivity to predictor drift (which affects all
             * hypotheses equally), we compute a RELATIVE metric: how much
             * better each hypothesis explains the data vs the others.
             */

            float ia_rec = -(i_b + i_c);
            float ib_rec = -(i_a + i_c);
            float ic_rec = -(i_a + i_b);

            /* Per-hypothesis total prediction error */
            float err_A = fabsf(ia_rec - ia_pred) + fabsf(i_b - ib_pred) + fabsf(i_c - ic_pred);
            float err_B = fabsf(i_a - ia_pred) + fabsf(ib_rec - ib_pred) + fabsf(i_c - ic_pred);
            float err_C = fabsf(i_a - ia_pred) + fabsf(i_b - ib_pred) + fabsf(ic_rec - ic_pred);

            fm->err_acc_A += err_A * dt;
            fm->err_acc_B += err_B * dt;
            fm->err_acc_C += err_C * dt;
            fm->E_acc += fabsf(E) * dt;

            if (fm->fault_isolation_timer >= ISOLATION_WINDOW) {
                float eA = fm->err_acc_A;
                float eB = fm->err_acc_B;
                float eC = fm->err_acc_C;

                /* Find best (minimum error) hypothesis */
                float min_err = eA; int best = 0;
                if (eB < min_err) { min_err = eB; best = 1; }
                if (eC < min_err) { min_err = eC; best = 2; }

                float second_err = 1e9f;
                if (best == 0) second_err = fminf(eB, eC);
                else if (best == 1) second_err = fminf(eA, eC);
                else second_err = fminf(eA, eB);

                /*
                 * Confidence criterion — two conditions must hold:
                 *
                 * 1. Separation: the gap between best and second-best must
                 *    be a meaningful fraction of the KCL residual integral.
                 *    For a single-channel offset of magnitude D on a balanced
                 *    motor, the correct hypothesis drops by ~|D| per tick
                 *    so the accumulated separation ≈ D*window. We require
                 *    separation > 0.3 * E_acc.
                 *
                 * 2. Ratio: second_err / min_err must be substantially > 1.
                 *    For an ambiguous (common-mode) fault, all hypotheses
                 *    have the same structure (one term −2D, two terms +D)
                 *    so the ratio ≈ 1. We require ratio > 1.3.
                 *
                 * Both must hold to declare confident isolation.
                 */
                float separation = second_err - min_err;
                bool confident = (separation > 0.3f * fm->E_acc)
                              && (fm->E_acc > 0.0001f)
                              && (min_err > 0.0f)
                              && (second_err > min_err * 1.3f);


                /* Stuck-sensor override: authoritative identification */
                if (fm->stuck_count_a > 20) { best = 0; confident = true; }
                else if (fm->stuck_count_b > 20) { best = 1; confident = true; }
                else if (fm->stuck_count_c > 20) { best = 2; confident = true; }

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

                if (fm->consecutive_confident >= 2) {
                    /* Latch the identified faulty channel */
                    if (fm->best_channel == 0) fm->fault_latch_a = true;
                    else if (fm->best_channel == 1) fm->fault_latch_b = true;
                    else fm->fault_latch_c = true;
                    fm->ambiguous_fault = false;
                } else if (fm->fault_isolation_timer > 0.020f) {
                    /* After 20ms without confident isolation → ambiguous */
                    fm->ambiguous_fault = true;
                }

                /* Reset accumulators for next window */
                fm->err_acc_A = 0; fm->err_acc_B = 0; fm->err_acc_C = 0;
                fm->E_acc = 0;
                fm->fault_isolation_timer = 0.00001f;
            }
        }
    }

    /* ==== 3. Output Reconstruction & Mode ==== */
    if (fm->fault_latch_a && fm->fault_latch_b && fm->fault_latch_c) {
        fm->status.sensor_fault_a = true;
        fm->status.sensor_fault_b = true;
        fm->status.sensor_fault_c = true;
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

    return fm->status;
}
