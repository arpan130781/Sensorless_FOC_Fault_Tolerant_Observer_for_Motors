with open("src/fault_monitor.h", "r") as f:
    content = f.read()
if "float i_alpha_clean;" not in content:
    content = content.replace("    float i_c_rec;", "    float i_c_rec;\n    float i_alpha_clean;\n    float i_beta_clean;")
with open("src/fault_monitor.h", "w") as f:
    f.write(content)

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

# 1. Reset timer in unlatch
content = content.replace("fm->consecutive_confident = 0;\n                fm->best_channel = -1;", "fm->consecutive_confident = 0;\n                fm->best_channel = -1;\n                fm->fault_isolation_timer = 0.0f;")

# 2. Unisolated timer bug
content = content.replace("        if (fm->fault_isolation_timer > 0.0f) {\n            fm->fault_isolation_timer += dt;\n", "        if (fm->fault_isolation_timer > 0.0f) {\n            fm->fault_isolation_timer += dt;\n            fm->unisolated_timer += dt;\n")

# 3. Add clean currents to return block
clean_logic = """    else {
        fm->status.i_a_rec = i_a;
        fm->status.i_b_rec = i_b;
        fm->status.i_c_rec = i_c;
        fm->status.degradation_state = CLOSED_LOOP;
    }

    if (fm->fault_isolation_timer > 0.0f || fm->ambiguous_fault || fm->fault_latch_a || fm->fault_latch_b || fm->fault_latch_c) {
        fm->status.i_alpha_clean = fm->i_alpha_pred;
        fm->status.i_beta_clean  = fm->i_beta_pred;
    } else {
        fm->status.i_alpha_clean = (2.0f/3.0f) * (i_a - 0.5f*i_b - 0.5f*i_c);
        fm->status.i_beta_clean  = 0.57735027f * (i_b - i_c);
    }

    return fm->status;
}"""
content = content.replace("""    else {
        fm->status.i_a_rec = i_a;
        fm->status.i_b_rec = i_b;
        fm->status.i_c_rec = i_c;
        fm->status.degradation_state = CLOSED_LOOP;
    }

    return fm->status;
}""", clean_logic)

with open("src/fault_monitor.c", "w") as f:
    f.write(content)

with open("src/foc_core.c", "r") as f:
    content = f.read()

# Scale prev_v_alpha
scale_code = """        scale = v_max_allowed / fmaxf(fabsf(va), fmaxf(fabsf(vb), fabsf(vc)));
    }
    
    prev_v_alpha = valpha * scale;
    prev_v_beta = vbeta * scale;"""
content = content.replace("""        scale = v_max_allowed / fmaxf(fabsf(va), fmaxf(fabsf(vb), fabsf(vc)));
    }""", scale_code)
content = content.replace("    prev_v_alpha = valpha;\n    prev_v_beta = vbeta;\n", "")

# Observer shield
obs_code_old = """    // Observers
    obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, i_alpha, i_beta, speed_est, dt_curr);"""
obs_code_new = """    // Observers
    obs_mgr_update(&obs_mgr, prev_v_alpha, prev_v_beta, fs.i_alpha_clean, fs.i_beta_clean, speed_est, dt_curr);"""
content = content.replace(obs_code_old, obs_code_new)

with open("src/foc_core.c", "w") as f:
    f.write(content)
