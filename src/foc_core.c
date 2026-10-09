#include "foc_api.h"
#include "pi_controller.h"
#include "smo.h"
#include "flux_observer.h"
#include "observer_manager.h"
#include "if_startup.h"
#include "handoff.h"
#include "fault_monitor.h"
#include <math.h>

static MotorParams motor;
static ControllerParams ctrl;

static PIController pi_id, pi_iq, pi_spd;
static ObserverManager obs_mgr;
static IFStartup startup;
static Handoff handoff;
static FaultMonitor fault;

static float current_omega_ref = 0.0f;
static float current_iq_ref = 0.0f;
static int tick_counter = 0;
static float dt_curr = 0.0f;
static float dt_spd = 0.0f;
static float safe_stop_timer = 0.0f;

void foc_init(const MotorParams* m, const ControllerParams* c) {
    motor = *m;
    ctrl = *c;
    dt_curr = 1.0f / ctrl.pwm_freq;
    dt_spd = 1.0f / ctrl.ctrl_rate_spd;
    foc_reset();
}

void foc_reset(void) {
    pi_init(&pi_id, ctrl.id_kp, ctrl.id_ki, -motor.Vbus, motor.Vbus);
    pi_init(&pi_iq, ctrl.iq_kp, ctrl.iq_ki, -motor.Vbus, motor.Vbus);
    pi_init(&pi_spd, ctrl.spd_kp, ctrl.spd_ki, -motor.In, motor.In);
    
    obs_mgr_init(&obs_mgr, motor.Rs, motor.Ls, motor.psi_f, ctrl.smo_k, ctrl.smo_h, ctrl.smo_lpf, ctrl.flux_wc, ctrl.observer_select);
    if_startup_init(&startup, 2.0f, 0.5f, 2.0f*M_PI*30.0f, 200.0f);
    handoff_init(&handoff);
    fault_init(&fault, motor.Rs, motor.Ls, motor.psi_f);
    
    current_omega_ref = 0.0f;
    current_iq_ref = 0.0f;
    tick_counter = 0;
    safe_stop_timer = 0.0f;
}

void foc_set_speed_ref(float omega_ref_rads) { current_omega_ref = omega_ref_rads; }
void foc_set_torque_ref(float iq_ref_A) { current_iq_ref = iq_ref_A; }

FocOutput foc_tick(const FocInput* input) {

    FocOutput out = {0};
    static float prev_v_alpha = 0.0f, prev_v_beta = 0.0f;
    static float speed_est = 0.0f;
    
    // Fault handling
    
    float obs_theta = obs_mgr_get_theta(&obs_mgr);
    FaultStatus fs = fault_update(&fault, input->i_a, input->i_b, input->i_c, prev_v_alpha, prev_v_beta, obs_theta, speed_est, dt_curr);

    
    float ia = fs.i_a_rec;
    float ib = fs.i_b_rec;
    float ic = fs.i_c_rec;
    
    // Clarke
    float i_alpha = (2.0f/3.0f) * (ia - 0.5f*ib - 0.5f*ic);
    float i_beta  = (2.0f/3.0f) * ((sqrtf(3.0f)/2.0f)*ib - (sqrtf(3.0f)/2.0f)*ic);
    
    // Previous v_alpha/beta applied
    
    // Observers
    obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, i_alpha, i_beta, speed_est, dt_curr);

    float obs_omega = obs_mgr_get_omega(&obs_mgr);
    
    speed_est = obs_omega;
    
    // Speed loop
    if (tick_counter == 0) {
        if (handoff.current_mode == CLOSED_LOOP || handoff.current_mode == DEGRADED || handoff.current_mode == LIMP) {
            float err = current_omega_ref - obs_omega;
            current_iq_ref = pi_update(&pi_spd, err, dt_spd);
            
            if (handoff.current_mode == DEGRADED) {
                if (current_iq_ref > motor.In * 0.8f) current_iq_ref = motor.In * 0.8f;
                if (current_iq_ref < -motor.In * 0.8f) current_iq_ref = -motor.In * 0.8f;
            } else if (handoff.current_mode == LIMP) {
                if (current_iq_ref > motor.In * 0.4f) current_iq_ref = motor.In * 0.4f;
                if (current_iq_ref < -motor.In * 0.4f) current_iq_ref = -motor.In * 0.4f;
            }
        }
    }
    tick_counter++;
    if (tick_counter >= (int)(ctrl.pwm_freq / ctrl.ctrl_rate_spd)) tick_counter = 0;
    
    // Startup
    float forced_theta, id_start, iq_start;
    bool done;
    if_startup_update(&startup, dt_curr, &forced_theta, &id_start, &iq_start, &done);
    
    // Handoff state machine
    int mode = handoff_update(&handoff, obs_mgr.health, obs_mgr.disagreement, obs_omega, done, fs.degradation_state, dt_curr);
    
    // Blending 
    float angle = 0.0f;
    float id_ref = 0.0f;
    float iq_ref = 0.0f;
    
    if (mode == ALIGN || mode == OPEN_LOOP) {
        angle = forced_theta;
        id_ref = id_start;
        iq_ref = iq_start;
    } else if (mode == CLOSED_LOOP || mode == DEGRADED || mode == LIMP) {
        angle = obs_theta;
        id_ref = 0.0f;
        iq_ref = current_iq_ref;
    } else { // SAFE_STOP
        angle = 0.0f;
        id_ref = 0.0f;
        iq_ref = 0.0f;
        safe_stop_timer += dt_curr;
    }
    
    // Park
    float c = cosf(angle);
    float s = sinf(angle);
    float id =  i_alpha * c + i_beta * s;
    float iq = -i_alpha * s + i_beta * c;
    
    // PI
    float vd = pi_update(&pi_id, id_ref - id, dt_curr);
    float vq = pi_update(&pi_iq, iq_ref - iq, dt_curr);
    
    if (mode == SAFE_STOP) { vd = 0.0f; vq = 0.0f; }
    
    // Inv Park
    float valpha = vd * c - vq * s;
    float vbeta  = vd * s + vq * c;
    
    prev_v_alpha = valpha;
    prev_v_beta = vbeta;
    
    // SVM
    float va = valpha;
    float vb = -0.5f*valpha + (sqrtf(3.0f)/2.0f)*vbeta;
    float vc = -0.5f*valpha - (sqrtf(3.0f)/2.0f)*vbeta;
    
    float vmin = fminf(va, fminf(vb, vc));
    float vmax = fmaxf(va, fmaxf(vb, vc));
    float vcom = -0.5f * (vmax + vmin);
    
    va += vcom; vb += vcom; vc += vcom;
    
    out.duty_a = (va / input->v_bus) + 0.5f;
    out.duty_b = (vb / input->v_bus) + 0.5f;
    out.duty_c = (vc / input->v_bus) + 0.5f;
    
    if (mode == SAFE_STOP) { out.duty_a = 0.5f; out.duty_b = 0.5f; out.duty_c = 0.5f; }
    
    out.theta_hat = angle;
    out.omega_hat = obs_omega;
    out.health_score = obs_mgr.health;
    out.control_mode = mode;
    out.i_d = id;
    out.i_q = iq;
    out.emf_alpha = obs_mgr.smo.emf_alpha;
    out.emf_beta = obs_mgr.smo.emf_beta;
    out.theta_hat_smo = obs_mgr.smo.theta_hat;
    out.theta_hat_flux = obs_mgr.flux.theta_hat;
    
    out.fault_channel = (fs.sensor_fault_a ? 1 : (fs.sensor_fault_b ? 2 : (fs.sensor_fault_c ? 3 : 0)));
    out.i_a_rec = ia; out.i_b_rec = ib; out.i_c_rec = ic;
    out.smo_health = obs_mgr.smo_health;
    out.flux_health = obs_mgr.flux_health;
    out.observer_disagreement = obs_mgr.disagreement;
    out.emf_mag = obs_mgr.emf_mag;
    out.confidence_smo = obs_mgr.confidence_smo;
    out.confidence_flux = obs_mgr.confidence_flux;
    
    return out;
}
