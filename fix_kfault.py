with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("""    else {
        fm->status.i_a_rec = i_a;
        fm->status.i_b_rec = i_b;
        fm->status.i_c_rec = i_c;
        fm->status.degradation_state = CLOSED_LOOP;
    }""", """    else {
        fm->status.i_a_rec = i_a;
        fm->status.i_b_rec = i_b;
        fm->status.i_c_rec = i_c;
        if (fm->fault_isolation_timer > 0.0f) fm->status.degradation_state = DEGRADED;
        else fm->status.degradation_state = CLOSED_LOOP;
    }""")

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
