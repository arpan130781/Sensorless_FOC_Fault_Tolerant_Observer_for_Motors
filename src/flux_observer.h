#pragma once

typedef struct {
    float flux_alpha, flux_beta;
    float theta_hat, omega_hat;
    float wc, Rs, Ls, psi_f;
    float prev_theta;
} FluxObserver;

void flux_obs_init(FluxObserver* obs, float Rs, float Ls, float psi_f, float wc);
void flux_obs_reset(FluxObserver* obs);
void flux_obs_update(FluxObserver* obs, float v_alpha, float v_beta, float i_alpha, float i_beta, float omega_hat, float dt);
float flux_obs_get_theta(const FluxObserver* obs);
float flux_obs_get_omega(const FluxObserver* obs);
