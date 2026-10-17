#include "observer_manager.h"
#include <math.h>

void obs_mgr_init(ObserverManager* mgr, float Rs, float Ls, float psi_f, float k, float h, float lpf, float wc, int select) {
    smo_init(&mgr->smo, Rs, Ls, k, h, lpf);
    flux_obs_init(&mgr->flux, Rs, Ls, psi_f, wc);
    mgr->observer_select = select;
    obs_mgr_reset(mgr);
}

void obs_mgr_reset(ObserverManager* mgr) {
    smo_reset(&mgr->smo);
    flux_obs_reset(&mgr->flux);
    mgr->disagreement = 0.0f;
    mgr->emf_mag = 0.0f;
    mgr->smo_health = 1.0f;
    mgr->flux_health = 1.0f;
    mgr->confidence_smo = 1.0f;
    mgr->confidence_flux = 1.0f;
    mgr->health = 1.0f;
}

void obs_mgr_update(ObserverManager* mgr, float v_alpha, float v_beta, float i_alpha, float i_beta, float omega_est, float dt) {
    smo_update(&mgr->smo, v_alpha, v_beta, i_alpha, i_beta, dt);
    flux_obs_update(&mgr->flux, v_alpha, v_beta, i_alpha, i_beta, omega_est, dt);
    
    float theta_smo = smo_get_theta(&mgr->smo);
    float theta_flux = flux_obs_get_theta(&mgr->flux);
    
    float diff = theta_smo - theta_flux;
    diff = fmodf(diff + (float)M_PI, 2.0f * (float)M_PI);
    if (diff < 0.0f) diff += 2.0f * (float)M_PI;
    diff -= (float)M_PI;
    mgr->disagreement = fabsf(diff);
    mgr->emf_mag = smo_get_emf_magnitude(&mgr->smo);
    
    // Evaluate health separately
    mgr->smo_health = 1.0f;
    if (mgr->emf_mag < 0.05f) mgr->smo_health = 0.5f;
    
    mgr->flux_health = 1.0f;
    if (fabsf(omega_est) < 10.0f) mgr->flux_health = 0.5f;
    
    // Evaluate confidences
    mgr->confidence_smo = mgr->smo_health;
    mgr->confidence_flux = mgr->flux_health;
    
    // Reduce confidence based on disagreement
    float h_disagree = 1.0f - 0.5f * (mgr->disagreement / (float)M_PI);
    if (h_disagree < 0.0f) h_disagree = 0.0f;
    
    mgr->confidence_smo *= h_disagree;
    mgr->confidence_flux *= h_disagree;
    
    
    float inst_health = (mgr->confidence_smo > mgr->confidence_flux) ? mgr->confidence_smo : mgr->confidence_flux;
    mgr->health += 0.1f * (inst_health - mgr->health); // LPF

}

float obs_mgr_get_theta(ObserverManager* mgr) {
    if (mgr->observer_select == 1) return smo_get_theta(&mgr->smo);
    if (mgr->observer_select == 2) return flux_obs_get_theta(&mgr->flux);
    
    // Fusion
    float theta_smo = smo_get_theta(&mgr->smo);
    float theta_flux = flux_obs_get_theta(&mgr->flux);
    
    if (mgr->confidence_smo > mgr->confidence_flux * 1.5f) return theta_smo;
    if (mgr->confidence_flux > mgr->confidence_smo * 1.5f) return theta_flux;
    
    float w_smo = mgr->confidence_smo / (mgr->confidence_smo + mgr->confidence_flux + 1e-6f);
    float w_flux = 1.0f - w_smo;
    
    float s = w_smo * sinf(theta_smo) + w_flux * sinf(theta_flux);
    float c = w_smo * cosf(theta_smo) + w_flux * cosf(theta_flux);
    return atan2f(s, c);
}

float obs_mgr_get_omega(ObserverManager* mgr) {
    if (mgr->observer_select == 1) return smo_get_omega(&mgr->smo);
    if (mgr->observer_select == 2) return flux_obs_get_omega(&mgr->flux);
    
    if (mgr->confidence_smo > mgr->confidence_flux * 1.5f) return smo_get_omega(&mgr->smo);
    if (mgr->confidence_flux > mgr->confidence_smo * 1.5f) return flux_obs_get_omega(&mgr->flux);
    
    float w_smo = mgr->confidence_smo / (mgr->confidence_smo + mgr->confidence_flux + 1e-6f);
    float w_flux = 1.0f - w_smo;
    return w_smo * smo_get_omega(&mgr->smo) + w_flux * flux_obs_get_omega(&mgr->flux);
}
