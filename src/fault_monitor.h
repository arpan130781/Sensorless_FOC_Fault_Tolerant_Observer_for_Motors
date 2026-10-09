#pragma once
#include <stdbool.h>
#include "foc_api.h"

typedef struct {
    float health_score;
    int degradation_state;
    bool sensor_fault_a;
    bool sensor_fault_b;
    bool sensor_fault_c;
    float i_a_rec;
    float i_b_rec;
    float i_c_rec;
} FaultStatus;

typedef struct {
    float Rs, Ls, psi_f;
    float i_alpha_pred, i_beta_pred;
    float lkg_theta, lkg_omega;
    bool fault_latch_a, fault_latch_b, fault_latch_c;
    float clear_timer;
    float fault_isolation_timer;
    float err_acc_A, err_acc_B, err_acc_C;
    FaultStatus status;

    float prev_i_a, prev_i_b, prev_i_c;
    int stuck_count_a, stuck_count_b, stuck_count_c;

    bool ambiguous_fault;
    int consecutive_confident;
    int best_channel;
} FaultMonitor;

void fault_init(FaultMonitor* fm, float Rs, float Ls, float psi_f);
void fault_reset(FaultMonitor* fm);
FaultStatus fault_update(FaultMonitor* fm, float i_a, float i_b, float i_c, float v_alpha, float v_beta, float theta, float omega, float dt);
