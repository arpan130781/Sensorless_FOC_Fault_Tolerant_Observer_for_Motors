with open("src/foc_core.c", "r") as f:
    content = f.read()

content = content.replace("float obs_omega = obs_mgr_get_omega(&obs_mgr);", "")
content = content.replace("float angle = 0.0f;", "")
content = content.replace("angle = obs_theta;", "angle = frozen_theta;")

with open("src/foc_core.c", "w") as f:
    f.write(content)
