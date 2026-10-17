/*
 * sfun_foc_controller.c
 * 
 * Level-2 MATLAB/Simulink C MEX S-Function wrapping the Sensorless FOC
 * with Fault-Tolerant Sliding Mode & Flux Observers.
 *
 * Inputs (Port 0, Width 5):
 *   u[0..2] : [i_a, i_b, i_c]         - Measured phase currents (Amperes)
 *   u[3]    : [v_bus]                 - Inverter DC link voltage (Volts)
 *   u[4]    : [speed_ref_rpm]         - Mechanical speed reference (RPM)
 *
 * Outputs (Port 0, Width 17):
 *   y[0..2] : [duty_a, duty_b, duty_c]- Inverter duty cycles (0.0 to 1.0)
 *   y[3]    : theta_hat               - Estimated electrical angle (rad)
 *   y[4]    : omega_rpm_hat           - Estimated rotor speed (RPM)
 *   y[5]    : health_score            - System health score (0.0 to 1.0)
 *   y[6]    : control_mode            - Operating mode (0:ALIGN, 1:OPEN_LOOP, 2:CLOSED_LOOP, 3:DEGRADED, 4:LIMP, 5:SAFE_STOP)
 *   y[7..9] : [ia_rec, ib_rec, ic_rec]- Reconstructed currents (Amperes)
 *   y[10]   : fault_channel           - Fault channel (0:None, 1:A, 2:B, 3:C)
 *   y[11..12]: [i_d, i_q]             - Stator d-q currents (Amperes)
 *   y[13..14]: [emf_alpha, emf_beta]  - Estimated back-EMF (Volts)
 *   y[15..16]: [theta_smo, theta_flux]- Individual observer angle estimates (rad)
 */

#define S_FUNCTION_NAME  sfun_foc_controller
#define S_FUNCTION_LEVEL 2

#include "simstruc.h"
#include <math.h>
#include "../src/foc_api.h"

#define NUM_PARAMS 3
#define PARAM_MOTOR(S) ssGetSFcnParam(S, 0)
#define PARAM_CTRL(S)  ssGetSFcnParam(S, 1)
#define PARAM_TS(S)    ssGetSFcnParam(S, 2)

static void mdlInitializeSizes(SimStruct *S) {
    ssSetNumSFcnParams(S, NUM_PARAMS);
    if (ssGetNumSFcnParams(S) != ssGetSFcnParamsCount(S)) {
        return;
    }

    ssSetNumContStates(S, 0);
    ssSetNumDiscStates(S, 0);

    /* 1 Input Port of Width 5: [ia, ib, ic, Vbus, speed_ref_rpm] */
    if (!ssSetNumInputPorts(S, 1)) return;
    ssSetInputPortWidth(S, 0, 5);
    ssSetInputPortDirectFeedThrough(S, 0, 1);
    ssSetInputPortRequiredContiguous(S, 0, 1);

    /* 1 Output Port of Width 17 */
    if (!ssSetNumOutputPorts(S, 1)) return;
    ssSetOutputPortWidth(S, 0, 17);

    ssSetNumSampleTimes(S, 1);
    ssSetNumRWork(S, 0);
    ssSetNumIWork(S, 0);
    ssSetNumPWork(S, 0);
    ssSetNumModes(S, 0);
    ssSetNumNonsampledZCs(S, 0);

    ssSetOptions(S, SS_OPTION_EXCEPTION_FREE_CODE);
}

static void mdlInitializeSampleTimes(SimStruct *S) {
    real_T Ts = mxGetScalar(PARAM_TS(S));
    ssSetSampleTime(S, 0, Ts);
    ssSetOffsetTime(S, 0, 0.0);
}

#define MDL_START
#if defined(MDL_START)
static void mdlStart(SimStruct *S) {
    const real_T *pMotor = mxGetPr(PARAM_MOTOR(S));
    const real_T *pCtrl  = mxGetPr(PARAM_CTRL(S));

    MotorParams motor;
    motor.Rs    = (float)pMotor[0];
    motor.Ls    = (float)pMotor[1];
    motor.psi_f = (float)pMotor[2];
    motor.P     = (int)pMotor[3];
    motor.J     = (float)pMotor[4];
    motor.B     = (float)pMotor[5];
    motor.Vbus  = (float)pMotor[6];
    motor.In    = (float)pMotor[7];

    ControllerParams ctrl;
    ctrl.id_kp         = (float)pCtrl[0];
    ctrl.id_ki         = (float)pCtrl[1];
    ctrl.iq_kp         = (float)pCtrl[2];
    ctrl.iq_ki         = (float)pCtrl[3];
    ctrl.spd_kp        = (float)pCtrl[4];
    ctrl.spd_ki        = (float)pCtrl[5];
    ctrl.smo_k         = (float)pCtrl[6];
    ctrl.smo_h         = (float)pCtrl[7];
    ctrl.smo_lpf       = (float)pCtrl[8];
    ctrl.flux_wc       = (float)pCtrl[9];
    ctrl.pwm_freq      = (float)pCtrl[10];
    ctrl.ctrl_rate_curr = (float)pCtrl[10];
    ctrl.ctrl_rate_spd  = 1000.0f;
    ctrl.observer_select = 0;

    foc_init(&motor, &ctrl);
}
#endif

static void mdlOutputs(SimStruct *S, int_T tid) {
    const real_T *u = (const real_T*) ssGetInputPortRealSignal(S, 0);
    real_T *y       = ssGetOutputPortRealSignal(S, 0);

    const real_T *pMotor = mxGetPr(PARAM_MOTOR(S));
    int P = (int)pMotor[3];

    /* Speed reference in rad/s electrical */
    float spd_ref_rpm = (float)u[4];
    float spd_ref_rads_elec = spd_ref_rpm * (2.0f * (float)M_PI / 60.0f) * (float)P;
    foc_set_speed_ref(spd_ref_rads_elec);

    /* Form controller input */
    FocInput in;
    in.i_a   = (float)u[0];
    in.i_b   = (float)u[1];
    in.i_c   = (float)u[2];
    in.v_bus = (float)u[3];

    /* Execute 20kHz FOC step */
    FocOutput out = foc_tick(&in);

    /* y[0..2] : Duties */
    y[0]  = (real_T)out.duty_a;
    y[1]  = (real_T)out.duty_b;
    y[2]  = (real_T)out.duty_c;

    /* y[3..6] : Status */
    y[3]  = (real_T)out.theta_hat;
    y[4]  = (real_T)(out.omega_hat * (60.0f / (2.0f * (float)M_PI * (float)P)));
    y[5]  = (real_T)out.health_score;
    y[6]  = (real_T)out.control_mode;

    /* y[7..10] : Reconstructed currents & fault channel */
    y[7]  = (real_T)out.i_a_rec;
    y[8]  = (real_T)out.i_b_rec;
    y[9]  = (real_T)out.i_c_rec;
    y[10] = (real_T)out.fault_channel;

    /* y[11..14] : DQ currents & back-EMF */
    y[11] = (real_T)out.i_d;
    y[12] = (real_T)out.i_q;
    y[13] = (real_T)out.emf_alpha;
    y[14] = (real_T)out.emf_beta;

    /* y[15..16] : Observer detail */
    y[15] = (real_T)out.theta_hat_smo;
    y[16] = (real_T)out.theta_hat_flux;

    (void)tid;
}

static void mdlTerminate(SimStruct *S) {
    (void)S;
}

#ifdef MATLAB_MEX_FILE
#include "simulink.c"
#else
#include "cg_sfun.h"
#endif
