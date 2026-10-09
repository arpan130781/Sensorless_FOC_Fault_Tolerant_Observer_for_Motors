import re

with open("src/fault_monitor.c", "r") as f:
    text = f.read()

bad = """    if (!k_fault && !fm->fault_latch_a && !fm->fault_latch_b && !fm->fault_latch_c && !fm->ambiguous_fault) {
        fm->lkg_theta = theta;
        fm->lkg_omega = omega;
    }"""

good = """    if (!k_fault && !fm->fault_latch_a && !fm->fault_latch_b && !fm->fault_latch_c && !fm->ambiguous_fault) {
        fm->lkg_theta = theta;
        fm->lkg_omega += 50.0f * dt * (omega - fm->lkg_omega);
    }"""

text = text.replace(bad, good)

with open("src/fault_monitor.c", "w") as f:
    f.write(text)
