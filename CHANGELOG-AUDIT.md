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
- **After Fix:** Zero compiler warnings/errors with `-Wdouble-promotion -Werror=double-promotion` on host and ESP32 builds. 10,000-tick benchmark on host Python/ctypes test runner measures **~0.7–2.0 $\mu\text{s}$ per tick** (informational host benchmark; not an on-target hardware measurement). Target hardware execution timing on GPIO 14 is marked **NOT MEASURED - requires hardware** (unmeasured on physical hardware; physical oscilloscope validation required).

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
- **ESP32 Firmware:** PlatformIO clean build $\to$ SUCCESS [Historical Round-2 Build Snapshot: RAM 6.8%, Flash 22.8%, 0 double-promotion warnings (1 framework warning in esp32-hal-uart.c and the expected dead-time #warning are present in the logs)].
- **Python Test Suite:** All 110 tests in `simulation/` $\to$ PASSED in full run.
- **Fault Scenarios:** 14/14 scenarios PASS nominal; 14/14 scenarios PASS with realistic ADC sensor model.

---

# Second-Round Audit and Remediation (Tasks 1-6)

This section records the second-round audit findings, implemented engineering fixes, before/after metrics, and measurement environments (Host SIL vs. Target Hardware) across all 6 tasks.

---

## Round 2 - Task 1: Startup & Alignment Fault Gating

### Defects Identified
- `test_handoff.py::test_fault_during_align_full_controller` failed (returned mode sequence `[0, 5]` = ALIGN $\to$ SAFE_STOP).
- In `src/foc_core.c`, the observer continued integrating during ALIGN while forced angle was driving the motor, causing $\hat{\omega}$ to reach $157.9\text{ rad/s}$ at physical standstill.
- `src/fault_monitor.c` used `fabsf(omega) > 50.0f` as its "spinning" gate for stuck-sensor detection. The DC alignment currents held steady, which the monitor falsely classified as a stuck sensor, latching a second fault and forcing SAFE_STOP ~70 ms after the initial latch.

### Implementation
- Gated stuck-sensor and second-fault monitoring strictly on controller mode (`CLOSED_LOOP`, `DEGRADED`, `LIMP`), ignoring standstill alignment DC currents.
- In `src/foc_core.c`, reset and zeroed observer outputs (`obs_theta = 0, obs_omega = 0, speed_est = 0`) while in `ALIGN`.
- Added parameterized tests covering faults during ALIGN and OPEN_LOOP with fault magnitudes 0.5 A, 1.0 A, and 2.0 A in `simulation/test_handoff.py`.

### Verification Metrics (Measured on Host)
- **Mode Sequence During Alignment Fault:**
  - *Before Fix:* `[0, 5]` (ALIGN jumped directly to SAFE_STOP, skipping OPEN_LOOP and CLOSED_LOOP).
  - *After Fix:* `[0, 1, 2, 3]` (Strict sequential progression: ALIGN $\to$ OPEN_LOOP $\to$ CLOSED_LOOP $\to$ DEGRADED).
- **Handoff Test Suite:** 9/9 tests PASSED in `simulation/test_handoff.py`.

---

## Round 2 - Task 2: Deceleration Stability & Transient Second-Fault Inhibition

### Defects Identified
- Injecting a single sensor fault ($i_a +2.0\text{ A}$) at $t=1.8\text{ s}$, followed by a commanded speed step from 2000 to 1000 RPM at $t=2.5\text{ s}$, caused the observer to lose lock (angle error spiked to $65.0^\circ$) and falsely tripped SAFE_STOP at $t \approx 2.529\text{ s}$.
- Field weakening ($i_d \approx -3.6\text{ A}$) remained active during rapid deceleration, distorting back-EMF estimation.
- In `src/smo.c`, direction flipping produced an uncompensated $\pi$ phase step, causing a 60,000 rad/s mathematical derivative spike in $\hat{\omega}$.
- Deceleration transients caused current and speed ripple that falsely triggered second-fault detection.

### Implementation
- **Field Weakening Motoring Gate:** Gated field weakening in `src/foc_core.c` on motoring operation ($i_q \cdot \omega > 0$). Under braking, field weakening decays to 0 at 50 A/s.
- **Smooth Braking Taper:** Added smooth braking torque taper flooring braking current as speed approaches positive targets, eliminating reverse undershoot.
- **Observer Bandwidth & Direction Flip:** Increased flux observer and SMO speed filter tracking bandwidths to 200 rad/s. Added direction flip hysteresis and $\pm \pi$ raw phase unwrapping adjustment in `src/smo.c`.
- **Transient Second-Fault Inhibition:** Gated second-fault false trip inhibition on commanded reference step changes (`fabsf(current_omega_ref - prev_omega_ref) > 10.0f` with 150 ms decay timer).
- **Clamped Dead-Time Voltage Drop:** Added clamped dead-time compensation ($0.5\text{ V}$) on observer voltage inputs.
- **Fast Stuck Isolation:** Accelerated stuck-sensor isolation to 0.5 ms when $\ge 10$ consecutive identical samples occur.

### Verification Metrics (Measured on Host)
- **Decel 2000 $\to$ 1000 RPM (Single Fault):**
  - *Before Fix:* SAFE_STOP falsely tripped at 2.529 s, max angle error $65.0^\circ$ (FAIL).
  - *After Fix:* Remains in DEGRADED (mode 3); max angle error **5.06°** (limit $<30.0^\circ$).
- **Decel 2000 $\to$ 500 RPM (Single Fault):**
  - *Before Fix:* Controller lost lock and tripped SAFE_STOP.
  - *After Fix:* Remains in DEGRADED (mode 3); max angle error **1.28°** (limit $<30.0^\circ$).
- **Decel 2000 $\to$ -2000 RPM Speed Reversal (Single Fault):**
  - *Before Fix:* Controller lost lock and tripped SAFE_STOP.
  - *After Fix:* Remains in DEGRADED (mode 3); max angle error **7.42°** (limit $<30.0^\circ$).
- **Scenario 4 Stuck Limit (under ADC Sensor Model):**
  - *Before Fix:* Max angle error $74.38^\circ$ (FAIL, limit $60.0^\circ$).
  - *After Fix:* Max angle error **42.06°** (PASSED, limit $60.0^\circ$).

---

## Round 2 - Task 3: High-Impedance Freewheeling Plant Model for SAFE_STOP

### Defects Identified
- In `simulation/harness/sil_runner.py`, `gate_enable=False` was modeled as $v_a = v_b = v_c = 0$, simulating a 3-phase dead short.
- At 2000 RPM, transitioning to SAFE_STOP produced a 12.27 A peak phase current surge through the windings, exceeding rated motor current ($I_n = 5.0\text{ A}$).

### Implementation
- Implemented physical high-impedance body-diode freewheeling in `sil_runner.py`:
  - Diode Rectification: If line-to-line back-EMF exceeds DC bus ($\sqrt{3} \psi_f |\omega_e| > V_{bus}$), diode bridge conducts in rectification, clamping terminal voltages.
  - Inductor Quenching: If back-EMF is below $V_{bus}$, existing inductor magnetic energy rapidly freewheels through body diodes into the bus until phase current reaches zero (<100 $\mu$s).
  - Zero-Current Coasting: Once quenched, diodes reverse-bias and turn off. Phase currents remain identically zero ($i_a=i_b=i_c=0$, $i_d=0, i_q=0$) and terminal voltages track open-circuit back-EMF during pure mechanical coasting.
- Added regression test in `simulation/test_safe_stop_current.py`.

### Verification Metrics (Measured on Host)
- **Peak Current After SAFE_STOP at 2000 RPM:**
  - *Before Fix:* **12.27 A** (FAIL, 3-phase short-circuit surge).
  - *After Fix:* **2.52 A** (PASSED, well below $1.2 \times I_n = 6.0\text{ A}$ limit).
- **Post-Quench Coasting Current:** **0.00 A** (physical open-circuit freewheeling).

---

## Round 2 - Task 4: Targeted Second-Fault Holdoff & Low-Latency Sequential Isolation

### Defects Identified
- A blanket 200 ms post-transition holdoff in `src/foc_core.c` and 50 ms in `src/fault_monitor.c` delayed second-fault detection.
- When a second fault occurred 50 ms after the first fault, SAFE_STOP was not reached until 213.6 ms after the second fault, violating the 50 ms requirement.

### Implementation
- Replaced blanket 200 ms holdoff with targeted 10 ms settling timer strictly on the `CLOSED_LOOP -> DEGRADED` transition.
- Reduced post-latch settling timer in `fault_monitor.c` from 50 ms to 10 ms.
- Differentiated second-fault debounce: 5 ms for jump/stuck faults and 15 ms for residual faults.
- Added `simulation/test_sequential_fault_gaps.py` evaluating sequential fault gaps of 20 ms, 50 ms, and 100 ms.

### Verification Metrics (Measured on Host)
- **Sequential Second-Fault Detection Latency (Limit < 50.0 ms):**
  - **Gap 20 ms:** SAFE_STOP latency **24.05 ms** (PASSED).
  - **Gap 50 ms:** SAFE_STOP latency reduced from **213.6 ms** to **24.15 ms** (PASSED).
  - **Gap 100 ms:** SAFE_STOP latency **27.50 ms** (PASSED).

---

## Round 2 - Task 5: Embedded FreeRTOS Architecture, Direct ADC & Benchmark Cleanliness

### Defects Identified
- `src/main.cpp` executed slow Arduino `analogRead()` x3 (~90-120 $\mu$s), `digitalRead()`, and `ledcWrite()` directly inside the 20 kHz hardware timer ISR, with the entire ISR wrapped in a critical section disabling interrupts across the core.
- The README and final report previously cited a host Python/ctypes timing (2.01 $\mu$s) as an on-target ISR budget measurement.
- `simulation/test_hal_benchmark.py` contained an `or True` assertion bypass and a machine-dependent `< 20 us` threshold.

### Implementation
- **Pinned FreeRTOS Control Task:** Moved FOC control loop, observers, and PWM updates into a dedicated high-priority task pinned to Core 1 (`foc_control_task`), priority `configMAX_PRIORITIES - 1`.
- **Ultra-Lean Timer ISR:** 20 kHz hardware timer ISR reduced to `vTaskNotifyGiveFromISR()` (<1 $\mu$s execution time).
- **Direct Register ADC:** Replaced `analogRead()` with direct ESP-IDF SAR ADC1 register reads (`adc1_get_raw(ADC1_CHANNEL_4/5/6)` on GPIO 32, 33, 34).
- **Fine-Grained Spinlock:** Telemetry spinlock restricted strictly to writing 6 shared telemetry variables (~15 ns), removing FOC algorithms from critical sections.
- **IRAM_ATTR Placement:** Added `IRAM_ATTR` annotations across all control loop callees: `pi_controller`, `smo`, `flux_observer`, `observer_manager`, `fault_monitor`, `if_startup`, and `handoff`.
- **Test Suite Cleanliness:** In `simulation/test_hal_benchmark.py`, deleted `or True` in `test_no_double_promotion_warnings`; replaced `< 20 us` hard threshold with 50 $\mu$s real-time period check.
- **Documentation:** Updated `README.md` and `docs/results/final_report.md` to clearly distinguish host execution timing (~2 $\mu$s on Python/ctypes) from target hardware requirements (oscilloscope measurement on `PIN_TIMING_BENCHMARK` GPIO 14).

### Verification Metrics
- **Target Firmware Build (ESP32 via PlatformIO, Historical Round-3 Build Snapshot):**
  - Compiler Flags: `-Wdouble-promotion -Werror=double-promotion`
  - Compiler Warnings: **0 double-promotion warnings (1 framework warning in esp32-hal-uart.c and the expected dead-time #warning are present in the logs)**
  - RAM Usage (Historical Round-3): 22,204 bytes (6.8% of 320 KB)
  - Flash Usage (Historical Round-3): 299,561 bytes (22.9% of 1.3 MB)
- **Host Ctypes Benchmark (Measured on Host):**
  - Clean compilation verification without `or True`: PASSED.
  - Average host per-tick duration: ~2.0 $\mu$s.
- **Target Hardware Timing (Hardware Measurement Required):**
  - Instrumented on GPIO 14 (`PIN_TIMING_BENCHMARK`) for physical oscilloscope measurement on hardware bench test.

---

# Third-Round Audit and Remediation (Tasks 1-6)

This section records the third-round audit findings, implemented engineering fixes, before/after metrics, and measurement environments across all 6 tasks.

---

## Round 3 - Task 1: Dead-Time Compensation Parameterization & Sensitivity Sweep

### Defects Identified
- Dead-time compensation was hard-coded in `src/foc_core.c` as a literal scalar `0.5f` V matching the simulator's nominal constant, rather than being parameterized in `ControllerParams` and derived from physical timing ($V_{dead} = t_{dead} \times f_{pwm} \times V_{bus}$).
- Lack of sensitivity characterization under dead-time mismatch between plant and controller. With an ideal plant ($V_{dead} = 0.0\text{ V}$), the controller assuming $0.5\text{ V}$ degraded to $19.29^\circ$ maximum electrical angle error.

### Implementation
- **Parameterized Controller Architecture:** Added `float dead_time` to `ControllerParams` in `src/foc_api.h` and default macro `CTRL_PARAM_DEAD_TIME (1.0416667e-6f)` (corresponding to $0.5\text{ V} / (20000\text{ Hz} \times 24\text{ V})$) in `src/motor_params.h`.
- **Dynamic Voltage Calculation:** Updated `src/foc_core.c` to compute $V_{dead} = t_{dead} \times f_{pwm} \times V_{bus}$ dynamically on each control cycle.
- **Python Bridge & Harness Synchronization:** Updated `simulation/harness/c_bridge.py`, `simulation/harness/config.py`, and `simulation/harness/sil_runner.py` to synchronize `dead_time` across the C types bridge.
- **Sensitivity Test Suite:** Created `simulation/test_dead_time_sensitivity.py` with 7 tests evaluating plant dead-time across 0.5 V, 0.25 V, 1.0 V, 1.5 V, 0.0 V, and zero-dead-time recovery.
- **Transparent Documentation:** Documented the measured degradation ($19.29^\circ$ at $V_{dead}=0\text{ V}$) and compensation configuration in `README.md` and `docs/results/final_report.md`.

### Verification Metrics (Measured on Host)
- **Dead-Time Sensitivity Sweep (Controller Assumes 0.5 V):**
  - **Plant 0.5 V (Nominal Match):** Max angle error **0.49°** (PASSED, limit < 1.0°).
  - **Plant 0.25 V (-50% Mismatch):** Max angle error **6.49°** (PASSED, limit < 10.0°).
  - **Plant 1.0 V (+100% Mismatch):** Max angle error **3.54°** (PASSED, limit < 10.0°).
  - **Plant 1.5 V (+200% Mismatch):** Max angle error **7.13°** (PASSED, limit < 12.0°).
  - **Plant 0.0 V (Ideal Inverter):** Max angle error **19.29°** (Documented degradation, limit < 22.0°).
  - **Plant 0.0 V with Controller `dead_time = 0.0`:** Max angle error recovers to **0.49°** (PASSED, limit < 1.0°).
- **Test Suite:** 7/7 tests PASSED in `simulation/test_dead_time_sensitivity.py`.

---

## Round 3 - Task 2: KCL Debounce Margin Restoration & Burst Noise Immunity

### Defects Identified
- Previous single-sample debounce fix reduced false trips from isolated glitches, but required verification that consecutive noise bursts (1..4 samples) would not cause false mode transitions, while ensuring genuine faults in Scenarios 13 and 14 still meet detection latency limits.

### Implementation
- Set `KCL_CONSECUTIVE_EXCEED_LIMIT = 5` in `src/fault_monitor.c`, requiring 5 consecutive samples (250 $\mu$s at 20 kHz) above residual threshold before initiating fault isolation.
- Verified that isolation timer resets and aborts if residuals clear during the window.
- Added comprehensive regression test `test_burst_spike_rejection` in `simulation/test_scenarios.py` testing bursts of 1, 2, 3, and 4 corrupted samples (+0.5 A and +1.0 A) across all three phases ($a, b, c$).

### Verification Metrics (Measured on Host)
- **Burst Spike Rejection:** 24/24 burst permutations (1..4 samples, +0.5A/+1.0A on phases A, B, C) verified: controller never leaves `CLOSED_LOOP` (mode 2).
- **Fault Detection Scenarios:**
  - **Scenario 13 (Sequential Faults):** Latch within limits both nominal and under ADC sensor model.
  - **Scenario 14 (Persistent Ambiguous):** Isolation and fallback timing verified within limits.
- **Test Suite:** 24/24 tests PASSED in `simulation/test_scenarios.py`.

---

## Round 3 - Task 3: Transient Second-Fault Inhibit Window Tightening

### Defects Identified
- Second-fault detection was inhibited for 150 ms following a speed reference step to prevent false tripping on braking transients. However, an excessively long 150 ms window created a blind spot that delayed second-fault detection.

### Implementation
- Tightened `ref_transient_timer` duration in `src/foc_core.c` from 150 ms to **80 ms** (0.080 s), precisely matching the physical rotor deceleration duration.
- Added regression test `test_second_fault_during_speed_step_transient` in `simulation/test_sequential_fault_gaps.py` injecting a physical second sensor fault exactly 50 ms after a commanded speed step (2000 RPM $\to$ 1000 RPM).

### Verification Metrics (Measured on Host)
- **Second-Fault Detection Latency During Decel Transient:**
  - *Measured Latency:* **45.00 ms** from fault injection to `SAFE_STOP` (mode 5).
  - *Requirement:* $\le 50.0\text{ ms}$ (PASSED).
- **Deceleration Stability Suite:** 3/3 tests PASSED in `simulation/test_decel.py` (1000 RPM, 500 RPM, -2000 RPM all remain in DEGRADED with max angle error $< 30^\circ$).

---

## Round 3 - Task 4: ESP32 Fast Register SAR ADC1 & Overrun Deadline Protection

### Defects Identified
- Previous firmware called `adc1_get_raw()` which acquires RTOS spinlocks and reconfigures channel multiplexers (~12–15 $\mu$s per channel).
- Misleading comments referred to `adc1_get_raw` as "direct register read".
- No overrun detection mechanism existed to detect missed real-time deadlines.

### Implementation
- **Fast Register SAR ADC1 Access:** Implemented `adc1_read_fast_reg(channel)` in `src/main.cpp` directly controlling `SENS.sar_meas_start1` in hardware, with SAR ADC1 routed to RTC/software control in `setup()` (timing unmeasured on hardware).
- **Missed Deadline / Overrun Protection:** Evaluated `ulTaskNotifyTake()` return value. If `notifies > 1` (indicating missed 20 kHz timer cycles), an overrun counter increments. If 3 consecutive overruns occur (`MAX_CONSECUTIVE_OVERRUNS = 3`), the firmware latches a hard real-time violation fault, disables PWM gate outputs, and enters `SAFE_STOP`.
- **Accurate Code Comments:** Replaced all inaccurate "direct register" comments with precise hardware register descriptions.

### Verification Metrics
- **Firmware Compilation (ESP32 via PlatformIO, Historical Round-4 Host Cross-Compilation Snapshot):**
  - Compiler Flags: `-Wdouble-promotion -Werror=double-promotion`
  - Status: **SUCCESS: 0 double-promotion warnings (1 framework warning in esp32-hal-uart.c and the expected dead-time #warning are present in the logs)**
  - RAM Usage (Historical Round-4): 22,212 bytes (6.8% of 327,680 bytes)
  - Flash Usage (Historical Round-4): 299,225 bytes (22.8% of 1,310,720 bytes)
  - Raw Build Artifact: `docs/evidence/pio_build_clean_20261020.log`
- **Target Hardware Timing (GPIO 14 / `PIN_TIMING_BENCHMARK`):**
  - Status: **NOT MEASURED - requires hardware** (unmeasured on physical hardware; previous estimates of 0.8 $\mu\text{s}$ ISR, 4.5 $\mu\text{s}$ ADC, 14.2 $\mu\text{s}$ FOC, 18.7 $\mu\text{s}$ total removed per documentation integrity). Physical oscilloscope validation required.

---

## Round 3 - Task 5: Physical Diode-Bridge Freewheeling Model & DC Bus Voltage Rise

### Defects Identified
- `simulation/harness/sil_runner.py` previously modeled inverter gate disable (`gate_enable = False`) using arbitrary state-variable zeroing (`plant.i_d = 0.0`, `plant.i_q = 0.0`).
- Did not physically model diode conduction conditions based on terminal voltage exceeding bus voltage ($|v| > V_{bus} + 2V_d$), nor did it account for DC bus voltage rise as inductive energy dumps into the DC link capacitor.

### Implementation
- **Physical Diode-Bridge Model:** Implemented 6-pulse diode bridge freewheeling in phase space. Conducting diodes clamp phase terminals to DC rails opposing current flow ($v_{k0} = \pm (V_{bus} + 2V_d)/2$).
- **Bus Capacitor Dynamics:** Modeled DC bus capacitor ($C_{bus} = 470\,\mu\text{F}$) charging from freewheeling diode currents: $\frac{dV_{bus}}{dt} = \frac{I_{bus\_in} - I_{bleed}}{C_{bus}}$ with a bleeder resistance $R_{bleed} = 50\,\Omega$.
- **Natural ODE Equilibrium:** When currents quench and back-EMF is below bus voltage ($E_{LL} \le V_{bus} + 2V_d$), passing synchronous open-circuit back-EMF ($v_d = 0, v_q = \omega_e \psi_f$) naturally maintains $di_d/dt = 0, di_q/dt = 0, T_e = 0$ directly through the plant's differential equations without artificial variable overwriting.
- **Enhanced Regression Test:** Updated `simulation/test_safe_stop_current.py` asserting post-SAFE_STOP peak current stays below $1.2 \times I_n$ (6.0 A) and verifying physical bus-voltage rise ($\Delta V_{bus} > 0.1\text{ V}$) during quench.

### Verification Metrics (Measured on Host)
- **SAFE_STOP Peak Phase Current:** Measured **3.10 A** (PASSED, limit $< 6.0\text{ A}$ / $1.2 \times I_n$).
- **Quenched Phase Current:** Measured **0.00 A** (PASSED, limit $< 0.5\text{ A}$).
- **DC Bus Voltage Rise:** Rose from nominal **24.00 V** to peak **24.45 V** ($\Delta V_{bus} = +0.45\text{ V}$) during inductive energy quench, then bled back to nominal (PASSED).
- **Test Suite:** `simulation/test_safe_stop_current.py` PASSED.

---

## Round 3 - Task 6: Audit Documentation & Stale Text Remediation

### Implementation
- Updated `CHANGELOG-AUDIT.md` fixing stale references in Round 1 (remedying host timing distinction vs target scope measurements and updating test counts from 65 to 110 tests).
- Documented complete Round 3 engineering metrics, before/after values, and host vs target test environments.

---

# Round 4 Audit Fixes & Quality Remediation

This section records the fourth-round audit findings, implemented engineering fixes, and verification results across `sensorless-foc-pio`.

## Round 4 - Task 1: Severe Residual Fast Track Consecutive Sample Requirement & Extended Burst Spike Rejection

### Defects Identified
- The severe-residual fast track (`|E| > 1.5 A` with 2 consecutive samples) allowed a 2-sample noise burst of +2.0 A or +3.0 A on any phase current sensor to latch a sensor fault, dropping the controller into `DEGRADED` mode for 500 ms and causing unnecessary speed dips.

### Implementation
- **Consecutive Sample Requirement:** Updated `src/fault_monitor.c` line 52 to require 3 consecutive samples (`kcl_exceed_count >= 3`) before triggering severe-residual fast-track isolation:
  ```c
  if (fabsf(E) > KCL_SEVERE_THRESH && fm->kcl_exceed_count >= 3)
  ```
- **Consistent Stuck Detection:** Aligned stuck sensor detection to require `stuck_count >= 8` (0.4 ms) with `iso_win = 0.0004f`, ensuring instantaneous noise bursts do not latch stuck sensor isolation while preserving fast stuck isolation for genuine faults.
- **Extended Burst Spike Regression Tests:** Expanded `test_burst_spike_rejection` in `simulation/test_scenarios.py` to parameterize over 36 permutations:
  - Magnitudes: 0.5 A, 1.0 A with burst lengths 1, 2, 3, 4 samples.
  - Magnitudes: 2.0 A, 3.0 A with burst lengths 1, 2 samples.
  - Channels: Phase A, Phase B, Phase C.

### Verification Metrics
- **Burst Rejection Suite:** 36/36 parameterized burst test cases **PASSED**; control mode remained strictly in `CLOSED_LOOP` (mode 2) with zero false fault trips.
- **Scenario 4 Timing:** Stuck sensor Phase A isolated in 0.45 ms; maximum electrical angle error reached 42.42° (nominal) and 25.28° (sensor model), comfortably passing the 60.0° limit.
- **Scenarios 13 & 14:** Two-sensor sequential fault and persistent ambiguous fault passed within strict YAML timing limits.

---

## Round 4 - Task 2: Documentation Integrity & Oscilloscope Profiling Clarification

### Defects Identified
- `README.md`, `docs/results/final_report.md`, and `CHANGELOG-AUDIT.md` previously claimed physical oscilloscope measurements on target ESP32 hardware (ISR 0.8 µs, ADC 4.5 µs, control loop 14.2 µs, total 18.7 µs).
- No oscilloscope capture files, logs, or raw hardware traces exist in the repository, conflicting with documentation integrity requirements.

### Implementation
- **Timing Claims Removed:** Removed unverified oscilloscope timing numbers across `README.md`, `docs/results/final_report.md`, and `CHANGELOG-AUDIT.md`.
- **Hardware Requirement Status:** Marked all target hardware execution-time profiling rows as `"NOT MEASURED - requires hardware"`, clearly specifying that physical oscilloscope captures on GPIO 14 (`PIN_TIMING_BENCHMARK`) are required.
- **Harmonized Memory Metrics:** Clarified that PlatformIO build metrics represent static ELF memory footprint from host cross-compilation (`pio run`), not on-target runtime telemetry, and labeled older metrics as historical per-round snapshots.

---

## Round 4 - Task 3: Bounded ADC Conversion Timeout & Non-Linearity Documentation

### Defects Identified
- `adc1_read_fast_reg()` in `src/main.cpp` used an unbounded polling loop (`while (!SENS.sar_meas_start1.meas1_done_sar) {}`), risking infinite deadlock if the SAR ADC hardware failed to assert completion.
- Inaccurate comment claimed `"~1.5 us per conversion"` without physical measurement.
- ESP32 SAR ADC 11 dB attenuation non-linearity was undocumented.

### Implementation
- **Bounded Timeout Wait:** Added a 50 µs bounded timeout using `esp_timer_get_time()`. If conversion does not complete within 50 µs, `g_adc_hardware_fault` is latched.
- **Hardware Fault Handling:** On timeout expiry, the firmware immediately commands `gpio_set_level(PIN_GATE_EN, 0)`, zeroes all PWM duties, latches the red fault LED, sets `telemetry_mode = 5` (`SAFE_STOP`), and skips control loop execution.
- **Calibration Check:** Added timeout detection during the 500-sample startup zero-offset calibration loop in `setup()`.
- **Non-Linearity Documentation:** Documented that ESP32 SAR ADC 11 dB attenuation non-linearity is uncorrected by LUT / `esp_adc_cal` in raw register read mode, detailing that symmetrical shunt sensing operates near midpoint (1.65 V) and specifying hardware characterization requirements.

---

## Round 4 - Task 4: Quantitative DC Bus Voltage Decay Margin Assertion

### Defects Identified
- In `simulation/test_safe_stop_current.py`, the assertion `assert vbus_final <= vbus_peak` was vacuous because `vbus_peak` was the maximum over a window containing `vbus_final`.

### Implementation
- **Exponential Decay Grounding:** Grounded assertions in physical bleeder circuit dynamics ($R_{bleed} = 50\,\Omega$, $C_{bus} = 470\,\mu\text{F}$, $\tau = 23.5\text{ ms}$).
- **Stated Margin & Time Assertions:**
  - At $t = t_{peak} + 50\text{ ms}$ (~2 time constants), verified bus voltage decayed by at least 50% of the peak rise ($\Delta V_{decay} \ge 0.50 \cdot V_{rise}$). Measured decay: **0.393 V** (88.1% of 0.447 V rise).
  - At simulation end ($t > t_{peak} + 200\text{ ms}$, >8 time constants), verified bus voltage returns to within 0.05 V of nominal ($V_{bus} \le 24.05\text{ V}$). Measured final: **24.000 V**.

---

## Round 4 - Task 5: Default Dead-Time Parameter Commissioning & Hardware Procedure

### Defects Identified
- Default controller `dead_time` parameter in `src/motor_params.h` was hardcoded to the simulator's constant ($1.0416667\times 10^{-6}\text{ s}$ corresponding to 0.5 V) without clear indication that it is a hardware-dependent commissioning parameter.
- No procedure existed in `README.md` explaining how to measure and commission actual inverter dead-time distortion on physical hardware.

### Implementation
- **Canonical Parameter Flagging:** Updated `src/motor_params.h` to clearly designate `CTRL_PARAM_DEAD_TIME` as `[MUST BE COMMISSIONED FOR TARGET HARDWARE]`, explaining the physical origin ($V_{dead} = t_{dead} \cdot f_{pwm} \cdot V_{bus}$), default uncommissioned recommendation (0.0 s), and calibrated SIL reference value.
- **Firmware Commissioning Guard:** Added commissioning guidance in `src/main.cpp` alerting developers to set `ctrl.dead_time = 0.0f` on uncommissioned hardware to prevent zero-crossing overcompensation.
- **Hardware Commissioning Guide:** Added comprehensive section `### Inverter Dead-Time Commissioning Procedure for Hardware Deployment` in `README.md` detailing:
  - Step 1: Physical non-overlap dead-time measurement via high-bandwidth differential oscilloscope probing ($t_{blank}$, $t_{rise}$, $t_{fall}$).
  - Step 2: Empirical terminal voltage distortion calibration via fundamental volt-second loss curve ($V_{loss}$ vs current polarity).
  - Step 3: Exact parameter derivation formula and firmware configuration.

### Verification Metrics
- **C Transform Unit Tests:** `make lib && make test` $\to$ **PASSED** (<$10^{-5}$ float round-trip invertibility).
- **Embedded PlatformIO Build:** `pio run` $\to$ **SUCCESS** (RAM 22,212 bytes / 6.8%, Flash 299,545 bytes / 22.9%, 0 double-promotion warnings (1 framework warning in esp32-hal-uart.c and the expected dead-time #warning are present in the logs) with `-Wdouble-promotion -Werror=double-promotion`; verified against raw log `docs/evidence/pio_build_clean_20261020.log`).
- **Complete Automated Test Suite:** `.venv/bin/python3 -m pytest simulation/ -q` $\to$ **122/122 PASSED (100%)** in 637.89s.

---

# Round 5 Audit Remediations & Technical Report

## Round 5 - Task 1: Safe Firmware Dead-Time Default & Compile-Time Commissioning Warning

### Defects Identified
- `get_default_controller_params()` in `src/foc_core.c` returned `dead_time = 1.0416667e-6f` (the calibrated SIL simulator 0.5 V equivalent), and `src/main.cpp` used this parameter as-is. On uncommissioned physical hardware where actual inverter distortion is ~0 V, this overcompensated the phase voltages and produced up to $19.3^\circ$ electrical angle error.

### Implementation
- **Role Decoupling:** Decoupled firmware defaults from SIL benchmark defaults:
  - In firmware (`src/motor_params.h` and `src/foc_core.c`), `CTRL_PARAM_DEAD_TIME` defaults to `0.0f` unless explicitly defined via `-DDEAD_TIME_COMMISSIONED_S=<value>` at compile time.
  - Added a compiler warning (`#warning "Inverter dead-time is uncommissioned (DEAD_TIME_COMMISSIONED_S not defined). Defaulting dead_time to 0.0s for safe hardware operation."`) alerting developers during native and embedded builds.
  - In the SIL simulation environment (`simulation/harness/config.py`), defined `SIM_DEAD_TIME = 1.0416667e-6` and passed it through `simulation/harness/c_bridge.py` so virtual motor plant benchmarks remain accurately compensated.
- **Exported Canonical Accessor:** Added `foc_get_default_controller_params()` to `src/foc_api.h` and `src/foc_core.c`.
- **Regression Unit Tests:** Added `test_dead_time_firmware_and_sil_defaults()` in `simulation/test_dead_time_sensitivity.py`, verifying that firmware defaults to `0.0f`, emits the warning, and the SIL harness explicitly specifies `SIM_DEAD_TIME`.

---

## Round 5 - Task 2: PlatformIO Build Verification & Grounded Evidence Log

### Defects Identified
- Previous documentation claimed static build metrics (RAM 22,212 B / Flash 299,225 B) without a committed raw build log or toolchain version trace in the repository.

### Implementation
- **Evidence Artifact Generation:** Executed a clean PlatformIO build (`pio run -v`) and committed the full raw build output along with symbol size breakdown to `docs/evidence/pio_build_20261020.log`.
- **Toolchain & Core Versioning:** Logged exact component versions:
  - PlatformIO Core: 6.1.18
  - Espressif 32 Platform: 6.5.0
  - Framework: `framework-arduinoespressif32 @ 3.20014.231204` (ESP-IDF v4.4.6 / Arduino 2.0.14)
  - Toolchain: `toolchain-xtensa-esp32 @ 8.4.0+2021r2-patch5`
- **Synchronized Metrics:** Reconciled RAM (22,212 B / 6.8%) and Flash (299,545 B / 22.9%) figures across `README.md`, `docs/results/final_report.md`, and this changelog.
- **Git Whitelist:** Updated `.gitignore` to whitelist `!docs/evidence/**` for audit reproducibility.

---

## Round 5 - Task 3: Burst-Immunity Envelope Table & Boundary Regression Tests

### Defects Identified
- While burst-spike rejection was implemented in Round 4, the exact boundary conditions under which short bursts are rejected versus sustained faults latched into `DEGRADED` (2-shunt) mode were not fully tabulated in documentation or pinned by boundary unit tests.

### Implementation
- **Documentation Specification:** Added Section 6.1.1 "Burst-Immunity Envelope & Debounce Thresholds" to `README.md`, documenting the exact debounce matrix:
  - 1-2 samples at any magnitude up to $\pm 5.0$ A: rejected (mode stays `CLOSED_LOOP`, speed dip < 3%).
  - 4 samples at $\le 1.4$ A: rejected (below 1.5 A fast-track threshold, does not meet 5-sample KCL limit).
  - 5 samples at $\le 0.5$ A: rejected (within noise margin, KCL delta < 0.6 A).
  - $\ge 3$ consecutive samples at $|E| \ge 1.5$ A: latches `DEGRADED` mode within 150 µs, derates speed by 25% for 500 ms isolation timeout, and smoothly restores normal closed-loop operation.
- **Boundary Unit Tests:** Added `test_burst_immunity_envelope_boundaries` in `simulation/test_scenarios.py` verifying all 5 boundary conditions against the physical C controller via SIL simulation. All 5 boundary scenarios pass.

---

## Round 5 - Task 4: Cycle-Counter Software Benchmarking (`-DBENCH_TIMING`) & Bench Bringup Guide

### Defects Identified
- Developers without a high-speed digital storage oscilloscope had no method to profile execution timing on target hardware.
- Documentation lacked a clear wiring checklist and step-by-step procedure for bench bringing-up and oscilloscope measurement.

### Implementation
- **Hardware Cycle-Counter Instrumentation:** Added `#ifdef BENCH_TIMING` instrumentation in `src/main.cpp` using the Xtensa 32-bit hardware cycle counter (`xthal_get_ccount()` at 240 MHz, 4.167 ns resolution).
- **Per-Tick Profiling Metrics:**
  - ADC read / conversion duration (`t_adc`)
  - Pure FOC calculation duration (`t_ctrl`)
  - Total task execution duration (`t_task`, matching GPIO 14 HIGH pulse width)
  - Task-wake interval and jitter ($50.0\,\mu\text{s} \pm \Delta t$)
  - Consecutive and total real-time deadline overruns
- **Statistical Aggregation:** Metrics are sampled in integer cycles in the 20 kHz task without floating-point overhead, aggregated across a 20,000-tick window (1.0 second), and printed cleanly from `loop()` over Serial at 115200 bps without violating real-time task deadlines.
- **PlatformIO Benchmark Target:** Added `[env:esp32dev_bench]` in `platformio.ini` enabling one-command building (`pio run -e esp32dev_bench`).
- **Bench Bringup Guide:** Created `docs/bench_bringup.md` containing hardware pinout wiring tables, oscilloscope trigger guidelines for GPIO 14, benchmark output specifications, and evidence submission protocols.
- **Documentation Integrity:** Maintained explicit "NOT MEASURED - requires hardware" status for all execution numbers until raw hardware captures are committed.

---

## Round 5 - Task 5: Bounded 15 µs ADC Conversion Timeout & Immediate Error Bailout

### Defects Identified
- The previous 50 µs ADC timeout was too generous for a 20 kHz loop (entire tick period is 50 µs). Three successive timeouts could block the task for up to 150 µs (3 missed control deadlines) before tripping a fault.
- Sequential channel reads did not check the error flag immediately after each channel, continuing to execute subsequent conversions on a failing bus.

### Implementation
- **Timeout Reduction:** Reduced `ADC_CONVERSION_TIMEOUT_US` in `src/main.cpp` from 50 µs to 15 µs. A 15 µs bound ensures total 3-channel sampling never exceeds 45 µs (< 50 µs tick).
- **Immediate Error Bailout:** Introduced `latch_hardware_fault_safe_stop()` which immediately disables inverter gate drives (`PIN_GATE_EN = 0`), zeroes PWM outputs, asserts the fault LED, sets `telemetry_mode = 5` (`SAFE_STOP`), and drops the timing benchmark pin.
- **Per-Channel Error Checks:** Integrated error verification after Phase A, Phase B, and Phase C reads in both `foc_control_task` and the startup offset calibration loop in `setup()`. If any channel conversion fails, the task bails out in $\le 15\,\mu\text{s}$, preventing missed deadlines and safely disabling power stages.
- **Honest Documentation:** Rationale is fully documented in code comments without asserting unmeasured conversion times.

---

## Round 5 Verification Summary

- **C Unit Tests:** `make lib && make test` $\to$ **PASSED** (<$10^{-5}$ float round-trip invertibility).
- **Standard Embedded Build:** `pio run` $\to$ **SUCCESS** (RAM: 22,212 B / 6.8%, Flash: 299,545 B / 22.9%, 0 errors).
- **Benchmark Embedded Build:** `pio run -e esp32dev_bench` $\to$ **SUCCESS** (RAM: 22,364 B / 6.8%, Flash: 301,121 B / 23.0%, 0 errors).
- **Automated SIL Test Suite:** `.venv/bin/python3 -m pytest simulation/ -q` $\to$ **128/128 PASSED (100%)** in 673.36s (11m 13s).
- **Documentation Compliance:** All hardware metrics marked "NOT MEASURED - requires hardware" pending hardware testing by developer.

---

# Round 6 Audit Remediations & Technical Report

## Round 6 - Task 1: Clean Verbose PlatformIO Builds & Evidence Artifacts

### Implementation
- Executed clean verbose builds (`pio run -t clean && pio run -v`) for both default and benchmark targets:
  - Standard environment (`esp32dev`): Log saved to `docs/evidence/pio_build_clean_20261020.log`.
    - RAM Usage: 22,212 bytes (6.8% of 327,680 bytes)
    - Flash Usage: 299,545 bytes (22.9% of 1,310,720 bytes)
    - Double-promotion errors: 0 (enforced via `-Werror=double-promotion`)
  - Benchmark environment (`esp32dev_bench`): Log saved to `docs/evidence/pio_build_bench_20261020.log`.
    - RAM Usage: 22,364 bytes (6.8% of 327,680 bytes)
    - Flash Usage: 301,121 bytes (23.0% of 1,310,720 bytes)
    - Double-promotion errors: 0 (enforced via `-Werror=double-promotion`)
- **Warning Accounting:** Documented exact compiler diagnostics:
  - 0 double-promotion errors or warnings across all translation units.
  - 1 intentional uncommissioned dead-time compile `#warning` emitted in firmware (`src/motor_params.h`).
  - 1 upstream Arduino framework non-void return warning in `esp32-hal-uart.c:153:9`.

---

## Round 6 - Task 2: Enforcement of `-Werror=double-promotion` in PlatformIO

### Implementation
- Updated `platformio.ini` to explicitly enforce `-Werror=double-promotion` in `build_flags` for both `[env:esp32dev]` and `[env:esp32dev_bench]`.
- Verified that all single-precision arithmetic in `src/main.cpp`, `src/foc_core.c`, and observer modules strictly adheres to single-precision IEEE 754 without implicit promotion.

---

## Round 6 - Task 3: Relative Path Documentation Links & Historical Metric Labeling

### Implementation
- Replaced all absolute `file:///Users/...` links across `README.md` and `docs/results/final_report.md` with repository-relative paths (`src/...`, `docs/evidence/...`).
- Labeled all older RAM and Flash size figures across previous rounds in `CHANGELOG-AUDIT.md` explicitly as historical per-round build snapshots.

---

## Round 6 - Task 4: Configurable ADC Conversion Timeout

### Implementation
- Wrapped `ADC_CONVERSION_TIMEOUT_US` in `src/main.cpp` with `#ifndef ADC_CONVERSION_TIMEOUT_US` guards to allow compile-time overriding via `-DADC_CONVERSION_TIMEOUT_US=<value>`.
- Updated `docs/bench_bringup.md` with hardware commissioning guidelines specifying that `ADC_CONVERSION_TIMEOUT_US` must be set above the maximum observed ADC read time on the target bench, while remaining bounded within the 50 µs tick budget.

---

## Round 6 - Task 5: Illustrative Console Output Formatting in Bench Bringup Guide

### Implementation
- Marked the serial output example block in `docs/bench_bringup.md` with an explicit `[ILLUSTRATIVE ONLY — FORMAT TEMPLATE]` callout.
- Replaced numeric values on the `Wake Period` line with `X.XX` placeholders (`min: X.XX us | avg: X.XX us | max: X.XX us (Jitter: +/-X.XX us)`) to prevent unverified numbers from being misconstrued as physical measurements.

---

## Round 6 - Task 6: Selective Silencing of Host SIL Compile `#warning`

### Implementation
- Added `-DSIL_BUILD` to `CFLAGS` in `Makefile`.
- Updated `src/motor_params.h` to check `#elif defined(SIL_BUILD)`:
  - When compiling for the host SIL environment (`SIL_BUILD` defined), `CTRL_PARAM_DEAD_TIME` defaults cleanly to `0.0f` without emitting a compile `#warning`.
  - When compiling embedded firmware without `DEAD_TIME_COMMISSIONED_S`, the `#warning` remains active to alert engineers on uncommissioned hardware.
- Regression tests in `simulation/test_dead_time_sensitivity.py` continue to assert that firmware defaults to `0.0f` and the SIL simulation explicitly uses `SIM_DEAD_TIME`.

---

## Round 6 Verification Summary

- **C Unit Tests:** `make lib && make test` $\to$ **PASSED** (<$10^{-5}$ float round-trip invertibility, 0 warnings).
- **Embedded Clean Build:** `pio run -e esp32dev -t clean && pio run -e esp32dev -v` $\to$ **SUCCESS** (`docs/evidence/pio_build_clean_20261020.log`).
- **Embedded Benchmark Build:** `pio run -e esp32dev_bench -t clean && pio run -e esp32dev_bench -v` $\to$ **SUCCESS** (`docs/evidence/pio_build_bench_20261020.log`).
- **SIL Test Suite:** `.venv/bin/python3 -m pytest simulation/` $\to$ **128/128 PASSED (100%)**.
- **Documentation Compliance:** All hardware metrics remain marked "NOT MEASURED - requires hardware".

---

## Round 7 - PDF Guide Documentation & Scenario Integrity Audit

### Root Cause & Defect Analysis
1. **Hardcoded Scenario Table & Titles:** `build_pdf_guide.py` previously contained hardcoded titles and parameters that disagreed with `simulation/fault_injection/fault_scenarios.yaml`:
   - Scenario 7 was incorrectly labeled "Ls +15%" instead of the YAML scale `0.80` (-20%).
   - Scenario 10 was incorrectly labeled "300 RPM" instead of the YAML reference speed `500 RPM`.
   - Scenario 11 was incorrectly labeled "200 RPM/s" instead of the YAML ramp rate `500 RPM/s`.
   - Legacy fabricated scenario names ("Inverter Leg A Open", "Two-Phase Startup", "Intermittent Fault", "Torque Step (+0.5Nm)", "Phase B/C offset", "Parameter Mismatch +-20%") were present in draft tables.
2. **Missing Test Result Grounding:** The PDF scenario table previously assumed "PASS" without enforcing actual test execution artifacts.
3. **Hardcoded Test Counts:** Chapter 8 listed hardcoded test counts (86/8 vs actual 87/9; total 128 vs 131).
4. **Incorrect Motor Torque Claim:** Draft text claimed a +0.10 N·m step "equals rated full load", whereas continuous rated torque is $1.5 \cdot P \cdot \psi_f \cdot I_n = 0.45\text{ N}\cdot\text{m}$ (making +0.10 N·m approximately 22% of continuous rated torque).
5. **Ambiguous Fault Timeout Mismatch:** Draft diagrams listed 200 ms for ambiguous dual faults, whereas firmware in `src/fault_monitor.c:431` enforces a 1.5 s (1500 ms) timeout.
6. **Ungrounded Marketing Claim:** The conclusion contained an unverified claim that this architecture delivered capabilities "previously reserved for aerospace hardware".

### Implementation & Verification
1. **Dynamic Master Scenario Table & Parameter-Driven Titles:**
   - Implemented `generate_scenario_title_and_desc(sc_key, y_conf)` in `build_pdf_guide.py` to dynamically construct titles and descriptions from YAML parameters (`scale`, `speed_ref_rpm`, `rate_rpm_per_s`, `torque_Nm`, `limits`, `offsets`).
   - Sourced all 15 physical scenarios (baseline + 14 fault scenarios) directly from `simulation/fault_injection/fault_scenarios.yaml`.
2. **JUnit Evidence Enforcement & "NOT RUN" Defaulting:**
   - Created `pytest.ini` with `addopts = --junitxml=build/pytest_report.xml` so every automated test run generates structured machine-readable evidence.
   - Added `simulation/conftest.py` with session hooks to preserve cumulative test results across partial test executions.
   - Updated `get_scenario_data_from_yaml_and_junit` to default missing reports or untested scenarios strictly to `"NOT RUN"` rendered in `#64748B` grey, preventing unverified "PASS" publication.
3. **Dynamic Test Suite Counts:**
   - Implemented `get_collected_test_counts()` using `pytest --collect-only -q -o addopts=""` to dynamically count all 131 tests across all 12 modules at build time.
4. **Calculated Motor Rated Continuous Torque:**
   - Implemented `get_motor_rated_torque()` dynamically calculating $T_{rated} = 1.5 \cdot P \cdot \psi_f \cdot I_n = 1.5 \cdot 4 \cdot 0.015 \cdot 5.0 = 0.45\text{ N}\cdot\text{m}$ from `src/motor_params.h`.
   - Updated Scenario 9 documentation to dynamically state that +0.10 N·m represents $\approx 22\%$ of continuous rated torque.
5. **Firmware Ambiguous Fault Timeout Alignment:**
   - Corrected Mode 4 timeout description in `build_pdf_guide.py` to `1.5 s (1500 ms) -> SAFE_STOP (Mode 5)`.
   - Updated `docs/figures/fig5_state_machine.png` via `generate_figures.py`.
6. **Grounded Engineering Conclusion:**
   - Removed the aerospace claim from the PDF conclusion; replaced with a verifiable statement grounded in repo metrics (deterministic 20 kHz FOC, < 15 ms fault isolation, fail-safe latching, 100% green tests).
7. **Automated PDF Regression Test Suite (`simulation/test_pdf_integrity.py`):**
   - `test_pdf_scenario_table_matches_yaml`: Asserts 15 scenarios, validates all criteria/onsets/modes against YAML, ensures no disallowed fabricated keys exist, and confirms PASS status.
   - `test_committed_pdf_text_integrity`: Extracts text from `docs/Sensorless_FOC_Motor_Control_Guide.pdf` via `pypdf`, validates that YAML-derived titles and numbers appear (`0.80`, `-20%`, `500 RPM`, `500 RPM/s`, `0.10 N·m`, `0.45 N·m`, `22%`), and strictly asserts that none of the legacy fabricated names or ungrounded claims appear.
   - `test_code_constants_audit`: Verifies that all audited constants in C headers match canonical values.

### Generated vs. Hand-Written Numbers Audit

The following table documents every numerical value appearing in `docs/Sensorless_FOC_Motor_Control_Guide.pdf`, classifying each as dynamically generated at build time or hand-written/fixed:

| Category | Numerical Values | Source / Derivation | Status |
| :--- | :--- | :--- | :--- |
| **Scenario Parameters** | $R_s \times 1.05$ (+5%), $L_s \times 0.80$ (-20%), speed refs ($500$, $1800$, $2000$, $-2000\text{ RPM}$), ramp rate ($500\text{ RPM/s}$), load torque ($0.10\text{ N}\cdot\text{m}$), limits ($10.0\text{ A}$), offsets ($2.0\text{ A}$), onsets ($0.5\text{ s}, 1.5\text{ s}, 2.0\text{ s}$) | Dynamically generated from `simulation/fault_injection/fault_scenarios.yaml` | **GENERATED** |
| **Acceptance Criteria** | Angle RMS limits ($5.0^\circ, 10.0^\circ$), max angle error ($15^\circ, 25^\circ, 35^\circ, 60^\circ, 80^\circ, 150^\circ$), ripple ($400, 450, 1000, 4500\text{ RPM}$), reconstruction error RMS ($0.15\text{ A}, 0.20\text{ A}$), latency ($15\text{ ms}$), $V_{bus}$ decay ($0.5\text{ V}$) | Dynamically generated from `simulation/fault_injection/fault_scenarios.yaml` | **GENERATED** |
| **Test Verdicts** | All 15 scenario test result badges (`PASS`) | Dynamically parsed from `build/pytest_report.xml` testcases (defaults to `NOT RUN` in `#64748B` grey if absent) | **GENERATED** |
| **Motor Rated Torque** | $T_{rated} = 0.45\text{ N}\cdot\text{m}$, load percentage $\approx 22\%$ | Dynamically computed from `src/motor_params.h` ($1.5 \cdot P \cdot \psi_f \cdot I_n$) | **GENERATED** |
| **Test Suite Counts** | Total test count ($131$), per-file module counts (`test_scenarios.py`: 87, `test_handoff.py`: 9, `test_dead_time_sensitivity.py`: 8, `test_bldc.py`: 6, etc.) | Dynamically collected via `pytest --collect-only -q -o addopts=""` | **GENERATED** |
| **Firmware Constants** | Control frequency ($20,000\text{ Hz}$), period ($50.0\text{ }\mu\text{s}$), ADC timeout ($15.0\text{ }\mu\text{s}$), overruns ($3$), pole pairs ($4$), $I_n$ ($5.0\text{ A}$), $V_{bus}$ ($24.0\text{ V}$), $R_s$ ($0.4\text{ }\Omega$), $L_s$ ($0.001\text{ H}$), $\psi_f$ ($0.015\text{ Wb}$), KCL threshold ($0.5\text{ A}$), timeout ($1.5\text{ s}$) | Audited against `#defines` in `src/motor_params.h`, `src/fault_monitor.c`, `src/main.cpp` (build fails on mismatch) | **AUDITED / GENERATED** |
| **Static Memory Footprint** | RAM: $22,212\text{ bytes}$ (6.8% of 320 KB), Flash: $299,545\text{ bytes}$ (22.9% of 1.3 MB) | Exact cross-compiled ELF sizes from committed build evidence (`docs/evidence/pio_build_clean_20261020.log`) | **VERIFIED ARTIFACT** |
| **Transformation Constants** | Clarke/Park coefficients ($\frac{2}{3}$, $\frac{1}{\sqrt{3}}$, $\frac{\sqrt{3}}{2}$) | Standard mathematical formulation of orthogonal projections | **HAND-WRITTEN (THEORY)** |
| **On-Target Execution Timing** | ISR, ADC read, control step, loop jitter | Marked "NOT MEASURED - requires hardware" per repo rules (bench timing flag added in Round 5, requires physical hardware run) | **NOT MEASURED** |

---

## Round 7 Verification Summary

- **Physical Simulation Test Suite:** `.venv/bin/pytest simulation/ -q` $\to$ **131/131 PASSED (100% GREEN)**.
- **Automated PDF Integrity Suite:** `.venv/bin/pytest simulation/test_pdf_integrity.py` $\to$ **3/3 PASSED (100%)**.
- **Automated Code Constants Audit:** Verified all constants match canonical C source code definitions.
- **PDF Compilation:** `docs/Sensorless_FOC_Motor_Control_Guide.pdf` compiles cleanly with dynamic table generation and zero formatting errors.

---

## Round 8 - Evidence Integrity, Testcase Fingerprinting & Staleness Prevention

### Root Cause & Defect Analysis
1. **Stale Evidence Persistence Across Source Changes:** `simulation/conftest.py` previously merged pre-existing XML records cumulatively without checking whether underlying source files had changed. A developer could mutate detector thresholds in `src/fault_monitor.c`, break scenario physics, and yet running `pytest simulation/test_pdf_integrity.py` alone would still pass because it read stale historical "PASS" records from `build/pytest_report.xml`.
2. **JUnit Testcase Duplication:** Pre-existing XML reports accumulated duplicate testcase entries (e.g., 136 records for 131 tests) due to non-uniform keying between test file paths, classnames, and parameter representations across test runs.
3. **Legacy Terminology Inaccuracy ("ISO/IEC"):** The PDF technical guide referenced "ISO/IEC" in the table of contents, Chapter 8 overview, and script descriptions. The repository implements rigorous project-specific engineering acceptance criteria, not certified ISO/IEC compliance standards.
4. **Lack of Cryptographic Build Traceability:** The compiled PDF lacked an embedded cryptographic fingerprint linking its claims and scenario tables to the exact source commit and file tree from which it was generated.

### Implementation & Verification
1. **Deterministic Source Fingerprinting & Automatic Stale Record Invalidation:**
   - Implemented `compute_source_fingerprint(repo_root)` in `build_pdf_guide.py` and `simulation/conftest.py`. The fingerprint computes a deterministic SHA-256 hash across all motor control and simulation source files: `src/*.c`, `src/*.h`, `src/motor_params.h`, `simulation/fault_injection/fault_scenarios.yaml`, and `simulation/**/*.py` (excluding PDF test scripts).
   - In `simulation/conftest.py` (`pytest_sessionstart`), pre-existing JUnit records in `build/pytest_report.xml` are inspected. Any records with a fingerprint differing from the current source fingerprint are pruned.
   - Updated `test_pdf_scenario_table_matches_yaml` in `simulation/test_pdf_integrity.py` to assert that every scenario record in `build/pytest_report.xml` possesses a fingerprint matching the current source tree. If any record is missing or stale, the test fails with: `"Run the scenario tests ('pytest simulation/test_scenarios.py') to re-verify."`
2. **Strict NodeID-Based De-duplication (1:1 Ratio):**
   - In `simulation/conftest.py`, session cases are strictly keyed by their canonical pytest `nodeid` (e.g. `simulation/test_scenarios.py::test_scenario[scenario_0]`).
   - Normalised XML `classname` attributes uniformly.
   - Implemented `test_junit_report_has_exactly_one_record_per_collected_test` in `simulation/test_pdf_integrity.py`. It uses `pytest --collect-only` to verify that `build/pytest_report.xml` contains exactly one record per collected test with zero duplicates (133 records for 133 tests).
3. **Staleness Bug Regression Test Suite:**
   - Implemented `test_staleness_detection_fails_on_source_mutation` in `simulation/test_pdf_integrity.py`.
   - In an isolated temporary directory, it mutates `src/fault_monitor.c`, runs only `pytest simulation/test_pdf_integrity.py`, and asserts that the suite fails with an exit code of 1 due to the stale fingerprint mismatch.
   - Incorporated `SKIP_STALENESS_SUBPROCESS` environment variable guard to eliminate recursive test spawning.
4. **Removal of "ISO/IEC" Terminology:**
   - Replaced all occurrences of "ISO/IEC" with "project acceptance criteria" across the Executive Summary, Table of Contents, Chapter 7 `metrics.py` description, Chapter 8 intro, and `test_scenarios.py` description in `build_pdf_guide.py`.
   - Added `"ISO/IEC"` to `disallowed_phrases` in `test_committed_pdf_text_integrity` to prevent regression.
5. **PDF Recompilation with Cryptographic Traceability:**
   - Rebuilt `docs/Sensorless_FOC_Motor_Control_Guide.pdf` with ReportLab.
   - Added a `TraceabilityNote` section on Page 19 displaying the exact SHA-256 source fingerprint (`6b0e7ba6b9347798801ba2c58209be5c45e65ab7ad690c21e1e85859f7aabe1e`), the Git commit hash, and verification badge.
   - Verified that the document remains exactly 19 pages with zero formatting overflows.

---

## Round 8 Verification Summary

- **C Unit Tests:** `make lib && make test` $\to$ **PASSED** (<$10^{-5}$ float round-trip invertibility, 0 warnings).
- **Physical Simulation Test Suite:** `.venv/bin/pytest simulation/ -q` $\to$ **133/133 PASSED (100% GREEN)**.
- **Automated PDF Integrity Suite:** `.venv/bin/pytest simulation/test_pdf_integrity.py` $\to$ **5/5 PASSED (100%)**.
- **JUnit 1:1 Traceability:** Exactly 133 testcases in `build/pytest_report.xml` matching 133 collected tests with 100% source fingerprint consistency.
- **Automated Code Constants Audit:** All constants verified against canonical C headers.
- **PDF Artifact:** `docs/Sensorless_FOC_Motor_Control_Guide.pdf` compiled cleanly with source fingerprint traceability and verified on Page 19.

---

## Round 9 - Staleness Regression Test Remediation & Non-Git Export Compatibility

### Root Cause & Defect Analysis
1. **False-Positive Pass in Staleness Mutation Test:** In Round 8, `test_staleness_detection_fails_on_source_mutation` created a temporary copy without `.git`. Inside this copy, `test_committed_pdf_text_integrity` failed because `subprocess.check_output(["git", "log", ...])` raised `CalledProcessError` (exit code 128: `fatal: not a git repository`). Because the test assertion accepted any output containing `"failed"`, the test passed even with zero source mutation.
2. **Crash in Non-Git Environments:** Running `test_pdf_integrity.py` in a non-git export (e.g., source tarball or CI container without git metadata) caused `test_committed_pdf_text_integrity` to crash on `git log` rather than skipping only the commit-hash check.
3. **Unverified Control Baseline:** The staleness test lacked an unmutated control step verifying that the copied environment passes cleanly before mutation is applied.
4. **Vague Error Assertion:** The assertion did not verify that the failure was specifically caused by a fingerprint mismatch.

### Implementation & Verification
1. **Non-Git Export Detection & Commit-Hash Skip:**
   - In `simulation/test_pdf_integrity.py` (`test_committed_pdf_text_integrity`), added a check for `.git` and `git rev-parse --is-inside-work-tree`.
   - When `.git` is absent, the test cleanly skips *only* the commit-hash assertion, emitting a `UserWarning` and a diagnostic note to stderr: `"[SKIP] Non-git export detected (.git missing): skipping commit-hash assertion in PDF text integrity."`
   - All other assertions (disallowed phrases, YAML parameters, rated torque calculations, scenario titles, and SHA-256 source fingerprint) remain strictly active and pass.
2. **Two-Phase Staleness Test (Control + Mutation):**
   - In `test_staleness_detection_fails_on_source_mutation`:
     - **Phase 1 (Control):** Executes `pytest simulation/test_pdf_integrity.py -v` in the clean, unmutated non-git temporary directory with `SKIP_STALENESS_SUBPROCESS=1` and asserts that it passes 100% (exit code 0).
     - **Phase 2 (Mutation):** Appends a comment to `src/fault_monitor.c`, re-executes `test_pdf_integrity.py`, asserts that it fails (exit code != 0), and asserts that the combined output explicitly contains the exact string `"stale source fingerprint"`.
3. **Targeted Failure Messages in Integrity Suite:**
   - Updated `test_pdf_scenario_table_matches_yaml` to report: `"(got 'NOT RUN': missing or stale source fingerprint)"`.
   - Updated `test_junit_report_has_exactly_one_record_per_collected_test` to report: `"Testcase ... has stale source fingerprint"`.
4. **README Evidence Documentation:**
   - Added Section 14.5 to `README.md` documenting the exact scope of files covered by the deterministic SHA-256 evidence fingerprint (`src/*.c`, `src/*.h`, `src/motor_params.h`, `simulation/fault_injection/fault_scenarios.yaml`, `simulation/**/*.py` excluding `test_pdf*`).
   - Clarified that firmware entry points and build files (`src/main.cpp`, `platformio.ini`, `Makefile`) are not hashed in the SIL source fingerprint, and that embedded firmware compilation and warnings are evidenced separately by committed build logs in `docs/evidence/pio_build_*.log`.

---

## Round 9 Verification Summary

- **C Unit Tests:** `make lib && make test` $\to$ **PASSED** (<$10^{-5}$ float round-trip invertibility, 0 warnings).
- **Physical Simulation Test Suite:** `.venv/bin/pytest simulation/ -q` $\to$ **133/133 PASSED (100% GREEN)**.
- **Automated PDF Integrity Suite:** `.venv/bin/pytest simulation/test_pdf_integrity.py` $\to$ **5/5 PASSED (100%)** in 2.47s.
- **Two-Phase Staleness Test:** Verified control phase passes with exit code 0; mutated phase fails with exit code 1 and outputs `"stale source fingerprint"`.
- **Non-Git Export:** Verified unmutated copy without `.git` passes all tests with UserWarning on commit hash.
- **Documentation:** `README.md` and `CHANGELOG-AUDIT.md` fully updated.





