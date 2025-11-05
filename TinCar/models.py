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


def create_notifications_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            type TEXT NOT NULL,
            status TEXT DEFAULT 'unread',
            reservation_id INTEGER,
            owner_id INTEGER,
            eta INTEGER,
            extra_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(reservation_id) REFERENCES reservations(id),
            FOREIGN KEY(owner_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()


def add_reservation(driver_id, parking_id, status='pending', duration_minutes=10, eta_minutes=0):
    """Crea una reserva; duration_minutes y eta_minutes son opcionales.
    Devuelve el registro creado."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Obtener información del conductor y del parqueadero para las notificaciones
    cursor.execute('SELECT name FROM users WHERE id = ?', (driver_id,))
    driver_row = cursor.fetchone()
    driver_name = driver_row[0] if driver_row else "Un conductor"
    
    cursor.execute('SELECT owner_id, name FROM parkings WHERE id = ?', (parking_id,))
    parking_row = cursor.fetchone()
    owner_id = parking_row[0] if parking_row else None
    parking_name = parking_row[1] if parking_row else "el parqueadero"
    
    # Intentar insertar incluyendo las nuevas columnas (si existen)
    try:
        cursor.execute('INSERT INTO reservations (driver_id, parking_id, status, duration_minutes, eta_minutes) VALUES (?, ?, ?, ?, ?)', 
                      (driver_id, parking_id, status, duration_minutes, eta_minutes))
    except Exception:
        # Si la tabla no tiene las columnas nuevas, caer atrás a la inserción antigua
        cursor.execute('INSERT INTO reservations (driver_id, parking_id, status) VALUES (?, ?, ?)', 
                      (driver_id, parking_id, status))
    conn.commit()
    last_id = cursor.lastrowid

    try:
        # Notificación para el arrendador
        if owner_id:
            add_notification(
                user_id=owner_id,
                message=f"{driver_name} ha reservado {parking_name}. Llegará en aproximadamente {eta_minutes} minutos.",
                type='new_reservation',
                reservation_id=last_id,
                owner_id=owner_id,
                eta=eta_minutes,
                extra_data=f'{{"driver_id": {driver_id}, "driver_name": "{driver_name}"}}'
            )

        # Notificación para el conductor
        add_notification(
            user_id=driver_id,
            message=f'Tienes una reserva activa en {parking_name}. Debes llegar en {eta_minutes} minutos.',
            type='active_reservation',
            reservation_id=last_id,
            owner_id=owner_id,
            eta=eta_minutes,
            extra_data=f'{{"parking_name": "{parking_name}", "duration": {duration_minutes}}}'
        )
    except Exception as e:
        print(f"Error creando notificaciones: {e}")

    # Intentar seleccionar las columnas nuevas si existen
    try:
        cursor.execute('SELECT id, driver_id, parking_id, status, duration_minutes, eta_minutes, created_at FROM reservations WHERE id = ?', (last_id,))
        r = cursor.fetchone()
    except Exception:
        cursor.execute('SELECT id, driver_id, parking_id, status, created_at FROM reservations WHERE id = ?', (last_id,))
        r = cursor.fetchone()
    
    if not r:
        conn.close()
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
    
    conn.close()
    return out


def add_notification(user_id, message, type, reservation_id=None, owner_id=None, eta=None, extra_data=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO notifications (user_id, message, type, reservation_id, owner_id, eta, extra_data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, message, type, reservation_id, owner_id, eta, extra_data))
    conn.commit()
    conn.close()


def get_notifications_by_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, message, type, status, created_at, reservation_id, owner_id, eta, extra_data 
        FROM notifications 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            'id': row[0],
            'message': row[1],
            'type': row[2],
            'status': row[3],
            'created_at': row[4],
            'reservation_id': row[5],
            'owner_id': row[6],
            'eta': row[7],
            'extra_data': row[8]
        }
        for row in rows
    ]


def get_reservations_count_by_driver(driver_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM reservations WHERE driver_id = ?', (driver_id,))
    row = cursor.fetchone()
    conn.close()
    return int(row[0]) if row else 0


def get_reservation_by_driver_and_parking(driver_id, parking_id):
    """Devuelve la reserva activa del conductor para un parking, o None.
    Solo considera reservas con estado 'pending' o 'arrived'."""
    conn = get_connection()
    cursor = conn.cursor()
    # Intentar seleccionar también duration/eta si existen
    try:
        cursor.execute('''
            SELECT id, driver_id, parking_id, status, duration_minutes, eta_minutes, created_at 
            FROM reservations 
            WHERE driver_id = ? AND parking_id = ? AND status IN ('pending', 'arrived') 
            ORDER BY created_at DESC LIMIT 1
        ''', (driver_id, parking_id))
        r = cursor.fetchone()
    except Exception:
        cursor.execute('''
            SELECT id, driver_id, parking_id, status, created_at 
            FROM reservations 
            WHERE driver_id = ? AND parking_id = ? AND status IN ('pending', 'arrived')
            ORDER BY created_at DESC LIMIT 1
        ''', (driver_id, parking_id))
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


def get_reservation(id):
    """Obtiene una reserva por su ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id, driver_id, parking_id, status, duration_minutes, eta_minutes, created_at FROM reservations WHERE id = ?', (id,))
        r = cursor.fetchone()
    except Exception:
        cursor.execute('SELECT id, driver_id, parking_id, status, created_at FROM reservations WHERE id = ?', (id,))
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
    return out

def cancel_reservation(reservation_id, cancelled_by_id):
    """Cancela una reserva y envía notificaciones apropiadas.
    cancelled_by_id: ID del usuario que cancela (puede ser conductor u arrendador)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Obtener la información de la reserva
    reservation = get_reservation(reservation_id)
    if not reservation:
        conn.close()
        return False
        
    # Obtener información del conductor y del parqueadero
    cursor.execute('SELECT name FROM users WHERE id = ?', (reservation['driver_id'],))
    driver_row = cursor.fetchone()
    driver_name = driver_row[0] if driver_row else "El conductor"
    
    cursor.execute('SELECT owner_id, name FROM parkings WHERE id = ?', (reservation['parking_id'],))
    parking_row = cursor.fetchone()
    owner_id = parking_row[0] if parking_row else None
    parking_name = parking_row[1] if parking_row else "el parqueadero"
    
    # Actualizar el estado de la reserva
    cursor.execute('UPDATE reservations SET status = ? WHERE id = ?', ('cancelled', reservation_id))
    conn.commit()
    
    # Reactivar el parqueadero
    try:
        update_parking(reservation['parking_id'], active=1, occupied_since=None)
    except Exception as e:
        print(f"Error reactivando parqueadero: {e}")

    try:
        # Determinar quién canceló y crear notificaciones apropiadas
        if cancelled_by_id == reservation['driver_id']:
            # El conductor canceló
            if owner_id:
                add_notification(
                    user_id=owner_id,
                    message=f"{driver_name} ha cancelado su reserva en {parking_name}.",
                    type='reservation_cancelled',
                    reservation_id=reservation_id,
                    owner_id=owner_id,
                    extra_data=f'{{"cancelled_by": "driver", "driver_id": {reservation["driver_id"]}}}'
                )
            # Notificación de confirmación para el conductor
            add_notification(
                user_id=reservation['driver_id'],
                message=f'Has cancelado tu reserva en {parking_name}.',
                type='reservation_cancelled',
                reservation_id=reservation_id,
                owner_id=owner_id,
                extra_data=f'{{"cancelled_by": "self", "parking_name": "{parking_name}"}}'
            )
        else:
            # El arrendador canceló
            add_notification(
                user_id=reservation['driver_id'],
                message=f'Tu reserva en {parking_name} ha sido cancelada por el arrendador.',
                type='reservation_cancelled',
                reservation_id=reservation_id,
                owner_id=owner_id,
                extra_data=f'{{"cancelled_by": "owner", "parking_name": "{parking_name}"}}'
            )
            if owner_id:
                add_notification(
                    user_id=owner_id,
                    message=f'Has cancelado la reserva de {driver_name} en {parking_name}.',
                    type='reservation_cancelled',
                    reservation_id=reservation_id,
                    owner_id=owner_id,
                    extra_data=f'{{"cancelled_by": "self", "driver_id": {reservation["driver_id"]}}}'
                )
    except Exception as e:
        print(f"Error creando notificaciones de cancelación: {e}")
    
    conn.close()
    return True


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


def finish_reservation(reservation_id, finished_by_id):
    """Marca una reserva como 'completed' y envía notificaciones apropiadas."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Obtener la información de la reserva
    reservation = get_reservation(reservation_id)
    if not reservation or reservation['status'] not in ['arrived', 'active']:
        conn.close()
        return False
        
    # Obtener información del conductor y del parqueadero
    cursor.execute('SELECT name FROM users WHERE id = ?', (reservation['driver_id'],))
    driver_row = cursor.fetchone()
    driver_name = driver_row[0] if driver_row else "El conductor"
    
    cursor.execute('SELECT owner_id, name FROM parkings WHERE id = ?', (reservation['parking_id'],))
    parking_row = cursor.fetchone()
    owner_id = parking_row[0] if parking_row else None
    parking_name = parking_row[1] if parking_row else "el parqueadero"
    
    # Actualizar el estado de la reserva
    cursor.execute('UPDATE reservations SET status = ? WHERE id = ?', ('completed', reservation_id))
    conn.commit()
    
    # Reactivar el parqueadero
    try:
        update_parking(reservation['parking_id'], active=1, occupied_since=None)
    except Exception as e:
        print(f"Error reactivando parqueadero: {e}")

    try:
        # Determinar quién finalizó la reserva y crear notificaciones apropiadas
        if finished_by_id == reservation['driver_id']:
            # El conductor finalizó
            if owner_id:
                add_notification(
                    user_id=owner_id,
                    message=f"{driver_name} ha finalizado su reserva en {parking_name}.",
                    type='reservation_completed',
                    reservation_id=reservation_id,
                    owner_id=owner_id,
                    extra_data=f'{{"completed_by": "driver", "driver_id": {reservation["driver_id"]}}}'
                )
            # Notificación de confirmación para el conductor
            add_notification(
                user_id=reservation['driver_id'],
                message=f'Has finalizado tu reserva en {parking_name}.',
                type='reservation_completed',
                reservation_id=reservation_id,
                owner_id=owner_id,
                extra_data=f'{{"completed_by": "self", "parking_name": "{parking_name}"}}'
            )
        else:
            # El arrendador finalizó
            add_notification(
                user_id=reservation['driver_id'],
                message=f'Tu reserva en {parking_name} ha sido finalizada por el arrendador.',
                type='reservation_completed',
                reservation_id=reservation_id,
                owner_id=owner_id,
                extra_data=f'{{"completed_by": "owner", "parking_name": "{parking_name}"}}'
            )
            if owner_id:
                add_notification(
                    user_id=owner_id,
                    message=f'Has finalizado la reserva de {driver_name} en {parking_name}.',
                    type='reservation_completed',
                    reservation_id=reservation_id,
                    owner_id=owner_id,
                    extra_data=f'{{"completed_by": "self", "driver_id": {reservation["driver_id"]}}}'
                )
    except Exception as e:
        print(f"Error creando notificaciones de finalización: {e}")
    
    conn.close()
    return True

def mark_driver_arrived(reservation_id):
    """Marca una reserva como 'arrived' cuando el conductor llega al parqueadero y envía notificaciones."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Obtener la información de la reserva
    reservation = get_reservation(reservation_id)
    if not reservation or reservation['status'] != 'pending':
        conn.close()
        return False
        
    # Obtener información del conductor y del parqueadero
    cursor.execute('SELECT name FROM users WHERE id = ?', (reservation['driver_id'],))
    driver_row = cursor.fetchone()
    driver_name = driver_row[0] if driver_row else "El conductor"
    
    cursor.execute('SELECT owner_id, name FROM parkings WHERE id = ?', (reservation['parking_id'],))
    parking_row = cursor.fetchone()
    owner_id = parking_row[0] if parking_row else None
    parking_name = parking_row[1] if parking_row else "el parqueadero"
    
    # Actualizar el estado de la reserva
    cursor.execute('UPDATE reservations SET status = ? WHERE id = ?', ('arrived', reservation_id))
    conn.commit()

    try:
        # Notificación para el arrendador
        if owner_id:
            add_notification(
                user_id=owner_id,
                message=f"{driver_name} ha llegado a {parking_name}.",
                type='driver_arrived',
                reservation_id=reservation_id,
                owner_id=owner_id,
                extra_data=f'{{"driver_id": {reservation["driver_id"]}, "driver_name": "{driver_name}"}}'
            )
        
        # Notificación de confirmación para el conductor
        add_notification(
            user_id=reservation['driver_id'],
            message=f'Has llegado a {parking_name}.',
            type='arrived_confirmation',
            reservation_id=reservation_id,
            owner_id=owner_id,
            extra_data=f'{{"parking_name": "{parking_name}"}}'
        )
    except Exception as e:
        print(f"Error creando notificaciones de llegada: {e}")
    
    conn.close()
    return True
