#include "smo.h"
#include <math.h>

static float sat(float x, float h) {
    if (x > h) return 1.0f;
    if (x < -h) return -1.0f;
    return x / h;
}

void smo_init(SMO* smo, float Rs, float Ls, float k, float h, float lpf_gain) {
    smo->k = k; smo->h = h; smo->lpf_gain = lpf_gain;
    smo->Rs = Rs; smo->Ls = Ls;
    smo_reset(smo);
}

void smo_reset(SMO* smo) {
    smo->i_alpha_hat = 0.0f; smo->i_beta_hat = 0.0f;
    smo->emf_alpha = 0.0f; smo->emf_beta = 0.0f;
    smo->theta_hat = 0.0f; smo->omega_hat = 0.0f;
    smo->prev_theta = 0.0f;
    smo->prev_theta_raw = 0.0f;
    smo->dir = 1.0f;
}

void smo_update(SMO* smo, float v_alpha, float v_beta, float i_alpha, float i_beta, float dt) {
    float err_alpha = smo->i_alpha_hat - i_alpha;
    float err_beta  = smo->i_beta_hat - i_beta;
    
    float z_alpha = smo->k * sat(err_alpha, smo->h);
    float z_beta  = smo->k * sat(err_beta, smo->h);
    
    smo->i_alpha_hat += dt * (1.0f / smo->Ls) * (v_alpha - smo->Rs * smo->i_alpha_hat - z_alpha);
    smo->i_beta_hat  += dt * (1.0f / smo->Ls) * (v_beta  - smo->Rs * smo->i_beta_hat  - z_beta);
    
    // LPF on Z to get EMF
    smo->emf_alpha += smo->lpf_gain * dt * (z_alpha - smo->emf_alpha);
    smo->emf_beta  += smo->lpf_gain * dt * (z_beta  - smo->emf_beta);
    
    // Direction tracking with hysteresis to prevent low-speed chattering/flips
    float prev_dir = smo->dir;
    if (smo->omega_hat > 5.0f) {
        smo->dir = 1.0f;
    } else if (smo->omega_hat < -5.0f) {
        smo->dir = -1.0f;
    }
    if (smo->dir != prev_dir) {
        smo->prev_theta_raw += (smo->dir > 0.0f) ? -(float)M_PI : (float)M_PI;
        if (smo->prev_theta_raw > (float)M_PI)  smo->prev_theta_raw -= 2.0f * (float)M_PI;
        if (smo->prev_theta_raw < -(float)M_PI) smo->prev_theta_raw += 2.0f * (float)M_PI;
    }
    
    // Angle estimation (Note PMSM convention)
    float e_alpha_norm = -smo->emf_alpha;
    float e_beta_norm  =  smo->emf_beta;
    if (smo->dir < 0.0f) {
        e_alpha_norm = -e_alpha_norm;
        e_beta_norm  = -e_beta_norm;
    }
    float theta_raw = atan2f(e_alpha_norm, e_beta_norm);
    
    // Omega estimation from raw back-EMF angle derivative (eliminates algebraic feedback loop)
    float dtheta_raw = theta_raw - smo->prev_theta_raw;
    if (dtheta_raw > (float)M_PI)  dtheta_raw -= 2.0f * (float)M_PI;
    if (dtheta_raw < -(float)M_PI) dtheta_raw += 2.0f * (float)M_PI;
    smo->prev_theta_raw = theta_raw;
    smo->omega_hat += 200.0f * dt * ((dtheta_raw / dt) - smo->omega_hat);
    
    // Phase compensation for LPF delay
    float phase_comp = atan2f(smo->omega_hat, smo->lpf_gain);
    smo->theta_hat = theta_raw + phase_comp;
    
    while (smo->theta_hat > (float)M_PI)  smo->theta_hat -= 2.0f * (float)M_PI;
    while (smo->theta_hat < -(float)M_PI) smo->theta_hat += 2.0f * (float)M_PI;
    
    smo->prev_theta = smo->theta_hat;
}

float smo_get_theta(const SMO* smo) { return smo->theta_hat; }
float smo_get_omega(const SMO* smo) { return smo->omega_hat; }
float smo_get_emf_magnitude(const SMO* smo) { return sqrtf(smo->emf_alpha * smo->emf_alpha + smo->emf_beta * smo->emf_beta); }
