import re
with open('src/fault_monitor.h', 'r') as f:
    h_code = f.read()
if "float unisolated_timer;" not in h_code:
    h_code = h_code.replace("    float fault_isolation_timer;", "    float fault_isolation_timer;\n    float unisolated_timer;")
with open('src/fault_monitor.h', 'w') as f:
    f.write(h_code)

with open('src/fault_monitor.c', 'r') as f:
    c_code = f.read()
c_code = c_code.replace("fm->fault_isolation_timer = 0;", "fm->fault_isolation_timer = 0.0f; fm->unisolated_timer = 0.0f;")
c_code = c_code.replace("fm->ambiguous_fault = false;", "fm->ambiguous_fault = false; fm->unisolated_timer = 0.0f;")
c_code = re.sub(r"        if \(fm->fault_isolation_timer > 0.0f\) \{\n            fm->fault_isolation_timer \+= dt;", "        if (fm->fault_isolation_timer > 0.0f) {\n            fm->fault_isolation_timer += dt;\n            fm->unisolated_timer += dt;", c_code)

amb_section = r"""                \} else if \(fm->fault_isolation_timer > 0.020f\) \{
                    /\* After 20ms without confident isolation → ambiguous \*/
                    fm->ambiguous_fault = true;
                \}"""
c_code = re.sub(amb_section, """                }
                if (fm->unisolated_timer > 0.002f) {
                    fm->ambiguous_fault = true;
                }""", c_code)

snap_section = r"    if \(!k_fault && !fm->fault_latch_a && !fm->fault_latch_b && !fm->fault_latch_c && !fm->ambiguous_fault\) \{"
c_code = re.sub(snap_section, "    if (!k_fault && !fm->fault_latch_a && !fm->fault_latch_b && !fm->fault_latch_c && !fm->ambiguous_fault && fm->unisolated_timer == 0.0f) {", c_code)

confident_section = r"                bool confident = \(separation > 0.3f \* fm->E_acc\)\s+&& \(fm->E_acc > 0.0001f\)\s+&& \(min_err > 0.0f\)\s+&& \(second_err > min_err \* 1.3f\);"
replacement = """                bool confident = (separation > 0.3f * fm->E_acc) && (fm->E_acc > 0.0001f) && (min_err < 1.0f * fm->E_acc);"""
c_code = re.sub(confident_section, replacement, c_code)

ret_section = r"""    \} else \{
        fm->status.i_a_rec = i_a;
        fm->status.i_b_rec = i_b;
        fm->status.i_c_rec = i_c;
        fm->status.degradation_state = CLOSED_LOOP;
    \}"""
replacement_ret = """    } else if (fm->fault_isolation_timer > 0.0f) {
        float ia_pred = fm->i_alpha_pred;
        float ib_pred = -0.5f * fm->i_alpha_pred + 0.8660254f * fm->i_beta_pred;
        float ic_pred = -0.5f * fm->i_alpha_pred - 0.8660254f * fm->i_beta_pred;
        fm->status.i_a_rec = ia_pred;
        fm->status.i_b_rec = ib_pred;
        fm->status.i_c_rec = ic_pred;
    } else {
        fm->status.i_a_rec = i_a;
        fm->status.i_b_rec = i_b;
        fm->status.i_c_rec = i_c;
    }
    
    if (fm->ambiguous_fault) {
        fm->status.degradation_state = LIMP;
    } else {
        fm->status.degradation_state = CLOSED_LOOP;
    }"""
c_code = re.sub(ret_section, replacement_ret, c_code)
c_code = c_code.replace("""    if (fm->ambiguous_fault) {
        fm->status.degradation_state = LIMP;
    }""", "")

with open('src/fault_monitor.c', 'w') as f:
    f.write(c_code)
