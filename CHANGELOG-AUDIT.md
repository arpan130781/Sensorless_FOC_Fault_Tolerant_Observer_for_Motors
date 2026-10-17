# Audit and Remediation Changelog (Tasks 1-8)

This changelog records the defects identified, mathematical and software root causes, implemented engineering fixes, and before/after verification metrics across all 8 tasks of the sensorless FOC audit.

---

## Task 1: Fault Monitor Debounce and Isolation Abort

### Defects Identified
- **Single-Sample False Trip:** In `src/fault_monitor.c`, the Kirchhoff's Current Law ($\sum i = 0$) check was a single-sample threshold comparison. A single corrupted sample (+0.5 A spike on any phase at $t=2.0\text{ s}$ during 2000 RPM closed-loop operation) triggered the fault isolation sequence.
- **Dead Isolation Abort:** In `src/fault_monitor.c`, when the current residual cleared, the isolation timer was never aborted or cleared. After 15 ms of healthy residuals following a single transient spike, the monitor timed out and declared an ambiguous fault, degrading the controller into LIMP mode (mode 4) for ~500 ms.

### Root Causes
- Lack of noise-rejection temporal debouncing on initial residual trigger.
- Lack of reset logic for `unresolved_fault_timer` and isolation candidate state when currents returned to the balanced manifold ($\|i_a + i_b + i_c\| < \text{threshold}$).

### Implementation
- Added `KCL_CONSECUTIVE_EXCEED_LIMIT = 5` (250 $\mu\text{s}$ at 20 kHz current loop rate) requiring 5 consecutive samples exceeding the KCL threshold before declaring a valid fault candidate.
- Preserved the candidate onset jump channel across debounce ticks to prevent losing the initial gradient signature.
- Added residual-clearing abort: when the KCL residual remains below threshold for a full evaluation window, cancelled active isolation and reset `unresolved_fault_timer`.

### Verification Metrics
- **Test:** Added `test_single_sample_spike_rejection` in `simulation/test_scenarios.py` injecting isolated single-sample spikes (+0.5 A, +1.0 A, +2.0 A) across phases A, B, and C at $t=2.0\text{ s}$.
- **Before Fix:** Single +0.5 A spike forced control mode transition $2 \to 4$ (LIMP) for 500 ms with significant speed drop.
- **After Fix:** Control mode strictly remains 2 (CLOSED_LOOP); speed dip is 0.00% (well within 3.0% limit). Existing scenarios 2, 3, 4, 5, 12 continue to isolate faults within their YAML latency limits (1.45 ms – 7.15 ms).

---

## Task 2: Handoff State Machine and Integrator Preloading

### Defects Identified
- **Startup Bypass:** If a DEGRADED or LIMP request occurred during ALIGN or OPEN_LOOP, `handoff_update()` jumped directly to DEGRADED/LIMP, completely skipping startup and closed-loop handoff.
- **Fault-Clearing Skip:** Clearing a fault transitioned DEGRADED $\to$ CLOSED_LOOP directly, even if startup was incomplete.
- **Stall Fallback Latching:** On stall fallback (`CLOSED_LOOP -> OPEN_LOOP`), `if_startup` was never reset; `startup.done` remained `true`, causing immediate re-entry into closed loop without re-alignment or acceleration.
- **Integrator Transients:** `pi_id`, `pi_iq`, and `pi_spd` integrators were never reset or preloaded on mode transitions. `pi_spd` started at 0 A while startup commanded 2.0 A, causing a step transient on handoff.

### Root Causes
- Unconstrained state transitions in `src/handoff.c`.
- Lack of state-machine re-initialization hooks on fallback in `src/foc_core.c`.
- Discontinuous control handoff without bumpless transfer integrator preloading.

### Implementation
- Constrained `handoff_update()` in `src/handoff.c`: DEGRADED/LIMP transitions are only permitted from `CLOSED_LOOP`. If a fault is detected during ALIGN or OPEN_LOOP, it is latched as pending and applied only after successful handoff.
- On `CLOSED_LOOP -> OPEN_LOOP` stall fallback in `src/foc_core.c`, reset `if_startup` and `obs_mgr`.
- On every mode change, reset current-loop integrators (`pi_id`, `pi_iq`) and preload `pi_spd.integral` with the last applied $i_q$ reference (`last_applied_iq_ref`) for bumpless transfer.

### Verification Metrics
- **Test:** Added `simulation/test_handoff.py` covering unit-level mode transition rules, stall fallback, and full controller startup sequence.
- **Before Fix:** Injecting fault during ALIGN jumped directly to mode 3, skipping stages; speed step glitch on handoff.
- **After Fix:** Mode progression is strictly ALIGN (0) $\to$ OPEN_LOOP (1) $\to$ CLOSED_LOOP (2) $\to$ DEGRADED (3). Bumpless transfer confirmed with smooth torque/current continuity.

---

## Task 3: Voltage Limiting and Simulation Realism

### Defects Identified
- **Voltage Vector Over-Modulation:** $v_d$ and $v_q$ were independently clamped to $\pm V_{bus} = \pm 24\text{ V}$, allowing a resultant voltage vector $\|v\| = \sqrt{v_d^2 + v_q^2} \le 34.0\text{ V}$. The physical linear modulation limit of an inverter with Space Vector Modulation is $V_{max} = V_{bus}/\sqrt{3} \approx 13.856\text{ V}$.
- **Inverter Voltage Mismatch:** Observers integrated the unconstrained commanded voltages rather than the actual voltage applied by the inverter.
- **Unclamped Plant Inverter:** `simulation/plant/inverter_model.py` did not clamp duty cycles. Baseline simulation operated with duties ranging from $-0.37$ to $+1.37$. Clamping duties to $[0.0, 1.0]$ caused baseline max angle error to spike to $18.5^\circ$, failing the $15.0^\circ$ criterion due to voltage saturation.

### Root Causes
- Rectangular rather than circular voltage limiting in `src/foc_core.c`.
- Lack of back-calculation anti-windup in `src/pi_controller.c`.
- Lack of high-speed field weakening to counteract back-EMF near voltage saturation.
- Idealized, unclamped inverter duty conversion in `inverter_model.py`.

### Implementation
- Added circular voltage vector clamping in `src/foc_core.c` at $V_{max} = V_{bus}/\sqrt{3} \approx 13.856\text{ V}$ with d-axis priority ($v_{q,max} = \sqrt{V_{max}^2 - v_d^2}$).
- Implemented back-calculation anti-windup (`pi_back_calculate`) in `src/pi_controller.c` for both d-axis and q-axis current PI loops.
- Observers now receive the circularly limited voltages actually applied to the motor.
- Clamped inverter duty cycles strictly to $[0.0, 1.0]$ in both `src/foc_core.c` and `simulation/plant/inverter_model.py`.
- Implemented dynamic field weakening ($i_{d,fw} < 0$) in `src/foc_core.c` when voltage magnitude exceeds $88\%$ of $V_{max}$ at speeds $>1200\text{ RPM}$, decaying to zero at low speeds and zero crossings for observer stability.

### Verification Metrics
- **Test:** Added `simulation/test_voltage_limiting.py` asserting PWM duty cycles $\in [0.0, 1.0]$, circular voltage radius $\le 13.856\text{ V}$, back-calculation anti-windup activation, and baseline criteria compliance.
- **Before Fix:** Duty cycles in $[-0.37, 1.37]$; unconstrained voltage $\le 34\text{ V}$; clamped baseline max angle error $18.5^\circ$ (FAIL).
- **After Fix:** Duty cycles strictly in $[0.0, 1.0]$; circular voltage radius $\le 13.856\text{ V}$; baseline max angle error reduced to **$2.92^\circ$** (RMS $1.29^\circ$, speed ripple $202.7\text{ RPM}$), passing all criteria with substantial margin.

---

## Task 4: Reachable SAFE_STOP and Output Disabling

### Defects Identified
- **Dead Safe Stop Logic:** In `src/fault_monitor.c`, fault isolation logic stopped running as soon as any phase was latched (`if (fm->fault_latched) return;`). Consequently, the branch checking for all three channels latched was unreachable dead code.
- **Undetected Second Sensor Fault:** If a second sensor failed while the controller was in DEGRADED mode (e.g. Phase A offset followed by Phase B offset), the second fault was never detected, leaving the controller in DEGRADED mode on corrupt data indefinitely.
- **No Hardware Gate Disabling:** SAFE_STOP was not implemented as a gate driver disable. The controller continued driving 50% PWM (`duty = 0.5f`), applying active braking and common-mode voltage rather than high-impedance freewheeling.

### Root Causes
- Premature return in `fault_update()` upon first latch.
- Missing two-channel consistency checks during single-sensor degraded operation.
- Lack of a hardware gate driver enable signal in `FocOutput`.

### Implementation
- Added continuous second-sensor fault monitoring in `src/fault_monitor.c` using the remaining two healthy channels and the model predictor. Gated the check with a post-latch settling holdoff (200 ms) and speed threshold $|\omega| > 50\text{ rad/s}$ to prevent false standstill trips.
- Implemented an ambiguous fault timeout: if an ambiguous fault persists longer than 1.5 s, the monitor transitions to `SAFE_STOP` (mode 5).
- Permanently latched `SAFE_STOP` until explicit `foc_reset()`.
- Added `bool gate_enable;` to `FocOutput` across `src/foc_api.h`, `c_bridge.py`, and `sil_runner.py`. In `SAFE_STOP`, `gate_enable = false` and all duty cycles are set strictly to `0.0f`.
- In `src/main.cpp`, drove hardware gate driver pin (`PIN_GATE_EN`, GPIO 22) LOW and set LEDC PWM outputs to 0 upon entering `SAFE_STOP`.
- Added `scenario_13_sequential_two_sensor` and `scenario_14_persistent_ambiguous_fault` in `simulation/fault_injection/fault_scenarios.yaml`.

### Verification Metrics
- **Test:** Added `test_safe_stop_reachable_on_second_fault_and_ambiguous` in `simulation/test_scenarios.py`.
- **Before Fix:** Second sensor fault ignored; controller remained in mode 3 indefinitely; SAFE_STOP drove 50% PWM.
- **After Fix:**
  - Scenario 13 (sequential two-sensor fault): Enters SAFE_STOP in **1.45 ms** (limit $\le 50.0\text{ ms}$).
  - Scenario 14 (persistent ambiguous fault): Enters SAFE_STOP in **1500.0 ms** (limit $\le 1600.0\text{ ms}$).
  - In SAFE_STOP, `gate_enable == False`, duties $= 0.0$, `PIN_GATE_EN == LOW`, permanently latched until reset.

---

## Task 5: Current-Sense Scaling and Calibration

### Defects Identified
- **False Clipping and Spurious Faults:** In `src/main.cpp`, `CURRENT_SCALE` yielded an effective full-scale range of only $\pm 3.3\text{ A}$. However, nominal rated current is $I_n = 5.0\text{ A}$ and baseline peak phase currents at 2000 RPM reach $4.99\text{ A}$. Phase current measurements clipped at 3.3 A, creating an artificial KCL residual imbalance and triggering false fault isolation at $t \approx 1.448\text{ s}$.

### Root Causes
- Hardcoded ADC count scaling without derivation from physical shunt resistance, amplifier gain, and ADC reference voltage.
- Sizing current measurement range below peak operational motor currents.

### Implementation
- Sized sensing chain parameters from physical named constants in `src/main.cpp`:
  - $V_{ref} = 3.3\text{ V}$
  - $R_{shunt} = 10\text{ m}\Omega$ (0.010 $\Omega$)
  - $Gain = 20.0$
  - Full-scale sensing range: $I_{FS} = \frac{V_{ref}/2}{R_{shunt} \cdot Gain} = \pm 8.25\text{ A}$ ($>60\%$ headroom over $I_n = 5.0\text{ A}$).
- Added compile-time check:
  `static_assert(CURRENT_FULL_SCALE > 1.2f * MOTOR_NOMINAL_IN, "Current sensing full-scale range must exceed 1.2 * In");`
- Added startup ADC offset calibration in `src/main.cpp`: averages 500 samples per channel with PWM disabled prior to timer interrupt activation.
- Created `simulation/plant/sensor_model.py` incorporating clipping at $\pm 8.25\text{ A}$, 12-bit ADC quantization, 30 mA RMS Gaussian noise, 20 LSB DC offset, and startup offset calibration.

### Verification Metrics
- **Test:** Added `simulation/test_current_sense.py` comparing the old 3.3 A scale against the new 8.25 A scale under the realistic sensor model.
- **Before Fix:** 3.3 A scale clipped at 3.3 A, triggering spurious KCL fault at $t \approx 1.448\text{ s}$ during baseline run.
- **After Fix:** 8.25 A scale exhibits zero clipping, zero false trips, and baseline max angle error remains $2.92^\circ$. Compile-time assertion verifies $>1.2 \times I_n$ headroom.

---

## Task 6: Test and Metrics Integrity

### Defects Identified
- **Excluded Fault Windows:** In `simulation/harness/sil_runner.py` and `simulation/test_scenarios.py`, `start_time` was hardcoded to `2.0 s`. Scenarios 1, 5, 6, 7, and 9 inject faults or disturbances at $t = 1.5\text{ s}$, meaning the entire disturbance transient from $1.5\text{ s}$ to $2.0\text{ s}$ was completely excluded from metrics evaluation.
- **Decoupled Transform Unit Test:** `src/tests/test_transforms.c` contained local, handwritten duplicate Clarke and Park equations rather than testing the functions in the compiled C library.
- **Missing Sensor Model Sweep:** No automated test executed the full fault scenario set under a realistic ADC sensor model.

### Root Causes
- Hardcoded evaluation start time in metric calculation.
- Lack of exported library transform symbols in `src/foc_api.h`.

### Implementation
- Exported and implemented library transforms in `src/foc_api.h` and `src/foc_core.c`: `clarke_transform`, `park_transform`, `inv_park_transform`, and `inv_clarke_transform`.
- Refactored `foc_tick()` in `src/foc_core.c` to use library transform functions throughout.
- Replaced `src/tests/test_transforms.c` with comprehensive unit and invertibility tests verifying full $(a,b,c) \to (\alpha,\beta) \to (d,q) \to (\alpha,\beta) \to (a,b,c)$ round-trip accuracy to float precision ($<10^{-5}$) across 360 electrical degrees and varied current amplitudes.
- Added `get_scenario_evaluation_start_time()` in `sil_runner.py` and `test_scenarios.py` to dynamically evaluate each scenario from its own fault/load/reversal onset time.
- Added `--sensor-model` option to `sil_runner.py` and implemented `test_all_scenarios_under_sensor_model` in `test_scenarios.py`.

### Verification Metrics
- **Test:** `make test` runs `test_transforms` calling library symbols; `test_all_scenarios_under_sensor_model` executes all 14 scenarios under the sensor model.
- **Before Fix:** Scenarios 1, 5, 6, 7, 9 evaluated only for $t \ge 2.0\text{ s}$; `test_transforms.c` tested duplicate code.
- **After Fix:** All scenarios evaluated from actual onset time ($1.5\text{ s}$, $0.5\text{ s}$, or $2.0\text{ s}$); 14/14 scenarios PASS nominal sweep; 14/14 scenarios PASS under realistic ADC sensor model.

---

## Task 7: ESP32 HAL Hot Path Optimization

### Defects Identified
- **Double-Precision Arithmetic in ISR:** `src/main.cpp` and observer modules (`src/smo.c`, `src/flux_observer.c`, `src/observer_manager.c`, `src/foc_core.c`) contained unadorned `M_PI` constants from `<math.h>`, causing GCC to implicitly promote single-precision float operands to double-precision arithmetic in the 20 kHz ISR hot path.
- **Missing IRAM Placement:** Core FOC functions called from the ISR lacked `IRAM_ATTR` annotations, risking flash cache miss latency during timer interrupt servicing.
- **No Scope Instrumentation:** No hardware pin was toggled to measure ISR execution duration on an oscilloscope.

### Root Causes
- Omission of `-Wdouble-promotion` compiler warning flags in `Makefile` and `platformio.ini`.
- Standard C `<math.h>` `M_PI` macro evaluating as `double`.

### Implementation
- Added `-Wdouble-promotion -Werror=double-promotion` to `CFLAGS` in `Makefile` and `build_flags` in `platformio.ini`.
- Cast all `M_PI` references to `(float)M_PI` across `src/flux_observer.c`, `src/observer_manager.c`, and `src/foc_core.c`.
- Added portable `IRAM_ATTR` macro to `src/foc_api.h` and applied it to `foc_tick` and all transform functions.
- Refactored `foc_isr` in `src/main.cpp` to use library transform functions and single-precision literals.
- Added `PIN_TIMING_BENCHMARK` (GPIO 14) toggling HIGH on entry to `foc_isr` and LOW on exit via fast `gpio_set_level` for oscilloscope profiling.
- Added 10,000-tick performance benchmark in `simulation/test_hal_benchmark.py`.

### Verification Metrics
- **Test:** `simulation/test_hal_benchmark.py` and `pio run`.
- **Before Fix:** Multiple `-Wdouble-promotion` warnings during compilation; no scope measurement pin.
- **After Fix:** Zero compiler warnings/errors with `-Wdouble-promotion -Werror=double-promotion` on host and ESP32 builds. 10,000-tick benchmark measures **2.01 $\mu\text{s}$ per tick** (including ctypes bridge overhead), occupying only **4.02%** of the 50.0 $\mu\text{s}$ ISR budget.

---

## Task 8: Parameter Harmonization and Final Validation

### Defects Identified
- **Mismatched Motor & Controller Parameters:** Motor and controller parameters were independently defined in `src/motor_params.h`, `simulation/harness/config.py`, and `src/main.cpp`. `motor_params.h` had obsolete speed controller gains (`C_KP_W 0.0314f`, `C_KI_W 9.87f`, `C_SMO_K 37.7f`) that conflicted with the validated controller tuning (`spd_kp = 0.194`, `spd_ki = 17.4`, `smo_k = 20.0`).

### Root Causes
- Multiple unlinked copies of parameter definitions across C headers, C++ firmware, and Python simulation configuration.

### Implementation
- Updated `src/motor_params.h` as the canonical single source of truth with `get_default_motor_params()` and `get_default_controller_params()`.
- Updated `src/main.cpp` to include `src/motor_params.h` and initialize motor/controller state using `get_default_motor_params()` and `get_default_controller_params()`.
- Updated `simulation/harness/config.py` to dynamically parse `src/motor_params.h` on load, guaranteeing bit-for-bit parameter synchronization between C, C++, and Python.
- Updated documentation in `README.md` and `docs/results/final_report.md`.

### Verification Metrics
- **C Transform Tests:** `make lib && make test` $\to$ PASSED.
- **ESP32 Firmware:** PlatformIO clean build $\to$ SUCCESS (RAM 6.8%, Flash 23.0%, 0 warnings).
- **Python Test Suite:** All 65 tests in `simulation/` $\to$ PASSED in full run.
- **Fault Scenarios:** 14/14 scenarios PASS nominal; 14/14 scenarios PASS with realistic ADC sensor model.
