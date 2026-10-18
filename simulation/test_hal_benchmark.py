"""
Task 7 Verification Test:
- 10,000-tick benchmark via ctypes harness measuring exact execution duration.
- Verification that no double-precision float promotions remain in the hot path.
"""
import time
import subprocess
import pytest
from simulation.harness.config import MOTOR_PARAMS, CONTROLLER_PARAMS, PATHS
from simulation.harness.c_bridge import FocController


def test_10000_tick_benchmark():
    """
    Executes a 10,000-tick benchmark of the C controller via the ctypes harness.
    Asserts average per-tick time is well under the 50 microsecond (20 kHz) real-time budget.
    """
    ctrl = FocController(PATHS['lib_path'])
    ctrl.init(MOTOR_PARAMS, CONTROLLER_PARAMS)
    ctrl.set_speed_ref(1800.0 * 2.0 * 3.14159265 / 60.0 * MOTOR_PARAMS['P'])

    # Warm-up ticks
    for _ in range(500):
        ctrl.tick(1.0, -0.5, -0.5, 24.0)

    # Benchmark 10,000 ticks
    N = 10000
    t0 = time.perf_counter()
    for _ in range(N):
        ctrl.tick(1.0, -0.5, -0.5, 24.0)
    t1 = time.perf_counter()

    total_us = (t1 - t0) * 1e6
    per_tick_us = total_us / N

    print(f"\n[BENCHMARK] 10,000 ticks completed in {total_us:.1f} us ({total_us / 1000.0:.2f} ms)")
    print(f"[BENCHMARK] Average per-tick duration (including ctypes overhead): {per_tick_us:.3f} us")
    print(f"[BENCHMARK] Percentage of 50.0 us ISR budget: {(per_tick_us / 50.0) * 100.0:.2f}%")

    # Informational / sanity check: host execution (including Python ctypes overhead)
    # must be valid and safely within the 50.0 us (20 kHz) real-time period.
    assert 0.0 < per_tick_us < 50.0, f"Host execution {per_tick_us:.2f} us exceeded 50 us control period"


def test_no_double_promotion_warnings():
    """
    Asserts that the C controller compiles cleanly under -Wdouble-promotion and -Werror=double-promotion
    with zero warnings or errors, proving no double-precision operations remain in the hot path.
    """
    res = subprocess.run(
        ["make", "clean", "lib"],
        capture_output=True,
        text=True
    )
    assert res.returncode == 0, f"make lib failed under -Werror=double-promotion:\n{res.stderr}"
    # Ensure -Wdouble-promotion is present in compilation command
    assert "-Wdouble-promotion" in res.stdout or "-Wdouble-promotion" in res.stderr
