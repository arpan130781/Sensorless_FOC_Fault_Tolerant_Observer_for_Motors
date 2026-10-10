with open("src/fault_monitor.c", "r") as f:
    content = f.read()

content = content.replace("fm->err_acc_A += err_A * dt;", 'if (fm->fault_isolation_timer > 0.0f) printf("t=%f, i_a=%f, iap=%f, i_b=%f, ibp=%f, i_c=%f, icp=%f\\n", fm->fault_isolation_timer, i_a, ia_pred, i_b, ib_pred, i_c, ic_pred);\n            fm->err_acc_A += err_A * dt;')

with open("src/fault_monitor.c", "w") as f:
    f.write(content)
