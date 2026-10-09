import matplotlib
matplotlib.use('Agg')
import os
import matplotlib.pyplot as plt

OUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'results')

def _save_or_show(fig, filename, show=False):
    os.makedirs(OUT_DIR, exist_ok=True)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, filename))
    if show:
        plt.close()
    plt.close(fig)

def plot_basic_response(res, show=False):
    fig, axs = plt.subplots(4, 1, figsize=(10, 10), sharex=True)
    
    axs[0].plot(res.time, res.speed_rpm, label='Actual Speed (RPM)')
    axs[0].plot(res.time, res.omega_hat * 60 / (2 * 3.14159), label='Est Speed (RPM)')
    axs[0].set_ylabel('Speed (RPM)')
    axs[0].legend()
    axs[0].grid(True)
    
    axs[1].plot(res.time, res.i_d, label='i_d (A)')
    axs[1].plot(res.time, res.i_q, label='i_q (A)')
    axs[1].set_ylabel('Current (A)')
    axs[1].legend()
    axs[1].grid(True)
    
    axs[2].plot(res.time, res.angle_error, label='Angle Error (deg)')
    axs[2].set_ylabel('Error (deg)')
    axs[2].grid(True)
    
    axs[3].plot(res.time, res.duty_a, label='Duty A')
    axs[3].plot(res.time, res.duty_b, label='Duty B')
    axs[3].plot(res.time, res.duty_c, label='Duty C')
    axs[3].set_ylabel('Duty Cycle')
    axs[3].set_xlabel('Time (s)')
    axs[3].legend()
    axs[3].grid(True)
    
    _save_or_show(fig, 'basic_response.png', show)

def plot_observer_comparison(res, show=False):
    fig, axs = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    
    axs[0].plot(res.time, res.theta_true, label='True Angle')
    axs[0].plot(res.time, res.theta_hat_smo, label='SMO Angle')
    axs[0].plot(res.time, res.theta_hat_flux, label='Flux Angle')
    axs[0].set_ylabel('Angle (rad)')
    axs[0].legend()
    axs[0].grid(True)
    
    axs[1].plot(res.time, res.angle_error, label='Selected Angle Error (deg)')
    axs[1].set_ylabel('Error (deg)')
    axs[1].grid(True)
    
    axs[2].plot(res.time, res.health_score, label='Health Score')
    axs[2].set_ylabel('Score (0-1)')
    axs[2].set_xlabel('Time (s)')
    axs[2].grid(True)
    
    _save_or_show(fig, 'observer_comp.png', show)

def plot_fault_response(res, show=False):
    fig, axs = plt.subplots(5, 1, figsize=(12, 12), sharex=True)
    
    axs[0].plot(res.time, res.speed_rpm, label='Speed (RPM)')
    axs[0].set_ylabel('Speed')
    axs[0].grid(True)
    
    axs[1].plot(res.time, res.angle_error, label='Angle Error')
    axs[1].set_ylabel('Error (deg)')
    axs[1].grid(True)
    
    axs[2].plot(res.time, res.health_score, label='Health Score', color='r')
    axs[2].axhline(y=0.5, color='gray', linestyle='--')
    axs[2].set_ylabel('Health')
    axs[2].grid(True)
    
    axs[3].plot(res.time, res.control_mode, label='Mode (1=N, 2=F)')
    axs[3].set_ylabel('Control Mode')
    axs[3].grid(True)
    
    axs[4].plot(res.time, res.i_a, label='i_a')
    axs[4].plot(res.time, res.i_b, label='i_b')
    axs[4].plot(res.time, res.i_c, label='i_c')
    axs[4].set_ylabel('Phase Currents (A)')
    axs[4].set_xlabel('Time (s)')
    axs[4].legend()
    axs[4].grid(True)
    
    _save_or_show(fig, 'fault_response.png', show)

def plot_mode_timeline(res, show=False):
    fig, ax = plt.subplots(figsize=(10, 2))
    ax.scatter(res.time, res.control_mode, marker='|', color='b')
    ax.set_yticks([1, 2])
    ax.set_yticklabels(['Normal', 'Fault'])
    ax.set_xlabel('Time (s)')
    ax.grid(True)
    _save_or_show(fig, 'mode_timeline.png', show)
