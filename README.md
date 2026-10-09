# Sensorless FOC Simulation — Fault-Tolerant Observer on ESP32 (SIL)

This repository implements an industrial-grade Sensorless Field-Oriented Control (FOC) algorithm for a Permanent Magnet Synchronous Motor (PMSM), designed specifically for the ESP32. It features a robust, model-assisted Fault-Tolerant observer capable of detecting, isolating, and riding through severe single-sensor failures (e.g., stuck-at-limit, constant offset, and noise bursts) using purely mathematical reconstruction.

## Architecture

The system uses a hybrid observer structure:
- **High Speed**: Sliding Mode Observer (SMO)
- **Low Speed**: Voltage-Model Flux Observer
- **Fusion**: A complementary filter blends the two observer outputs based on electrical frequency.

### Hybrid Fault Isolation
This stack uses a robust hybrid isolation strategy that handles both hard stuck sensors and constant offsets:
1. **Flat-Line Detection:** A `stuck_count` rapidly detects and isolates sensors that freeze at a constant limit. If a channel remains perfectly constant over a 1ms window while the motor is moving, it is instantly latched.
2. **LPF Baseline Prediction:** For offset faults, an independent low-pass filtered alpha-beta current predictor runs in parallel. When KCL error exceeds 0.3A, this model's state freezes, acting as a perfect pre-fault baseline.
3. **Hypothesis Evaluation:** During a 2ms evaluation window, three explicit hypotheses ($H_A$, $H_B$, $H_C$) are continuously compared against the frozen LPF baseline.
4. **Transient Shielding:** If the fault cannot be confidently isolated (e.g., during high-frequency noise bursts), the system enters `LIMP` mode with reduced torque limits rather than making an unsafe phase-specific guess.
5. **Recovery Debouncing:** Latched and ambiguous faults enforce a strict 50ms `RECOVERY_WINDOW` after KCL returns to normal before restoring `CLOSED_LOOP` operation. 

## Prerequisites
- Python 3.8+
- `gcc` or `clang`
- Python packages: `numpy`, `scipy`, `matplotlib`, `pyyaml`, `pytest`

## Quick Start
```bash
# Set up the Python virtual environment
./setup_env.sh

# Build the C shared library (macOS/Linux)
make lib

# Run the complete test suite (8 standard scenarios + comprehensive isolation sweep)
./scripts/run_all_scenarios.sh
```

## Project Structure
```text
.
├── src/                    # C FOC implementation (ESP32-ready)
│   ├── fault_monitor.c     # Independent kinematics & fault isolation
│   ├── flux_observer.c     # Low-speed flux observer
│   ├── foc_core.c          # FOC orchestrator
│   ├── handoff.c           # Mode transition FSM (ALIGN -> OPEN_LOOP -> CLOSED_LOOP)
│   ├── observer_manager.c  # Observer fusion (Complementary Filter)
│   ├── pi_controller.c     # PI loop with anti-windup
│   └── smo.c               # Sliding Mode Observer
├── simulation/             # Python SIL Harness
│   ├── plant/              # PMSM and Inverter models
│   ├── fault_injection/    # Yaml scenarios and fault injectors
│   ├── analysis/           # Metrics and matplotlib plotter
│   └── harness/            # ctypes bridge and runner
├── scripts/                # Build and test orchestration
├── tests/                  # Pytest unit tests
└── Makefile                # Cross-platform build system
```

## Motor Parameters (Standard 100W SPM)
| Parameter | Value |
|-----------|-------|
| Stator Resistance ($R_s$) | $0.5 \Omega$ |
| Stator Inductance ($L_s$) | $1.0$ mH |
| Flux Linkage ($\psi_f$) | $0.015$ Wb |
| Pole Pairs ($P$) | $4$ |
| Inertia ($J$) | $0.0001$ kg·m² |
| Damping ($B$) | $0.001$ N·m·s/rad |
| Nominal Current ($I_n$) | $5.0$ A peak |
| Bus Voltage ($V_{bus}$) | $24.0$ V |

## Validation Scenarios (12/12 PASS)
The SIL environment evaluates the controller against the following strict scenarios. The fault monitor dynamically recovers tracking and maintains $<10^\circ$ RMS angle error post-fault.

| Scenario | Type | Description |
|----------|------|-------------|
| `no_fault_baseline` | Nominal | Accelerates to 2000 RPM smoothly using startup ramp and hands off to CLOSED_LOOP. |
| `scenario_1_rs_drift` | Plant Mismatch | Simulates thermal heating ($R_s$ increases by 50%). SMO natively rides through. |
| `scenario_2_offset_a_2_0` | Constant Offset | 2.0A constant offset injected into Phase A at 2.0s. Correctly isolated in 10ms. |
| `scenario_3_stuck_b_2_0` | Sensor Stuck | Phase B freezes at 2.0A at 2.0s. Overcomes zero-crossing ambiguity via kinematics model. |
| `scenario_4_stuck_a_limit` | Hard Fault | Phase A jumps to ADC maximum (10A). Shielding mechanism prevents observer explosion. |
| `scenario_5_simultaneous` | Load + Fault | 2.0A offset on C alongside a sudden 0.1Nm load torque step. |
| `scenario_6_noise_burst` | Transient Noise | 100ms blast of 1.0A Gaussian noise. Controller enters DEGRADED safely, then fully recovers to CLOSED_LOOP 50ms after noise clears. |
| `scenario_7_inductance_mismatch` | Plant Mismatch | $L_s$ differs by 20%. |

## Performance (Target Hardware pending)

*Note: These are estimates. Worst-case execution time, interrupt latency, and PWM/ADC synchronization will be explicitly measured and validated on the physical ESP32 target hardware in Phase 2.*

The C controller is written strictly with `float` types to leverage the ESP32 single-precision FPU.
- **Estimated cycles per tick:** ~150 cycles (*Note: These are preliminary simulation estimates and have not yet been measured on target ESP32 hardware*)
- **Estimated control loop duration:** $< 1 \mu s$ at 240MHz.
- **Estimated Max PWM Frequency:** $> 40$ kHz.

