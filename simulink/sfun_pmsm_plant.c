/*
 * sfun_pmsm_plant.c
 *
 * Level-2 Continuous-State C-MEX S-Function for 3-Phase Surface PMSM Motor
 *
 * Parameters:
 *   Param 0: MotorParamVec [Rs, Ls, psi_f, P, J, B, Vbus, In]
 *   Param 1: Tcog_mag (N*m)
 *
 * Inputs (Port 0, Width 5):
 *   u[0..2] : [duty_a, duty_b, duty_c] - Inverter duty cycles (0..1)
 *   u[3]    : T_load                   - External load torque (N*m)
 *   u[4]    : V_bus                    - Inverter DC link voltage (V)
 *
 * Outputs (Port 0, Width 9):
 *   y[0..2] : [i_a, i_b, i_c]          - Actual motor phase currents (A)
 *   y[3]    : theta_e                  - True electrical angle (rad, [0, 2pi))
 *   y[4]    : speed_rpm                - Rotor mechanical speed (RPM)
 *   y[5]    : omega_e                  - Electrical angular velocity (rad/s)
 *   y[6]    : T_e                      - Electromagnetic torque (N*m)
 *   y[7..8] : [i_d, i_q]               - Actual d-q currents (A)
 */

#define S_FUNCTION_NAME  sfun_pmsm_plant
#define S_FUNCTION_LEVEL 2

#include "simstruc.h"
#include <math.h>

#define NUM_PARAMS 2
#define PARAM_MOTOR(S) ssGetSFcnParam(S, 0)
#define PARAM_TCOG(S)  ssGetSFcnParam(S, 1)

#define NUM_CONT_STATES 4

static void mdlInitializeSizes(SimStruct *S) {
    ssSetNumSFcnParams(S, NUM_PARAMS);
    if (ssGetNumSFcnParams(S) != ssGetSFcnParamsCount(S)) {
        return;
    }

    ssSetNumContStates(S, NUM_CONT_STATES);
    ssSetNumDiscStates(S, 0);

    /* 1 Input Port of Width 5 */
    if (!ssSetNumInputPorts(S, 1)) return;
    ssSetInputPortWidth(S, 0, 5);
    ssSetInputPortDirectFeedThrough(S, 0, 0);
    ssSetInputPortRequiredContiguous(S, 0, 1);

    /* 1 Output Port of Width 9 */
    if (!ssSetNumOutputPorts(S, 1)) return;
    ssSetOutputPortWidth(S, 0, 9);

    ssSetNumSampleTimes(S, 1);
    ssSetNumRWork(S, 0);
    ssSetNumIWork(S, 0);
    ssSetNumPWork(S, 0);
    ssSetNumModes(S, 0);
    ssSetNumNonsampledZCs(S, 0);

    ssSetOptions(S, SS_OPTION_EXCEPTION_FREE_CODE);
}

static void mdlInitializeSampleTimes(SimStruct *S) {
    ssSetSampleTime(S, 0, CONTINUOUS_SAMPLE_TIME);
    ssSetOffsetTime(S, 0, 0.0);
}

#define MDL_INITIALIZE_CONDITIONS
#if defined(MDL_INITIALIZE_CONDITIONS)
static void mdlInitializeConditions(SimStruct *S) {
    real_T *x = ssGetContStates(S);
    x[0] = 0.0; /* i_d */
    x[1] = 0.0; /* i_q */
    x[2] = 0.0; /* omega_m */
    x[3] = 0.0; /* theta_e */
}
#endif

static void mdlOutputs(SimStruct *S, int_T tid) {
    real_T *x = ssGetContStates(S);
    real_T *y = ssGetOutputPortRealSignal(S, 0);

    const real_T *pMotor = mxGetPr(PARAM_MOTOR(S));
    real_T psi_f = pMotor[2];
    int_T  P     = (int_T)pMotor[3];

    real_T id = x[0];
    real_T iq = x[1];
    real_T omega_m = x[2];
    real_T theta_e = x[3];

    /* Normalize angle for output */
    real_T theta_norm = fmod(theta_e, 2.0 * M_PI);
    if (theta_norm < 0.0) theta_norm += 2.0 * M_PI;

    /* Inverse Park Transform */
    real_T cos_th = cos(theta_norm);
    real_T sin_th = sin(theta_norm);
    real_T i_alpha = id * cos_th - iq * sin_th;
    real_T i_beta  = id * sin_th + iq * cos_th;

    /* Inverse Clarke Transform */
    real_T ia = i_alpha;
    real_T ib = -0.5 * i_alpha + 0.8660254037844386 * i_beta;
    real_T ic = -0.5 * i_alpha - 0.8660254037844386 * i_beta;

    /* Torque and speed calculations */
    real_T Te = 1.5 * (real_T)P * psi_f * iq;
    real_T omega_e = (real_T)P * omega_m;
    real_T speed_rpm = omega_m * (60.0 / (2.0 * M_PI));

    /* y[0..2] : Phase currents */
    y[0] = ia;
    y[1] = ib;
    y[2] = ic;

    /* y[3..6] : Kinematics */
    y[3] = theta_norm;
    y[4] = speed_rpm;
    y[5] = omega_e;
    y[6] = Te;

    /* y[7..8] : d-q currents */
    y[7] = id;
    y[8] = iq;

    (void)tid;
}

#define MDL_DERIVATIVES
#if defined(MDL_DERIVATIVES)
static void mdlDerivatives(SimStruct *S) {
    real_T *x = ssGetContStates(S);
    real_T *dx = ssGetdX(S);

    const real_T *u = (const real_T*) ssGetInputPortRealSignal(S, 0);

    const real_T *pMotor = mxGetPr(PARAM_MOTOR(S));
    real_T Rs       = pMotor[0];
    real_T Ls       = pMotor[1];
    real_T psi_f    = pMotor[2];
    int_T  P        = (int_T)pMotor[3];
    real_T J        = pMotor[4];
    real_T B        = pMotor[5];
    real_T Tcog_mag = mxGetScalar(PARAM_TCOG(S));

    real_T Tload = u[3];
    real_T Vbus  = u[4];

    real_T id = x[0];
    real_T iq = x[1];
    real_T omega_m = x[2];
    real_T theta_e = x[3];

    /* Convert duty cycles to phase voltages */
    real_T va = (u[0] - 0.5) * Vbus;
    real_T vb = (u[1] - 0.5) * Vbus;
    real_T vc = (u[2] - 0.5) * Vbus;

    /* Clarke transform to stationary alpha-beta frame */
    real_T v_alpha = (2.0 / 3.0) * (va - 0.5 * vb - 0.5 * vc);
    real_T v_beta  = (1.0 / 1.732050807568877) * (vb - vc);

    /* Park transform to rotating d-q frame */
    real_T cos_th = cos(theta_e);
    real_T sin_th = sin(theta_e);
    real_T vd =  v_alpha * cos_th + v_beta * sin_th;
    real_T vq = -v_alpha * sin_th + v_beta * cos_th;

    real_T omega_e = (real_T)P * omega_m;

    /* d-q current derivatives */
    dx[0] = (1.0 / Ls) * (vd - Rs * id + omega_e * Ls * iq);
    dx[1] = (1.0 / Ls) * (vq - Rs * iq - omega_e * Ls * id - omega_e * psi_f);

    /* Torque & Mechanical dynamics */
    real_T Te = 1.5 * (real_T)P * psi_f * iq;
    real_T Tcog = Tcog_mag * sin(6.0 * theta_e);
    dx[2] = (1.0 / J) * (Te - Tload - Tcog - B * omega_m);

    /* Electrical angle derivative */
    dx[3] = omega_e;
}
#endif

static void mdlTerminate(SimStruct *S) {
    (void)S;
}

#ifdef MATLAB_MEX_FILE
#include "simulink.c"
#else
#include "cg_sfun.h"
#endif
