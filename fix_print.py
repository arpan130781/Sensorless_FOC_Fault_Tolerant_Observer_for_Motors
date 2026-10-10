with open("src/foc_core.c", "r") as f:
    content = f.read()

content = content.replace("if (tick_counter == 0) printf(\"err=%f, iq_ref=%f, int=%f, ref=%f, est=%f\\n\", err, current_iq_ref, pi_spd.integral, current_omega_ref, obs_omega);", "")

with open("src/foc_core.c", "w") as f:
    f.write(content)
