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


def create_parkings_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parkings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            name TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            department TEXT,
            city TEXT,
            housing_type TEXT,
            size TEXT,
            features TEXT,
            image_path TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def add_parking(owner_id, name, phone=None, email=None, address=None, department=None, city=None,
                housing_type=None, size=None, features=None, image_path=None, active=1):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO parkings (owner_id, name, phone, email, address, department, city, housing_type, size, features, image_path, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (owner_id, name, phone, email, address, department, city, housing_type, size, features, image_path, active))
    conn.commit()
    last_id = cursor.lastrowid
    # Recuperar el registro insertado y devolverlo como dict
    cursor.execute('SELECT id, owner_id, name, phone, email, address, department, city, housing_type, size, features, image_path, active, created_at FROM parkings WHERE id = ?', (last_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        'id': row[0],
        'owner_id': row[1],
        'name': row[2],
        'phone': row[3],
        'email': row[4],
        'address': row[5],
        'department': row[6],
        'city': row[7],
        'housing_type': row[8],
        'size': row[9],
        'features': row[10],
        'image_path': row[11],
        'active': bool(row[12]),
        'created_at': row[13]
    }


def get_parkings_by_owner(owner_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, phone, email, address, department, city, housing_type, size, features, image_path, active FROM parkings WHERE owner_id = ?', (owner_id,))
    rows = cursor.fetchall()
    conn.close()
    # Convert to list of dicts
    parkings = []
    for r in rows:
        parkings.append({
            'id': r[0], 'name': r[1], 'phone': r[2], 'email': r[3], 'address': r[4], 'department': r[5], 'city': r[6],
            'housing_type': r[7], 'size': r[8], 'features': r[9], 'image_path': r[10], 'active': bool(r[11])
        })
    return parkings


def get_parking(parking_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, owner_id, name, phone, email, address, department, city, housing_type, size, features, image_path, active, created_at FROM parkings WHERE id = ?', (parking_id,))
    r = cursor.fetchone()
    conn.close()
    if not r:
        return None
    return {
        'id': r[0], 'owner_id': r[1], 'name': r[2], 'phone': r[3], 'email': r[4], 'address': r[5], 'department': r[6], 'city': r[7],
        'housing_type': r[8], 'size': r[9], 'features': r[10], 'image_path': r[11], 'active': bool(r[12]), 'created_at': r[13]
    }


def update_parking(parking_id, **fields):
    # fields: name, phone, email, address, department, city, housing_type, size, features, image_path, active
    allowed = ['name','phone','email','address','department','city','housing_type','size','features','image_path','active']
    keys = [k for k in fields.keys() if k in allowed]
    if not keys:
        return False
    set_clause = ', '.join([f"{k} = ?" for k in keys])
    params = [ (1 if fields[k] is True else 0) if k=='active' and isinstance(fields[k], bool) else fields[k] for k in keys]
    params.append(parking_id)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f'UPDATE parkings SET {set_clause} WHERE id = ?', params)
    conn.commit()
    conn.close()
    return True


def delete_parking(parking_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM parkings WHERE id = ?', (parking_id,))
    conn.commit()
    conn.close()
    return True

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
