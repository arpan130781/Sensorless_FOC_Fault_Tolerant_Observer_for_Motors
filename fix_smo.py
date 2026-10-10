with open("src/motor_params.h", "r") as f:
    content = f.read()

content = content.replace("params.smo_k = 37.7f;", "params.smo_k = 20.0f;")

with open("src/motor_params.h", "w") as f:
    f.write(content)
