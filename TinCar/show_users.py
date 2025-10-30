import sqlite3

# Conectar a la base de datos
conn = sqlite3.connect("database/tincar.db")
cursor = conn.cursor()

cursor.execute("SELECT id, nombre, email, role FROM users")
users = cursor.fetchall()

print("Usuarios registrados:")
for user in users:
    print(user)

conn.close()


try:
    # Verificar que la tabla users existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
    if cursor.fetchone() is None:
        print("No se encontró la tabla 'users'.")
    else:
        # Obtener todos los usuarios
        cursor.execute("SELECT id, name, email, phone, role FROM users;")
        rows = cursor.fetchall()
        if not rows:
            print("No hay usuarios registrados.")
        else:
            print("Usuarios registrados:")
            for row in rows:
                print(f"ID: {row[0]}, Nombre: {row[1]}, Email: {row[2]}, Teléfono: {row[3]}, Rol: {row[4]}")
finally:
    conn.close()
