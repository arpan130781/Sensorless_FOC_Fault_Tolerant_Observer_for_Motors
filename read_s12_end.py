import numpy as np
data = np.load('out.npz')
t = data['time']
mode = data['control_mode']
err = data['angle_error']
iq = data['i_q']
omega = data['omega_true']
omega_hat = data['omega_hat']

fault_idx = int(2.0 * 20000)
end_idx = fault_idx + 400 # 20ms later

print("At 20ms:")
print("Mode:", mode[end_idx])
print("Angle error:", err[end_idx])
print("Omega true:", omega[end_idx])
print("Omega hat:", omega_hat[end_idx])

max_err_idx = np.argmax(np.abs(err))
print("\nMax error at", t[max_err_idx], "seconds")
print("Mode:", mode[max_err_idx])
print("Max error:", err[max_err_idx])
print("Omega true:", omega[max_err_idx])
print("Omega hat:", omega_hat[max_err_idx])
