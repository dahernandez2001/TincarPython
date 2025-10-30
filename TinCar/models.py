import os
import sqlite3

# Usar una ruta absoluta al archivo de base de datos dentro del paquete `TinCar`
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'tincar.db')


def ensure_db_dir():
    """Asegura que el directorio para la DB exista."""
    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)


def get_connection():
    ensure_db_dir()
    try:
        conn = sqlite3.connect(DB_PATH)
    except Exception as e:
        # Si no se puede abrir DB en la ruta prevista (permisos, FS de solo lectura,
        # despliegues especiales), intentar usar /tmp como fallback.
        try:
            alt_path = os.path.join('/tmp', 'tincar.db')
            print(f"[models] warning: no se puede abrir {DB_PATH} ({e}), usando {alt_path} como fallback")
            conn = sqlite3.connect(alt_path)
        except Exception as e2:
            # Último recurso: usar DB en memoria (no persistente)
            print(f"[models] error abriendo fallback DB ({e2}), usando ':memory:' - los datos no persistirán")
            conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row  # para acceder a columnas por nombre
    return conn

def create_users_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password BLOB NOT NULL,
            phone TEXT,
            role TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_user(name, email, password, phone, role):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (name, email, password, phone, role)
        VALUES (?, ?, ?, ?, ?)
    ''', (name, email, password, phone, role))
    conn.commit()
    conn.close()

def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    user = cursor.fetchone()
    conn.close()
    return user
