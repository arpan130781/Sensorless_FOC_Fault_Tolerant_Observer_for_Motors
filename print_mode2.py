with open("src/foc_core.c", "r") as f:
    content = f.read()

content = "#include <stdio.h>\n" + content

with open("src/foc_core.c", "w") as f:
    f.write(content)
