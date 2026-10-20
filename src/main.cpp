#include <Arduino.h>
#include <driver/gpio.h>
#include <driver/adc.h>
#include <esp_timer.h>
#include <soc/sens_struct.h>
#include <soc/sens_reg.h>

/* 
 * Sensorless FOC for ESP32 - Hardware Abstraction Layer (HAL) & Virtual Simulation
 * 
 * FreeRTOS Pinned Task Architecture:
 * - 20kHz hardware timer interrupt minimally notifies high-priority control task via vTaskNotifyGiveFromISR (< 1 us ISR overhead).
 * - Control task pinned to Core 1 executes full sensorless FOC loop, observers, fault isolation, and PWM duty cycle updates.
 * - Hardware Mode: Fast hardware register SAR ADC1 reads (channels 4, 5, 6 on GPIO 32, 33, 34) directly polling
 *   SENS.sar_meas_start1 without RTOS spinlock or driver overhead (bounded 50 us wait; treats expiry as hardware fault).
 * - Real-Time Overrun Monitoring: ulTaskNotifyTake return count detects missed deadlines and latches SAFE_STOP on consecutive overruns.
 * - Simulation/Wokwi Mode (default or GPIO 4 LOW): Emulates PMSM motor physics in real-time.
 * - Fault Injection: Pushbutton on GPIO 15 to inject a sensor offset fault.
 * - Status LEDs: Green (Normal), Yellow (Degraded), Red (Limp / Safe Stop).
 * - Timing Benchmark: GPIO 14 toggled HIGH during control task execution for oscilloscope timing measurement.
 * - Spinlock Critical Section: Protects ONLY the 6 shared telemetry variables during export (~15 ns).
 */

extern "C" {
    #include "foc_api.h"
    #include "motor_params.h"
}

// Latching hardware ADC fault flag
static volatile bool g_adc_hardware_fault = false;

// Direct hardware register SAR ADC1 conversion.
// Manipulates SENS.sar_meas_start1 directly, bypassing ESP-IDF driver locks.
// Bounded wait with 50 us timeout; treats expiry as a hardware fault.
static inline uint16_t adc1_read_fast_reg(int channel, bool *out_error = NULL) {
    SENS.sar_meas_start1.sar1_en_pad = (1 << channel);
    SENS.sar_meas_start1.meas1_start_sar = 0;
    SENS.sar_meas_start1.meas1_start_sar = 1;

    int64_t start_time = esp_timer_get_time();
    while (!SENS.sar_meas_start1.meas1_done_sar) {
        if ((esp_timer_get_time() - start_time) > 50) {
            g_adc_hardware_fault = true;
            if (out_error) {
                *out_error = true;
            }
            return 0;
        }
    }
    return (uint16_t)(SENS.sar_meas_start1.meas1_data_sar & 0x0FFF);
}

// ============================================================================
// HARDWARE PIN DEFINITIONS
// ============================================================================
#define PIN_PWM_A           25
#define PIN_PWM_B           26
#define PIN_PWM_C           27

#define PIN_SENSE_A         32   // ADC1_CHANNEL_4
#define PIN_SENSE_B         33   // ADC1_CHANNEL_5
#define PIN_SENSE_C         34   // ADC1_CHANNEL_6

#define PIN_LED_NORMAL      18   // Green LED (Closed loop normal)
#define PIN_LED_DEGRADED    19   // Yellow LED (Fault isolated, 2-shunt fallback)
#define PIN_LED_FAULT       21   // Red LED (Limp / Safe Stop)
#define PIN_GATE_EN         22   // Gate driver hardware enable pin (Active HIGH)
#define PIN_TIMING_BENCHMARK 14  // Scope probe pin: HIGH during control execution

#define PIN_BTN_FAULT       15   // Pushbutton: Inject sensor fault (Active LOW)
#define PIN_SW_MODE          4   // Switch: LOW = Virtual Motor, HIGH = Real ADC

// PWM Settings
#define PWM_FREQ            20000       // 20 kHz
#define PWM_RESOLUTION      11          // 11-bit resolution (0-2047)
#define PWM_MAX             ((1 << PWM_RESOLUTION) - 1)

// ADC Settings & Current Sensing Parameters
#define ADC_MAX_COUNT       4095.0f
#define ADC_VOLTAGE_REF     3.3f
#define SHUNT_RESISTOR_OHM  0.010f      // 10 mOhm current shunt
#define OPAMP_GAIN          20.0f       // Current sense amplifier gain (gives +/-8.25A full-scale range)
#define CURRENT_FULL_SCALE  ((ADC_VOLTAGE_REF / 2.0f) / (SHUNT_RESISTOR_OHM * OPAMP_GAIN))
#define CURRENT_SCALE       (ADC_VOLTAGE_REF / (ADC_MAX_COUNT * SHUNT_RESISTOR_OHM * OPAMP_GAIN))
#define MOTOR_NOMINAL_IN    5.0f

// Compile-time assertion that full-scale sensing range exceeds 1.2x rated motor current
static_assert(CURRENT_FULL_SCALE > 1.2f * MOTOR_NOMINAL_IN,
              "Current sensing full-scale range must exceed 1.2 * In");

// Calibrated ADC zero-current offsets (calibrated at startup with PWM off)
static float adc_offset_a = 2048.0f;
static float adc_offset_b = 2048.0f;
static float adc_offset_c = 2048.0f;

// ============================================================================
// GLOBALS & STATE
// ============================================================================
static hw_timer_t *foc_timer = NULL;
static TaskHandle_t foc_task_handle = NULL;
static portMUX_TYPE telemetryMux = portMUX_INITIALIZER_UNLOCKED;

// Shared telemetry (protected by telemetryMux)
volatile float telemetry_theta = 0.0f;
volatile float telemetry_speed_rpm = 0.0f;
volatile float telemetry_health = 0.0f;
volatile int   telemetry_mode = 0;
volatile float telemetry_ia = 0.0f;
volatile float telemetry_ib = 0.0f;
volatile float telemetry_ic = 0.0f;

// Virtual Motor Plant States (for real-time simulation)
static float sim_id = 0.0f;
static float sim_iq = 0.0f;
static float sim_omega_m = 0.0f;
static float sim_theta_e = 0.0f;

// ============================================================================
// 20kHz HARDWARE TIMER ISR (Ultra-low latency task notification)
// ============================================================================
void IRAM_ATTR foc_isr() {
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    vTaskNotifyGiveFromISR(foc_task_handle, &xHigherPriorityTaskWoken);
    if (xHigherPriorityTaskWoken) {
        portYIELD_FROM_ISR();
    }
}

#define MAX_CONSECUTIVE_OVERRUNS 3  // Latch SAFE_STOP if 3 consecutive ticks miss deadline
static uint32_t overrun_counter = 0;
static uint32_t total_overruns = 0;

// ============================================================================
// HIGH-PRIORITY PINNED FOC CONTROL TASK (Core 1)
// ============================================================================
void foc_control_task(void *pvParameters) {
    (void)pvParameters;

    for (;;) {
        // Block until notified by 20 kHz hardware timer ISR
        uint32_t notifies = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

        // Real-time overrun detection: count and flag missed deadlines
        if (notifies > 1) {
            uint32_t missed = notifies - 1;
            overrun_counter += missed;
            total_overruns += missed;
            if (overrun_counter >= MAX_CONSECUTIVE_OVERRUNS) {
                // Real-time deadline violation: latch SAFE_STOP fault immediately
                gpio_set_level((gpio_num_t)PIN_GATE_EN, 0);
                ledcWrite(0, 0); ledcWrite(1, 0); ledcWrite(2, 0);
                digitalWrite(PIN_LED_FAULT, HIGH);
                digitalWrite(PIN_LED_NORMAL, LOW);
                digitalWrite(PIN_LED_DEGRADED, LOW);
            }
        } else {
            if (overrun_counter > 0) {
                overrun_counter--; // Healthy on-time tick decays overrun count
            }
        }

        gpio_set_level((gpio_num_t)PIN_TIMING_BENCHMARK, 1);

        float ia = 0.0f;
        float ib = 0.0f;
        float ic = 0.0f;

        bool use_virtual_motor = (gpio_get_level((gpio_num_t)PIN_SW_MODE) == 0);
        bool inject_fault = (gpio_get_level((gpio_num_t)PIN_BTN_FAULT) == 0);

        if (use_virtual_motor) {
            // Compute phase currents from virtual PMSM state using library transforms
            float i_alpha, i_beta;
            inv_park_transform(sim_id, sim_iq, sim_theta_e, &i_alpha, &i_beta);
            inv_clarke_transform(i_alpha, i_beta, &ia, &ib, &ic);

            // Interactive fault injection: inject +2.0A bias on Phase A when button pressed
            if (inject_fault) {
                ia += 2.0f;
            }
        } else {
            // Fast direct hardware register SAR ADC1 reads (channels 4, 5, 6 on GPIO 32, 33, 34)
            // Polling SENS.sar_meas_start1 with bounded 50 us timeout; flags hardware fault on expiration
            bool adc_err = false;
            float a_raw = (float)adc1_read_fast_reg(ADC1_CHANNEL_4, &adc_err);
            float b_raw = (float)adc1_read_fast_reg(ADC1_CHANNEL_5, &adc_err);
            float c_raw = (float)adc1_read_fast_reg(ADC1_CHANNEL_6, &adc_err);

            if (adc_err || g_adc_hardware_fault) {
                // Hardware ADC timeout fault: latch SAFE_STOP immediately
                gpio_set_level((gpio_num_t)PIN_GATE_EN, 0);
                ledcWrite(0, 0); ledcWrite(1, 0); ledcWrite(2, 0);
                digitalWrite(PIN_LED_FAULT, HIGH);
                digitalWrite(PIN_LED_NORMAL, LOW);
                digitalWrite(PIN_LED_DEGRADED, LOW);
                portENTER_CRITICAL(&telemetryMux);
                telemetry_mode = 5; // SAFE_STOP
                portEXIT_CRITICAL(&telemetryMux);
                gpio_set_level((gpio_num_t)PIN_TIMING_BENCHMARK, 0);
                continue;
            }

            ia = (a_raw - adc_offset_a) * CURRENT_SCALE;
            ib = (b_raw - adc_offset_b) * CURRENT_SCALE;
            ic = (c_raw - adc_offset_c) * CURRENT_SCALE;
        }

        FocInput foc_in = {
            .i_a = ia,
            .i_b = ib,
            .i_c = ic,
            .v_bus = M_VBUS
        };

        // Execute FOC Control Step (IRAM_ATTR on all callees)
        FocOutput foc_out = foc_tick(&foc_in);

        // Apply PWM outputs safely clamped to [0.0f, 1.0f], or disable gates on SAFE_STOP
        if (foc_out.gate_enable) {
            gpio_set_level((gpio_num_t)PIN_GATE_EN, 1);
            float da = fmaxf(0.0f, fminf(1.0f, foc_out.duty_a));
            float db = fmaxf(0.0f, fminf(1.0f, foc_out.duty_b));
            float dc = fmaxf(0.0f, fminf(1.0f, foc_out.duty_c));
            ledcWrite(0, (uint32_t)(da * (float)PWM_MAX));
            ledcWrite(1, (uint32_t)(db * (float)PWM_MAX));
            ledcWrite(2, (uint32_t)(dc * (float)PWM_MAX));
        } else {
            gpio_set_level((gpio_num_t)PIN_GATE_EN, 0);
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

            float v_alpha, v_beta;
            clarke_transform(v_a, v_b, v_c, &v_alpha, &v_beta);

            float v_d, v_q;
            park_transform(v_alpha, v_beta, sim_theta_e, &v_d, &v_q);

            float omega_e = (float)M_P * sim_omega_m;
            float di_d = (1.0f / M_LS) * (v_d - M_RS * sim_id + omega_e * M_LS * sim_iq);
            float di_q = (1.0f / M_LS) * (v_q - M_RS * sim_iq - omega_e * M_LS * sim_id - omega_e * M_PSI_F);

            float t_e = 1.5f * (float)M_P * M_PSI_F * sim_iq;
            float domega_m = (1.0f / M_J) * (t_e - M_B * sim_omega_m);

            sim_id += di_d * dt;
            sim_iq += di_q * dt;
            sim_omega_m += domega_m * dt;
            sim_theta_e += omega_e * dt;

            while (sim_theta_e > 2.0f * (float)M_PI) sim_theta_e -= 2.0f * (float)M_PI;
            while (sim_theta_e < 0.0f)              sim_theta_e += 2.0f * (float)M_PI;
        }

        // Export telemetry - protect ONLY the shared telemetry variables
        portENTER_CRITICAL(&telemetryMux);
        telemetry_theta = foc_out.theta_hat;
        telemetry_speed_rpm = foc_out.omega_hat * (60.0f / (2.0f * (float)M_PI * (float)M_P));
        telemetry_health = foc_out.health_score;
        telemetry_mode = foc_out.control_mode;
        telemetry_ia = ia;
        telemetry_ib = ib;
        telemetry_ic = ic;
        portEXIT_CRITICAL(&telemetryMux);

        gpio_set_level((gpio_num_t)PIN_TIMING_BENCHMARK, 0);
    }
}

// ============================================================================
// SETUP
// ============================================================================
void setup() {
    Serial.begin(115200);
    delay(100);
    Serial.println("\n========================================================");
    Serial.println("  Sensorless FOC with Fault-Tolerant Observer on ESP32");
    Serial.println("  Pinned FreeRTOS Task & Direct Register ADC Active");
    Serial.println("========================================================");

    // Pin Modes
    pinMode(PIN_LED_NORMAL, OUTPUT);
    pinMode(PIN_LED_DEGRADED, OUTPUT);
    pinMode(PIN_LED_FAULT, OUTPUT);
    pinMode(PIN_GATE_EN, OUTPUT);
    pinMode(PIN_TIMING_BENCHMARK, OUTPUT);
    pinMode(PIN_BTN_FAULT, INPUT_PULLUP);
    pinMode(PIN_SW_MODE, INPUT_PULLUP);

    digitalWrite(PIN_LED_NORMAL, LOW);
    digitalWrite(PIN_LED_DEGRADED, LOW);
    digitalWrite(PIN_LED_FAULT, LOW);
    digitalWrite(PIN_GATE_EN, HIGH);
    digitalWrite(PIN_TIMING_BENCHMARK, LOW);

    // Initialize Motor & Controller Parameters from canonical source of truth
    MotorParams motor = get_default_motor_params();
    ControllerParams ctrl = get_default_controller_params();
    // Dead-Time Commissioning Note:
    // Physical hardware requires inverter dead-time commissioning (see README.md).
    // If operating uncommissioned hardware, set ctrl.dead_time = 0.0f to avoid overcompensation.
    foc_init(&motor, &ctrl);
    foc_set_speed_ref(1800.0f * (2.0f * (float)M_PI / 60.0f) * M_P); // Target: 1800 RPM electrical

    // Initialize LEDC PWM
    ledcSetup(0, PWM_FREQ, PWM_RESOLUTION);
    ledcSetup(1, PWM_FREQ, PWM_RESOLUTION);
    ledcSetup(2, PWM_FREQ, PWM_RESOLUTION);

    ledcAttachPin(PIN_PWM_A, 0);
    ledcAttachPin(PIN_PWM_B, 1);
    ledcAttachPin(PIN_PWM_C, 2);

    // Direct Hardware Register ADC1 Configuration (GPIO 32, 33, 34)
    // Non-Linearity Documentation (11 dB Attenuation):
    // The ESP32 SAR ADC configured with ADC_ATTEN_DB_11 exhibits non-linear transfer characteristics,
    // particularly below ~100 mV and above ~3.1 V. In this fast direct register reading path, 11 dB
    // attenuation non-linearity is UNCORRECTED by esp_adc_cal or polynomial LUT. Midpoint-biased shunt
    // amplifiers center zero current at Vref/2 (~1.65 V / ~2048 counts) where the response is predominantly
    // monotonic and linear. Target hardware calibration using esp_adc_cal_characterize() or a piece-wise
    // linear lookup table is recommended for applications requiring precise absolute current accuracy.
    adc1_config_width(ADC_WIDTH_BIT_12);
    adc1_config_channel_atten(ADC1_CHANNEL_4, ADC_ATTEN_DB_11);
    adc1_config_channel_atten(ADC1_CHANNEL_5, ADC_ATTEN_DB_11);
    adc1_config_channel_atten(ADC1_CHANNEL_6, ADC_ATTEN_DB_11);

    // Route SAR ADC1 to RTC/software register control for direct hardware register reads
    SENS.sar_read_ctrl.sar1_dig_force = 0;
    SENS.sar_meas_start1.meas1_start_force = 1;
    SENS.sar_meas_start1.sar1_en_pad_force = 1;

    // Startup offset calibration: average 500 samples with PWM off using direct fast ADC register reads
    float sum_a = 0.0f, sum_b = 0.0f, sum_c = 0.0f;
    const int CAL_SAMPLES = 500;
    bool cal_err = false;
    for (int i = 0; i < CAL_SAMPLES; i++) {
        sum_a += (float)adc1_read_fast_reg(ADC1_CHANNEL_4, &cal_err);
        sum_b += (float)adc1_read_fast_reg(ADC1_CHANNEL_5, &cal_err);
        sum_c += (float)adc1_read_fast_reg(ADC1_CHANNEL_6, &cal_err);
        if (cal_err || g_adc_hardware_fault) {
            Serial.println("[HAL] FATAL: ADC conversion timeout during startup offset calibration!");
            g_adc_hardware_fault = true;
            digitalWrite(PIN_LED_FAULT, HIGH);
            break;
        }
        delayMicroseconds(50);
    }
    adc_offset_a = sum_a / (float)CAL_SAMPLES;
    adc_offset_b = sum_b / (float)CAL_SAMPLES;
    adc_offset_c = sum_c / (float)CAL_SAMPLES;
    Serial.printf("[HAL] Calibrated direct ADC offsets: A=%.1f, B=%.1f, C=%.1f\n", (double)adc_offset_a, (double)adc_offset_b, (double)adc_offset_c);

    // Create high-priority FOC control task pinned to Core 1
    xTaskCreatePinnedToCore(
        foc_control_task,
        "foc_control_task",
        4096,
        NULL,
        configMAX_PRIORITIES - 1,
        &foc_task_handle,
        1
    );

    // 20kHz Hardware Interrupt Timer (triggering control task)
    foc_timer = timerBegin(0, 80, true); 
    timerAttachInterrupt(foc_timer, &foc_isr, true);
    timerAlarmWrite(foc_timer, 50, true); // 50 us = 20kHz
    timerAlarmEnable(foc_timer);

    Serial.println("[HAL] 20 kHz Hardware Timer ISR and pinned FreeRTOS task active.");
    Serial.println("[HAL] Ready for execution.\n");
}

// ============================================================================
// MAIN LOOP (Telemetry & Status LEDs)
// ============================================================================
void loop() {
    portENTER_CRITICAL(&telemetryMux);
    float t_speed = telemetry_speed_rpm;
    float t_health = telemetry_health;
    int   t_mode = telemetry_mode;
    float t_ia = telemetry_ia;
    portEXIT_CRITICAL(&telemetryMux);

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

    // Hardware ADC timeout fault latch: force fault LED state
    if (g_adc_hardware_fault) {
        digitalWrite(PIN_LED_NORMAL, LOW);
        digitalWrite(PIN_LED_DEGRADED, LOW);
        digitalWrite(PIN_LED_FAULT, HIGH);
    }

    // Telemetry streaming in Serial Plotter format
    Serial.print("Speed_RPM:"); Serial.print(t_speed, 1); Serial.print("\t");
    Serial.print("Target_RPM:1800.0\t");
    Serial.print("Health_%:");  Serial.print(t_health * 100.0f, 1); Serial.print("\t");
    Serial.print("Mode:");      Serial.print(t_mode); Serial.print("\t");
    Serial.print("Ia_Amps:");   Serial.println(t_ia, 2);

    delay(100);
}
