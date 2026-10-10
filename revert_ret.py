import re
with open('src/fault_monitor.c', 'r') as f:
    c_code = f.read()

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
    }"""
orig_ret = """    } else {
        fm->status.i_a_rec = i_a;
        fm->status.i_b_rec = i_b;
        fm->status.i_c_rec = i_c;
    }"""
c_code = c_code.replace(replacement_ret, orig_ret)
with open('src/fault_monitor.c', 'w') as f:
    f.write(c_code)
