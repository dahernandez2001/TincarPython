from models import get_connection
from utils.security import hash_password

# Datos de prueba
email = 'arrendador@demo.test'
name = 'Arrendador Demo'
password = 'Password123!'
role = 'arrendador'

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id FROM users WHERE email = ?", (email,))
if cur.fetchone():
    print('Usuario ya existe:', email)
else:
    hashed = hash_password(password)
    cur.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)", (name, email, hashed, role))
    conn.commit()
    print('Usuario creado:', email)

conn.close()
print('Credenciales de prueba:')
print('  email:', email)
print('  password:', password)
