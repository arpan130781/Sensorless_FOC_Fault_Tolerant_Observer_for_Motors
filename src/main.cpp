#include <Arduino.h>

/* 
 * Sensorless FOC for ESP32 - Hardware Abstraction Layer (HAL)
 * 
 * This sketch wraps the pure C FOC algorithm to run on the ESP32.
 * It sets up a 20kHz hardware timer interrupt to execute the control loop,
 * reads phase currents via ADC, and outputs duty cycles via LEDC (PWM).
 */

extern "C" {
    #include "foc_api.h"
}

// ============================================================================
// HARDWARE CONFIGURATION (Update these for your specific inverter/board!)
// ============================================================================
#define PIN_PWM_A 25
#define PIN_PWM_B 26
#define PIN_PWM_C 27

#define PIN_SENSE_A 32
#define PIN_SENSE_B 33
#define PIN_SENSE_C 34

// PWM Settings
#define PWM_FREQ 20000       // 20 kHz
#define PWM_RESOLUTION 11    // 11-bit resolution (0-2047)
#define PWM_MAX ((1 << PWM_RESOLUTION) - 1)

// ADC Settings (Assuming standard ESP32 12-bit ADC, 3.3V, inline shunts)
#define ADC_MAX 4095.0f
#define ADC_VOLTAGE_REF 3.3f
#define SHUNT_RESISTOR 0.01f // 10 mOhm
#define OPAMP_GAIN 50.0f
#define CURRENT_SCALE (ADC_VOLTAGE_REF / (ADC_MAX * SHUNT_RESISTOR * OPAMP_GAIN))
#define ADC_OFFSET 2048.0f   // Center voltage for 0 Amps

// ============================================================================
// GLOBALS & TIMER
// ============================================================================
hw_timer_t *foc_timer = NULL;
portMUX_TYPE timerMux = portMUX_INITIALIZER_UNLOCKED;

// Shared data for telemetry loop
volatile float telemetry_theta = 0.0f;
volatile float telemetry_speed = 0.0f;
volatile float telemetry_health = 0.0f;
volatile int   telemetry_mode = 0;

// ============================================================================
// 20kHz HARDWARE INTERRUPT (The core control loop)
// ============================================================================
void IRAM_ATTR foc_isr() {
    // Measure execution time
    uint32_t start_cycles = ESP.getCycleCount();

    portENTER_CRITICAL_ISR(&timerMux);

    // 1. Read ADC (Phase Currents)
    // NOTE: For true FOC, ADC reads must be synchronized to the PWM center!
    // This basic analogRead is a placeholder. For production, use the I2S or MCPWM sync triggers.
    float a_raw = analogRead(PIN_SENSE_A);
    float b_raw = analogRead(PIN_SENSE_B);
    float c_raw = analogRead(PIN_SENSE_C);

    FocInput foc_in = {0};
    foc_in.i_a = (a_raw - ADC_OFFSET) * CURRENT_SCALE;
    foc_in.i_b = (b_raw - ADC_OFFSET) * CURRENT_SCALE;
    foc_in.i_c = (c_raw - ADC_OFFSET) * CURRENT_SCALE;
    foc_in.v_bus = 24.0f; // Alternatively read from a VBUS ADC pin

    // 2. Execute FOC Math (The C code)
    FocOutput foc_out = foc_tick(&foc_in);

    // 3. Write PWM Duty Cycles
    // foc_out.duty_x is [0.0, 1.0]. Convert to hardware timer ticks.
    ledcWrite(0, (uint32_t)(foc_out.duty_a * PWM_MAX));
    ledcWrite(1, (uint32_t)(foc_out.duty_b * PWM_MAX));
    ledcWrite(2, (uint32_t)(foc_out.duty_c * PWM_MAX));

    // 4. Safely export data to the non-blocking main loop
    telemetry_theta = foc_out.theta_hat;
    telemetry_speed = foc_out.omega_hat;
    telemetry_health = foc_out.health_score;
    telemetry_mode = foc_out.control_mode;

    portEXIT_CRITICAL_ISR(&timerMux);
}

// ============================================================================
// SETUP
// ============================================================================
void setup() {
    Serial.begin(115200);
    Serial.println("Starting Sensorless FOC (Fault-Tolerant) on ESP32...");

    // 1. Initialize FOC Parameters
    MotorParams motor = {
        .Rs = 0.5f, .Ls = 1.0e-3f, .psi_f = 0.015f, .P = 4,
        .J = 0.0001f, .B = 0.001f, .Vbus = 24.0f, .In = 5.0f
    };
    
    ControllerParams ctrl = {
        .id_kp = 6.28f, .id_ki = 3142.0f,
        .iq_kp = 6.28f, .iq_ki = 3142.0f,
        .spd_kp = 0.194f, .spd_ki = 17.4f,
        .smo_k = 37.7f, .smo_h = 0.5f, .smo_lpf = 50.0f,
        .flux_wc = 125.6f,
        .pwm_freq = 20000.0f, .ctrl_rate_curr = 20000.0f, .ctrl_rate_spd = 1000.0f
    };

    foc_init(&motor, &ctrl);
    foc_set_speed_ref(100.0f); // Target speed in rad/s (~950 RPM)

    // 2. Initialize Hardware PWM (LEDC)
    ledcSetup(0, PWM_FREQ, PWM_RESOLUTION);
    ledcSetup(1, PWM_FREQ, PWM_RESOLUTION);
    ledcSetup(2, PWM_FREQ, PWM_RESOLUTION);

    ledcAttachPin(PIN_PWM_A, 0);
    ledcAttachPin(PIN_PWM_B, 1);
    ledcAttachPin(PIN_PWM_C, 2);

    // 3. Initialize ADC
    analogReadResolution(12);

    // 4. Start 20kHz Hardware Timer Interrupt
    // ESP32 timer counts in microseconds (1MHz clock -> prescaler 80 on 80MHz APB)
    foc_timer = timerBegin(0, 80, true); 
    timerAttachInterrupt(foc_timer, &foc_isr, true);
    timerAlarmWrite(foc_timer, 50, true); // 50 microseconds = 20kHz
    timerAlarmEnable(foc_timer);
    
    Serial.println("FOC Interrupt Started at 20kHz.");
}

// ============================================================================
// MAIN LOOP (Telemetry & Commands)
// ============================================================================
void loop() {
    // Print telemetry to Serial Plotter at 10 Hz
    portENTER_CRITICAL(&timerMux);
    float t_theta = telemetry_theta;
    float t_speed = telemetry_speed;
    float t_health = telemetry_health;
    int   t_mode = telemetry_mode;
    portEXIT_CRITICAL(&timerMux);

    Serial.print("Speed_rads:"); Serial.print(t_speed); Serial.print(" ");
    Serial.print("Health:"); Serial.print(t_health * 100.0f); Serial.print(" ");
    Serial.print("Mode:"); Serial.println(t_mode);

    delay(100);
}
