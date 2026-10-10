import re

with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("fm->consecutive_confident = 0;\n                fm->best_channel = -1;", "fm->consecutive_confident = 0;\n                fm->best_channel = -1;\n                fm->fault_isolation_timer = 0.0f;")

# Let's also restore consecutive_confident >= 10, because if the noise burst IS NOT LATCHED in 2ms, it will be declared AMBIGUOUS, which sets it to LIMP mode. But wait... if it sets to LIMP mode, it unlatches when the noise burst ends! So it DOES recover from LIMP mode if I fix the variable reset! Let me test that!
with open("src/fault_monitor.c", "w") as f:
    f.write(content)
