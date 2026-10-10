with open('src/foc_core.c', 'r') as f:
    c_code = f.read()

# We will just rewrite foc_tick completely to ensure correct ordering.
# Instead of replacing, I'll extract it and rewrite it.
