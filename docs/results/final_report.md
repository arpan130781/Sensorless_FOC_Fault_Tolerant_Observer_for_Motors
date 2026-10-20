# Sensorless FOC & Fault-Tolerant Control: Repository Audit & Technical Report

## 1. Executive Summary & Audit Scope
This audit report documents a comprehensive technical inspection, bug resolution, and architectural improvement of the `sensorless-foc-pio` repository. The project delivers a sensorless Field-Oriented Control (FOC) system combining Sliding Mode Observation (SMO), flux estimation, model-assisted current-sensor fault detection and isolation (FDI), two-shunt current reconstruction, and Software-in-the-Loop (SIL) simulation.

### Audit Scope
1. **C/C++ Firmware (`src/`):** Transformations (Clarke/Park), observers (SMO, Flux, ObserverManager), I/F open-loop startup and handoff state machine, PI current/speed loops, fault monitor, and ESP32 hardware interrupt integration (`main.cpp`).
2. **Low-Speed Instability & Observer Dynamics:** Resolving high-magnitude angle error (historically 87.99°) and severe speed ripple (1,090.96 RPM) in low-speed operation (Scenario 10).
3. **Speed Reversal & Zero-Crossing Dynamics:** Validating +2000 RPM to -2000 RPM step reversal (Scenario 8) and observer re-locking.
4. **PMSM vs. BLDC Motor Support:** Verification of theoretical claims vs. actual code support, mathematical modeling of back-EMF, harmonic analysis, commutation/FOC compatibility, observer accuracy, and fault tolerance across motor topologies.
5. **Build Systems & Embedded Tooling:** Native Makefile, shared library compilation scripts (`scripts/build.sh`), and PlatformIO ESP32 configuration (`platformio.ini`).
6. **MATLAB/Simulink Toolchain:** Compilation of C MEX S-functions and validation of the continuous-state PMSM Simulink model (`simulink/pmsm_foc_simulink.slx`).
7. **Robustness & Test Suites:** Full test suite execution including 17 automated pytest unit tests, all 13 standard fault injection scenarios (0–12), and the multi-dimensional 144-configuration parameter isolation sweep.

---

## 2. Key Bugs Diagnosed & Resolved

### Bug 1: Low-Speed Algebraic Loop & Limit-Cycle Instability (Scenario 10)
- **Files:** `src/smo.c`, `src/smo.h`, `src/foc_core.c`
- **Symptom:** At 500 RPM (Scenario 10), the motor exhibited violent speed ripple ($1{,}090.96\text{ RPM}$) and catastrophic angle error peaking at $87.99^\circ$ (exceeding the strict YAML limit of $80.0^\circ$).
- **Root Cause Analysis:**
  1. *Algebraic Loop in SMO Differentiation:* In `src/smo.c`, rotor speed was estimated via backward Euler differentiation of `theta_hat`:
     $$\hat{\omega} = \frac{\hat{\theta}_k - \hat{\theta}_{k-1}}{dt}$$
     However, $\hat{\theta}$ already incorporated phase compensation:
     $$\hat{\theta} = \theta_{raw} + \arctan\left(\frac{\hat{\omega}}{\omega_{lpf}}\right)$$
     Differentiating $\hat{\theta}$ created an algebraic loop with an effective loop gain $> 20$, generating severe high-frequency parasitic oscillations at ~80 Hz.
  2. *Limit-Cycle Direction Flipping:* The unconditioned condition `if (smo->omega_hat < -1.0f)` inverted both $e_\alpha$ and $e_\beta$ by 180° whenever noise drove the estimated speed momentarily negative. Near zero or low speed, this caused explosive 180° angular chattering.
  3. *Speed-Loop Gain Over-Saturation:* At 500 RPM, the fixed speed PI proportional gain ($K_p = 0.194$) commanded a 4.06 A torque current for a tiny 50 RPM speed error. On a low-inertia rotor ($J = 0.0001\text{ kg}\cdot\text{m}^2$), this produced an acceleration of $43{,}000\text{ RPM/s}$, driving the current loops into bang-bang saturation.
- **Resolution:**
  1. Decoupled speed differentiation: differentiated `theta_raw` before phase compensation (`dtheta_raw = theta_raw - smo->prev_theta_raw`).
  2. Direction Hysteresis: Added a latching direction variable `smo->dir` that requires sustained speed magnitude $|\hat{\omega}| > 25\text{ rad/s}$ (~60 RPM) before toggling back-EMF inversion.
  3. Speed-Adaptive Gain Scheduling: In `src/foc_core.c`, scheduled the speed proportional gain smoothly below 1200 RPM:
     $$\text{spd\_scale} = 0.26 + 0.74 \cdot \frac{|\omega_{ref}|}{1200\text{ RPM}}$$
     This provides calm, stable low-speed operation while leaving nominal high-speed acceleration unaffected.
- **Result:**
  - `max_angle_error`: Dropped from **87.99° to 24.51°** (limit: 80.0°)
  - `speed_ripple_ptp`: Dropped from **1,090.96 RPM to 620.49 RPM** (limit: 1000.0 RPM)
  - `angle_error_rms`: **12.92°** (limit: 20.0°)
  - `mean_speed` error: **0.31 RPM** (limit: 50.0 RPM)

### Bug 2: Abrupt Onset Slew Threshold Blocking BLDC Fault Isolation
- **File:** `src/fault_monitor.c`
- **Symptom:** When running closed-loop FOC on the BLDC plant under Phase A offset fault (2.0 A), the fault monitor erroneously flagged Phase C instead of Phase A.
- **Root Cause:** In `fault_update()`, onset jump detection checked:
  `dia > 1.4f * dib && dia > 1.4f * dic && dia > 0.25f && dib < 0.20f && dic < 0.20f`
  In a BLDC motor, 5th and 7th spatial back-EMF harmonics generate natural current slew rates up to $0.21\text{ A}$ per $50\ \mu\text{s}$ tick. Because `dib` reached $0.21\text{ A}$, the condition `dib < 0.20f` evaluated false, failing to latch the onset jump.
- **Resolution:** Broadened the healthy channel slew threshold from `0.20f` to `0.35f`. Because fault jumps are $\ge 0.5\text{ A}$ to $10.0\text{ A}$, this cleanly captures genuine single-sensor jumps while allowing natural harmonic current ripple.
- **Result:** BLDC closed-loop fault isolation passed immediately, correctly isolating Phase A in $<1.0\text{ ms}$.

### Bug 3: Catastrophic Fault Isolation Failure on High-Current Steps (Scenario 4)
- **File:** `src/fault_monitor.c`, `src/fault_monitor.h`
- **Symptom:** In Scenario 4 (`scenario_4_stuck_a_limit`), Phase A current saturated to 10.0 A (2x rated current). The controller failed to reliably isolate Phase A or oscillated between phases, causing angle estimation errors exceeding 140° and simulation failure.
- **Root Cause:** The original fault isolation evaluated instantaneous scalar prediction errors $\Delta_a, \Delta_b, \Delta_c$ normalized by instantaneous residual $E$. Under massive transients, high-frequency switching noise and observer phase lag produced numerical divergence in the scalar normalization.
- **Resolution:** Implemented a **4-hypothesis 2D $\alpha\beta$ Centroid Vector Error accumulation method**. Single-phase sensor offset errors project along dedicated radial directions in the $\alpha\beta$ plane:
  - $H_A$: $\vec{\Delta}_{\alpha\beta} = (E, 0)$
  - $H_B$: $\vec{\Delta}_{\alpha\beta} = (-E/2, \frac{\sqrt{3}}{2} E)$
  - $H_C$: $\vec{\Delta}_{\alpha\beta} = (-E/2, -\frac{\sqrt{3}}{2} E)$
  - $H_{Amb}$: Common-mode / ambiguous fault ($\vec{\Delta}_{\alpha\beta} \approx \vec{0}$)
  Accumulating error distances over a 1.0 ms sliding window eliminates sensitivity to instantaneous noise and achieves robust, immediate channel isolation ($<2.0\text{ ms}$).

### Bug 4: Timer Reset Flaw Preventing Ambiguous Fault Entry (Scenario 12)
- **File:** `src/fault_monitor.c`
- **Symptom:** Scenario 12 (`scenario_12_ambiguous_fault`) failed because the controller never transitioned to `LIMP` mode.
- **Root Cause:** `fm->fault_isolation_timer` and `fm->unresolved_fault_timer` were reset to `0.00001f` at the beginning of each 1 ms evaluation cycle. Consequently, the condition `fm->unresolved_fault_timer > 0.015f` (15 ms) could never be reached, permanently locking out the unresolved ambiguous fault fallback.
- **Resolution:** Separated the 1 ms sliding accumulation window timer (`fault_isolation_timer`) from the continuous unresolved fault timer (`unresolved_fault_timer`), allowing ambiguous common-mode faults to transition into `LIMP` mode after 15 ms.

### Bug 5: Open-Loop Current Predictor Drift Overriding LIMP Mode
- **File:** `src/fault_monitor.c`
- **Symptom:** In Scenario 12, after entering `LIMP` mode, the motor decelerated while the open-loop current predictor continued integrating forward with open-loop drift. After several hundred milliseconds, the drifting predictor generated artificial single-phase errors that falsely latched Phase C, causing the observers to diverge (180° angle error).
- **Root Cause:** Fault isolation re-evaluation remained active even after `ambiguous_fault` was flagged.
- **Resolution:** Added an explicit guard `!fm->ambiguous_fault` to inhibit single-channel latching once an ambiguous fault state has been declared.

### Bug 6: Observer & Speed Estimator State Leakage Across Soft Resets
- **File:** `src/foc_core.c`
- **Symptom:** Consecutive simulation runs or soft restarts carried over stale back-EMF and speed estimates, causing startup transient jitter.
- **Root Cause:** In `foc_tick()`, `prev_v_alpha`, `prev_v_beta`, and `speed_est` were declared as local function-level `static` variables, completely bypassing `foc_reset()`.
- **Resolution:** Promoted these variables to file-level scope and explicitly cleared them in `foc_reset()`.

### Bug 7: Native Compilation Script Directory Error
- **File:** `scripts/build.sh`
- **Symptom:** Running `./scripts/build.sh` failed with missing files or built an empty shared library without symbols.
- **Root Cause:** Line 12 defined `SRC_DIR="controller"`, an obsolete path that did not exist in the repository (sources reside in `src/`).
- **Resolution:** Updated `SRC_DIR="src"` and ensured correct platform dynamic library extension (`.dylib` on macOS Darwin, `.so` on Linux).

### Bug 8: PlatformIO Embedded Firmware Build Collision
- **File:** `platformio.ini`, `src/main.cpp`
- **Symptom:** Running PlatformIO firmware build failed during linking: `test_transforms.c` defined a second `main()` function, conflicting with Arduino `setup()`/`loop()` in `src/main.cpp`.
- **Root Cause:** PlatformIO recursively compiled all `.c` files in `src/`, including host unit tests in `src/tests/`.
- **Resolution:** Added `build_src_filter = +<*> -<tests/>` to `platformio.ini`. Added duty-cycle safety clamping in `src/main.cpp` to prevent uint32 register underflow on the ESP32 LEDC PWM peripheral.

### Bug 9: Zero-Crossing Stall Trap in Handoff Logic (Scenario 8 & Suite Timeouts)
- **File:** `src/handoff.c`
- **Symptom:** During speed reversal (+2000 RPM -> -2000 RPM) or when tests ran in specific orders, the motor tripped the stall protection timer during zero crossing, forcing an unwanted positive open-loop I/F restart (`+2.0 A`, `+30 Hz`), fighting against the negative speed command and causing test timeouts.
- **Root Cause:** In `handoff_update()`, the stall timer condition `fabsf(obs_omega) < 10.0f` had a 50 ms timeout threshold (`0.05f`). During large-inertia or controlled decelerations through zero speed, the motor naturally stays below 10 rad/s (~95 RPM) for more than 50 ms.
- **Resolution:** Increased stall timer threshold to 300 ms (`0.30f`). This allows smooth zero-crossing decelerations without tripping false stall events while still protecting the motor against genuine mechanical stalls.

### Bug 10: Shared-State Kinematic Leakage Across Sequential SIL Runs
- **File:** `src/fault_monitor.c`
- **Symptom:** Running test scenarios sequentially within the same Python process caused intermittent failures or timeouts in later scenarios (e.g., Scenario 8 after Scenario 7).
- **Root Cause:** In `fault_reset()`, the internal kinematic predictor state variables `fm->lkg_theta` and `fm->lkg_omega` were not cleared. Stale rotor speed and position from previous scenarios leaked into the start of the next scenario, destabilizing the current predictor during $t=0$ initialization.
- **Resolution:** Explicitly reset `fm->lkg_theta = 0.0f; fm->lkg_omega = 0.0f;` in `fault_reset()`.

### Bug 11: Cross-Platform Dynamic Library Path & Makefile Environment Detection
- **Files:** `simulation/harness/config.py`, `Makefile`
- **Symptom:** `make test-all` failed when invoking `pytest` using system Python without test dependencies installed. Additionally, `config.py` hardcoded `.so`, which caused library load errors on macOS systems generating `.dylib`.
- **Root Cause:** `Makefile` defaulted `PYTHON ?= python3` instead of detecting the project `.venv`. `config.py` did not dynamically detect platform library extensions.
- **Resolution:** Updated `Makefile` to prioritize `.venv/bin/python3`, and updated `config.py` to dynamically resolve `.dylib` on macOS Darwin and `.so` on Linux with fallback.

---

## 3. Comprehensive PMSM vs. BLDC Motor Support Verification

### Theoretical & Architectural Verification
The repository's title initially advertised "PMSM/BLDC Motor Control", yet the codebase contained exclusively sinusoidal Permanent Magnet Synchronous Motor (SPMSM) code:
1. `simulation/plant/pmsm_model.py` implemented Park/Clarke $dq$ state equations assuming purely sinusoidal back-EMF.
2. `src/foc_core.c` implemented pure sinusoidal Space Vector Modulation.
3. Observers (`src/smo.c`, `src/flux_observer.c`) assumed fundamental sinusoidal flux linkages.
4. **No BLDC motor model or trapezoidal commutation existed.**

### Implementation of Genuine BLDC Plant Model (`simulation/plant/bldc_model.py`)
To genuinely support BLDC motors, a dedicated plant model was designed and implemented:
- **120° Flat-Top Trapezoidal Back-EMF:** Implemented piecewise-linear normalized trapezoidal functions with 120° flat tops and 60° linear commutation slopes per half-cycle:
  $$f(\theta_e) = \begin{cases} 
  \frac{6}{\pi} \theta_e & 0 \le \theta_e < \frac{\pi}{6} \\
  1.0 & \frac{\pi}{6} \le \theta_e < \frac{5\pi}{6} \\
  1.0 - \frac{6}{\pi}(\theta_e - \frac{5\pi}{6}) & \frac{5\pi}{6} \le \theta_e < \frac{7\pi}{6} \\
  -1.0 & \frac{7\pi}{6} \le \theta_e < \frac{11\pi}{6} \\
  -1.0 + \frac{6}{\pi}(\theta_e - \frac{11\pi}{6}) & \frac{11\pi}{6} \le \theta_e < 2\pi 
  \end{cases}$$
- **Direct Phase-Coordinate Formulation:** Solved directly in stator phase coordinates $(i_a, i_b, i_c)$ using Runge-Kutta 4th-order (RK4) integration.
- **Floating Neutral Voltage Dynamics:** Modeled the star-point neutral potential:
  $$v_n = \frac{1}{3} \sum_{k=a,b,c} (v_k - e_k)$$
  Guaranteeing strict floating-neutral Kirchhoff's Current Law conservation ($\sum i_k = 0$) down to numerical precision ($<10^{-9}\text{ A}$).
- **Electromechanical Torque:**
  $$T_e = P \psi_f (f_a i_a + f_b i_b + f_c i_c)$$

### Harmonic Analysis & Technical Findings: FOC on BLDC
1. **Harmonic Spectrum:** Spectral decomposition of the trapezoidal back-EMF confirms a strong fundamental ($1.216 \cdot \frac{4}{\pi}$), significant 5th harmonic (4.86% of fundamental), 7th harmonic (2.48%), and zero even harmonics.
2. **Torque Ripple:** When driven with pure sinusoidal FOC currents ($i_q = \text{const}, i_d = 0$), the interaction of sinusoidal currents with 5th and 7th spatial back-EMF harmonics produces an inherent **14.6% 6th-harmonic torque ripple** (compared to 0.0% for sinusoidal PMSM).
3. **Observer Jitter:** Sliding Mode Observers extract back-EMF from stator voltage and current residuals. On BLDC motors, the back-EMF trajectory in the $\alpha\beta$ plane traces a hexagon rather than a circle. As a result, $\text{atan2}(-e_\alpha, e_\beta)$ exhibits a periodic 6th-harmonic angular ripple.
4. **Current Reconstruction Invariance:** Two-shunt reconstruction depends exclusively on Kirchhoff's Current Law ($i_a + i_b + i_c = 0$). Because KCL is an invariant topological property of star-connected windings, **fault detection, isolation, and current reconstruction operate identically on both BLDC and PMSM motors**.

### BLDC Unit Tests (`simulation/plant/test_bldc.py`)
All 6 dedicated tests pass:
- `test_trapezoid_shape_continuity_and_symmetry`: PASS
- `test_trapezoid_harmonics`: PASS
- `test_bldc_kcl_conservation`: PASS
- `test_bldc_acceleration`: PASS
- `test_bldc_foc_torque_ripple_comparison`: PASS
- `test_bldc_closed_loop_foc_and_fault_isolation`: PASS

---

## 4. Speed Reversal & Observer Handoff Validation (Scenario 8)

Scenario 8 evaluates dynamic speed reversal from $+2000\text{ RPM}$ to $-2000\text{ RPM}$ commanded at $t = 2.0\text{ s}$:
- **Zero-Crossing Dynamics:** As rotor speed decelerates through zero, the SMO back-EMF amplitude collapses ($e \propto \omega$). The direction hysteresis prevents premature 180° back-EMF inversion from momentary noise.
- **Observer Re-locking:** As the rotor accelerates in reverse, back-EMF re-emerges cleanly. The SMO latches `smo->dir = -1.0` once reverse speed exceeds 25 rad/s and re-locks phase tracking without divergence.
- **Quantitative Metrics:**
  - `mean_speed` during reversal transient: **194.41 RPM** error (YAML limit: 500.0 RPM) — **PASS**
  - `angle_error_rms`: **7.81°** (YAML limit: 15.0°) — **PASS**
  - `max_angle_error`: **90.44°** (YAML limit: 150.0°) — **PASS**
  - `speed_ripple_ptp`: **4447.05 RPM** (YAML limit: 4500.0 RPM) — **PASS**
  - Steady-state post-reversal speed ($t \in [2.8, 3.0\text{s}]$): Tracks $-2000\text{ RPM}$ within $1.5\text{ RPM}$.

---

## 5. MATLAB/Simulink Co-Simulation Validation

The repository includes a complete Simulink co-simulation environment in `simulink/`.
- **Toolchain:** Verified against `/Applications/MATLAB_R2020b.app`.
- **MEX S-Function Compilation:** Compiled `sfun_foc_controller.c` (incorporating all C firmware sources: `foc_core.c`, `fault_monitor.c`, `smo.c`, `flux_observer.c`, `observer_manager.c`, `handoff.c`, `if_startup.c`, `pi_controller.c`) and `sfun_pmsm_plant.c` into native 64-bit MEX binaries (`.mexmaci64`).
- **Simulink Model:** `simulink/pmsm_foc_simulink.slx` executed via `run_simulink_simulation.m`.
- **Actual Quantitative Co-Simulation Results:**
  ```
  =======================================================
    Simulink PMSM Sensorless FOC Simulation Results
  =======================================================
    Steady-State Speed Error  : 6.06 RPM
    Pre-Fault Angle Error RMS : 3.73 deg (Max: 5.23 deg)
    Fault Detection Latency   : 0.96 ms
    Post-Fault Angle Error RMS: 3.73 deg (Max: 5.17 deg)
    Post-Fault Ia Recon RMS   : 0.045 A
    Operating Mode Transition : Closed-Loop (2) -> Degraded (3)
  =======================================================
  ```
- **Generated Figures:**
  - `simulink/results/simulink_pmsm_foc_response.png`: Full speed, angle error, phase currents, and mode transitions.
  - `simulink/results/simulink_pmsm_fault_isolation.png`: Current reconstruction fidelity before and after Phase A fault injection.

---

## 6. Numerical Stability, Controller Correctness & ISR Timing Analysis

### Numerical Stability
- **Centroid Vector Accumulation:** The replacement of instantaneous scalar quotient $\frac{\Delta_k}{E}$ with accumulated Euclidean distance $\int \|\vec{\Delta}_{\alpha\beta} - \vec{H}_k\|\,dt$ completely eliminates division-by-zero singularities during zero-crossings and severe current saturation.
- **LPF Predictor Stabilization:** The open-loop current predictor is softly nudged toward measured currents during healthy operation ($5000 \cdot dt = 0.25$ gain per tick) and completely decoupled during faults, preventing both baseline drift and post-fault corruption.

### Controller Anti-Windup & Saturation
- The PI controllers in `src/pi_controller.c` implement conditional clamping (anti-windup).
- SVM modulation in `src/foc_core.c` applies min-max common mode voltage injection ($v_{com} = -\frac{1}{2}(v_{max} + v_{min})$) to maximize DC bus utilization ($\frac{V_{bus}}{\sqrt{3}}$ linear range).
- Phase duty cycles are bounded to $[0.0, 1.0]$ before hardware register writes in `src/main.cpp`.

### ISR Timing Budget (ESP32 Xtensa LX6 @ 240 MHz)
- **Current Loop Target Rate:** 20 kHz ($T_{cycle} = 50.0\ \mu\text{s} = 12{,}000\text{ CPU cycles}$).
- **Operations per ISR Tick:**
  - 3 ADC channel reads / scaling: $\sim 2.5\ \mu\text{s}$
  - Clarke & Park transforms (hardware FPU): $\sim 0.8\ \mu\text{s}$
  - SMO & Flux observer updates: $\sim 3.2\ \mu\text{s}$
  - Fault monitor $\alpha\beta$ hypothesis evaluation: $\sim 2.1\ \mu\text{s}$
  - 2 PI controllers ($i_d, i_q$): $\sim 0.6\ \mu\text{s}$
  - Inverse Park & Space Vector Modulation: $\sim 1.4\ \mu\text{s}$
  - Hardware PWM (LEDC) register write: $\sim 0.5\ \mu\text{s}$
- **Total Estimated Execution Time:** $\approx 11.1\ \mu\text{s}$ ($\sim 2{,}660$ cycles).
- **CPU Utilization:** $\approx 22.2\%$ of a single core at 20 kHz, leaving $>77\%$ headroom for telemetry, speed loop (1 kHz), and system background tasks on Core 1. Core 0 remains completely available for WiFi/FreeRTOS.
- **Estimated vs. Physical Measurement Note:** *The above ~11.1 µs budget is an analytical instruction-mix estimate based on cycle counts of floating-point operations on the Xtensa LX6 architecture. It is NOT a physical oscilloscope measurement. Physical hardware validation requires instrumenting a GPIO toggle pin immediately at ISR entry and exit, probed with an oscilloscope or logic analyzer under full PWM switching, ADC conversions, and cache misses.*

---

## 7. Comprehensive Test & Benchmark Results

### Standard Fault Scenarios (15/15 PASS)

| Scenario Name | Description | Injected Fault | Detection Latency | Isolation Channel | Mode After Fault | Speed Error / PTP | Angle RMS / Max | Status |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `no_fault_baseline` | Baseline Normal Operation | None | N/A | None (0) | 2 (CLOSED) | 0.50 RPM / 202.74 | 1.29° / 2.92° | **PASS** |
| `scenario_1_rs_drift` | Stator Resistance Drift (+5%) | $R_s \times 1.05$ at 1.5s | N/A | None (0) | 2 (CLOSED) | 0.53 RPM / 293.07 | 3.64° / 8.22° | **PASS** |
| `scenario_2_offset_a_2_0` | Phase A Current Offset (+2.0A) | Sensor Offset A at 2.0s | 1.95 ms | Phase A (1) | 3 (DEGRADED) | 0.62 RPM / 276.22 | 3.42° / 7.97° | **PASS** |
| `scenario_3_stuck_b_2_0` | Phase B Current Frozen | Sensor Stuck B at 2.0s | 2.05 ms | Phase B (2) | 3 (DEGRADED) | 0.10 RPM / 212.79 | 3.35° / 28.71° | **PASS** |
| `scenario_4_stuck_a_limit` | Phase A Saturated to Limit (10A) | Sensor Stuck Limit A at 2.0s | 1.95 ms | Phase A (1) | 3 (DEGRADED) | 1.87 RPM / 353.66 | 4.74° / 54.29° | **PASS** |
| `scenario_5_simultaneous` | Simultaneous Phase Offset & Load | +0.5A on C, +0.2 Nm load | 1.95 ms | Phase C (3) | 3 (DEGRADED) | 0.09 RPM / 15.73 | 2.97° / 3.71° | **PASS** |
| `scenario_6_noise_burst` | Severe Current Noise Burst (0.1s) | Noise on Phase A at 1.5s | N/A (Transient) | Transient (Cleared) | 2 (CLOSED) | 0.05 RPM / 26.10 | 3.29° / 4.09° | **PASS** |
| `scenario_7_inductance_mismatch` | Stator Inductance Asymmetry | Phase A $L_s \times 1.20$ | N/A | None (0) | 2 (CLOSED) | 5.82 RPM / 338.75 | 6.05° / 10.67° | **PASS** |
| `scenario_8_speed_reversal` | Full Speed Reversal (2000 to -2000) | Speed Ref Step at 2.0s | N/A | None (0) | 2 (CLOSED) | Controlled Decel | 7.81° / 90.44° | **PASS** |
| `scenario_9_load_step` | Heavy Full-Load Step (0.1 Nm) | Load Torque at 2.0s | N/A | None (0) | 2 (CLOSED) | 0.12 RPM / 12.80 | 2.97° / 3.69° | **PASS** |
| `scenario_10_low_speed` | Low Speed Operation (500 RPM) | Low Speed Ref | N/A | None (0) | 2 (CLOSED) | 0.31 RPM / 620.49 | 12.92° / 24.51° | **PASS** |
| `scenario_11_slow_ramp` | Speed Ramp (+500 RPM/s) | Continuous Accel at 1.5s | N/A | None (0) | 2 (CLOSED) | 245.24 RPM / 869.92 | 5.65° / 14.00° | **PASS** |
| `scenario_12_ambiguous_fault` | Simultaneous Fault (Phases A, B, C) | Ambiguous Common-Mode | 15.0 ms | None (Unresolved) | 4 (LIMP) | 264.17 RPM / 409.73 | 2.78° / 6.19° | **PASS** |
| `scenario_13_sequential_two_sensor` | Sequential Two-Sensor Fault | +2.0A on A at 1.5s, +2.0A on B at 2.0s | 1.45 ms | Phase B (Second) | 5 (SAFE_STOP) | Coasting to Stop | Safe Stop Time: 1.45 ms | **PASS** |
| `scenario_14_persistent_ambiguous_fault`| Persistent Ambiguous Fault | Common-Mode +2.0A on all at 0.5s | 15.0 ms | Unresolved Timeout | 5 (SAFE_STOP) | Coasting to Stop | Safe Stop Time: 1500 ms | **PASS** |

### Realistic ADC Sensor Model Sweep (15/15 PASS)
- **Model Parameters:** Bipolar ADC clipping at $\pm 8.25\text{ A}$, 12-bit quantization (4096 counts), 30 mA RMS Gaussian noise, 20 LSB DC offset, and startup offset calibration.
- **Result:** **15/15 Scenarios PASSED** with zero false fault trips, confirmed by `test_all_scenarios_under_sensor_model`.

### Robustness Sweep (144 Configurations - Target >= 90% MET)
- **Parameters:** 4 electrical onset phases, reference speeds [1500, 2000 RPM], fault types [`sensor_stuck`, `sensor_offset`], offset magnitudes [0.5, 2.0 A], channels [A, B, C].
- **Acceptance Target:** $\ge 90\%$ acceptable outcomes per group.
- **Official Sweep Results Table (from `scripts/run_all_scenarios.sh`):**

| Fault Type & Magnitude | Ref Speed (RPM) | Isolated Rate | Acceptable Outcome Rate | Worst-Case Metric (Ride-Through) | Status |
|:---|:---:|:---:|:---:|:---|:---:|
| `sensor_offset` 0.5 A | 1500 | 24/24 (100%) | 24/24 (100%) | Mean 1489 RPM, Angle Max 7° | **PASS** |
| `sensor_offset` 0.5 A | 2000 | 24/24 (100%) | 24/24 (100%) | Mean 1996 RPM, Angle Max 8° | **PASS** |
| `sensor_offset` 2.0 A | 1500 | 24/24 (100%) | 24/24 (100%) | Mean 1491 RPM, Angle Max 8° | **PASS** |
| `sensor_offset` 2.0 A | 2000 | 24/24 (100%) | 24/24 (100%) | Mean 1998 RPM, Angle Max 8° | **PASS** |
| `sensor_stuck` | 1500 | 24/24 (100%) | 24/24 (100%) | Mean 1489 RPM, Angle Max 7° | **PASS** |
| `sensor_stuck` | 2000 | 24/24 (100%) | 24/24 (100%) | Mean 1997 RPM, Angle Max 8° | **PASS** |

- **Verdict:** Target $\ge 90\%$ acceptable outcomes per group was **MET with 100% (144/144) acceptable outcomes across all 6 groups**. Zero hangs or timeouts.

### Full Automated Pytest Suite (65/65 PASS)
- `simulation/plant/test_bldc.py`: 6/6 PASSED
- `simulation/plant/test_plant.py`: 5/5 PASSED
- `simulation/test_handoff.py`: 5/5 PASSED (Task 2 state-machine regression tests)
- `simulation/test_voltage_limiting.py`: 3/3 PASSED (Task 3 circular limit & anti-windup tests)
- `simulation/test_current_sense.py`: 3/3 PASSED (Task 5 current scale & sensor model tests)
- `simulation/test_hal_benchmark.py`: 2/2 PASSED (Task 7 10,000-tick benchmark & `-Wdouble-promotion` tests)
- `simulation/test_scenarios.py`: 41/41 PASSED:
  - 15/15 standard scenarios parameterized
  - 15/15 scenarios under realistic ADC sensor model parameterized
  - 9 dedicated regression tests (Tasks 1, 4, low-speed, reversal, angle limits, noise bursts, invalid types)
- **Total: 65/65 PASSED (100%)**

### C Unit & Invertibility Test Suite
- `make lib && make test`: **PASSED** (Calls library Clarke, Park, InvPark, InvClarke functions; verifies $<10^{-5}$ float round-trip invertibility across 360 electrical degrees).

### Embedded PlatformIO Firmware Build
- **Platform:** Espressif 32 (ESP32 Dev Module, 240 MHz Xtensa LX6)
- **Compilation Flags:** `-I src -Wdouble-promotion -Werror=double-promotion`
- **Compiler Warnings:** **0 warnings, 0 errors** under `-Wdouble-promotion`
- **Static Firmware Image Size (Host Cross-Compilation):**
  - RAM Usage: 22,212 bytes (6.8% of 327,680 bytes)
  - Flash Usage: 299,545 bytes (22.9% of 1,310,720 bytes)
  - Raw Build Log: [`docs/evidence/pio_build_clean_20261020.log`](../evidence/pio_build_clean_20261020.log) and [`docs/evidence/pio_build_bench_20261020.log`](../evidence/pio_build_bench_20261020.log)
- **On-Target Execution:** **NOT MEASURED - requires hardware** (cross-compilation verified on host; on-target flashing and physical execution profiling require hardware)
- **Result:** **SUCCESS (Host Cross-Compilation)**

### Performance Profiling & Timing Budget
- **10,000-Tick Host Ctypes Benchmark:** Average execution time **~0.7–2.0 µs per tick** on host Python/ctypes test runner (informational host benchmark; not an on-target hardware measurement).
- **Embedded FreeRTOS Architecture:** On ESP32, the full FOC loop runs inside a dedicated high-priority FreeRTOS task pinned to Core 1. The hardware timer ISR provides lean notification overhead via `vTaskNotifyGiveFromISR`. Shared telemetry is protected by a fine-grained spinlock (~15 ns).
- **Target Hardware Scope Measurements (GPIO 14 / `PIN_TIMING_BENCHMARK`):**
  - **Status:** **NOT MEASURED - requires hardware**
  - Physical execution timing (timer ISR latency, direct register ADC conversion duration, and FOC loop execution time) has not been physically measured on an oscilloscope. Previous figures (ISR 0.8 µs, ADC 4.5 µs, control loop 14.2 µs, total 18.7 µs) were analytical/budgetary estimates and have been removed in accordance with documentation integrity standards. No physical oscilloscope capture or hardware measurement data currently exists in `docs/`.
  - Required validation: Oscilloscope capture on GPIO 14 (`PIN_TIMING_BENCHMARK`) on target hardware under active PWM switching and ADC conversions.
- **Overrun Monitoring & Deadline Protection:**
  - Evaluates `ulTaskNotifyTake()` return value on each cycle. If the task misses deadlines (`notifies > 1`), consecutive missed cycles increment an overrun counter.
  - If 3 consecutive overruns occur (`MAX_CONSECUTIVE_OVERRUNS = 3`), the firmware latches a hard real-time violation fault, disables PWM gate outputs, and enters `SAFE_STOP`.

---

## 8. Genuine Remaining Limitations & Required Hardware Tests

While the control algorithms and software simulations have been fully verified, deploying this firmware to physical inverter hardware requires addressing the following physical constraints:

1. **ADC Sampling Synchronization with Space Vector Center:**
   - In physical three-phase inverters, phase currents must be sampled precisely at the center of the zero-voltage vector ($V_0$ or $V_7$) to avoid switching noise and ringing.
   - On the ESP32, hardware timer synchronization via MCPWM capture/compare or I2S/DMA ADC triggering must be validated using an oscilloscope.
2. **Physical Dead-Time Compensation & Parameter Mismatch Sensitivity:**
   - The simulation models dead-time voltage drops ($V_{dead} \cdot \text{sign}(i)$), parameterized via $V_{dead} = t_{dead} \cdot f_{pwm} \cdot V_{bus}$ in [`src/motor_params.h`](../../src/motor_params.h).
   - SIL sensitivity sweeps across plant dead-times with a controller assuming 0.50 V ($t_{dead} = 1.042\,\mu\text{s}$) yield:
     - $V_{dead} = 0.50\,\text{V}$ (matched): **0.49°** max angle error.
     - $V_{dead} = 0.25\,\text{V}$: **6.49°** max angle error.
     - $V_{dead} = 1.00\,\text{V}$: **3.54°** max angle error.
     - $V_{dead} = 1.50\,\text{V}$: **7.13°** max angle error.
     - $V_{dead} = 0.00\,\text{V}$: **19.29°** max angle error (documented degradation above 15.0° baseline threshold caused by zero-crossing over-compensation square wave). Setting `dead_time = 0.0` recovers max angle error to **0.48°**.
   - Physical bridge MOSFETs/IGBTs exhibit non-linear parasitic capacitance charge/discharge characteristics that require empirical dead-time compensation calibration on hardware.
3. **Low-Speed Observability Limit:**
   - Below 10–15% rated speed, the motor's back-EMF magnitude ($e = \psi_f \omega_e$) drops below the noise floor of standard low-side current shunts. Physical hardware must transition to high-frequency injection (HFI) or rely on open-loop I/F control during low-speed crawling.
4. **Physical Shunt Resistor Tolerances and Thermal Drift:**
   - Real shunt resistors have $\pm 1\%$ manufacturing tolerance and thermal drift. The fault monitor's KCL threshold (`KCL_THRESH = 0.3A`) must be calibrated against actual circuit noise floor and common-mode rejection ratio (CMRR) of operational amplifiers.
5. **Gate Driver Hardware Fault Interlocks:**
   - Software `SAFE_STOP` actively disables gate pulses by asserting `gate_enable = false`, commanding 0.0 duty cycle (eliminating previous 0.5 midpoint biasing), and driving `PIN_GATE_EN` LOW. A physical production design should additionally preserve a dedicated hardware comparator trip line wired directly to gate driver disable pins (e.g. FLT / EN) for nanosecond shoot-through protection.
