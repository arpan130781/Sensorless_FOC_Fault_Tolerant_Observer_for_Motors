#pragma once
#include <math.h>
#include "foc_api.h"

typedef struct {
    float i_alpha_hat, i_beta_hat;
    float emf_alpha, emf_beta;
    float theta_hat, omega_hat;
    float k, h, lpf_gain, Rs, Ls;
    float prev_theta;
    float prev_theta_raw;
    float dir;
} SMO;

void smo_init(SMO* smo, float Rs, float Ls, float k, float h, float lpf_gain);
void smo_reset(SMO* smo);
IRAM_ATTR void smo_update(SMO* smo, float v_alpha, float v_beta, float i_alpha, float i_beta, float dt);
IRAM_ATTR float smo_get_theta(const SMO* smo);
IRAM_ATTR float smo_get_omega(const SMO* smo);
IRAM_ATTR float smo_get_emf_magnitude(const SMO* smo);
