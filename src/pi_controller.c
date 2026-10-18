#include "pi_controller.h"
#include <stdbool.h>

void pi_init(PIController* pi, float kp, float ki, float min, float max) {
    pi->kp = kp; pi->ki = ki;
    pi->output_min = min; pi->output_max = max;
    pi->integral = 0.0f; pi->output = 0.0f;
}

void pi_reset(PIController* pi) {
    pi->integral = 0.0f; pi->output = 0.0f;
}

float pi_update(PIController* pi, float error, float dt) {
    float unsat = (error * pi->kp) + pi->integral;
    bool sat_high = (unsat >= pi->output_max && error > 0.0f);
    bool sat_low  = (unsat <= pi->output_min && error < 0.0f);
    if (!sat_high && !sat_low) {
        pi->integral += error * pi->ki * dt;
        if (pi->integral > pi->output_max) pi->integral = pi->output_max;
        if (pi->integral < pi->output_min) pi->integral = pi->output_min;
    }
    
    pi->output = (error * pi->kp) + pi->integral;
    if (pi->output > pi->output_max) pi->output = pi->output_max;
    if (pi->output < pi->output_min) pi->output = pi->output_min;
    
    return pi->output;
}

void pi_back_calculate(PIController* pi, float limited_output, float error) {
    float desired_integral = limited_output - (error * pi->kp);
    if (desired_integral > pi->output_max) desired_integral = pi->output_max;
    if (desired_integral < pi->output_min) desired_integral = pi->output_min;
    pi->integral = desired_integral;
    pi->output = limited_output;
}

