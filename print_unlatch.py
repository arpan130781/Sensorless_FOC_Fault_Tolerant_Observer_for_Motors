import re

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

unlatch_code = """
                fm->fault_latch_a = false;
                fm->fault_latch_b = false;
                fm->fault_latch_c = false;
                fm->ambiguous_fault = false; fm->unisolated_timer = 0.0f;
                printf("UNLATCHED at clear_timer=%f\\n", fm->clear_timer);
"""
content = content.replace("""
                fm->fault_latch_a = false;
                fm->fault_latch_b = false;
                fm->fault_latch_c = false;
                fm->ambiguous_fault = false; fm->unisolated_timer = 0.0f;
""", unlatch_code)

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
