with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace('printf("t=%f, i_a=%f, iap=%f', 'printf("t=%f, v_alpha=%f, i_a=%f, iap=%f')
content = content.replace('fm->fault_isolation_timer, i_a,', 'fm->fault_isolation_timer, v_alpha, i_a,')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
