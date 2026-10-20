#pragma once
#include <stdint.h>
#include <stdbool.h>

enum ControlMode { ALIGN=0, OPEN_LOOP=1, CLOSED_LOOP=2, DEGRADED=3, LIMP=4, SAFE_STOP=5, FAULT_DETECTED=6 };

typedef struct {
    float i_a, i_b, i_c, v_bus;
} FocInput;

typedef struct {
    float duty_a, duty_b, duty_c;
    bool gate_enable;
    float theta_hat, omega_hat, health_score;
    int control_mode;
    float i_d, i_q;
    float emf_alpha, emf_beta;
    float theta_hat_smo, theta_hat_flux;
    
    int fault_channel; // 0=None, 1=A, 2=B, 3=C
    float i_a_rec, i_b_rec, i_c_rec;
    float smo_health, flux_health, observer_disagreement, emf_mag;
    float confidence_smo, confidence_flux;
} FocOutput;

typedef struct {
    float Rs, Ls, psi_f;
    int P;
    float J, B, Vbus, In;
} MotorParams;

typedef struct {
    float id_kp, id_ki;
    float iq_kp, iq_ki;
    float spd_kp, spd_ki;
    float smo_k, smo_h, smo_lpf;
    float flux_wc;
    int observer_select; 
    float pwm_freq, ctrl_rate_curr, ctrl_rate_spd;
    float dead_time;
} ControllerParams;

#ifndef IRAM_ATTR
#if defined(ESP_PLATFORM) || defined(ARDUINO_ARCH_ESP32)
#include <esp_attr.h>
#else
#define IRAM_ATTR
#endif
#endif

void foc_init(const MotorParams* motor, const ControllerParams* ctrl);
IRAM_ATTR FocOutput foc_tick(const FocInput* input);
void foc_reset(void);
void foc_set_speed_ref(float omega_ref_rads);
void foc_set_torque_ref(float iq_ref_A);
ControllerParams foc_get_default_controller_params(void);

/* Library Clarke and Park transforms (IRAM_ATTR for zero cache-miss latency) */
IRAM_ATTR void clarke_transform(float a, float b, float c, float* alpha, float* beta);
IRAM_ATTR void park_transform(float alpha, float beta, float theta, float* d, float* q);
IRAM_ATTR void inv_park_transform(float d, float q, float theta, float* alpha, float* beta);
IRAM_ATTR void inv_clarke_transform(float alpha, float beta, float* a, float* b, float* c);

