import mysql.connector
passwords = ['', 'root', '1234', '12345', 'password', 'admin', 'mysql', '123456']
for pw in passwords:
    try:
        conn = mysql.connector.connect(host='localhost', user='root', password=pw, port=3306)
        print(f'SUCCESS with password: "{pw}"')
        conn.close()
        break
    except Exception as e:
        err = str(e)
        if 'Access denied' in err:
            print(f'Wrong password: "{pw}"')
        elif 'Connection refused' in err or '2003' in err:
            print('MySQL not running on port 3306 - is MySQL installed?')
            break
        elif '2002' in err:
            print('MySQL socket not found - MySQL may not be running')
            break
        else:
            print(f'Error for "{pw}": {err}')
            break
