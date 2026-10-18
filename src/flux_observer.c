#include "flux_observer.h"
#include <math.h>

void flux_obs_init(FluxObserver* obs, float Rs, float Ls, float psi_f, float wc) {
    obs->wc = wc; obs->Rs = Rs; obs->Ls = Ls; obs->psi_f = psi_f;
    flux_obs_reset(obs);
}

void flux_obs_reset(FluxObserver* obs) {
    obs->flux_alpha = obs->psi_f;
    obs->flux_beta = 0.0f;
    obs->theta_hat = 0.0f;
    obs->omega_hat = 0.0f;
    obs->prev_theta = 0.0f;
}

IRAM_ATTR void flux_obs_update(FluxObserver* obs, float v_alpha, float v_beta, float i_alpha, float i_beta, float omega_hat, float dt) {
    (void)omega_hat;
    // Current model reference
    float flux_alpha_i = obs->psi_f * cosf(obs->theta_hat) + obs->Ls * i_alpha;
    float flux_beta_i  = obs->psi_f * sinf(obs->theta_hat) + obs->Ls * i_beta;
    
    // Voltage model integration with crossover blending
    float dflux_alpha = (v_alpha - obs->Rs * i_alpha) + obs->wc * (flux_alpha_i - obs->flux_alpha);
    float dflux_beta  = (v_beta  - obs->Rs * i_beta)  + obs->wc * (flux_beta_i  - obs->flux_beta);
    
    obs->flux_alpha += dflux_alpha * dt;
    obs->flux_beta  += dflux_beta * dt;
    
    // Rotor flux = stator flux - Ls * I
    float rotor_flux_alpha = obs->flux_alpha - obs->Ls * i_alpha;
    float rotor_flux_beta  = obs->flux_beta  - obs->Ls * i_beta;
    
    obs->theta_hat = atan2f(rotor_flux_beta, rotor_flux_alpha);
    
    float dtheta = obs->theta_hat - obs->prev_theta;
    if (dtheta > (float)M_PI)  dtheta -= 2.0f * (float)M_PI;
    if (dtheta < -(float)M_PI) dtheta += 2.0f * (float)M_PI;
    obs->omega_hat += 200.0f * dt * ((dtheta / dt) - obs->omega_hat);
    
    obs->prev_theta = obs->theta_hat;
}

IRAM_ATTR float flux_obs_get_theta(const FluxObserver* obs) { return obs->theta_hat; }
IRAM_ATTR float flux_obs_get_omega(const FluxObserver* obs) { return obs->omega_hat; }
