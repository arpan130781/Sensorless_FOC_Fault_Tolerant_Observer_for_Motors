#!/usr/bin/env python3
"""
generate_test_graphs.py - Runs key fault scenarios using SILRunner
and generates publication-quality test response graphs for inclusion in the PDF report.
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from simulation.harness.config import SIM_PARAMS
from simulation.harness.sil_runner import SILRunner

os.makedirs("docs/figures", exist_ok=True)
plt.rcParams['font.sans-serif'] = 'Helvetica', 'Arial', 'DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#CBD5E1'
plt.rcParams['axes.linewidth'] = 1.0

def plot_scenario_run(scenario_name, filename, title_text, xlim=None):
    print(f"Running simulation for {scenario_name}...")
    runner = SILRunner(SIM_PARAMS, scenario_name)
    res = runner.run()
    
    fig, axs = plt.subplots(4, 1, figsize=(10, 4.8), dpi=300, sharex=True)
    
    # Subplot 1: Speed Tracking
    axs[0].plot(res.time, res.speed_rpm, label='Physical Motor Speed', color='#1E3A8A', lw=1.6)
    axs[0].plot(res.time, res.omega_hat * 60.0 / (2.0 * np.pi * 4.0), label='Observer Est Speed', color='#0D9488', lw=1.2, ls='--')
    axs[0].set_ylabel('Speed [RPM]', fontsize=7.5, fontweight='bold', color='#1E293B')
    axs[0].set_title(title_text, fontsize=9.5, fontweight='bold', color='#1E293B', pad=6)
    axs[0].grid(True, ls=':', color='#CBD5E1')
    axs[0].legend(loc='upper right', fontsize=6.8)
    
    # Subplot 2: Phase Currents & Fault Onset
    axs[1].plot(res.time, res.i_a, label='$i_a$ (Measured)', color='#EF4444', lw=1.2)
    axs[1].plot(res.time, res.i_b, label='$i_b$', color='#3B82F6', lw=1.0, alpha=0.8)
    axs[1].plot(res.time, res.i_c, label='$i_c$', color='#8B5CF6', lw=1.0, alpha=0.8)
    axs[1].set_ylabel('Currents [A]', fontsize=7.5, fontweight='bold', color='#1E293B')
    axs[1].grid(True, ls=':', color='#CBD5E1')
    axs[1].legend(loc='upper right', fontsize=6.8)
    
    # Subplot 3: Observer Angle Error
    axs[2].plot(res.time, res.angle_error, label='Observer Angle Error', color='#D97706', lw=1.3)
    axs[2].axhline(15.0, color='#DC2626', ls=':', lw=1.0, label='15° Nominal Threshold')
    axs[2].axhline(-15.0, color='#DC2626', ls=':', lw=1.0)
    axs[2].set_ylabel('Error [deg]', fontsize=7.5, fontweight='bold', color='#1E293B')
    axs[2].grid(True, ls=':', color='#CBD5E1')
    axs[2].legend(loc='upper right', fontsize=6.8)
    
    # Subplot 4: Controller Mode & Health Score
    axs[3].step(res.time, res.control_mode, where='mid', label='Control Mode (2=Closed, 3=Degraded, 5=SafeStop)', color='#2563EB', lw=1.6)
    axs[3].plot(res.time, res.health_score * 5.0, label='Health Score (scaled 0-5)', color='#10B981', lw=1.2, ls='--')
    axs[3].set_ylabel('Mode / Health', fontsize=7.5, fontweight='bold', color='#1E293B')
    axs[3].set_xlabel('Time [seconds]', fontsize=8.0, fontweight='bold', color='#1E293B')
    axs[3].grid(True, ls=':', color='#CBD5E1')
    axs[3].legend(loc='upper right', fontsize=6.8)
    
    if xlim:
        axs[3].set_xlim(xlim)
    
    plt.tight_layout()
    out_path = os.path.join("docs/figures", filename)
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved {out_path}")

def generate_safe_stop_vbus_graph():
    print("Running simulation for Safe Stop Vbus & Diode Conduction...")
    from simulation.plant.sensor_model import SensorModel
    runner = SILRunner(SIM_PARAMS, 'scenario_13_sequential_two_sensor')
    res = runner.run()
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 3.4), dpi=300, sharex=True)
    
    # DC bus voltage rise and decay
    ax1.plot(res.time, res.v_bus, color='#DC2626', lw=1.8, label='DC Bus Voltage $V_{bus}$ (V)')
    ax1.axhline(24.0, color='#475569', ls='--', lw=1.0, label='Nominal 24.0 V Bus')
    ax1.axvline(2.0, color='#DC2626', ls=':', lw=1.2, label='2nd Fault Trips SAFE_STOP (t=2.0s)')
    ax1.set_ylabel('Bus Voltage [V]', fontsize=8.0, fontweight='bold', color='#1E293B')
    ax1.set_title("Post-SAFE_STOP Body-Diode Conduction & DC Bus Bleeder Decay", fontsize=9.5, fontweight='bold', color='#1E293B')
    ax1.grid(True, ls=':', color='#CBD5E1')
    ax1.legend(loc='upper right', fontsize=7.2)
    
    # Phase current envelope post safe stop
    ax2.plot(res.time, res.i_true_a, color='#1E3A8A', lw=1.2, label='Phase A Physical Current')
    ax2.plot(res.time, res.i_true_b, color='#0D9488', lw=1.2, label='Phase B Physical Current')
    ax2.axhline(6.0, color='#DC2626', ls='--', lw=1.0, label='1.2 x In Limit (6.0 A)')
    ax2.axhline(-6.0, color='#DC2626', ls='--', lw=1.0)
    ax2.axvline(2.0, color='#DC2626', ls=':', lw=1.2)
    ax2.set_xlabel('Time [seconds]', fontsize=8.0, fontweight='bold', color='#1E293B')
    ax2.set_ylabel('Current [A]', fontsize=8.0, fontweight='bold', color='#1E293B')
    ax2.set_xlim(1.8, 2.5)
    ax2.grid(True, ls=':', color='#CBD5E1')
    ax2.legend(loc='upper right', fontsize=7.2)
    
    plt.tight_layout()
    out_path = "docs/figures/test_graph_safe_stop_vbus.png"
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved {out_path}")

if __name__ == "__main__":
    plot_scenario_run('no_fault_baseline', 'test_graph_baseline.png', 
                      "Scenario 0: Healthy Baseline Operation at 2000 RPM (No Faults)")
    plot_scenario_run('scenario_2_offset_a_2_0', 'test_graph_offset_a.png', 
                      "Scenario 2: Phase A +2.0A Current Sensor Offset at t=2.0s (Seamless 2-Shunt Handoff)", xlim=(1.5, 3.0))
    plot_scenario_run('scenario_3_stuck_b_2_0', 'test_graph_stuck_sensor.png', 
                      "Scenario 3: Phase B Stuck Sensor Fault at t=2.0s (Zero-Variance Detection)", xlim=(1.5, 3.0))
    plot_scenario_run('scenario_8_speed_reversal', 'test_graph_speed_reversal.png', 
                      "Scenario 8: Full 4-Quadrant Speed Reversal (+2000 RPM to -2000 RPM through Zero)")
    plot_scenario_run('scenario_9_load_step', 'test_graph_load_step.png', 
                      "Scenario 9: Dynamic Mechanical Load Step (+0.1 Nm at t=1.5s with PI Disturbance Rejection)")
    plot_scenario_run('scenario_6_noise_burst', 'test_graph_noise_burst.png', 
                      "Scenario 6: High-Frequency Noise Burst on Phase A (Debounce Filtering & Recovery)")
    plot_scenario_run('scenario_13_sequential_two_sensor', 'test_graph_sequential_fault.png', 
                      "Scenario 13: Sequential Two-Sensor Fault (Sensor A @ 1.5s, Sensor B @ 2.0s -> SAFE_STOP)")
    generate_safe_stop_vbus_graph()
    print("All test scenario graphs generated successfully!")
