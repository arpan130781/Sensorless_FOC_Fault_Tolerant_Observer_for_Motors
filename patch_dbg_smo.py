import re
with open('src/foc_core.c', 'r') as f:
    c_code = f.read()

replacement = """    FocOutput out = {0};
    static float prev_v_alpha = 0.0f, prev_v_beta = 0.0f;
    static int log_cnt = 0;
    if (fault.fault_isolation_timer > 0.0f && log_cnt < 20) {
        FILE *f_dbg = fopen("debug_smo.log", "a");
        if (f_dbg) {
            fprintf(f_dbg, "lkg_th=%f, E_al=%f, smo_emf=%f, smo_th=%f, z_al=%f\\n", fault.lkg_theta, -fault.psi_f*fault.lkg_omega*sinf(fault.lkg_theta), smo.emf_alpha, smo.theta_hat, (smo.i_alpha_hat - i_alpha)*smo.k);
            fclose(f_dbg);
        }
        log_cnt++;
    }"""
c_code = re.sub(r"    FocOutput out = \{0\};\n    static float prev_v_alpha = 0.0f, prev_v_beta = 0.0f;", replacement, c_code)

if "<stdio.h>" not in c_code:
    c_code = "#include <stdio.h>\n" + c_code
with open('src/foc_core.c', 'w') as f:
    f.write(c_code)
