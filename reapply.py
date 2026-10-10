with open("src/fault_monitor.c", "r") as f:
    content = f.read()

# 1. Reset timer in unlatch
content = content.replace("fm->consecutive_confident = 0;\n                fm->best_channel = -1;", "fm->consecutive_confident = 0;\n                fm->best_channel = -1;\n                fm->fault_isolation_timer = 0.0f;")

# 2. Unisolated timer bug
content = content.replace("        if (fm->fault_isolation_timer > 0.0f) {\n            fm->fault_isolation_timer += dt;\n", "        if (fm->fault_isolation_timer > 0.0f) {\n            fm->fault_isolation_timer += dt;\n            fm->unisolated_timer += dt;\n")

# 3. Shield
shield_code = """    else if (fm->fault_isolation_timer > 0.0f) {
        fm->status.i_a_rec = fm->i_alpha_pred;
        fm->status.i_b_rec = -0.5f*fm->i_alpha_pred + 0.8660254f*fm->i_beta_pred;
        fm->status.i_c_rec = -0.5f*fm->i_alpha_pred - 0.8660254f*fm->i_beta_pred;
        fm->status.degradation_state = CLOSED_LOOP;
    }
    else {"""
content = content.replace("    else {", shield_code)

# 4. Print
content = content.replace("fm->err_acc_A += err_A * dt;", 'if (fm->fault_isolation_timer > 0.0f) printf("t=%f, err_A=%f, err_B=%f, err_C=%f, ia_true_diff=%f, ia_meas=%f, iap=%f\\n", fm->unisolated_timer, err_A, err_B, err_C, i_a - ia_pred, i_a, ia_pred);\n            fm->err_acc_A += err_A * dt;')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
