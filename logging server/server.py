import socket

srv = socket.socket()
srv.bind(("192.168.137.1", 5000))
srv.listen(1)
conn, addr = srv.accept()
print(f"Connected: {addr}")

with open("logs.csv", "w") as f:
    f.write("timestamp_ms,voltage_V,current_mA,power_mW,ambient_temp_C,ambient_humidity_%\n")
    while True:
        data = conn.recv(1024).decode()
        if not data:
            break
        f.write(data)
        f.flush()
        print(data.strip())