
from database import get_db_connection
from werkzeug.security import generate_password_hash

username = "admin"
new_password = input("Enter your new admin password: ")

if not new_password:
    print("Password cannot be empty.")
else:
    connection = get_db_connection()
    cursor = connection.cursor()

    password_hash = generate_password_hash(new_password)

    cursor.execute(
        "UPDATE admins SET password_hash = %s WHERE username = %s",
        (password_hash, username)
    )

    connection.commit()

    print("Admin password updated successfully!")

    cursor.close()
    connection.close()
