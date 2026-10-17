#include <Arduino.h>

/* 
 * Sensorless FOC for ESP32 - Hardware Abstraction Layer (HAL) & Virtual Simulation
 * 
 * Runs a 20kHz hardware timer interrupt executing the sensorless FOC loop.
 * - Hardware Mode: Reads real phase currents from analog shunts.
 * - Simulation/Wokwi Mode (default or GPIO 4 LOW): Emulates PMSM motor physics 
 *   in real-time so the entire sensorless FOC loop can be fully tested in Wokwi
 *   without requiring a physical motor connected.
 * - Fault Injection: Press button on GPIO 15 to inject a sensor offset fault.
 * - Status LEDs: Green (Normal), Yellow (Degraded), Red (Limp / Safe Stop).
 */

extern "C" {
    #include "foc_api.h"
}

// ============================================================================
// HARDWARE PIN DEFINITIONS
// ============================================================================
#define PIN_PWM_A           25
#define PIN_PWM_B           26
#define PIN_PWM_C           27

#define PIN_SENSE_A         32
#define PIN_SENSE_B         33
#define PIN_SENSE_C         34

#define PIN_LED_NORMAL      18   // Green LED (Closed loop normal)
#define PIN_LED_DEGRADED    19   // Yellow LED (Fault isolated, 2-shunt fallback)
#define PIN_LED_FAULT       21   // Red LED (Limp / Safe Stop)
#define PIN_GATE_EN         22   // Gate driver hardware enable pin (Active HIGH)

#define PIN_BTN_FAULT       15   // Pushbutton: Inject sensor fault (Active LOW)
#define PIN_SW_MODE          4   // Switch: LOW = Virtual Motor, HIGH = Real ADC

// PWM Settings
#define PWM_FREQ            20000       // 20 kHz
#define PWM_RESOLUTION      11          // 11-bit resolution (0-2047)
#define PWM_MAX             ((1 << PWM_RESOLUTION) - 1)

// ADC Settings
#define ADC_MAX             4095.0f
#define ADC_VOLTAGE_REF     3.3f
#define SHUNT_RESISTOR      0.01f       // 10 mOhm
#define OPAMP_GAIN          50.0f
#define CURRENT_SCALE       (ADC_VOLTAGE_REF / (ADC_MAX * SHUNT_RESISTOR * OPAMP_GAIN))
#define ADC_OFFSET          2048.0f     // Center point (1.65V)

// ============================================================================
// GLOBALS & STATE
// ============================================================================
hw_timer_t *foc_timer = NULL;
portMUX_TYPE timerMux = portMUX_INITIALIZER_UNLOCKED;

// Shared telemetry
volatile float telemetry_theta = 0.0f;
volatile float telemetry_speed_rpm = 0.0f;
volatile float telemetry_health = 0.0f;
volatile int   telemetry_mode = 0;
volatile float telemetry_ia = 0.0f;
volatile float telemetry_ib = 0.0f;
volatile float telemetry_ic = 0.0f;

// Motor Parameters
static const float M_RS    = 0.5f;
static const float M_LS    = 1.0e-3f;
static const float M_PSI_F = 0.015f;
static const int   M_P     = 4;
static const float M_J     = 0.0001f;
static const float M_B     = 0.001f;
static const float M_VBUS  = 24.0f;

// Virtual Motor Plant States (for real-time simulation)
static float sim_id = 0.0f;
static float sim_iq = 0.0f;
static float sim_omega_m = 0.0f;
static float sim_theta_e = 0.0f;

// ============================================================================
// 20kHz HARDWARE TIMER ISR
// ============================================================================
void IRAM_ATTR foc_isr() {
    portENTER_CRITICAL_ISR(&timerMux);

    float ia = 0.0f;
    float ib = 0.0f;
    float ic = 0.0f;

    bool use_virtual_motor = (digitalRead(PIN_SW_MODE) == LOW);
    bool inject_fault = (digitalRead(PIN_BTN_FAULT) == LOW);

    if (use_virtual_motor) {
        // Compute phase currents from virtual PMSM state
        float c_th = cosf(sim_theta_e);
        float s_th = sinf(sim_theta_e);
        float i_alpha = sim_id * c_th - sim_iq * s_th;
        float i_beta  = sim_id * s_th + sim_iq * c_th;

        ia = i_alpha;
        ib = -0.5f * i_alpha + 0.8660254f * i_beta;
        ic = -0.5f * i_alpha - 0.8660254f * i_beta;

        // Interactive fault injection: inject +2.0A bias on Phase A when button pressed
        if (inject_fault) {
            ia += 2.0f;
        }
    } else {
        // Read external physical ADC shunts
        float a_raw = analogRead(PIN_SENSE_A);
        float b_raw = analogRead(PIN_SENSE_B);
        float c_raw = analogRead(PIN_SENSE_C);

        ia = (a_raw - ADC_OFFSET) * CURRENT_SCALE;
        ib = (b_raw - ADC_OFFSET) * CURRENT_SCALE;
        ic = (c_raw - ADC_OFFSET) * CURRENT_SCALE;
    }

    FocInput foc_in = {
        .i_a = ia,
        .i_b = ib,
        .i_c = ic,
        .v_bus = M_VBUS
    };

    // Execute FOC Control Step
    FocOutput foc_out = foc_tick(&foc_in);

    // Apply PWM outputs safely clamped to [0.0f, 1.0f], or disable gates on SAFE_STOP
    if (foc_out.gate_enable) {
        digitalWrite(PIN_GATE_EN, HIGH);
        float da = fmaxf(0.0f, fminf(1.0f, foc_out.duty_a));
        float db = fmaxf(0.0f, fminf(1.0f, foc_out.duty_b));
        float dc = fmaxf(0.0f, fminf(1.0f, foc_out.duty_c));
        ledcWrite(0, (uint32_t)(da * PWM_MAX));
        ledcWrite(1, (uint32_t)(db * PWM_MAX));
        ledcWrite(2, (uint32_t)(dc * PWM_MAX));
    } else {
        digitalWrite(PIN_GATE_EN, LOW);
        ledcWrite(0, 0);
        ledcWrite(1, 0);
        ledcWrite(2, 0);
    }

    if (use_virtual_motor) {
        // Advance virtual motor plant by dt = 50 microseconds
        float dt = 50.0e-6f;
        float v_a = foc_out.gate_enable ? (foc_out.duty_a - 0.5f) * M_VBUS : 0.0f;
        float v_b = foc_out.gate_enable ? (foc_out.duty_b - 0.5f) * M_VBUS : 0.0f;
        float v_c = foc_out.gate_enable ? (foc_out.duty_c - 0.5f) * M_VBUS : 0.0f;

        float v_alpha = (2.0f/3.0f) * (v_a - 0.5f*v_b - 0.5f*v_c);
        float v_beta  = 0.57735027f * (v_b - v_c);

        float c_th = cosf(sim_theta_e);
        float s_th = sinf(sim_theta_e);
        float v_d =  v_alpha * c_th + v_beta * s_th;
        float v_q = -v_alpha * s_th + v_beta * c_th;

        float omega_e = M_P * sim_omega_m;
        float di_d = (1.0f / M_LS) * (v_d - M_RS * sim_id + omega_e * M_LS * sim_iq);
        float di_q = (1.0f / M_LS) * (v_q - M_RS * sim_iq - omega_e * M_LS * sim_id - omega_e * M_PSI_F);

        float t_e = 1.5f * M_P * M_PSI_F * sim_iq;
        float domega_m = (1.0f / M_J) * (t_e - M_B * sim_omega_m);

        sim_id += di_d * dt;
        sim_iq += di_q * dt;
        sim_omega_m += domega_m * dt;
        sim_theta_e += omega_e * dt;

        while (sim_theta_e > 2.0f * (float)M_PI) sim_theta_e -= 2.0f * (float)M_PI;
        while (sim_theta_e < 0.0f)              sim_theta_e += 2.0f * (float)M_PI;
    }

    // Export telemetry
    telemetry_theta = foc_out.theta_hat;
    telemetry_speed_rpm = foc_out.omega_hat * (60.0f / (2.0f * (float)M_PI * M_P));
    telemetry_health = foc_out.health_score;
    telemetry_mode = foc_out.control_mode;
    telemetry_ia = ia;
    telemetry_ib = ib;
    telemetry_ic = ic;

    portEXIT_CRITICAL_ISR(&timerMux);
}

// ============================================================================
// SETUP
// ============================================================================
void setup() {
    Serial.begin(115200);
    delay(100);
    Serial.println("\n========================================================");
    Serial.println("  Sensorless FOC with Fault-Tolerant Observer on ESP32");
    Serial.println("  Virtual Hardware & Real-Time Simulation Enabled");
    Serial.println("========================================================");

    // Pin Modes
    pinMode(PIN_LED_NORMAL, OUTPUT);
    pinMode(PIN_LED_DEGRADED, OUTPUT);
    pinMode(PIN_LED_FAULT, OUTPUT);
    pinMode(PIN_GATE_EN, OUTPUT);
    pinMode(PIN_BTN_FAULT, INPUT_PULLUP);
    pinMode(PIN_SW_MODE, INPUT_PULLUP);

    digitalWrite(PIN_LED_NORMAL, LOW);
    digitalWrite(PIN_LED_DEGRADED, LOW);
    digitalWrite(PIN_LED_FAULT, LOW);
    digitalWrite(PIN_GATE_EN, HIGH);

    // Initialize Motor & Controller Parameters
    MotorParams motor = {
        .Rs = M_RS, .Ls = M_LS, .psi_f = M_PSI_F, .P = M_P,
        .J = M_J, .B = M_B, .Vbus = M_VBUS, .In = 5.0f
    };
    
    ControllerParams ctrl = {
        .id_kp = 6.28f, .id_ki = 3142.0f,
        .iq_kp = 6.28f, .iq_ki = 3142.0f,
        .spd_kp = 0.194f, .spd_ki = 17.4f,
        .smo_k = 20.0f, .smo_h = 0.5f, .smo_lpf = 50.0f,
        .flux_wc = 125.6f,
        .pwm_freq = 20000.0f, .ctrl_rate_curr = 20000.0f, .ctrl_rate_spd = 1000.0f
    };

    foc_init(&motor, &ctrl);
    foc_set_speed_ref(1800.0f * (2.0f * (float)M_PI / 60.0f) * M_P); // Target: 1800 RPM electrical

    // Initialize LEDC PWM
    ledcSetup(0, PWM_FREQ, PWM_RESOLUTION);
    ledcSetup(1, PWM_FREQ, PWM_RESOLUTION);
    ledcSetup(2, PWM_FREQ, PWM_RESOLUTION);

    ledcAttachPin(PIN_PWM_A, 0);
    ledcAttachPin(PIN_PWM_B, 1);
    ledcAttachPin(PIN_PWM_C, 2);

    analogReadResolution(12);

    // 20kHz Hardware Interrupt Timer
    foc_timer = timerBegin(0, 80, true); 
    timerAttachInterrupt(foc_timer, &foc_isr, true);
    timerAlarmWrite(foc_timer, 50, true); // 50 us = 20kHz
    timerAlarmEnable(foc_timer);

    Serial.println("[HAL] 20 kHz Hardware Timer ISR active.");
    Serial.println("[HAL] Virtual PMSM plant engaged. Ready for simulation.\n");
}

// ============================================================================
// MAIN LOOP (Telemetry & Status LEDs)
// ============================================================================
void loop() {
    portENTER_CRITICAL(&timerMux);
    float t_speed = telemetry_speed_rpm;
    float t_health = telemetry_health;
    int   t_mode = telemetry_mode;
    float t_ia = telemetry_ia;
    portEXIT_CRITICAL(&timerMux);

    // Update Status LEDs according to control mode
    // 0: ALIGN, 1: OPEN_LOOP_RAMP, 2: CLOSED_LOOP, 3: DEGRADED, 4: LIMP, 5: SAFE_STOP
    if (t_mode == 2) {
        digitalWrite(PIN_LED_NORMAL, HIGH);
        digitalWrite(PIN_LED_DEGRADED, LOW);
        digitalWrite(PIN_LED_FAULT, LOW);
    } else if (t_mode == 3) {
        digitalWrite(PIN_LED_NORMAL, LOW);
        digitalWrite(PIN_LED_DEGRADED, HIGH);
        digitalWrite(PIN_LED_FAULT, LOW);
    } else if (t_mode >= 4) {
        digitalWrite(PIN_LED_NORMAL, LOW);
        digitalWrite(PIN_LED_DEGRADED, LOW);
        digitalWrite(PIN_LED_FAULT, HIGH);
    } else {
        // Alignment or startup ramp: blink normal LED
        static bool blink_state = false;
        blink_state = !blink_state;
        digitalWrite(PIN_LED_NORMAL, blink_state ? HIGH : LOW);
        digitalWrite(PIN_LED_DEGRADED, LOW);
        digitalWrite(PIN_LED_FAULT, LOW);
    }

    // Telemetry streaming in Serial Plotter format
    Serial.print("Speed_RPM:"); Serial.print(t_speed, 1); Serial.print("\t");
    Serial.print("Target_RPM:1800.0\t");
    Serial.print("Health_%:");  Serial.print(t_health * 100.0f, 1); Serial.print("\t");
    Serial.print("Mode:");      Serial.print(t_mode); Serial.print("\t");
    Serial.print("Ia_Amps:");   Serial.println(t_ia, 2);

    delay(100);
}
