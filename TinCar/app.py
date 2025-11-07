import os
import sqlite3
from time import time
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO
from routes.auth import auth
# Usar las funciones centralizadas de acceso a DB desde models
from models import (
    get_connection,
    create_users_table,
    add_user,
    get_user_by_email,
    create_parkings_table,
    add_parking,
    get_parkings_by_owner,
    get_parking,
    update_parking,
    delete_parking,
    create_reservations_table,
    create_reviews_table,
    get_active_parkings,
    get_reservations_count_by_driver,
    get_rating_sum_for_driver,
    add_reservation,
    add_notification,
    get_notifications_by_user,
    mark_driver_arrived,
    finish_reservation,
    get_reservation_by_driver_and_parking,
    cancel_reservation,
    get_reservation,
    add_review,
    notify_expired_reservations,
)
from utils.geocode import geocode_location
import requests
import threading
import time as _time

# Configuración rutas absolutas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, 'static'),
    template_folder=os.path.join(BASE_DIR, 'templates')
)

app.secret_key = 'clave-secreta'

# Inicializar SocketIO
socketio = SocketIO(app)

# Registrar blueprints
app.register_blueprint(auth)
DB_NAME = os.path.join(BASE_DIR, 'database', 'tincar.db')

# Alias a la conexión centralizada en models.py para unificar el acceso a la DB
get_db_connection = get_connection

# Las funciones de usuarios (create, add, get) vienen de models.py: create_users_table, add_user, get_user_by_email


# === Rutas principales ===
@app.route('/')
def home():
    # Si el usuario ya está logueado, redirigir al dashboard correspondiente
    if 'user_id' in session:
        role = session.get('role')
        if role == 'conductor':
            return redirect(url_for('driver_index'))
        elif role == 'arrendador':
            return redirect(url_for('landlord_index'))
    
    return render_template('index.html')


@app.route('/servicios')
def servicios():
    return render_template('servicios.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')
        role = request.form.get('role')  # conductor o arrendador

        if not all([name, email, password, phone, role]):
            flash('Por favor completa todos los campos.', 'error')
            return redirect(url_for('register'))

        if get_user_by_email(email):
            flash('El correo ya está registrado', 'error')
            return redirect(url_for('register'))

        # Guardar el nuevo usuario
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('INSERT INTO users (name, email, password, phone, role) VALUES (?, ?, ?, ?, ?)',
                  (name, email, password, phone, role))
        conn.commit()
        conn.close()

        flash('Cuenta creada exitosamente, ahora inicia sesión.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = get_user_by_email(email)

        if user and user['password'] == password:
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['email'] = user['email']
            session['role'] = user['role']
            print("ROL LOGUEADO:", user['role'])  # debug
            return redirect(url_for('dashboard'))
        else:
            flash('Correo o contraseña incorrectos', 'error')

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, role FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()

    # Si el usuario es arrendador, obtener sus parqueaderos desde la BD
    if user and user[2] == 'arrendador':
        try:
            parkings = get_parkings_by_owner(user[0])
        except Exception:
            # fallback: lista vacía
            parkings = []
        # Normalizar para la plantilla: incluir estado/price/time de ejemplo si faltan
        for p in parkings:
            p.setdefault('status', 'Libre')
            p.setdefault('price', '0')
            p.setdefault('time', '00:00:00')
        return render_template('dashboard_landlord.html', nombre=user[1], role=user[2], parkings=parkings)

    # Por defecto, renderizar dashboard genérico
    if user:
        return render_template('dashboard.html', nombre=user[1], role=user[2])
    # Si por alguna razón no encontramos usuario, redirigir al login
    return redirect(url_for('auth.login'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# === Ruta para conductor ===
@app.route('/driver')
def driver_index():
    # Verificar sesión
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    # Nombre de usuario (compatibilidad con distintos nombres de clave)
    nombre = session.get('user_name') or session.get('name') or '(usuario)'
    return render_template('index_driver.html', nombre=nombre)


@app.route('/driver/profile')
def driver_profile():
    """Página de perfil completo del conductor"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    from models import get_driver_profile, check_license_validity, get_driver_age
    
    user_id = session['user_id']
    profile = get_driver_profile(user_id)
    
    if not profile:
        flash('No se pudo cargar el perfil', 'error')
        return redirect(url_for('driver_index'))
    
    # Agregar datos calculados
    profile['age'] = get_driver_age(user_id)
    profile['license_validity'] = check_license_validity(user_id)
    
    return render_template('driver_profile_new.html', profile=profile)


@app.route('/parkings/create', methods=['POST'])
def create_parking():
    if 'user_id' not in session:
        return {'error': 'not authenticated'}, 401
    owner_id = session['user_id']
    form = request.form
    name = form.get('name') or form.get('garage_name')
    # Validación mínima
    if not name or not name.strip():
        return jsonify({'success': False, 'error': 'El nombre del parqueadero es obligatorio.'}), 400
    phone = form.get('phone')
    email = form.get('email')
    address = form.get('address')
    department = form.get('department')
    city = form.get('city')
    housing_type = form.get('housing_type')
    size = form.get('size')
    features = form.get('features')
    # Handle optional image upload
    image_path = None
    if 'image' in request.files:
        img = request.files.get('image')
        if img and img.filename:
            uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
            os.makedirs(uploads_dir, exist_ok=True)
            filename = secure_filename(img.filename)
            unique_name = f"{int(time())}_{filename}"
            save_path = os.path.join(uploads_dir, unique_name)
            img.save(save_path)
            # path relative to static for serving
            image_path = f"/static/uploads/{unique_name}"

    try:
        # support optional latitude/longitude in the creation form
        latitude_raw = form.get('latitude') or None
        longitude_raw = form.get('longitude') or None
        try:
            latitude = float(latitude_raw) if latitude_raw not in (None, '', 'None') else None
        except Exception:
            latitude = None
        try:
            longitude = float(longitude_raw) if longitude_raw not in (None, '', 'None') else None
        except Exception:
            longitude = None
        # Si no vienen coordenadas, intentar geocodificar usando departamento/ciudad/dirección
        if (latitude is None or longitude is None) and (department or city or address):
            # country_hint es opcional; ajustar según el país objetivo si se desea
            g_lat, g_lon = geocode_location(department=department, city=city, address=address, country_hint=None)
            if g_lat is not None and g_lon is not None:
                # Sólo rellenar los que falten
                if latitude is None:
                    latitude = g_lat
                if longitude is None:
                    longitude = g_lon
        # use keyword args to avoid positional mismatch after adding lat/lng
        parking = add_parking(owner_id=owner_id, name=name, phone=phone, email=email, address=address,
                              department=department, city=city, housing_type=housing_type, size=size,
                              features=features, image_path=image_path, latitude=latitude, longitude=longitude, active=1)
        if not parking:
            return jsonify({'success': False, 'error': 'No se pudo crear el parqueadero'}), 500
        # obtener registro completo (incluye latitude/longitude)
        try:
            full = get_parking(parking['id'])
        except Exception:
            full = None
        resp = {'success': True, 'parking': full or parking}
        # indicar si la geocodificación falló y por eso faltan coordenadas
        if not full or full.get('latitude') is None or full.get('longitude') is None:
            resp['geocode_failed'] = True
            resp['message'] = 'No se pudieron obtener coordenadas desde la dirección; por favor añade latitud/longitud manualmente si es necesario.'
        return jsonify(resp)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/parkings/<int:parking_id>/active', methods=['POST'])
def set_parking_active(parking_id):
    """Establece el campo active para un parking (payload JSON: { active: true/false })."""
    if 'user_id' not in session:
        return {'error': 'not authenticated'}, 401
    data = request.get_json(silent=True) or {}
    # allow form-encoded too
    if not data and request.form.get('active') is not None:
        val = request.form.get('active')
        data['active'] = val.lower() in ('1','true','yes','on')

    if 'active' not in data:
        return {'error': 'missing active'}, 400
    try:
        active_value = 1 if bool(data['active']) else 0
        conn = get_connection()
        cur = conn.cursor()
        # Ensure owner owns this parking
        cur.execute('SELECT owner_id FROM parkings WHERE id = ?', (parking_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return {'error': 'not found'}, 404
        if row[0] != session['user_id']:
            conn.close()
            return {'error': 'forbidden'}, 403
        cur.execute('UPDATE parkings SET active = ? WHERE id = ?', (active_value, parking_id))
        conn.commit()
        # fetch updated parking info to return
        cur.execute('SELECT id, name, address, latitude, longitude FROM parkings WHERE id = ?', (parking_id,))
        parking_info = cur.fetchone()
        conn.close()
        if not parking_info:
            return {'error': 'not found'}, 404
        return {
            'success': True,
            'id': parking_info[0],
            'name': parking_info[1],
            'address': parking_info[2],
            'latitude': parking_info[3],
            'longitude': parking_info[4],
            'active': bool(active_value)
        }
    except Exception as e:
        return {'error': str(e)}, 500


@app.route('/parkings/<int:parking_id>', methods=['GET'])
def parking_detail(parking_id):
    if 'user_id' not in session:
        return jsonify({'error':'not authenticated'}), 401
    try:
        p = get_parking(parking_id)
        if not p:
            return jsonify({'error':'not found'}), 404
        # Only allow owner to view details
        if p['owner_id'] != session['user_id']:
            return jsonify({'error':'forbidden'}), 403
        return jsonify({'success': True, 'parking': p})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/parkings/<int:parking_id>/update', methods=['POST'])
def parking_update(parking_id):
    if 'user_id' not in session:
        return jsonify({'error':'not authenticated'}), 401
    # collect fields
    form = request.form
    data = {}
    for key in ['name','phone','email','address','department','city','housing_type','size','features']:
        if key in form:
            data[key] = form.get(key)
    # permitir actualizar coordenadas desde el modal de edición
    for key in ['latitude','longitude']:
        if key in form:
            # intentar parsear a float si existe
            raw = form.get(key)
            try:
                data[key] = float(raw) if raw not in (None, '', 'None') else None
            except ValueError:
                data[key] = None

    # Actualizar en la base de datos
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Ensure owner owns this parking
        cur.execute('SELECT owner_id FROM parkings WHERE id = ?', (parking_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return {'error': 'not found'}, 404
        if row[0] != session['user_id']:
            conn.close()
            return {'error': 'forbidden'}, 403
        # Actualizar solo los campos que fueron enviados
        set_clause = ', '.join(f"{k} = ?" for k in data.keys())
        cur.execute(f'UPDATE parkings SET {set_clause} WHERE id = ?', (*data.values(), parking_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, phone, role FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    if not user:
        return redirect(url_for('auth.logout'))  # Forzar logout si no se encuentra el usuario
    return render_template('profile.html', user=user)


@app.route('/profile/update', methods=['POST'])
def profile_update():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    data = request.form
    user_id = session['user_id']
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')

    # Validar datos mínimos
    if not all([name, email, phone]):
        return jsonify({'success': False, 'error': 'Por favor completa todos los campos.'}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()
        # Actualizar usuario
        cur.execute('UPDATE users SET name = ?, email = ?, phone = ? WHERE id = ?', (name, email, phone, user_id))
        conn.commit()
        conn.close()
        # Actualizar datos en la sesión
        session['name'] = name
        session['email'] = email
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/reservations')
def reservations():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    conn = get_connection()
    cursor = conn.cursor()
    # Obtener reservas del conductor
    cursor.execute('''
        SELECT r.id, p.name, r.start_time, r.end_time, r.status
        FROM reservations r
        JOIN parkings p ON r.parking_id = p.id
        WHERE r.driver_id = ?
    ''', (session['user_id'],))
    reservations = cursor.fetchall()
    conn.close()
    return render_template('reservations.html', reservations=reservations)


@app.route('/reservations/create', methods=['POST'])
def create_reservation():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    data = request.get_json(silent=True) or {}
    # Validar datos
    required_fields = ['parking_id', 'start_time', 'end_time']
    if not all(field in data for field in required_fields):
        return jsonify({'success': False, 'error': 'Faltan datos requeridos.'}), 400

    try:
        # Crear reserva
        reservation_id = add_reservation(driver_id=session['user_id'], parking_id=data['parking_id'],
                                        start_time=data['start_time'], end_time=data['end_time'])
        if not reservation_id:
            return jsonify({'success': False, 'error': 'No se pudo crear la reserva.'}), 500
        return jsonify({'success': True, 'reservation_id': reservation_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/reservations/<int:reservation_id>/cancel', methods=['POST'])
def cancel_reservation_route(reservation_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    try:
        result = cancel_reservation(reservation_id, session['user_id'])
        if not result:
            return jsonify({'success': False, 'error': 'No se pudo cancelar la reserva.'}), 500
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/parkings/active', methods=['GET'])
def api_get_active_parkings():
    """API pública: lista de parqueaderos activos."""
    try:
        parkings = get_active_parkings()
        # Soportar filtro por bbox (minLat,minLng,maxLat,maxLng)
        bbox = request.args.get('bbox')
        if bbox:
            try:
                parts = [float(x) for x in bbox.split(',')]
                if len(parts) == 4:
                    minLat, minLng, maxLat, maxLng = parts
                    def in_bbox(p):
                        try:
                            lat = float(p.get('latitude'))
                            lng = float(p.get('longitude'))
                        except Exception:
                            return False
                        return lat >= minLat and lat <= maxLat and lng >= minLng and lng <= maxLng
                    parkings = [p for p in parkings if in_bbox(p)]
            except Exception:
                # ignorar bbox inválido y devolver todos
                pass

        result = [{
            'id': p['id'],
            'name': p['name'],
            'address': p.get('address'),
            'latitude': p.get('latitude'),
            'longitude': p.get('longitude'),
            'owner_id': p.get('owner_id'),
            'status': 'Libre'
        } for p in parkings]
        return jsonify({'success': True, 'parkings': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/parkings/<int:parking_id>/delete', methods=['POST'])
def api_delete_parking(parking_id):
    """API para eliminar un parqueadero."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
    # Verificar que el usuario sea el dueño del parqueadero
    parking = get_parking(parking_id)
    if not parking:
        return jsonify({'success': False, 'error': 'Parqueadero no encontrado'}), 404
    if parking['owner_id'] != session['user_id']:
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
    try:
        delete_parking(parking_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/parkings/<int:parking_id>', methods=['GET'])
def api_get_parking(parking_id):
    """API pública: detalles de un parqueadero."""
            
    # Método GET
    try:
        p = get_parking(parking_id)
        if not p:
            return jsonify({'success': False, 'error': 'Parqueadero no encontrado'}), 404
        return jsonify({
            'id': p['id'],
            'name': p['name'],
            'address': p['address'],
            'latitude': p['latitude'],
            'longitude': p['longitude'],
            'owner_id': p['owner_id'],
            'status': 'Libre'  # Asignar estado por defecto
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reservations', methods=['POST'])
def api_create_reservation():
    """API del conductor: crear una nueva reserva."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    
    data = request.get_json(silent=True) or {}
    parking_id = data.get('parking_id')
    duration_minutes = data.get('duration_minutes', 10)
    eta_minutes = data.get('eta_minutes', 0)
    
    if not parking_id:
        return jsonify({'success': False, 'error': 'Se requiere parking_id'}), 400
    
    try:
        # Verificar si ya existe una reserva activa para este parqueadero
        existing = get_reservation_by_driver_and_parking(session['user_id'], parking_id)
        if existing and existing.get('status') not in ['cancelled', 'completed']:
            # Forzar notificación si no existe
            from models import add_notification, get_notifications_by_user
            notifications = get_notifications_by_user(session['user_id'])
            notif_exists = any(n['type'] == 'active_reservation' and n['reservation_id'] == existing['id'] for n in notifications)
            if not notif_exists:
                # Obtener nombre del garaje
                from models import get_parking
                parking = get_parking(parking_id)
                parking_name = parking['name'] if parking and 'name' in parking else 'el garaje'
                add_notification(
                    user_id=session['user_id'],
                    message=f'Tienes una reserva activa en {parking_name}.',
                    type='active_reservation',
                    reservation_id=existing['id'],
                    owner_id=parking['owner_id'] if parking and 'owner_id' in parking else None,
                    eta=existing.get('eta_minutes', 0),
                    extra_data=f'{{"parking_name": "{parking_name}", "duration": {existing.get("duration_minutes", 10)}}}'
                )
            return jsonify({'success': False, 'error': 'Ya tienes una reserva activa para este parqueadero', 'reservation': existing}), 400
        # Crear la reserva
        reservation = add_reservation(
            driver_id=session['user_id'],
            parking_id=parking_id,
            duration_minutes=duration_minutes,
            eta_minutes=eta_minutes
        )
        if not reservation:
            return jsonify({'success': False, 'error': 'No se pudo crear la reserva'}), 500
        return jsonify({
            'success': True,
            'reservation': reservation
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reservations/driver', methods=['GET'])
def api_get_driver_reservations():
    """API del conductor: obtener reservas del conductor."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Obtener reservas del conductor
        cursor.execute('''
            SELECT r.id, p.name, r.start_time, r.end_time, r.status
            FROM reservations r
            JOIN parkings p ON r.parking_id = p.id
            WHERE r.driver_id = ?
        ''', (session['user_id'],))
        reservations = cursor.fetchall()
        conn.close()
        return jsonify([{
            'id': r['id'],
            'parking_name': r['name'],
            'start_time': r['start_time'],
            'end_time': r['end_time'],
            'status': r['status']
        } for r in reservations])
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reservations/active/driver', methods=['GET'])
def api_get_active_reservations_driver():
    """Devuelve las reservas activas (pending/arrived/active) del conductor logueado."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
         SELECT r.id, r.status, r.duration_minutes, r.eta_minutes, r.created_at, r.driver_id,
             u.name as driver_name, r.parking_id, p.name as parking_name, p.address, p.occupied_since,
             owner.name as owner_name
            FROM reservations r
            LEFT JOIN users u ON r.driver_id = u.id
            LEFT JOIN parkings p ON r.parking_id = p.id
            LEFT JOIN users owner ON p.owner_id = owner.id
            WHERE r.driver_id = ? AND r.status IN ('pending','arrived','active')
            ORDER BY r.created_at DESC
        ''', (session['user_id'],))
        rows = cursor.fetchall()
        conn.close()
        out = []
        for r in rows:
            try:
                # Get owner_name safely
                try:
                    owner_name = r['owner_name'] if r['owner_name'] else 'un arrendador'
                except (KeyError, IndexError):
                    owner_name = 'un arrendador'
                
                # Get optional fields safely
                try:
                    occupied_since = r['occupied_since']
                except (KeyError, IndexError):
                    occupied_since = None
                
                try:
                    duration_minutes = r['duration_minutes']
                except (KeyError, IndexError):
                    duration_minutes = None
                
                try:
                    eta_minutes = r['eta_minutes']
                except (KeyError, IndexError):
                    eta_minutes = None
                
                out.append({
                    'id': r['id'],
                    'status': r['status'],
                    'occupied_since': occupied_since,
                    'duration_minutes': duration_minutes,
                    'eta': eta_minutes,
                    'eta_minutes': eta_minutes,
                    'created_at': r['created_at'],
                    'driver_id': r['driver_id'],
                    'driver_name': r['driver_name'],
                    'parking_id': r['parking_id'],
                    'parking_name': r['parking_name'],
                    'address': r['address'],
                    'owner_name': owner_name
                })
            except Exception as e:
                print(f"Error parsing row: {e}, row: {r}")
                continue
        return jsonify({'success': True, 'reservations': out})
    except Exception as e:
        import traceback
        print(f"Error in active/driver: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reservations/active/owner', methods=['GET'])
def api_get_active_reservations_owner():
    """Devuelve las reservas activas para los parqueaderos del arrendador logueado."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
         SELECT r.id, r.status, r.duration_minutes, r.eta_minutes, r.created_at, r.driver_id,
             u.name as driver_name, r.parking_id, p.name as parking_name, p.address, p.occupied_since
            FROM reservations r
            LEFT JOIN users u ON r.driver_id = u.id
            LEFT JOIN parkings p ON r.parking_id = p.id
            WHERE p.owner_id = ? AND r.status IN ('pending','arrived','active')
            ORDER BY r.created_at DESC
        ''', (session['user_id'],))
        rows = cursor.fetchall()
        conn.close()
        out = []
        for r in rows:
            try:
                # calcular si la reserva ya expiró (occupied_since + duration <= now)
                expired = False
                try:
                    if r.get('occupied_since') and r.get('duration_minutes'):
                        import datetime
                        occ = datetime.datetime.fromisoformat(r['occupied_since'])
                        now = datetime.datetime.utcnow()
                        secs = (now - occ).total_seconds()
                        elapsed_min = int((secs + 59) // 60) if secs > 0 else 0
                        expired = elapsed_min >= int(r.get('duration_minutes', 0))
                except Exception:
                    expired = False

                out.append({
                    'id': r['id'],
                    'status': r['status'],
                    'duration_minutes': r.get('duration_minutes', None) if hasattr(r, 'keys') else (r[2] if len(r) > 2 else None),
                    'eta': r.get('eta_minutes', None) if hasattr(r, 'keys') else (r[3] if len(r) > 3 else None),
                    'created_at': r['created_at'] if 'created_at' in r.keys() else (r[4] if len(r) > 4 else None),
                    'driver_id': r['driver_id'],
                    'driver_name': r['driver_name'],
                    'parking_id': r['parking_id'],
                    'parking_name': r['parking_name'],
                    'address': r['address'],
                    'occupied_since': r['occupied_since'] if 'occupied_since' in r.keys() else None,
                    'expired': expired
                })
            except Exception:
                out.append({
                    'id': r[0], 'status': r[1], 'duration_minutes': r[2] if len(r) > 2 else None,
                    'eta': r[3] if len(r) > 3 else None, 'created_at': r[4] if len(r) > 4 else None,
                    'driver_id': r[5] if len(r) > 5 else None, 'driver_name': r[6] if len(r) > 6 else None,
                    'parking_id': r[7] if len(r) > 7 else None, 'parking_name': r[8] if len(r) > 8 else None,
                    'address': r[9] if len(r) > 9 else None
                })
        return jsonify({'success': True, 'reservations': out})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users/profile', methods=['GET'])
def api_get_user_profile():
    """API del usuario: obtener información del perfil."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, phone, role FROM users WHERE id = ?", (session['user_id'],))
        user = cursor.fetchone()
        conn.close()
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        return jsonify({
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
            'phone': user['phone'],
            'role': user['role']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users/profile/update', methods=['POST'])
def api_update_user_profile():
    """API del usuario: actualizar información del perfil."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    data = request.get_json(silent=True) or {}
    user_id = session['user_id']
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')

    # Validar datos mínimos
    if not all([name, email, phone]):
        return jsonify({'success': False, 'error': 'Por favor completa todos los campos.'}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()
        # Actualizar usuario
        cur.execute('UPDATE users SET name = ?, email = ?, phone = ? WHERE id = ?', (name, email, phone, user_id))
        conn.commit()
        conn.close()
        # Actualizar datos en la sesión
        session['name'] = name
        session['email'] = email
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/parkings/<int:parking_id>/reserve', methods=['POST'])
def api_reserve_parking(parking_id):
    """API pública: reservar un parqueadero."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    data = request.get_json(silent=True) or {}
    # Validar datos
    required_fields = ['start_time', 'end_time']
    if not all(field in data for field in required_fields):
        return jsonify({'success': False, 'error': 'Faltan datos requeridos.'}), 400

    try:
        # Crear reserva
        reservation_id = add_reservation(driver_id=session['user_id'], parking_id=parking_id,
                                        start_time=data['start_time'], end_time=data['end_time'])
        if not reservation_id:
            return jsonify({'success': False, 'error': 'No se pudo crear la reserva.'}), 500
        return jsonify({'success': True, 'reservation_id': reservation_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reservations/<int:reservation_id>/finish', methods=['POST'])
def api_finish_reservation(reservation_id):
    """API para finalizar una reserva."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
        
    try:
        # Obtener la reserva para verificar permisos
        reservation = get_reservation(reservation_id)
        if not reservation:
            return jsonify({'success': False, 'error': 'Reserva no encontrada'}), 404
        
        # Verificar que el usuario sea el conductor o el dueño del parqueadero
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT owner_id FROM parkings WHERE id = ?', (reservation['parking_id'],))
        parking = cursor.fetchone()
        conn.close()

        if not (reservation['driver_id'] == session['user_id'] or (parking and parking[0] == session['user_id'])):
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
            
        if reservation['status'] not in ['arrived', 'active']:
            return jsonify({'success': False, 'error': 'La reserva no está activa o el conductor no ha llegado'}), 400
            
        # Leer posible payload (rating opcional)
        data = request.get_json(silent=True) or {}
        rating = data.get('rating')
        comment = data.get('comment')
        # Si el arrendador envía una calificación, guardarla antes de finalizar
        try:
            if rating is not None:
                # reviewer = usuario que finaliza (arrendador)
                add_review(session['user_id'], reservation['driver_id'], reservation['parking_id'], int(rating), comment)
        except Exception:
            # No bloquear el flujo si falla la calificación
            pass

        # Finalizar la reserva y enviar notificaciones
        success = finish_reservation(reservation_id, session['user_id'])
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'No se pudo finalizar la reserva'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reservations/<int:reservation_id>/arrived', methods=['POST'])
def api_mark_arrived(reservation_id):
    """API del conductor: marcar que ha llegado al parqueadero."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    
    try:
        # Obtener la reserva para verificar permisos
        reservation = get_reservation(reservation_id)
        if not reservation:
            return jsonify({'success': False, 'error': 'Reserva no encontrada'}), 404
            
        if reservation['driver_id'] != session['user_id']:
            return jsonify({'success': False, 'error': 'No autorizado para esta reserva'}), 403
            
        if reservation['status'] == 'cancelled':
            return jsonify({'success': False, 'error': 'La reserva ya fue cancelada'}), 400
            
        success = mark_driver_arrived(reservation_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'No se pudo registrar la llegada'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reservations/<int:reservation_id>/cancel', methods=['POST'])
def api_cancel_reservation(reservation_id):
    """API pública: cancelar una reserva."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    try:
        user_id = session['user_id']
        # La función actualizada de cancel_reservation maneja las notificaciones
        result = cancel_reservation(reservation_id, user_id)
        if not result:
            return jsonify({'success': False, 'error': 'No se pudo cancelar la reserva.'}), 500
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reservations/<int:reservation_id>/request-extra-time', methods=['POST'])
def request_extra_time(reservation_id):
    """Conductor solicita tiempo extra al arrendador."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    try:
        data = request.get_json() or {}
        extra_minutes = data.get('extra_minutes', 0)
        if extra_minutes not in [10, 20, 30]:
            return jsonify({'success': False, 'error': 'Minutos inválidos'}), 400
        
        # Obtener la reserva
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('SELECT driver_id, parking_id FROM reservations WHERE id = ?', (reservation_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Reserva no encontrada'}), 404
        
        driver_id, parking_id = row[0], row[1]
        if driver_id != session['user_id']:
            conn.close()
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        # Obtener el owner_id del parqueadero
        cur.execute('SELECT owner_id FROM parkings WHERE id = ?', (parking_id,))
        parking_row = cur.fetchone()
        if not parking_row:
            conn.close()
            return jsonify({'success': False, 'error': 'Parqueadero no encontrado'}), 404
        
        owner_id = parking_row[0]
        
        conn.close()
        
        # NO eliminar vehicle_parked - el conductor debe seguir viendo su notificación de reserva activa
        
        # Crear notificación para el arrendador ÚNICAMENTE
        add_notification(
            user_id=owner_id,
            type='extra_time_request',
            message=f'El conductor solicita {extra_minutes} minutos adicionales',
            reservation_id=reservation_id,
            owner_id=owner_id,
            extra_data={'extra_minutes': extra_minutes, 'driver_id': driver_id}
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reservations/<int:reservation_id>/at-vehicle', methods=['POST'])
def at_vehicle(reservation_id):
    """Conductor notifica que llegó a su vehículo."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('SELECT driver_id, parking_id FROM reservations WHERE id = ?', (reservation_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Reserva no encontrada'}), 404
        
        driver_id, parking_id = row[0], row[1]
        if driver_id != session['user_id']:
            conn.close()
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        # Obtener el owner_id del parqueadero
        cur.execute('SELECT owner_id FROM parkings WHERE id = ?', (parking_id,))
        parking_row = cur.fetchone()
        if not parking_row:
            conn.close()
            return jsonify({'success': False, 'error': 'Parqueadero no encontrado'}), 404
        
        owner_id = parking_row[0]
        
        # Cerrar la conexión ANTES de las operaciones de notificaciones
        conn.close()
        
        # NO eliminar vehicle_parked - debe permanecer hasta que el arrendador confirme
        
        # Crear notificación para el arrendador ÚNICAMENTE (esto abre su propia conexión)
        add_notification(
            user_id=owner_id,
            type='at_vehicle',
            message='El conductor llegó a su vehículo',
            reservation_id=reservation_id,
            owner_id=owner_id,
            extra_data={'driver_id': driver_id}
        )
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reservations/<int:reservation_id>/approve-extra-time', methods=['POST'])
def approve_extra_time(reservation_id):
    """Arrendador aprueba tiempo extra solicitado por el conductor."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    try:
        data = request.get_json() or {}
        extra_minutes = data.get('extra_minutes', 0)
        notification_id = data.get('notification_id', 0)
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''SELECT r.driver_id, r.duration_minutes, p.owner_id 
                       FROM reservations r 
                       JOIN parkings p ON r.parking_id = p.id 
                       WHERE r.id = ?''', (reservation_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Reserva no encontrada'}), 404
        
        driver_id, current_duration, owner_id = row
        if owner_id != session['user_id']:
            conn.close()
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        # Obtener nombre del arrendador
        cur.execute('SELECT name FROM users WHERE id = ?', (owner_id,))
        owner_row = cur.fetchone()
        owner_name = owner_row[0] if owner_row else 'Arrendador'
        
        # Actualizar duración de la reserva
        new_duration = current_duration + extra_minutes
        cur.execute('UPDATE reservations SET duration_minutes = ? WHERE id = ?', (new_duration, reservation_id))
        
        # Hacer commit y cerrar ANTES de las operaciones de notificación
        conn.commit()
        conn.close()
        
        # Eliminar notificación de solicitud de tiempo extra del arrendador
        from models import delete_notifications_for_reservation
        try:
            delete_notifications_for_reservation(reservation_id, types_to_remove=['extra_time_request'], user_id=owner_id)
        except Exception:
            pass
        
        # Actualizar la notificación vehicle_parked del conductor con el nuevo duration_minutes
        try:
            conn2 = get_connection()
            cur2 = conn2.cursor()
            # Obtener occupied_since de parkings
            cur2.execute('SELECT occupied_since FROM parkings p JOIN reservations r ON p.id = r.parking_id WHERE r.id = ?', (reservation_id,))
            occ_row = cur2.fetchone()
            occupied_since = occ_row[0] if occ_row else None
            
            # Obtener parking_name
            cur2.execute('SELECT p.name FROM parkings p JOIN reservations r ON p.id = r.parking_id WHERE r.id = ?', (reservation_id,))
            park_row = cur2.fetchone()
            parking_name = park_row[0] if park_row else 'el parqueadero'
            
            # Actualizar el extra_data de la notificación vehicle_parked
            import json
            new_extra_data = json.dumps({
                'parking_name': parking_name,
                'duration_minutes': new_duration,
                'occupied_since': occupied_since
            })
            cur2.execute('UPDATE notifications SET extra_data = ? WHERE reservation_id = ? AND user_id = ? AND type = ?', 
                        (new_extra_data, reservation_id, driver_id, 'vehicle_parked'))
            conn2.commit()
            conn2.close()
        except Exception as e:
            print(f"Error actualizando notificación vehicle_parked: {e}")
        
        # Notificar al conductor que fue aprobado (esto abre su propia conexión)
        add_notification(
            user_id=driver_id,
            type='extra_time_approved',
            message=f'Se aprobaron {extra_minutes} minutos adicionales',
            reservation_id=reservation_id,
            extra_data={'extra_minutes': extra_minutes, 'owner_name': owner_name}
        )
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reservations/<int:reservation_id>/reject-extra-time', methods=['POST'])
def reject_extra_time(reservation_id):
    """Arrendador rechaza tiempo extra - se aplica multa de $500 cada 5 min."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    try:
        data = request.get_json() or {}
        notification_id = data.get('notification_id', 0)
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''SELECT r.driver_id, p.owner_id 
                       FROM reservations r 
                       JOIN parkings p ON r.parking_id = p.id 
                       WHERE r.id = ?''', (reservation_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Reserva no encontrada'}), 404
        
        driver_id, owner_id = row
        if owner_id != session['user_id']:
            conn.close()
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        # Obtener nombre del arrendador
        cur.execute('SELECT name FROM users WHERE id = ?', (owner_id,))
        owner_row = cur.fetchone()
        owner_name = owner_row[0] if owner_row else 'Arrendador'
        
        # Marcar que se rechazó - penalty_active=1 indica que cuando se cumpla duration_minutes
        # se debe empezar a cobrar la multa. penalty_start se calculará dinámicamente.
        cur.execute('UPDATE reservations SET penalty_active = 1 WHERE id = ?', (reservation_id,))
        
        # Hacer commit y cerrar ANTES de las operaciones de notificación
        conn.commit()
        conn.close()
        
        # Eliminar notificación de solicitud de tiempo extra del arrendador
        from models import delete_notifications_for_reservation
        try:
            delete_notifications_for_reservation(reservation_id, types_to_remove=['extra_time_request'], user_id=owner_id)
        except Exception:
            pass
        
        # Notificar al conductor que fue rechazado (esto abre su propia conexión)
        add_notification(
            user_id=driver_id,
            type='extra_time_rejected',
            message='Tu solicitud de tiempo extra fue rechazada. Se aplicará multa de $500 cada 5 min al exceder tu tiempo.',
            reservation_id=reservation_id,
            extra_data={'owner_name': owner_name}
        )
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reservations/<int:reservation_id>/clear-vehicle-parked', methods=['POST'])
def clear_vehicle_parked(reservation_id):
    """Arrendador confirma que el conductor llegó - eliminar notificación vehicle_parked del conductor."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''SELECT r.driver_id, p.owner_id 
                       FROM reservations r 
                       JOIN parkings p ON r.parking_id = p.id 
                       WHERE r.id = ?''', (reservation_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Reserva no encontrada'}), 404
        
        driver_id, owner_id = row
        if owner_id != session['user_id']:
            conn.close()
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        conn.close()
        
        # Eliminar notificación vehicle_parked del conductor
        from models import delete_notifications_for_reservation
        try:
            delete_notifications_for_reservation(reservation_id, types_to_remove=['vehicle_parked'], user_id=driver_id)
        except Exception as e:
            print(f"Error eliminando vehicle_parked: {e}")
        
        # También eliminar la notificación at_vehicle del arrendador
        try:
            delete_notifications_for_reservation(reservation_id, types_to_remove=['at_vehicle'], user_id=owner_id)
        except Exception as e:
            print(f"Error eliminando at_vehicle: {e}")
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reservations/<int:reservation_id>/vehicle-not-arrived', methods=['POST'])
def vehicle_not_arrived(reservation_id):
    """Arrendador indica que el conductor no ha llegado - el tiempo sigue corriendo."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('SELECT owner_id FROM reservations WHERE id = ?', (reservation_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Reserva no encontrada'}), 404
        
        if row[0] != session['user_id']:
            conn.close()
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        # Marcar notificación de at_vehicle como leída
        cur.execute('UPDATE notifications SET status = ? WHERE reservation_id = ? AND type = ?', 
                    ('read', reservation_id, 'at_vehicle'))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reservations/<int:reservation_id>', methods=['GET'])
def get_reservation_details(reservation_id):
    """API para obtener los detalles de una reserva incluyendo penalizaciones."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
        
    try:
        reservation = get_reservation(reservation_id)
        if not reservation:
            return jsonify({'success': False, 'error': 'Reserva no encontrada'}), 404
        
        # Verificar que el usuario sea el conductor o el dueño del parqueadero
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT owner_id, occupied_since FROM parkings WHERE id = ?', (reservation['parking_id'],))
        parking = cursor.fetchone()
        conn.close()

        if not (reservation['driver_id'] == session['user_id'] or (parking and parking[0] == session['user_id'])):
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        # Agregar occupied_since a la respuesta
        if parking and len(parking) > 1:
            reservation['occupied_since'] = parking[1]
        
        return jsonify({
            'success': True,
            'reservation': reservation,
            'penalty_amount': reservation.get('penalty_amount', 0) or 0,
            'penalty_active': reservation.get('penalty_active', 0) or 0
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/notifications')
def get_notifications():
    """API para obtener las notificaciones del usuario."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
        
    try:
        notifications = get_notifications_by_user(session['user_id'])
        return jsonify({
            'success': True,
            'notifications': notifications
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/notifications/mark-read', methods=['POST'])
def mark_notifications_read():
    """API para marcar todas las notificaciones como leídas."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
        
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET status = 'read' WHERE user_id = ? AND status = 'unread'",
                      (session['user_id'],))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/notifications/clear', methods=['POST'])
def clear_notifications():
    """Elimina todas las notificaciones del usuario exceptuando las que están relacionadas
    con un proceso de reserva (reservation_id IS NOT NULL)."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Contar las notificaciones que se eliminarán (AHORA: todas las del usuario)
        cursor.execute('SELECT COUNT(*) FROM notifications WHERE user_id = ?', (session['user_id'],))
        to_delete = cursor.fetchone()[0]
        # Eliminar todas las notificaciones del usuario (borrado permanente)
        cursor.execute('DELETE FROM notifications WHERE user_id = ?', (session['user_id'],))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'deleted': to_delete})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/parkings/nearby', methods=['GET'])
def api_get_nearby_parkings():
    """API pública: buscar parqueaderos cercanos a una ubicación."""
    # Se esperan parámetros de consulta: latitud, longitud, y opcionalmente radio en metros
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    radius = request.args.get('radius', default=500, type=int)  # Radio por defecto 500 metros

    if not lat or not lon:
        return jsonify({'success': False, 'error': 'Faltan latitud y/o longitud.'}), 400

    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return jsonify({'success': False, 'error': 'Latitud y longitud deben ser números.'}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Buscar parqueaderos en un radio alrededor de la ubicación dada
        cursor.execute('''
            SELECT id, name, address, latitude, longitude, owner_id
            FROM parkings
            WHERE active = 1 AND latitude IS NOT NULL AND longitude IS NOT NULL
            AND (6371000 * acos(
                cos(radians(?)) * cos(radians(latitude)) *
                cos(radians(longitude) - radians(?)) +
                sin(radians(?)) * sin(radians(latitude))
            )) <= ?
        ''', (lat, lon, lat, radius))
        parkings = cursor.fetchall()
        conn.close()
        return jsonify([{
            'id': p['id'],
            'name': p['name'],
            'address': p['address'],
            'latitude': p['latitude'],
            'longitude': p['longitude'],
            'owner_id': p['owner_id'],
            'status': 'Libre'  # Asignar estado por defecto
        } for p in parkings])
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# === Rutas para pruebas y depuración ===
@app.route('/debug/killall')
def debug_kill_all():
    """Ruta de depuración: termina todas las sesiones y procesos de fondo."""
    if os.environ.get('FLASK_ENV') == 'development':
        os._exit(0)
    return 'OK'


@app.route('/debug/db/reset', methods=['POST'])
def debug_db_reset():
    """Ruta de depuración: reinicia la base de datos (borrar y crear tablas)."""
    if os.environ.get('FLASK_ENV') != 'development':
        return jsonify({'success': False, 'error': 'Forbidden'}), 403
    try:
        conn = get_db_connection()
        c = conn.cursor()
        # Borrar datos existentes
        c.execute('DROP TABLE IF EXISTS users')
        c.execute('DROP TABLE IF EXISTS parkings')
        c.execute('DROP TABLE IF EXISTS reservations')
        c.execute('DROP TABLE IF EXISTS reviews')
        # Crear tablas nuevamente
        create_users_table()
        create_parkings_table()
        create_reservations_table()
        create_reviews_table()
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/debug/populate', methods=['POST'])
def debug_populate():
    """Ruta de depuración: llena la base de datos con datos de prueba."""
    if os.environ.get('FLASK_ENV') != 'development':
        return jsonify({'success': False, 'error': 'Forbidden'}), 403
    try:
        conn = get_db_connection()
        c = conn.cursor()
        # Insertar usuarios de prueba
        c.executemany('''
            INSERT INTO users (name, email, password, phone, role) VALUES (?, ?, ?, ?, ?)
        ''', [
            ('Conductor Uno', 'conductor1@example.com', 'password', '3001112233', 'conductor'),
            ('Conductor Dos', 'conductor2@example.com', 'password', '3002233445', 'conductor'),
            ('Arrendador Uno', 'arrendador1@example.com', 'password', '3109876543', 'arrendador'),
            ('Arrendador Dos', 'arrendador2@example.com', 'password', '3108765432', 'arrendador')
        ])
        # Insertar parqueaderos de prueba
        c.executemany('''
            INSERT INTO parkings (owner_id, name, phone, email, address, department, city, housing_type, size, features, image_path, latitude, longitude, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            (3, 'Parqueadero Centro', '3001112233', 'contacto@example.com', 'Calle 10 # 10-10', 'Antioquia', 'Medellín', 'Edificio', 'Pequeño', 'Cubierto', None, 6.2442, -75.5812, 1),
            (3, 'Parqueadero Norte', '3002223344', 'contacto@example.com', 'Carrera 30 # 20-20', 'Antioquia', 'Medellín', 'Casa', 'Mediano', 'Descubierto', None, 6.2518, -75.5636, 1),
            (4, 'Parqueadero Sur', '3109876543', 'contacto@example.com', 'Avenida 80 # 10-10', 'Cundinamarca', 'Bogotá', 'Edificio', 'Grande', 'Cubierto, CCTV', None, 4.6097, -74.0817, 1),
            (4, 'Parqueadero Este', '3108765432', 'contacto@example.com', 'Transversal 50 # 20-20', 'Cundinamarca', 'Bogotá', 'Casa', 'Pequeño', 'Descubierto', None, 4.6100, -74.0700, 1)
        ])
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API para obtener los parqueaderos del arrendador (dashboard)
@app.route('/api/owner/parkings', methods=['GET'])
def api_owner_parkings():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not authenticated'}), 401
    try:
        parkings = get_parkings_by_owner(session['user_id'])
        return jsonify({'success': True, 'parkings': parkings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    # ============================================================
    # APIS REST PARA PERFIL DEL CONDUCTOR
    # ============================================================
    
    from models import (
        get_driver_profile,
        update_driver_profile,
        update_driver_verification_status,
        update_driver_stats,
        update_last_activity,
        check_license_validity,
        get_driver_age
    )
    
    @app.route('/api/driver/profile/<int:user_id>', methods=['GET'])
    def api_get_driver_profile(user_id):
        """Obtener perfil completo del conductor"""
        try:
            # Verificar que el usuario tiene permiso para ver este perfil
            if 'user_id' not in session or (session['user_id'] != user_id and session.get('role') != 'admin'):
                return jsonify({'error': 'No autorizado'}), 403
            
            profile = get_driver_profile(user_id)
            if profile:
                # Agregar información adicional calculada
                profile['age'] = get_driver_age(user_id)
                profile['license_validity'] = check_license_validity(user_id)
                return jsonify(profile), 200
            else:
                return jsonify({'error': 'Perfil no encontrado'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/driver/profile/<int:user_id>', methods=['PUT'])
    def api_update_driver_profile(user_id):
        """Actualizar perfil del conductor"""
        try:
            # Verificar que el usuario tiene permiso
            if 'user_id' not in session or session['user_id'] != user_id:
                return jsonify({'error': 'No autorizado'}), 403
            
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No se recibieron datos'}), 400
            
            success = update_driver_profile(user_id, data)
            if success:
                update_last_activity(user_id)
                return jsonify({'message': 'Perfil actualizado correctamente'}), 200
            else:
                return jsonify({'error': 'Error al actualizar perfil'}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/driver/profile/<int:user_id>/verify', methods=['POST'])
    def api_verify_driver_documents(user_id):
        """Verificar documentos del conductor (solo admin)"""
        try:
            # Solo administradores pueden verificar
            if 'user_id' not in session or session.get('role') != 'admin':
                return jsonify({'error': 'No autorizado - Solo administradores'}), 403
            
            data = request.get_json()
            document_verified = data.get('document_verified')
            license_verified = data.get('license_verified')
            
            success = update_driver_verification_status(
                user_id,
                document_verified=document_verified,
                license_verified=license_verified
            )
            
            if success:
                # Crear notificación para el conductor
                if document_verified == 'verificado' or license_verified == 'verificado':
                    add_notification(
                        user_id,
                        'verification_approved',
                        'Tus documentos han sido verificados correctamente'
                    )
                elif document_verified == 'rechazado' or license_verified == 'rechazado':
                    add_notification(
                        user_id,
                        'verification_rejected',
                        'Algunos documentos fueron rechazados. Por favor revisa tu perfil.'
                    )
                
                return jsonify({'message': 'Estado de verificación actualizado'}), 200
            else:
                return jsonify({'error': 'Error al actualizar verificación'}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/driver/stats', methods=['GET'])
    def api_get_driver_stats():
        """Obtener estadísticas del conductor actual"""
        try:
            if 'user_id' not in session:
                return jsonify({'error': 'No autenticado'}), 401
            
            user_id = session['user_id']
            profile = get_driver_profile(user_id)
            
            if profile:
                stats = {
                    'rating': profile['rating'],
                    'total_reservations': profile['total_reservations'],
                    'total_cancellations': profile['total_cancellations'],
                    'account_status': profile['account_status'],
                    'document_verified': profile['document_verified'],
                    'license_verified': profile['license_verified']
                }
                return jsonify(stats), 200
            else:
                return jsonify({'error': 'Perfil no encontrado'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/driver/upload-photo', methods=['POST'])
    def api_upload_driver_photo():
        """Subir foto de perfil, documento o licencia"""
        try:
            if 'user_id' not in session:
                return jsonify({'error': 'No autenticado'}), 401
            
            if 'photo' not in request.files:
                return jsonify({'error': 'No se envió ninguna foto'}), 400
            
            file = request.files['photo']
            photo_type = request.form.get('type')  # 'profile', 'document', 'license'
            
            if file.filename == '':
                return jsonify({'error': 'Nombre de archivo vacío'}), 400
            
            if not photo_type or photo_type not in ['profile', 'document', 'license']:
                return jsonify({'error': 'Tipo de foto inválido'}), 400
            
            # Validar extensión
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
            if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
                return jsonify({'error': 'Formato de archivo no permitido'}), 400
            
            # Crear carpeta de uploads si no existe
            upload_folder = os.path.join(app.static_folder, 'uploads', 'profiles')
            os.makedirs(upload_folder, exist_ok=True)
            
            # Generar nombre único para el archivo
            user_id = session['user_id']
            timestamp = int(_time.time())
            filename = secure_filename(f"{user_id}_{photo_type}_{timestamp}_{file.filename}")
            filepath = os.path.join(upload_folder, filename)
            
            # Guardar archivo
            file.save(filepath)
            
            # Actualizar base de datos con la ruta relativa
            relative_path = f"/static/uploads/profiles/{filename}"
            field_map = {
                'profile': 'profile_photo',
                'document': 'document_photo',
                'license': 'license_photo'
            }
            
            update_data = {field_map[photo_type]: relative_path}
            success = update_driver_profile(user_id, update_data)
            
            if success:
                update_last_activity(user_id)
                return jsonify({
                    'message': 'Foto subida correctamente',
                    'path': relative_path
                }), 200
            else:
                # Eliminar archivo si falló la actualización en BD
                os.remove(filepath)
                return jsonify({'error': 'Error al actualizar base de datos'}), 500
                
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/driver/license-validity/<int:user_id>', methods=['GET'])
    def api_check_license_validity(user_id):
        """Verificar validez de la licencia"""
        try:
            if 'user_id' not in session or (session['user_id'] != user_id and session.get('role') != 'admin'):
                return jsonify({'error': 'No autorizado'}), 403
            
            validity = check_license_validity(user_id)
            return jsonify(validity), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/driver/vehicles', methods=['GET'])
    def api_get_driver_vehicles():
        """Obtener lista de vehículos del conductor"""
        try:
            if 'user_id' not in session:
                return jsonify({'error': 'No autorizado'}), 403
            
            user_id = session['user_id']
            
            # Por ahora, obtener el vehículo del perfil (posteriormente será una lista)
            profile = get_driver_profile(user_id)
            
            if not profile:
                return jsonify({'error': 'Perfil no encontrado'}), 404
            
            vehicles = []
            
            # Si tiene vehículo registrado en el perfil
            if profile.get('vehicle_plate'):
                vehicles.append({
                    'plate': profile.get('vehicle_plate'),
                    'brand': profile.get('vehicle_brand'),
                    'model': profile.get('vehicle_model'),
                    'color': profile.get('vehicle_color'),
                    'year': profile.get('vehicle_year'),
                    'dimensions': profile.get('vehicle_dimensions')
                })
            
            # Obtener vehículo actualmente seleccionado
            current_vehicle = None
            current_plate = session.get('current_vehicle_plate')
            
            if current_plate:
                current_vehicle = next((v for v in vehicles if v['plate'] == current_plate), None)
            elif vehicles:
                # Si no hay vehículo seleccionado, usar el primero por defecto
                current_vehicle = vehicles[0]
                session['current_vehicle_plate'] = current_vehicle['plate']
            
            return jsonify({
                'vehicles': vehicles,
                'current_vehicle': current_vehicle
            }), 200
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/driver/select-vehicle', methods=['POST'])
    def api_select_vehicle():
        """Seleccionar vehículo activo"""
        try:
            if 'user_id' not in session:
                return jsonify({'error': 'No autorizado'}), 403
            
            data = request.get_json()
            plate = data.get('plate')
            
            if not plate:
                return jsonify({'error': 'Placa requerida'}), 400
            
            # Verificar que el vehículo pertenece al usuario
            user_id = session['user_id']
            profile = get_driver_profile(user_id)
            
            if not profile or profile.get('vehicle_plate') != plate:
                return jsonify({'error': 'Vehículo no encontrado'}), 404
            
            # Guardar en sesión
            session['current_vehicle_plate'] = plate
            
            return jsonify({
                'success': True,
                'message': f'Vehículo {plate} seleccionado'
            }), 200
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # ============================================================
    # FIN APIS REST PERFIL CONDUCTOR
    # ============================================================

    # Crear tablas necesarias al iniciar
    from models import create_notifications_table
    create_users_table()
    create_parkings_table()
    create_reservations_table()
    create_reviews_table()
    create_notifications_table()
    # Start background thread to check for expired reservations
    def _expiration_worker():
        from models import notify_expired_reservations
        while True:
            try:
                notify_expired_reservations()
            except Exception:
                pass
            _time.sleep(30)

    t = threading.Thread(target=_expiration_worker, daemon=True)
    t.start()

    # Start SocketIO server; bind to 0.0.0.0 so it's reachable from host
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
