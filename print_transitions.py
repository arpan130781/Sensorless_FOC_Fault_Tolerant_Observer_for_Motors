import re

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

# I want to print whenever a latch happens
latch_code = """
                    if (fm->best_channel == 0) fm->fault_latch_a = true;
                    else if (fm->best_channel == 1) fm->fault_latch_b = true;
                    else fm->fault_latch_c = true;
                    printf("LATCHED: a=%d, b=%d, c=%d at t=%f\\n", fm->fault_latch_a, fm->fault_latch_b, fm->fault_latch_c, fm->unisolated_timer);
"""
content = content.replace("""
                    if (fm->best_channel == 0) fm->fault_latch_a = true;
                    else if (fm->best_channel == 1) fm->fault_latch_b = true;
                    else fm->fault_latch_c = true;
""", latch_code)

ambig_code = """
                if (fm->unisolated_timer > 0.002f) {
                    fm->ambiguous_fault = true;
                    printf("AMBIGUOUS FAULT at t=%f\\n", fm->unisolated_timer);
                }
"""
content = content.replace("""
                if (fm->unisolated_timer > 0.002f) {
                    fm->ambiguous_fault = true;
                }
""", ambig_code)

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
