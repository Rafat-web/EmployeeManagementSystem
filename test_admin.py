
from database import get_db_connection
from werkzeug.security import check_password_hash
from getpass import getpass

connection = get_db_connection()
cursor = connection.cursor(dictionary=True)

cursor.execute(
    "SELECT * FROM admins WHERE username = %s",
    ("admin",)
)

admin = cursor.fetchone()

if admin:
    password = getpass("Enter your new admin password: ")

    if check_password_hash(admin["password_hash"], password):
        print("SUCCESS: Password is correct!")
    else:
        print("FAILED: Password does not match!")
else:
    print("Admin account not found!")

cursor.close()
connection.close()
