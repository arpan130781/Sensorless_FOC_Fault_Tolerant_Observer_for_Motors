with open("simulation/harness/config.py", "r") as f:
    content = f.read()

content = content.replace("'observer_select': 1,", "'observer_select': 0,")

with open("simulation/harness/config.py", "w") as f:
    f.write(content)
