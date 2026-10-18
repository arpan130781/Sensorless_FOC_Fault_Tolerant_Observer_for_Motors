#pragma once
#include <stdbool.h>
#include "foc_api.h"

typedef struct {
    float I_start;
    float t_align;
    float omega_handoff;
    float ramp_rate;
    float timer;
    float omega_forced;
    float theta_forced;
    bool done;
} IFStartup;

void if_startup_init(IFStartup* s, float I_start, float t_align, float omega_handoff, float ramp_rate);
void if_startup_reset(IFStartup* s);
IRAM_ATTR void if_startup_update(IFStartup* s, float dt, float* out_theta, float* out_id, float* out_iq, bool* out_done);
