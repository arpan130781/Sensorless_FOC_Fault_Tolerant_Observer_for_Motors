with open("simulation/harness/config.py", "r") as f:
    content = f.read()

content = content.replace("'smo_k': 37.7,", "'smo_k': 20.0,")

with open("simulation/harness/config.py", "w") as f:
    f.write(content)
