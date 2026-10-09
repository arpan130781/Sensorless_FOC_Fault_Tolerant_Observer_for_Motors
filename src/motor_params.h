#pragma once
#include "foc_api.h"
#include <math.h>

#define M_RS 0.5f
#define M_LS 0.001f
#define M_PSI_F 0.015f
#define M_P 4
#define M_J 0.0001f
#define M_B 0.001f
#define M_VBUS 24.0f
#define M_IN 5.0f

#define C_KP_I 6.28f
#define C_KI_I 3142.0f
#define C_KP_W 0.0314f
#define C_KI_W 9.87f
#define C_SMO_K 37.7f
#define C_SMO_H 0.5f
#define C_SMO_LPF 50.0f // ~8Hz lpf on emf
#define C_FLUX_WC (2.0f * 3.14159265f * 20.0f)
#define C_PWM_FREQ 20000.0f
#define C_CTRL_CURR 20000.0f
#define C_CTRL_SPD 1000.0f

static inline MotorParams get_default_motor_params(void) {
    MotorParams p = {M_RS, M_LS, M_PSI_F, M_P, M_J, M_B, M_VBUS, M_IN};
    return p;
}

static inline ControllerParams get_default_controller_params(void) {
    ControllerParams p = {C_KP_I, C_KI_I, C_KP_I, C_KI_I, C_KP_W, C_KI_W, C_SMO_K, C_SMO_H, C_SMO_LPF, C_FLUX_WC, 0, C_PWM_FREQ, C_CTRL_CURR, C_CTRL_SPD};
    return p;
}
