#include "if_startup.h"

void if_startup_init(IFStartup* s, float I_start, float t_align, float omega_handoff, float ramp_rate) {
    s->I_start = I_start;
    s->t_align = t_align;
    s->omega_handoff = omega_handoff;
    s->ramp_rate = ramp_rate;
    if_startup_reset(s);
}

void if_startup_reset(IFStartup* s) {
    s->timer = 0.0f;
    s->omega_forced = 0.0f;
    s->theta_forced = 0.0f;
    s->done = false;
}

IRAM_ATTR void if_startup_update(IFStartup* s, float dt, float* out_theta, float* out_id, float* out_iq, bool* out_done) {
    s->timer += dt;
    
    if (s->timer < s->t_align) {
        *out_id = s->I_start;
        *out_iq = 0.0f;
        s->omega_forced = 0.0f;
        s->theta_forced = 0.0f;
    } else {
        *out_id = 0.0f;
        *out_iq = s->I_start;
        s->omega_forced += s->ramp_rate * dt;
        if (s->omega_forced > s->omega_handoff) {
            s->omega_forced = s->omega_handoff;
            s->done = true;
        }
        s->theta_forced += s->omega_forced * dt;
        if (s->theta_forced > 2.0f * 3.14159265f) s->theta_forced -= 2.0f * 3.14159265f;
    }
    
    *out_theta = s->theta_forced;
    *out_done = s->done;
}
