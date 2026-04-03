import mysql.connector

ports = [3306, 3307, 3308]
passwords = ['', 'root', '1234', '12345', 'password', 'admin', 'mysql', '123456', 'toor', 'test']

for port in ports:
    for pw in passwords:
        try:
            conn = mysql.connector.connect(host='localhost', user='root', password=pw, port=port, connect_timeout=2)
            print(f"FOUND: port={port} password='{pw}'")
            conn.close()
            exit()
        except mysql.connector.errors.InterfaceError:
            print(f"Port {port} not open")
            break
        except Exception as e:
            if 'Access denied' in str(e):
                pass  # wrong password, try next
            else:
                print(f"Port {port}: {e}")
                break

print("Done probing")
