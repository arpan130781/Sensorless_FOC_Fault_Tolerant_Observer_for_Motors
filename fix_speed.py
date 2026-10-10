with open("simulation/harness/config.py", "r") as f:
    content = f.read()

content = content.replace("2000.0", "1800.0")

with open("simulation/harness/config.py", "w") as f:
    f.write(content)
