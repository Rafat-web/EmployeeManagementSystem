
import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host="127.0.0.1",
        port=3309,
        user="root",
        password="Rafat@12345",
        database="employee_management"
    )
