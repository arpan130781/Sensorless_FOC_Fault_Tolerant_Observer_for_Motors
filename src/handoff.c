#include "handoff.h"
#include "foc_api.h"
#include <math.h>

void handoff_init(Handoff* h) {
    handoff_reset(h);
}

void handoff_reset(Handoff* h) {
    h->current_mode = ALIGN;
    h->time_in_state = 0.0f;
    h->blend_timer = 0.0f;
    h->lkg_theta = 0.0f;
    h->lkg_omega = 0.0f;
    h->stall_timer = 0.0f;
}

int handoff_update(Handoff* h, float obs_health, float obs_disagree, float obs_omega, bool startup_done, int fault_degradation_state, float dt) {
    h->time_in_state += dt;
    
    // Save LKG when healthy
    if (obs_health > 0.6f && h->current_mode == CLOSED_LOOP) {
        h->lkg_omega = obs_omega;
    }
    
    if (fault_degradation_state == SAFE_STOP) {
        if (h->current_mode != SAFE_STOP) {
            h->current_mode = SAFE_STOP;
            h->time_in_state = 0;
        }
        return SAFE_STOP;
    }
    
    if (h->current_mode == SAFE_STOP) return SAFE_STOP;

    if (fault_degradation_state == CLOSED_LOOP && (h->current_mode == DEGRADED || h->current_mode == LIMP)) { h->current_mode = CLOSED_LOOP; h->time_in_state = 0; }
    else if (fault_degradation_state == DEGRADED && h->current_mode != DEGRADED) {
        h->current_mode = DEGRADED;
        h->time_in_state = 0;
    } else if (fault_degradation_state == LIMP && h->current_mode != LIMP) {
        h->current_mode = LIMP;
        h->time_in_state = 0;
    }

    if (h->current_mode == ALIGN) {
        if (h->time_in_state > 0.5f) {
            h->current_mode = OPEN_LOOP;
            h->time_in_state = 0;
        }
    } else if (h->current_mode == OPEN_LOOP) {
        if (startup_done && obs_health > 0.6f && obs_disagree < 1.5f && fabsf(obs_omega) > 20.0f) {
            h->current_mode = CLOSED_LOOP;
            h->time_in_state = 0;
        }
    } else if (h->current_mode == CLOSED_LOOP) {
        
        if (fabsf(obs_omega) < 10.0f) {
            h->stall_timer += dt;
            if (h->stall_timer > 0.30f) { // 300 ms true stall timeout
                h->current_mode = OPEN_LOOP; // Fallback to I/F
                h->time_in_state = 0;
                h->stall_timer = 0.0f;
            }
        } else {
            h->stall_timer = 0.0f;
        }
    }

    return h->current_mode;
}
