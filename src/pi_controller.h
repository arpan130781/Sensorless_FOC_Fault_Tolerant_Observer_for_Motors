#pragma once

typedef struct {
    float kp, ki;
    float integral;
    float output_min, output_max;
    float output;
} PIController;

void pi_init(PIController* pi, float kp, float ki, float min, float max);
void pi_reset(PIController* pi);
float pi_update(PIController* pi, float error, float dt);
