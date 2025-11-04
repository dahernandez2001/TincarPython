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
            latitude REAL,
            longitude REAL,
            active INTEGER DEFAULT 1,
            occupied_since TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    # Si la tabla ya existía antes de agregar latitude/longitude, asegurarse de que las columnas estén presentes
    cursor.execute("PRAGMA table_info(parkings)")
    cols = [r[1] for r in cursor.fetchall()]
    if 'latitude' not in cols:
        try:
            cursor.execute('ALTER TABLE parkings ADD COLUMN latitude REAL')
        except Exception:
            pass
    if 'longitude' not in cols:
        try:
            cursor.execute('ALTER TABLE parkings ADD COLUMN longitude REAL')
        except Exception:
            pass
    if 'occupied_since' not in cols:
        try:
            cursor.execute("ALTER TABLE parkings ADD COLUMN occupied_since TEXT")
        except Exception:
            pass
    conn.commit()
    conn.close()


def add_parking(owner_id, name, phone=None, email=None, address=None, department=None, city=None,
                housing_type=None, size=None, features=None, image_path=None, latitude=None, longitude=None, active=1):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO parkings (owner_id, name, phone, email, address, department, city, housing_type, size, features, image_path, latitude, longitude, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (owner_id, name, phone, email, address, department, city, housing_type, size, features, image_path, latitude, longitude, active))
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
    cursor.execute('SELECT id, name, phone, email, address, department, city, housing_type, size, features, image_path, latitude, longitude, active, occupied_since FROM parkings WHERE owner_id = ?', (owner_id,))
    rows = cursor.fetchall()
    conn.close()
    # Convert to list of dicts
    parkings = []
    for r in rows:
        parkings.append({
            'id': r[0], 'name': r[1], 'phone': r[2], 'email': r[3], 'address': r[4], 'department': r[5], 'city': r[6],
            'housing_type': r[7], 'size': r[8], 'features': r[9], 'image_path': r[10], 'latitude': r[11], 'longitude': r[12], 'active': bool(r[13]), 'occupied_since': r[14]
        })
    return parkings


def get_parking(parking_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, owner_id, name, phone, email, address, department, city, housing_type, size, features, image_path, latitude, longitude, active, occupied_since, created_at FROM parkings WHERE id = ?', (parking_id,))
    r = cursor.fetchone()
    conn.close()
    if not r:
        return None
    return {
        'id': r[0], 'owner_id': r[1], 'name': r[2], 'phone': r[3], 'email': r[4], 'address': r[5], 'department': r[6], 'city': r[7],
        'housing_type': r[8], 'size': r[9], 'features': r[10], 'image_path': r[11], 'latitude': r[12], 'longitude': r[13], 'active': bool(r[14]), 'occupied_since': r[15], 'created_at': r[16]
    }


def update_parking(parking_id, **fields):
    # fields: name, phone, email, address, department, city, housing_type, size, features, image_path, active
    allowed = ['name','phone','email','address','department','city','housing_type','size','features','image_path','active']
    # Allow updating coordinates
    allowed += ['latitude','longitude','occupied_since']
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


def create_reservations_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER NOT NULL,
            parking_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            duration_minutes INTEGER DEFAULT 10,
            eta_minutes INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    # Migration: si la tabla existía sin las columnas nuevas, intentar agregarlas
    cursor.execute('PRAGMA table_info(reservations)')
    existing = [r[1] for r in cursor.fetchall()]
    if 'duration_minutes' not in existing:
        try:
            cursor.execute('ALTER TABLE reservations ADD COLUMN duration_minutes INTEGER DEFAULT 10')
        except Exception:
            pass
    if 'eta_minutes' not in existing:
        try:
            cursor.execute('ALTER TABLE reservations ADD COLUMN eta_minutes INTEGER DEFAULT 0')
        except Exception:
            pass
    conn.commit()
    conn.close()


def create_reviews_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reviewer_id INTEGER NOT NULL,
            driver_id INTEGER NOT NULL,
            parking_id INTEGER,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def add_reservation(driver_id, parking_id, status='pending', duration_minutes=10, eta_minutes=0):
    """Crea una reserva; duration_minutes y eta_minutes son opcionales.
    Devuelve el registro creado."""
    conn = get_connection()
    cursor = conn.cursor()
    # Intentar insertar incluyendo las nuevas columnas (si existen)
    try:
        cursor.execute('INSERT INTO reservations (driver_id, parking_id, status, duration_minutes, eta_minutes) VALUES (?, ?, ?, ?, ?)', (driver_id, parking_id, status, duration_minutes, eta_minutes))
    except Exception:
        # Si la tabla no tiene las columnas nuevas, caer atrás a la inserción antigua
        cursor.execute('INSERT INTO reservations (driver_id, parking_id, status) VALUES (?, ?, ?)', (driver_id, parking_id, status))
    conn.commit()
    last_id = cursor.lastrowid
    # Intentar seleccionar las columnas nuevas si existen
    try:
        cursor.execute('SELECT id, driver_id, parking_id, status, duration_minutes, eta_minutes, created_at FROM reservations WHERE id = ?', (last_id,))
        r = cursor.fetchone()
    except Exception:
        cursor.execute('SELECT id, driver_id, parking_id, status, created_at FROM reservations WHERE id = ?', (last_id,))
        r = cursor.fetchone()
    conn.close()
    if not r:
        return None
    # Normalizar salida: incluir duration_minutes y eta_minutes si existen
    out = {'id': r[0], 'driver_id': r[1], 'parking_id': r[2], 'status': r[3]}
    try:
        # Si la consulta devolvió duration/eta
        if len(r) >= 6:
            out['duration_minutes'] = r[4]
            out['eta_minutes'] = r[5]
            out['created_at'] = r[6]
        else:
            out['created_at'] = r[4]
    except Exception:
        out['created_at'] = None
    # Marcar el parking como ocupado y guardar timestamp
    try:
        import datetime
        occupied_ts = datetime.datetime.utcnow().isoformat()
        try:
            update_parking(parking_id, active=0, occupied_since=occupied_ts)
        except Exception:
            pass
    except Exception:
        pass
    return out


def get_reservations_count_by_driver(driver_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM reservations WHERE driver_id = ?', (driver_id,))
    row = cursor.fetchone()
    conn.close()
    return int(row[0]) if row else 0


def get_reservation_by_driver_and_parking(driver_id, parking_id):
    """Devuelve la reserva activa (o cualquier reserva) del conductor para un parking, o None."""
    conn = get_connection()
    cursor = conn.cursor()
    # Intentar seleccionar también duration/eta si existen
    try:
        cursor.execute('SELECT id, driver_id, parking_id, status, duration_minutes, eta_minutes, created_at FROM reservations WHERE driver_id = ? AND parking_id = ? ORDER BY created_at DESC LIMIT 1', (driver_id, parking_id))
        r = cursor.fetchone()
    except Exception:
        cursor.execute('SELECT id, driver_id, parking_id, status, created_at FROM reservations WHERE driver_id = ? AND parking_id = ? ORDER BY created_at DESC LIMIT 1', (driver_id, parking_id))
        r = cursor.fetchone()
    conn.close()
    if not r:
        return None
    out = {'id': r[0], 'driver_id': r[1], 'parking_id': r[2], 'status': r[3]}
    try:
        if len(r) >= 6:
            out['duration_minutes'] = r[4]
            out['eta_minutes'] = r[5]
            out['created_at'] = r[6]
        else:
            out['created_at'] = r[4]
    except Exception:
        out['created_at'] = None
    return out


def cancel_reservation(reservation_id):
    """Marca la reserva como 'cancelled'. Devuelve True si se actualizó alguna fila."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # obtener parking_id asociado
        cursor.execute('SELECT parking_id FROM reservations WHERE id = ?', (reservation_id,))
        row = cursor.fetchone()
        parking_id = row[0] if row else None
        cursor.execute("UPDATE reservations SET status = 'cancelled' WHERE id = ?", (reservation_id,))
        conn.commit()
        changed = cursor.rowcount
    except Exception:
        conn.rollback()
        changed = 0
    conn.close()
    # Si se canceló, liberar el parking (si existe)
    if changed and parking_id:
        try:
            update_parking(parking_id, active=1, occupied_since=None)
        except Exception:
            pass
    return changed > 0


def add_review(reviewer_id, driver_id, parking_id, rating, comment=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO reviews (reviewer_id, driver_id, parking_id, rating, comment) VALUES (?, ?, ?, ?, ?)', (reviewer_id, driver_id, parking_id, rating, comment))
    conn.commit()
    conn.close()


def get_rating_sum_for_driver(driver_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(rating) FROM reviews WHERE driver_id = ?', (driver_id,))
    row = cursor.fetchone()
    conn.close()
    return int(row[0]) if row and row[0] is not None else 0


def get_active_parkings():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, owner_id, name, phone, email, address, department, city, housing_type, size, features, image_path, latitude, longitude FROM parkings WHERE active = 1')
    rows = cursor.fetchall()
    conn.close()
    parkings = []
    for r in rows:
        parkings.append({
            'id': r[0], 'owner_id': r[1], 'name': r[2], 'phone': r[3], 'email': r[4], 'address': r[5],
            'department': r[6], 'city': r[7], 'housing_type': r[8], 'size': r[9], 'features': r[10], 'image_path': r[11],
            'latitude': r[12], 'longitude': r[13]
        })
    return parkings
