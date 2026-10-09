#pragma once
#include <stdbool.h>

typedef struct {
    int current_mode;
    float time_in_state;
    float blend_timer;
    float lkg_theta; // last known good theta
    float lkg_omega;
    float stall_timer;
} Handoff;

void handoff_init(Handoff* h);
void handoff_reset(Handoff* h);
int handoff_update(Handoff* h, float obs_health, float obs_disagree, float obs_omega, bool startup_done, int fault_degradation_state, float dt);
