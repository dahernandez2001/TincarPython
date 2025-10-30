import sqlite3

# Conectar a la base de datos
from models import get_connection

conn = get_connection()
cursor = conn.cursor()

cursor.execute("SELECT id, name, email, phone, role FROM users")
users = cursor.fetchall()

print("Usuarios registrados:")
for user in users:
    print(user)

conn.close()
