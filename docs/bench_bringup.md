# ESP32 Bench Bringup & Timing Profiling Guide

This checklist guides physical bringing-up, oscilloscope profiling, and CPU cycle-counter benchmarking of the sensorless FOC firmware on ESP32 hardware.

---

## 1. Hardware Pinout & Wiring

| ESP32 Pin | Function | Wiring / Probe Connection |
|:---|:---|:---|
| **GPIO 14** | `PIN_TIMING_BENCHMARK` | Connect Oscilloscope Channel 1 probe tip. |
| **GND** | Ground Reference | Connect Oscilloscope ground crocodile clip to ESP32 ground pin. |
| **GPIO 32** | `PIN_SENSE_A` (ADC1_CH4) | Inverter Phase A low-side current shunt amplifier output. |
| **GPIO 33** | `PIN_SENSE_B` (ADC1_CH5) | Inverter Phase B low-side current shunt amplifier output. |
| **GPIO 34** | `PIN_SENSE_C` (ADC1_CH6) | Inverter Phase C low-side current shunt amplifier output. |
| **GPIO 25** | `PIN_PWM_A` (LEDC CH0) | Gate driver high/low input Phase A (via dead-time buffer). |
| **GPIO 26** | `PIN_PWM_B` (LEDC CH1) | Gate driver high/low input Phase B (via dead-time buffer). |
| **GPIO 27** | `PIN_PWM_C` (LEDC CH2) | Gate driver high/low input Phase C (via dead-time buffer). |
| **GPIO 22** | `PIN_GATE_EN` | Inverter gate enable pin (active HIGH, pulled LOW on SAFE_STOP). |
| **GPIO 15** | `PIN_BTN_FAULT` | Pushbutton to GND for physical fault injection (active LOW). |
| **GPIO 4** | `PIN_SW_MODE` | Switch to GND: LOW = Virtual Motor SIL, HIGH = Physical ADC. |

---

## 2. Oscilloscope Measurement Procedure

1. **Probe Connection:**
   - Attach a standard 10x passive probe to **GPIO 14** (`PIN_TIMING_BENCHMARK`).
   - Clip probe ground to the nearest ESP32 GND pin with a short ground lead to minimize inductive ringing.
2. **Scope Trigger Settings:**
   - **Mode:** Normal / Edge trigger, Positive slope on Channel 1.
   - **Trigger Level:** +1.65 V (halfway between 0 V and 3.3 V).
   - **Timebase:** 10 µs / div or 20 µs / div (to view the 50 µs tick period and pulse width).
   - **Voltage Scale:** 1.0 V / div (0 V to 3.3 V rail).
3. **What to Observe:**
   - **Pulse Period:** Exactly 50.0 µs (20.0 kHz hardware timer interrupt frequency).
   - **Pulse HIGH Width:** Total task execution duration from ISR wake through ADC acquisition, FOC core calculation, PWM update, and telemetry export.
   - **Jitter:** Persistence mode on the oscilloscope reveals period jitter ($50.0\,\mu\text{s} \pm \Delta t$).

---

## 3. Cycle-Counter Software Benchmarking (`-DBENCH_TIMING`)

When an oscilloscope is unavailable, on-target timing can be measured with cycle-accurate precision using the ESP32 hardware cycle counter (`xthal_get_ccount` at 240 MHz, 4.167 ns per cycle).

### How to Build & Flash with `-DBENCH_TIMING`

#### Option A: PlatformIO Environment (Recommended)
```bash
# Build the benchmark environment
pio run -e esp32dev_bench

# Flash to connected ESP32 target
pio run -e esp32dev_bench -t upload

# Open serial monitor
pio device monitor -b 115200
```

#### Option B: Direct Flag in `platformio.ini`
Add `-DBENCH_TIMING` to `build_flags` under `[env:esp32dev]`:
```ini
build_flags = -I src -Wdouble-promotion -DBENCH_TIMING
```

---

## 4. Expected Serial Output

When `-DBENCH_TIMING` is active, the firmware prints telemetry at 10 Hz and a consolidated timing benchmark banner every 1 second (accumulated over 20,000 real-time control ticks):

```text
Speed_RPM:1800.0	Target_RPM:1800.0	Health_%:100.0	Mode:2	Ia_Amps:0.12
Speed_RPM:1800.0	Target_RPM:1800.0	Health_%:100.0	Mode:2	Ia_Amps:0.15

--- [BENCH_TIMING (20000 ticks / 1 s)] ---
ADC Read:      min:   X.XX us | avg:   X.XX us | max:   X.XX us
Control Step:  min:   X.XX us | avg:   X.XX us | max:   X.XX us
Total Task:    min:   X.XX us | avg:   X.XX us | max:   X.XX us
Wake Period:   min:  49.80 us | avg:  50.00 us | max:  50.20 us (Jitter: +/-0.20 us)
Overruns:      consecutive: 0 | total: 0
------------------------------------------
```

### Metrics Explained
- **`ADC Read`:** Duration of 3-channel SAR ADC1 register sampling (or virtual motor plant step).
- **`Control Step`:** Pure FOC computation time (`foc_tick`: Park/Clarke, SMO/flux observer, PI current loops, SVPWM, fault isolation).
- **`Total Task`:** Complete task activation window (matches GPIO 14 HIGH pulse width on scope).
- **`Wake Period & Jitter`:** Elapsed time between successive ISR task notifications ($50.0\,\mu\text{s}$ nominal).
- **`Overruns`:** Counts real-time deadline misses detected via `ulTaskNotifyTake` return value.

---

## 5. Submitting Evidence for Hardware Verification

In compliance with repository documentation integrity standards, all on-target timing metrics in `README.md` and `docs/results/final_report.md` are marked **`NOT MEASURED - requires hardware`** until raw validation artifacts are committed:

1. **For Oscilloscope Verification:**
   - Save the raw scope screen capture (`.png`) and/or CSV waveform export.
   - Commit the file to `docs/evidence/scope_gpio14_<date>.png`.
2. **For Serial Cycle-Counter Verification:**
   - Save the raw terminal session capture with `-DBENCH_TIMING` active.
   - Commit the log to `docs/evidence/bench_timing_<date>.log`.
3. Update the execution profile tables in `README.md` and `docs/results/final_report.md` with the verified numbers, citing the committed evidence artifact.
