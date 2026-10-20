#pragma once
#include "foc_api.h"

// ============================================================================
// CANONICAL MOTOR PARAMETERS (Single Source of Truth)
// ============================================================================
#define MOTOR_PARAM_RS          0.5f        // Stator resistance (Ohms)
#define MOTOR_PARAM_LS          0.001f      // Stator inductance (Henries)
#define MOTOR_PARAM_PSI_F       0.015f      // PM rotor flux linkage (V*s = Wb)
#define MOTOR_PARAM_POLE_PAIRS  4           // Pole pairs (P)
#define MOTOR_PARAM_J           0.0001f     // Rotor inertia (kg*m^2)
#define MOTOR_PARAM_B           0.001f      // Viscous damping (N*m*s/rad)
#define MOTOR_PARAM_VBUS        24.0f       // DC bus voltage (V)
#define MOTOR_PARAM_IN          5.0f        // Rated nominal current (A RMS)

// Backwards-compatible aliases
#define M_RS    MOTOR_PARAM_RS
#define M_LS    MOTOR_PARAM_LS
#define M_PSI_F MOTOR_PARAM_PSI_F
#define M_P     MOTOR_PARAM_POLE_PAIRS
#define M_J     MOTOR_PARAM_J
#define M_B     MOTOR_PARAM_B
#define M_VBUS  MOTOR_PARAM_VBUS
#define M_IN    MOTOR_PARAM_IN

// ============================================================================
// CANONICAL CONTROLLER PARAMETERS (Single Source of Truth)
// ============================================================================
#define CTRL_PARAM_ID_KP        6.28f       // D-axis current loop Kp
#define CTRL_PARAM_ID_KI        3142.0f     // D-axis current loop Ki
#define CTRL_PARAM_IQ_KP        6.28f       // Q-axis current loop Kp
#define CTRL_PARAM_IQ_KI        3142.0f     // Q-axis current loop Ki
#define CTRL_PARAM_SPD_KP       0.194f      // Speed loop Kp
#define CTRL_PARAM_SPD_KI       17.4f       // Speed loop Ki
#define CTRL_PARAM_SMO_K        20.0f       // Sliding mode observer gain K
#define CTRL_PARAM_SMO_H        0.5f        // SMO boundary layer thickness
#define CTRL_PARAM_SMO_LPF      50.0f       // SMO back-EMF filter cutoff (rad/s)
#define CTRL_PARAM_FLUX_WC      125.6f      // Flux observer cutoff (rad/s)
#define CTRL_PARAM_OBS_SELECT   0           // Default observer: 0=SMO
#define CTRL_PARAM_PWM_FREQ     20000.0f    // PWM & current loop frequency (Hz)
#define CTRL_PARAM_CTRL_CURR    20000.0f    // Current control execution rate (Hz)
#define CTRL_PARAM_CTRL_SPD     1000.0f     // Speed loop execution rate (Hz)

// Inverter dead-time compensation (s):
// [FIRMWARE DEFAULT IS SAFE: 0.0s UNCOMMISSIONED]
// Physical inverters drop phase voltage according to gate-driver switching dead-time:
//   V_dead = dead_time * pwm_freq * V_bus
// On uncommissioned hardware, dead_time must default to 0.0s to avoid zero-crossing
// over-compensation distortion (~19.3 deg error on 0V plant).
// To commission for target hardware, define build flag -DDEAD_TIME_COMMISSIONED_S=<value>
// (e.g. 1.0416667e-6f for 0.5V distortion at 20 kHz / 24V).
#ifdef DEAD_TIME_COMMISSIONED_S
#define CTRL_PARAM_DEAD_TIME    ((float)(DEAD_TIME_COMMISSIONED_S))
#elif defined(SIL_BUILD)
#define CTRL_PARAM_DEAD_TIME    0.0f
#else
#warning "Inverter dead-time is uncommissioned (DEAD_TIME_COMMISSIONED_S not defined). Defaulting dead_time to 0.0s for safe hardware operation."
#define CTRL_PARAM_DEAD_TIME    0.0f
#endif

static inline MotorParams get_default_motor_params(void) {
    MotorParams p = {
        .Rs = MOTOR_PARAM_RS,
        .Ls = MOTOR_PARAM_LS,
        .psi_f = MOTOR_PARAM_PSI_F,
        .P = MOTOR_PARAM_POLE_PAIRS,
        .J = MOTOR_PARAM_J,
        .B = MOTOR_PARAM_B,
        .Vbus = MOTOR_PARAM_VBUS,
        .In = MOTOR_PARAM_IN
    };
    return p;
}

static inline ControllerParams get_default_controller_params(void) {
    ControllerParams c = {
        .id_kp = CTRL_PARAM_ID_KP,
        .id_ki = CTRL_PARAM_ID_KI,
        .iq_kp = CTRL_PARAM_IQ_KP,
        .iq_ki = CTRL_PARAM_IQ_KI,
        .spd_kp = CTRL_PARAM_SPD_KP,
        .spd_ki = CTRL_PARAM_SPD_KI,
        .smo_k = CTRL_PARAM_SMO_K,
        .smo_h = CTRL_PARAM_SMO_H,
        .smo_lpf = CTRL_PARAM_SMO_LPF,
        .flux_wc = CTRL_PARAM_FLUX_WC,
        .observer_select = CTRL_PARAM_OBS_SELECT,
        .pwm_freq = CTRL_PARAM_PWM_FREQ,
        .ctrl_rate_curr = CTRL_PARAM_CTRL_CURR,
        .ctrl_rate_spd = CTRL_PARAM_CTRL_SPD,
        .dead_time = CTRL_PARAM_DEAD_TIME
    };
    return c;
}
