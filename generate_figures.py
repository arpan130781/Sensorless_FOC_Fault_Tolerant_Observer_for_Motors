#!/usr/bin/env python3
"""
generate_figures.py - Generates compact, publication-quality technical diagrams
optimized for balanced, professional PDF layout.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

os.makedirs("docs/figures", exist_ok=True)
plt.rcParams['font.sans-serif'] = 'Helvetica', 'Arial', 'DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#CBD5E1'
plt.rcParams['axes.linewidth'] = 1.0

# -----------------------------------------------------------------------------
# Figure 1: Anatomy of a Brushless Motor & The 90-Degree Torque Principle
# -----------------------------------------------------------------------------
def generate_fig1():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.6), dpi=300)
    
    # Left subplot: Motor cross-section
    ax1.set_xlim(-1.45, 1.45)
    ax1.set_ylim(-1.45, 1.45)
    ax1.set_aspect('equal')
    ax1.axis('off')
    ax1.set_title("Cross-Section of a 3-Phase PMSM Motor", fontsize=10.5, fontweight='bold', color='#1E293B', pad=10)
    
    stator_outer = plt.Circle((0, 0), 1.30, color='#F1F5F9', ec='#334155', lw=2.2)
    stator_inner = plt.Circle((0, 0), 1.00, color='#FFFFFF', ec='#64748B', lw=1.2, ls='--')
    ax1.add_patch(stator_outer)
    ax1.add_patch(stator_inner)
    
    coils = [
        (90, 'Phase A (+)', '#EF4444'), (270, 'Phase A (-)', '#F87171'),
        (210, 'Phase B (+)', '#3B82F6'), (30, 'Phase B (-)', '#60A5FA'),
        (330, 'Phase C (+)', '#10B981'), (150, 'Phase C (-)', '#34D399')
    ]
    for angle_deg, label, col in coils:
        rad = np.radians(angle_deg)
        x = 1.14 * np.cos(rad)
        y = 1.14 * np.sin(rad)
        pole = plt.Circle((x, y), 0.15, color=col, ec='#1E293B', lw=1.0, zorder=3)
        ax1.add_patch(pole)
        
    rotor_body = plt.Circle((0, 0), 0.65, color='#E2E8F0', ec='#0F172A', lw=1.8, zorder=4)
    ax1.add_patch(rotor_body)
    
    north_wedge = patches.Wedge((0, 0), 0.65, 0, 180, color='#DC2626', zorder=5)
    south_wedge = patches.Wedge((0, 0), 0.65, 180, 360, color='#2563EB', zorder=5)
    ax1.add_patch(north_wedge)
    ax1.add_patch(south_wedge)
    
    shaft = plt.Circle((0, 0), 0.20, color='#F8FAFC', ec='#0F172A', lw=1.2, zorder=6)
    ax1.add_patch(shaft)
    ax1.text(0, 0.38, 'N', color='white', fontweight='bold', fontsize=11, ha='center', va='center', zorder=7)
    ax1.text(0, -0.38, 'S', color='white', fontweight='bold', fontsize=11, ha='center', va='center', zorder=7)
    ax1.text(0, 0, 'Shaft', color='#0F172A', fontsize=6.5, ha='center', va='center', zorder=7)
    
    # Right subplot: 90-degree torque angle principle
    ax2.set_xlim(-1.4, 1.4)
    ax2.set_ylim(-1.4, 1.4)
    ax2.set_aspect('equal')
    ax2.axis('off')
    ax2.set_title("The 'Carrot on a Stick' FOC Principle", fontsize=10.5, fontweight='bold', color='#1E293B', pad=10)
    
    ax2.annotate('', xy=(0, 0.95), xytext=(0, 0),
                 arrowprops=dict(arrowstyle="->", color='#DC2626', lw=2.5, mutation_scale=15))
    ax2.text(0.08, 0.90, 'Rotor Flux $\\vec{\\psi}_m$ (d-axis)', color='#DC2626', fontweight='bold', fontsize=9)
    
    ax2.annotate('', xy=(-1.05, 0), xytext=(0, 0),
                 arrowprops=dict(arrowstyle="->", color='#059669', lw=2.5, mutation_scale=15))
    ax2.text(-1.10, -0.16, 'Stator Field $\\vec{B}_{net}$ (q-axis)\n(Torque Producer)', color='#059669', fontweight='bold', fontsize=9)
    
    arc = patches.Arc((0, 0), 0.55, 0.55, angle=0, theta1=90, theta2=180, color='#0284C7', lw=1.8, ls='--')
    ax2.add_patch(arc)
    ax2.text(-0.22, 0.22, '90°\n(Max Torque)', color='#0284C7', fontweight='bold', fontsize=8.5, ha='center')
    
    rot_arc = patches.Arc((0, 0), 1.8, 1.8, angle=0, theta1=60, theta2=130, color='#64748B', lw=1.5)
    ax2.add_patch(rot_arc)
    ax2.annotate('', xy=(-0.60, 0.68), xytext=(-0.53, 0.74),
                 arrowprops=dict(arrowstyle="->", color='#64748B', lw=1.5, mutation_scale=12))
    ax2.text(-0.65, 0.82, 'Rotation ($\omega$)', color='#475569', fontsize=8, fontstyle='italic')
    
    plt.tight_layout()
    plt.savefig("docs/figures/fig1_motor_physics.png", dpi=300, bbox_inches='tight')
    plt.close()

# -----------------------------------------------------------------------------
# Figure 2: The Field-Oriented Control (FOC) Mathematical Pipeline
# -----------------------------------------------------------------------------
def generate_fig2():
    fig, ax = plt.subplots(figsize=(10.5, 3.0), dpi=300)
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 3.2)
    ax.axis('off')
    ax.set_title("Field-Oriented Control (FOC) Closed-Loop Mathematical Architecture", 
                 fontsize=10.5, fontweight='bold', color='#1E293B', pad=8)
    
    boxes = [
        (0.4, 1.5, 1.2, 0.95, '3-Phase Current\nSensors ($i_a, i_b, i_c$)', '#DBEAFE', '#1D4ED8'),
        (2.0, 1.5, 1.2, 0.95, 'Clarke Transform\n($i_\\alpha, i_\\beta$)', '#E0E7FF', '#4338CA'),
        (3.6, 1.5, 1.2, 0.95, 'Park Transform\n($i_d, i_q$)', '#EDE9FE', '#6D28D9'),
        (5.2, 1.5, 1.4, 0.95, 'PI Current Regs\n($v_d, v_q$)', '#FCE7F3', '#BE185D'),
        (7.0, 1.5, 1.2, 0.95, 'Inv Park\n($v_\\alpha, v_\\beta$)', '#EDE9FE', '#6D28D9'),
        (8.6, 1.5, 1.5, 0.95, 'SVPWM & Inverter\nDuties ($d_a, d_b, d_c$)', '#FEF3C7', '#B45309'),
        (3.6, 0.15, 3.0, 0.85, 'Sliding Mode Observer (SMO)\nCalculates Back-EMF $\\to$ Angle $\\hat{\\theta}$, Speed $\\hat{\\omega}$', '#DCFCE7', '#15803D')
    ]
    
    for x, y, w, h, text, bg, border in boxes:
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06,rounding_size=0.12",
                                      facecolor=bg, edgecolor=border, lw=1.5)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, text, color='#0F172A', fontsize=7.2, fontweight='bold',
                ha='center', va='center', multialignment='center')
        
    arrows = [
        (1.6, 1.97, 2.0, 1.97),
        (3.2, 1.97, 3.6, 1.97),
        (4.8, 1.97, 5.2, 1.97),
        (6.6, 1.97, 7.0, 1.97),
        (8.2, 1.97, 8.6, 1.97)
    ]
    for x1, y1, x2, y2 in arrows:
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color='#334155', lw=1.5, mutation_scale=10))
        
    ax.annotate('', xy=(4.2, 1.5), xytext=(4.2, 1.0),
                arrowprops=dict(arrowstyle="->", color='#15803D', lw=1.5, ls='--', mutation_scale=10))
    ax.text(4.25, 1.22, '$\\hat{\\theta}$', color='#15803D', fontsize=7.5, fontweight='bold')
    
    ax.plot([5.8, 7.6, 7.6], [0.57, 0.57, 1.5], color='#15803D', lw=1.5, ls='--')
    ax.annotate('', xy=(7.6, 1.5), xytext=(7.6, 1.4),
                arrowprops=dict(arrowstyle="->", color='#15803D', lw=1.5, mutation_scale=10))
    
    ax.plot([2.6, 2.6, 3.6], [1.5, 0.57, 0.57], color='#4338CA', lw=1.3, ls=':')
    ax.annotate('', xy=(3.6, 0.57), xytext=(3.5, 0.57),
                arrowprops=dict(arrowstyle="->", color='#4338CA', lw=1.3, mutation_scale=9))
    
    plt.tight_layout()
    plt.savefig("docs/figures/fig2_foc_pipeline.png", dpi=300, bbox_inches='tight')
    plt.close()

# -----------------------------------------------------------------------------
# Figure 3: Kirchhoff's Current Law & Sensor Fault Isolation
# -----------------------------------------------------------------------------
def generate_fig3():
    t = np.linspace(1.85, 2.15, 400)
    omega = 2 * np.pi * 50
    
    ia_true = 3.0 * np.sin(omega * t)
    ib_true = 3.0 * np.sin(omega * t - 2*np.pi/3)
    ic_true = 3.0 * np.sin(omega * t + 2*np.pi/3)
    
    ia_measured = np.copy(ia_true)
    fault_mask = t >= 2.0
    ia_measured[fault_mask] += 2.0
    kcl_residual = ia_measured + ib_true + ic_true
    
    reconstruct_mask = t >= 2.015
    ia_corrected = np.copy(ia_measured)
    ia_corrected[reconstruct_mask] = -(ib_true[reconstruct_mask] + ic_true[reconstruct_mask])
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 3.6), dpi=300, sharex=True)
    
    ax1.plot(t, ia_measured, label='Measured $i_a$ (Sensor A corrupted +2A)', color='#EF4444', lw=1.6, ls=':')
    ax1.plot(t, ia_corrected, label='Active Controller $i_a$ (Reconstructed via 2-Shunt KCL)', color='#10B981', lw=2.0)
    ax1.plot(t, ib_true, label='Phase B $i_b$ (Healthy)', color='#3B82F6', lw=1.2, alpha=0.7)
    ax1.plot(t, ic_true, label='Phase C $i_c$ (Healthy)', color='#8B5CF6', lw=1.2, alpha=0.7)
    ax1.axvline(2.0, color='#DC2626', ls='--', lw=1.0)
    ax1.axvline(2.015, color='#059669', ls='--', lw=1.0)
    ax1.set_ylabel('Current [A]', fontsize=8.5, fontweight='bold', color='#1E293B')
    ax1.set_title("Fault Detection & 2-Shunt Seamless Current Reconstruction", fontsize=10, fontweight='bold', color='#1E293B')
    ax1.grid(True, ls=':', color='#CBD5E1')
    ax1.legend(loc='upper right', fontsize=7.2, framealpha=0.9)
    
    ax2.plot(t, np.abs(kcl_residual), label='KCL Residual $|i_a + i_b + i_c|$', color='#DC2626', lw=1.8)
    ax2.axhline(0.6, color='#F59E0B', ls='--', lw=1.2, label='KCL Threshold (0.6 A)')
    ax2.axvline(2.0, color='#DC2626', ls='--', lw=1.0)
    ax2.axvline(2.015, color='#059669', ls='--', lw=1.0)
    
    ax2.text(1.92, 1.2, 'NORMAL\n(3-Shunt)', color='#059669', fontweight='bold', fontsize=7.5, ha='center')
    ax2.text(2.007, 1.4, 'ISOLATING\n(15 ms)', color='#DC2626', fontweight='bold', fontsize=7.0, ha='center')
    ax2.text(2.08, 1.2, 'DEGRADED\n(2-Shunt)', color='#2563EB', fontweight='bold', fontsize=7.5, ha='center')
    
    ax2.set_xlabel('Time [seconds]', fontsize=8.5, fontweight='bold', color='#1E293B')
    ax2.set_ylabel('Residual [A]', fontsize=8.5, fontweight='bold', color='#1E293B')
    ax2.grid(True, ls=':', color='#CBD5E1')
    ax2.legend(loc='upper right', fontsize=7.2, framealpha=0.9)
    
    plt.tight_layout()
    plt.savefig("docs/figures/fig3_kcl_fault_isolation.png", dpi=300, bbox_inches='tight')
    plt.close()

# -----------------------------------------------------------------------------
# Figure 4: Debounce Envelope & Noise Spike Immunity
# -----------------------------------------------------------------------------
def generate_fig4():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 2.9), dpi=300)
    
    ticks1 = np.arange(0, 9)
    current_spike = np.zeros(9)
    current_spike[3] = 3.0
    current_spike[4] = 3.0
    mode_spike = np.full(9, 2)
    
    ax1.step(ticks1, current_spike, where='mid', color='#EF4444', lw=1.8, label='Current Error')
    ax1.plot(ticks1, mode_spike, color='#10B981', lw=2.0, label='Mode (2: CLOSED_LOOP)')
    ax1.axhline(1.5, color='#F59E0B', ls='--', lw=1.1, label='Fast-Track (1.5 A)')
    ax1.set_ylim(-0.3, 3.8)
    ax1.set_xlabel('Ticks (50 µs each)', fontsize=8, fontweight='bold', color='#1E293B')
    ax1.set_ylabel('Amplitude', fontsize=8, fontweight='bold', color='#1E293B')
    ax1.set_title("Case A: 2-Sample Transient Spike (Noise)\n-> Debounce Filter Rejects, Zero Mode Change", 
                  fontsize=8.5, fontweight='bold', color='#1E293B')
    ax1.grid(True, ls=':', color='#CBD5E1')
    ax1.legend(loc='upper right', fontsize=6.8)
    
    ticks2 = np.arange(0, 9)
    current_sustained = np.zeros(9)
    current_sustained[2:7] = 2.0
    mode_sustained = np.full(9, 2)
    mode_sustained[5:] = 3
    
    ax2.step(ticks2, current_sustained, where='mid', color='#EF4444', lw=1.8, label='Current Error')
    ax2.step(ticks2, mode_sustained, where='mid', color='#3B82F6', lw=2.0, label='Mode (3: DEGRADED)')
    ax2.axhline(1.5, color='#F59E0B', ls='--', lw=1.1, label='Fast-Track (1.5 A)')
    ax2.set_ylim(-0.3, 3.8)
    ax2.set_xlabel('Ticks (50 µs each)', fontsize=8, fontweight='bold', color='#1E293B')
    ax2.set_ylabel('Amplitude', fontsize=8, fontweight='bold', color='#1E293B')
    ax2.set_title("Case B: 3+ Consecutive Samples\n-> Confirmed Fault, Latches 2-Shunt Mode", 
                  fontsize=8.5, fontweight='bold', color='#1E293B')
    ax2.grid(True, ls=':', color='#CBD5E1')
    ax2.legend(loc='upper right', fontsize=6.8)
    
    plt.tight_layout()
    plt.savefig("docs/figures/fig4_burst_debounce.png", dpi=300, bbox_inches='tight')
    plt.close()

# -----------------------------------------------------------------------------
# Figure 5: Controller State Machine & Safe Operation Flow
# -----------------------------------------------------------------------------
def generate_fig5():
    fig, ax = plt.subplots(figsize=(11.5, 4.8), dpi=300)
    ax.set_xlim(0, 11.5)
    ax.set_ylim(0, 4.8)
    ax.axis('off')
    
    # Title & Subtitle
    ax.text(5.75, 4.55, "Sensorless FOC Operational State Machine & Fault-Tolerant Transitions", 
            fontsize=12, fontweight='bold', color='#0F172A', ha='center', va='center')
    ax.text(5.75, 4.35, "Fail-operational architecture: single-fault ride-through (Mode 3), ambiguous fault derating (Mode 4), and fail-safe latch (Mode 5)", 
            fontsize=7.5, color='#64748B', ha='center', va='center', style='italic')
    
    # State Boxes: (x, y, w, h, text, bg, border, text_color)
    states = [
        # Top Row: Normal Progression & Fail-Operational (y: 2.9 to 4.1)
        (0.5, 2.9, 1.6, 1.2, 'ALIGN (0)\n\nDC current hold\nlocks rotor to 0°', '#F8FAFC', '#64748B', '#1E293B'),
        (2.7, 2.9, 1.7, 1.2, 'OPEN LOOP (1)\n\nI-F rotating ramp\n0 -> 500 RPM', '#FEF3C7', '#D97706', '#92400E'),
        (5.1, 2.9, 2.1, 1.2, 'CLOSED LOOP (2)\n\nFull 3-Shunt FOC\nSMO angle tracking', '#DCFCE7', '#16A34A', '#166534'),
        (9.0, 2.9, 2.1, 1.2, 'DEGRADED (3)\n\nFail-operational 2-shunt\nReconstructed phase', '#DBEAFE', '#2563EB', '#1E40AF'),
        
        # Bottom Row: Ambiguous Derating & Terminal Fail-Safe (y: 0.5 to 1.7)
        (5.1, 0.5, 2.1, 1.2, 'LIMP (4)\n\nAmbiguous fault\n50% speed / current derate', '#F3E8FF', '#9333EA', '#6B21A8'),
        (9.0, 0.5, 2.1, 1.2, 'SAFE STOP (5)\n\nGates disabled (LOW)\nDiode freewheeling stop', '#FEE2E2', '#DC2626', '#991B1B')
    ]
    
    for x, y, w, h, text, bg, border, tc in states:
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06,rounding_size=0.12",
                                      facecolor=bg, edgecolor=border, lw=2.0)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, text, color=tc, fontsize=8.2, fontweight='bold',
                ha='center', va='center', multialignment='center')
        
    # 1. ALIGN -> OPEN_LOOP
    ax.annotate('', xy=(2.7, 3.5), xytext=(2.1, 3.5),
                arrowprops=dict(arrowstyle="->", color='#0F172A', lw=1.8, mutation_scale=12))
    ax.text(2.4, 3.68, 'Time > 500ms', fontsize=7.2, ha='center', color='#475569', fontweight='bold')
    
    # 2. OPEN_LOOP -> CLOSED_LOOP
    ax.annotate('', xy=(5.1, 3.5), xytext=(4.4, 3.5),
                arrowprops=dict(arrowstyle="->", color='#0F172A', lw=1.8, mutation_scale=12))
    ax.text(4.75, 3.68, 'Lock err < 15°', fontsize=7.2, ha='center', color='#475569', fontweight='bold')
    
    # 3. CLOSED_LOOP -> DEGRADED (Forward single fault)
    ax.annotate('', xy=(9.0, 3.75), xytext=(7.2, 3.75),
                arrowprops=dict(arrowstyle="->", color='#2563EB', lw=1.8, mutation_scale=12))
    ax.text(8.1, 3.92, 'Single Sensor Fault', fontsize=7.5, ha='center', color='#2563EB', fontweight='bold')
    
    # 4. DEGRADED -> CLOSED_LOOP (Recovery)
    ax.annotate('', xy=(7.2, 3.25), xytext=(9.0, 3.25),
                arrowprops=dict(arrowstyle="->", color='#16A34A', lw=1.8, ls='--', mutation_scale=12))
    ax.text(8.1, 3.07, 'Fault Clears > 500ms (Recover)', fontsize=7.2, ha='center', color='#16A34A', fontweight='bold')
    
    # 5. CLOSED_LOOP -> LIMP (Vertical down)
    ax.annotate('', xy=(5.7, 1.7), xytext=(5.7, 2.9),
                arrowprops=dict(arrowstyle="->", color='#9333EA', lw=1.8, mutation_scale=12))
    ax.text(5.62, 2.30, 'Ambiguous Fault\n(Unresolved phase)', fontsize=7.2, ha='right', va='center', color='#9333EA', fontweight='bold')
    
    # 6. DEGRADED -> SAFE_STOP (Vertical down)
    ax.annotate('', xy=(10.5, 1.7), xytext=(10.5, 2.9),
                arrowprops=dict(arrowstyle="->", color='#DC2626', lw=1.8, mutation_scale=12))
    ax.text(10.58, 2.30, '2nd Sensor Fault\n(Reconstruction lost)', fontsize=7.2, ha='left', va='center', color='#DC2626', fontweight='bold')
    
    # 7. LIMP -> SAFE_STOP (Horizontal)
    ax.annotate('', xy=(9.0, 1.1), xytext=(7.2, 1.1),
                arrowprops=dict(arrowstyle="->", color='#9333EA', lw=1.8, ls='--', mutation_scale=12))
    ax.text(8.1, 1.28, 'Timeout > 200ms', fontsize=7.5, ha='center', color='#9333EA', fontweight='bold')
    
    # 8. CLOSED_LOOP -> SAFE_STOP (Critical Inverter Fault / Task Overrun)
    ax.annotate('', xy=(9.0, 1.7), xytext=(7.2, 2.9),
                arrowprops=dict(arrowstyle="->", color='#DC2626', lw=1.8, ls=':', mutation_scale=12))
    ax.text(8.1, 2.30, 'Critical Inverter Fault / Leg Open\n>3 Missed Ticks (Task Overrun)', 
            fontsize=7.2, ha='center', va='center', color='#DC2626', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.25', facecolor='#FEF2F2', edgecolor='#DC2626', lw=1.2, ls=':'))
    
    plt.tight_layout()
    plt.savefig("docs/figures/fig5_state_machine.png", dpi=300, bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    generate_fig1()
    generate_fig2()
    generate_fig3()
    generate_fig4()
    generate_fig5()
    print("Regenerated all 5 compact technical figures.")
