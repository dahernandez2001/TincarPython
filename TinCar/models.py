import os
import sqlite3
import json

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
    if 'penalty_active' not in existing:
        try:
            cursor.execute('ALTER TABLE reservations ADD COLUMN penalty_active INTEGER DEFAULT 0')
        except Exception:
            pass
    if 'penalty_start' not in existing:
        try:
            cursor.execute('ALTER TABLE reservations ADD COLUMN penalty_start TIMESTAMP')
        except Exception:
            pass
    if 'penalty_amount' not in existing:
        try:
            cursor.execute('ALTER TABLE reservations ADD COLUMN penalty_amount INTEGER DEFAULT 0')
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
        # Notificación para el arrendador ÚNICAMENTE
        if owner_id:
            add_notification(
                user_id=owner_id,
                message=f"{driver_name} ha reservado {parking_name}. Llegará en aproximadamente {eta_minutes} minutos.",
                type='new_reservation',
                reservation_id=last_id,
                owner_id=owner_id,
                eta=eta_minutes,
                extra_data={'driver_id': driver_id, 'driver_name': driver_name, 'parking_name': parking_name}
            )

        # NO crear notificación para el conductor al momento de reservar
        # El conductor solo verá su reserva activa en la sección de "Mis Reservas"
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
        # Reservar el parking (lo bloqueamos para evitar doble reserva) pero no fijamos
        # `occupied_since` hasta que el conductor confirme llegada.
        try:
            update_parking(parking_id, active=0, occupied_since=None)
        except Exception:
            pass
    except Exception:
        pass
    
    conn.close()
    return out


def add_notification(user_id, message, type, reservation_id=None, owner_id=None, eta=None, extra_data=None):
    conn = get_connection()
    cursor = conn.cursor()
    # Convertir extra_data a JSON string si es un diccionario
    if extra_data and isinstance(extra_data, dict):
        extra_data = json.dumps(extra_data)
    cursor.execute('''
        INSERT INTO notifications (user_id, message, type, reservation_id, owner_id, eta, extra_data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, message, type, reservation_id, owner_id, eta, extra_data))
    conn.commit()
    conn.close()


def delete_notifications_for_reservation(reservation_id, types_to_remove=None, user_id=None):
    """Elimina notificaciones asociadas a una reserva.

    - reservation_id: id de la reserva cuyas notificaciones se eliminarán.
    - types_to_remove: lista opcional de tipos a eliminar; si es None se eliminan todas las notifs para esa reserva.
    - user_id: si se pasa, limitar la eliminación a ese usuario.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if types_to_remove and len(types_to_remove) > 0:
            # Construir placeholders para tipos
            placeholders = ','.join('?' for _ in types_to_remove)
            if user_id:
                sql = f"DELETE FROM notifications WHERE reservation_id = ? AND type IN ({placeholders}) AND user_id = ?"
                params = [reservation_id] + list(types_to_remove) + [user_id]
            else:
                sql = f"DELETE FROM notifications WHERE reservation_id = ? AND type IN ({placeholders})"
                params = [reservation_id] + list(types_to_remove)
        else:
            if user_id:
                sql = "DELETE FROM notifications WHERE reservation_id = ? AND user_id = ?"
                params = (reservation_id, user_id)
            else:
                sql = "DELETE FROM notifications WHERE reservation_id = ?"
                params = (reservation_id,)
        cursor.execute(sql, params)
        conn.commit()
    except Exception:
        # No fallar si algo va mal; el proceso principal debe continuar
        pass
    finally:
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
        cursor.execute('SELECT id, driver_id, parking_id, status, duration_minutes, eta_minutes, created_at, penalty_active, penalty_start, penalty_amount FROM reservations WHERE id = ?', (id,))
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
        # Si la consulta devolvió duration/eta/penalty
        if len(r) >= 10:
            out['duration_minutes'] = r[4]
            out['eta_minutes'] = r[5]
            out['created_at'] = r[6]
            out['penalty_active'] = r[7]
            out['penalty_start'] = r[8]
            out['penalty_amount'] = r[9]
        elif len(r) >= 6:
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
        # Antes de crear notificaciones nuevas, eliminar notificaciones previas de esta reserva
        try:
            delete_notifications_for_reservation(reservation_id)
        except Exception:
            pass
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
    """Marca una reserva como 'completed', calcula tiempo usado/importe, registra calificación opcional
    y envía notificaciones apropiadas.

    Asunciones razonables: si no existe una tarifa por minuto en la DB, usamos una tarifa por defecto
    de 100 unidades por minuto. La función acepta que el arrendador finalice la reserva y opcionalmente
    envíe una calificación (la calificación se debe haber registrado previamente usando add_review).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Obtener la información de la reserva
    reservation = get_reservation(reservation_id)
    # Permitir que el arrendador finalice una reserva incluso si aún está en 'pending'.
    # En condiciones normales el conductor sólo puede finalizar cuando está 'arrived' o 'active'.
    if not reservation:
        conn.close()
        return False
    if reservation['status'] not in ['arrived', 'active']:
        # Si quien finaliza NO es el conductor (p.ej. arrendador) y la reserva está en 'pending', permitirlo.
        if finished_by_id != reservation['driver_id'] and reservation['status'] == 'pending':
            # continuar: el arrendador está forzando la finalización de una reserva pendiente
            pass
        else:
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
    
    # Calcular tiempo usado y total a cobrar (si es posible)
    elapsed_minutes = None
    total_amount = None
    try:
        # Obtener occupied_since desde parkings
        cursor.execute('SELECT occupied_since FROM parkings WHERE id = ?', (reservation['parking_id'],))
        park_row = cursor.fetchone()
        occupied_since = park_row[0] if park_row else None
        if occupied_since:
            try:
                import datetime
                occ = datetime.datetime.fromisoformat(occupied_since)
                now = datetime.datetime.utcnow()
                secs = (now - occ).total_seconds()
                elapsed_minutes = int((secs + 59) // 60) if secs > 0 else 0
            except Exception:
                elapsed_minutes = None
    except Exception:
        elapsed_minutes = None

    # tarifa por minuto por defecto (asunción): 100
    rate_per_minute = 100
    if elapsed_minutes is None:
        # fallback a la duración planificada
        elapsed_minutes = reservation.get('duration_minutes', None) or 0
    try:
        total_amount = int(elapsed_minutes) * int(rate_per_minute)
    except Exception:
        total_amount = None

    # Agregar penalización si existe
    penalty_amount = reservation.get('penalty_amount', 0) or 0
    if total_amount is not None:
        total_amount += penalty_amount

    # Actualizar el estado de la reserva
    cursor.execute('UPDATE reservations SET status = ? WHERE id = ?', ('completed', reservation_id))
    conn.commit()

    # Reactivar el parqueadero
    try:
        update_parking(reservation['parking_id'], active=1, occupied_since=None)
    except Exception as e:
        print(f"Error reactivando parqueadero: {e}")

    try:
        # Antes de crear notificaciones nuevas, limpiar notificaciones previas de esta reserva
        try:
            delete_notifications_for_reservation(reservation_id)
        except Exception:
            pass
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
                    extra_data=f'{{"completed_by": "driver", "driver_id": {reservation["driver_id"]}, "elapsed_minutes": {elapsed_minutes}, "amount": {total_amount}}}'
                )
            # Notificación de confirmación para el conductor
            add_notification(
                user_id=reservation['driver_id'],
                message=f'Has finalizado tu reserva en {parking_name}.',
                type='reservation_completed',
                reservation_id=reservation_id,
                owner_id=owner_id,
                extra_data=f'{{"completed_by": "self", "parking_name": "{parking_name}", "elapsed_minutes": {elapsed_minutes}, "amount": {total_amount}}}'
            )
        else:
            # El arrendador finalizó
            add_notification(
                user_id=reservation['driver_id'],
                message=f'Tu reserva en {parking_name} ha sido finalizada por el arrendador.',
                type='reservation_completed',
                reservation_id=reservation_id,
                owner_id=owner_id,
                extra_data=f'{{"completed_by": "owner", "parking_name": "{parking_name}", "elapsed_minutes": {elapsed_minutes}, "amount": {total_amount}}}'
            )
            if owner_id:
                add_notification(
                    user_id=owner_id,
                    message=f'Has finalizado la reserva de {driver_name} en {parking_name}.',
                    type='reservation_completed',
                    reservation_id=reservation_id,
                    owner_id=owner_id,
                    extra_data=f'{{"completed_by": "self", "driver_id": {reservation["driver_id"]}, "elapsed_minutes": {elapsed_minutes}, "amount": {total_amount}}}'
                )
        # Si quien finalizó es el arrendador y se envió una calificación por POST, el controlador del endpoint
        # debe haber llamado a add_review separadamente; aquí no lo forzamos para no mezclar responsabilidades.
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
    
    # Actualizar el estado de la reserva a 'active' (conductor ocupando el sitio)
    cursor.execute('UPDATE reservations SET status = ? WHERE id = ?', ('active', reservation_id))
    conn.commit()

    try:
        # Limpiar notificaciones de INTERFAZ 1 al pasar a INTERFAZ 2
        try:
            # Eliminar notificaciones de trayecto para ambos usuarios
            delete_notifications_for_reservation(reservation_id, types_to_remove=['active_reservation', 'new_reservation', 'eta_expired', 'reservation_expired'])
        except Exception:
            pass
        # Registrar occupied_since en el parking (timer inicia ahora)
        import datetime
        # Guardar con zona UTC explícita para que JS y Python parseen correctamente
        occupied_ts = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()
        try:
            update_parking(reservation['parking_id'], occupied_since=occupied_ts, active=0)
        except Exception:
            pass

        # Notificación para el arrendador ÚNICAMENTE: conductor llegó al garaje
        if owner_id:
            add_notification(
                user_id=owner_id,
                message=f"Hay un vehículo guardado en {parking_name}.",
                type='driver_arrived',
                reservation_id=reservation_id,
                owner_id=owner_id,
                eta=None,
                extra_data={
                    'driver_id': reservation["driver_id"], 
                    'driver_name': driver_name, 
                    'duration_minutes': reservation.get("duration_minutes", 10), 
                    'occupied_since': occupied_ts
                }
            )

        # Notificación para el conductor ÚNICAMENTE: vehículo guardado
        add_notification(
            user_id=reservation['driver_id'],
            message=f'Tu vehículo está guardado en {parking_name}.',
            type='vehicle_parked',
            reservation_id=reservation_id,
            owner_id=owner_id,
            extra_data={
                'parking_name': parking_name, 
                'duration_minutes': reservation.get("duration_minutes", 10), 
                'occupied_since': occupied_ts
            }
        )
    except Exception as e:
        print(f"Error creando notificaciones de llegada: {e}")
    
    conn.close()
    return True


def notify_expired_reservations():
    """Busca reservas con status 'active' cuyo tiempo desde occupied_since
    excede duration_minutes y envía notificaciones (una sola vez) tanto al
    arrendador como al conductor indicando que el tiempo finalizó y que el
    arrendador puede finalizar el servicio.
    
    También busca reservas con status 'pending' cuyo tiempo de ETA ha expirado
    y notifica al conductor que no ha llegado al parqueadero.

    Esta función está pensada para ejecutarse periódicamente desde el servidor
    (ej. hilo background) o invocarse desde un endpoint de verificación.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Verificar reservas pendientes cuyo ETA ha expirado
        import datetime
        cursor.execute('''
            SELECT r.id, r.driver_id, r.parking_id, r.eta_minutes, r.created_at,
                   p.name as parking_name, p.owner_id
            FROM reservations r
            LEFT JOIN parkings p ON r.parking_id = p.id
            WHERE r.status = 'pending'
        ''')
        pending_rows = cursor.fetchall()
        
        for r in pending_rows:
            try:
                reservation_id = r['id'] if 'id' in r.keys() else r[0]
                driver_id = r['driver_id'] if 'driver_id' in r.keys() else r[1]
                parking_id = r['parking_id'] if 'parking_id' in r.keys() else r[2]
                eta_minutes = r['eta_minutes'] if 'eta_minutes' in r.keys() and r['eta_minutes'] is not None else (r[3] if len(r) > 3 else None)
                created_at = r['created_at'] if 'created_at' in r.keys() else (r[4] if len(r) > 4 else None)
                parking_name = r['parking_name'] if 'parking_name' in r.keys() else (r[5] if len(r) > 5 else 'el parqueadero')
                owner_id = r['owner_id'] if 'owner_id' in r.keys() else (r[6] if len(r) > 6 else None)
                
                if not created_at or eta_minutes is None:
                    continue
                
                try:
                    created_dt = datetime.datetime.fromisoformat(created_at)
                except Exception:
                    continue
                
                now = datetime.datetime.utcnow()
                elapsed_secs = (now - created_dt).total_seconds()
                eta_secs = int(eta_minutes) * 60
                
                # Si el tiempo de ETA ha expirado
                if elapsed_secs >= eta_secs:
                    # Evitar notificar repetidamente
                    cursor.execute('SELECT COUNT(*) FROM notifications WHERE reservation_id = ? AND type = ?', (reservation_id, 'eta_expired'))
                    exists = cursor.fetchone()[0]
                    if exists and exists > 0:
                        continue
                    
                    # Obtener nombre del conductor para la notificación del arrendador
                    cursor.execute('SELECT name FROM users WHERE id = ?', (driver_id,))
                    driver_row = cursor.fetchone()
                    driver_name = driver_row[0] if driver_row else 'El conductor'
                    
                    # Notificación para el conductor (no llegó a tiempo)
                    add_notification(
                        user_id=driver_id,
                        message=f"No has llegado al parqueadero {parking_name}",
                        type='eta_expired',
                        reservation_id=reservation_id,
                        owner_id=owner_id,
                        extra_data={'parking_name': parking_name, 'parking_id': parking_id, 'eta_minutes': eta_minutes}
                    )
                    
                    # Notificación para el arrendador (conductor no llegó a tiempo)
                    if owner_id:
                        add_notification(
                            user_id=owner_id,
                            message=f"El conductor no llegó al garaje en el tiempo estimulado.",
                            type='reservation_expired',
                            reservation_id=reservation_id,
                            owner_id=owner_id,
                            extra_data={'driver_id': driver_id, 'driver_name': driver_name, 'parking_name': parking_name}
                        )
            except Exception:
                continue
        
        # 2. Seleccionar reservas activas con occupied_since
        cursor.execute('''
            SELECT r.id, r.driver_id, r.parking_id, r.duration_minutes, u.name as driver_name,
                   p.owner_id, p.name as parking_name, p.occupied_since
            FROM reservations r
            LEFT JOIN users u ON r.driver_id = u.id
            LEFT JOIN parkings p ON r.parking_id = p.id
            WHERE r.status = 'active' AND p.occupied_since IS NOT NULL
        ''')
        rows = cursor.fetchall()
        import datetime
        for r in rows:
            try:
                occ = r['occupied_since'] if 'occupied_since' in r.keys() else (r[7] if len(r) > 7 else None)
                if not occ:
                    continue
                try:
                    occ_dt = datetime.datetime.fromisoformat(occ)
                except Exception:
                    # Skip if date unparsable
                    continue
                now = datetime.datetime.utcnow()
                elapsed_secs = (now - occ_dt).total_seconds()
                elapsed_min = int((elapsed_secs + 59) // 60) if elapsed_secs > 0 else 0
                desired = r['duration_minutes'] if 'duration_minutes' in r.keys() and r['duration_minutes'] is not None else (r[3] if len(r) > 3 else None)
                if desired is None:
                    continue
                if elapsed_min >= int(desired):
                    reservation_id = r['id'] if 'id' in r.keys() else r[0]
                    owner_id = r['owner_id'] if 'owner_id' in r.keys() else r[5]
                    driver_id = r['driver_id'] if 'driver_id' in r.keys() else r[1]
                    parking_name = r['parking_name'] if 'parking_name' in r.keys() else (r[6] if len(r) > 6 else 'el parqueadero')
                    driver_name = r['driver_name'] if 'driver_name' in r.keys() else (r[4] if len(r) > 4 else 'El conductor')
                    # Evitar notificar repetidamente: buscar notificación previa de tipo 'reservation_expired'
                    cursor.execute('SELECT COUNT(*) FROM notifications WHERE reservation_id = ? AND type = ?', (reservation_id, 'reservation_expired'))
                    exists = cursor.fetchone()[0]
                    if exists and exists > 0:
                        continue
                    # Limpiar notificaciones previas que puedan confundir (p.ej. parking_occupied)
                    try:
                        delete_notifications_for_reservation(reservation_id, types_to_remove=['parking_occupied'])
                    except Exception:
                        pass
                    
                    # NO enviar más notificaciones de "reservation_expired" 
                    # El arrendador ya tiene la notificación de "driver_arrived" que le muestra el tiempo restante
                    # El conductor ya tiene la notificación de "vehicle_parked" con el contador
                    # Cuando el arrendador haga click en "Confirmar", ahí se abre el modal de finalización
            except Exception:
                continue
        
        # 3. Calcular penalizaciones para reservas con penalty_active=1
        # La multa solo comienza DESPUÉS de que expire duration_minutes
        cursor.execute('''
            SELECT r.id, r.duration_minutes, p.occupied_since
            FROM reservations r
            LEFT JOIN parkings p ON r.parking_id = p.id
            WHERE r.penalty_active = 1 AND r.status = 'active' AND p.occupied_since IS NOT NULL
        ''')
        penalty_rows = cursor.fetchall()
        
        for r in penalty_rows:
            try:
                reservation_id = r['id'] if 'id' in r.keys() else r[0]
                duration_minutes = r['duration_minutes'] if 'duration_minutes' in r.keys() else (r[1] if len(r) > 1 else 0)
                occupied_since = r['occupied_since'] if 'occupied_since' in r.keys() else (r[2] if len(r) > 2 else None)
                
                if not occupied_since or not duration_minutes:
                    continue
                
                try:
                    occupied_dt = datetime.datetime.fromisoformat(occupied_since)
                except Exception:
                    continue
                
                now = datetime.datetime.utcnow()
                elapsed_secs = (now - occupied_dt).total_seconds()
                elapsed_minutes = int(elapsed_secs // 60)
                
                # Calcular cuántos minutos han pasado DESPUÉS del tiempo permitido
                overtime_minutes = elapsed_minutes - duration_minutes
                
                # Solo cobrar multa si ya se excedió el tiempo
                if overtime_minutes > 0:
                    # Calcular penalización: $500 por cada 5 minutos completos de EXCESO
                    penalty_periods = overtime_minutes // 5
                    new_penalty = penalty_periods * 500
                    
                    # Actualizar penalty_amount
                    cursor.execute('''
                        UPDATE reservations
                        SET penalty_amount = ?
                        WHERE id = ?
                    ''', (new_penalty, reservation_id))
                    conn.commit()
                else:
                    # Si aún no se ha excedido, la multa es 0
                    cursor.execute('''
                        UPDATE reservations
                        SET penalty_amount = 0
                        WHERE id = ?
                    ''', (reservation_id,))
                    conn.commit()
            except Exception:
                continue
    except Exception:
        pass
    finally:
        conn.close()
