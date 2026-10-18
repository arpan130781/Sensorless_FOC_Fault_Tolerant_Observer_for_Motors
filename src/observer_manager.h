#pragma once
#include "smo.h"
#include "flux_observer.h"
#include "foc_api.h"

typedef struct {
    SMO smo;
    FluxObserver flux;
    int observer_select;
    
    float disagreement;
    float emf_mag;
    
    float smo_health;
    float flux_health;
    float confidence_smo;
    float confidence_flux;
    float health;
} ObserverManager;

void obs_mgr_init(ObserverManager* mgr, float Rs, float Ls, float psi_f, float k, float h, float lpf, float wc, int select);
void obs_mgr_reset(ObserverManager* mgr);
IRAM_ATTR void obs_mgr_update(ObserverManager* mgr, float v_alpha, float v_beta, float i_alpha, float i_beta, float omega_est, float dt);
IRAM_ATTR float obs_mgr_get_theta(ObserverManager* mgr);
IRAM_ATTR float obs_mgr_get_omega(ObserverManager* mgr);
