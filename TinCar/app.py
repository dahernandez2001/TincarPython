import os
import sqlite3
from time import time
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from routes.auth import auth
from models import get_connection, create_parkings_table, add_parking, get_parkings_by_owner
from models import get_parking, update_parking, delete_parking
from models import create_reservations_table, create_reviews_table, get_active_parkings, get_reservations_count_by_driver, get_rating_sum_for_driver
from models import add_reservation
from utils.geocode import geocode_location
import requests

# Configuración rutas absolutas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, 'static'),
    template_folder=os.path.join(BASE_DIR, 'templates')
)

app.secret_key = 'clave-secreta'

# Registrar blueprints
app.register_blueprint(auth)
DB_NAME = os.path.join(BASE_DIR, 'tincar.db')


# === Funciones de base de datos ===
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Permite acceder por nombre de columna
    return conn


def create_users_table():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT,
            role TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE email = ?', (email,))
    user = c.fetchone()
    conn.close()
    return user


def insert_user(name, email, password, role):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)',
              (name, email, password, role))
    conn.commit()
    conn.close()


# === Rutas principales ===
@app.route('/')
def home():
    return render_template('index.html')


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
    return redirect(url_for('auth.login'))


# === Ruta para conductor ===
@app.route('/driver')
def driver_index():
    # Verificar sesión
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    # Nombre de usuario (compatibilidad con distintos nombres de clave)
    nombre = session.get('user_name') or session.get('name') or '(usuario)'
    return render_template('index_driver.html', nombre=nombre)


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
            except Exception:
                data[key] = None
    # image handling
    if 'image' in request.files:
        img = request.files.get('image')
        if img and img.filename:
            uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
            os.makedirs(uploads_dir, exist_ok=True)
            filename = secure_filename(img.filename)
            unique_name = f"{int(time())}_{filename}"
            save_path = os.path.join(uploads_dir, unique_name)
            img.save(save_path)
            data['image_path'] = f"/static/uploads/{unique_name}"
    try:
        # verify ownership
        p = get_parking(parking_id)
        if not p:
            return jsonify({'error':'not found'}), 404
        if p['owner_id'] != session['user_id']:
            return jsonify({'error':'forbidden'}), 403
        # Si no se envían coordenadas explícitas en el form, intentar geocodificar
        need_geo = False
        if 'latitude' not in data or data.get('latitude') in (None, ''):
            need_geo = True
        if 'longitude' not in data or data.get('longitude') in (None, ''):
            need_geo = True
        if need_geo:
            addr = data.get('address') or p.get('address')
            dept = data.get('department') or p.get('department')
            cityv = data.get('city') or p.get('city')
            g_lat, g_lon = geocode_location(department=dept, city=cityv, address=addr, country_hint=None)
            if g_lat is not None and g_lon is not None:
                # sólo añadir las coordenadas que falten
                if not data.get('latitude'):
                    data['latitude'] = g_lat
                if not data.get('longitude'):
                    data['longitude'] = g_lon
        update_parking(parking_id, **data)
        p2 = get_parking(parking_id)
        resp = {'success': True, 'parking': p2}
        if p2.get('latitude') is None or p2.get('longitude') is None:
            resp['geocode_failed'] = True
            resp['message'] = 'No se pudieron obtener coordenadas desde la dirección; por favor añade latitud/longitud manualmente si es necesario.'
        return jsonify(resp)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/parkings/<int:parking_id>/delete', methods=['POST'])
def parking_delete(parking_id):
    if 'user_id' not in session:
        return jsonify({'error':'not authenticated'}), 401
    try:
        p = get_parking(parking_id)
        if not p:
            return jsonify({'error':'not found'}), 404
        if p['owner_id'] != session['user_id']:
            return jsonify({'error':'forbidden'}), 403
        delete_parking(parking_id)
        return jsonify({'success': True, 'id': parking_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/parkings/active', methods=['GET'])
def api_active_parkings():
    # devuelve los parqueaderos activos para que el conductor los vea en el mapa
    try:
        # soportar filtro por bbox (minLat,minLng,maxLat,maxLng)
        bbox = request.args.get('bbox')
        if bbox:
            try:
                parts = [float(x) for x in bbox.split(',')]
                if len(parts) == 4:
                    min_lat, min_lng, max_lat, max_lng = parts
                else:
                    raise ValueError('bbox must have 4 numbers')
            except Exception:
                return jsonify({'success': False, 'error': 'invalid bbox'}), 400
            conn = get_connection()
            cur = conn.cursor()
            # latitude between min_lat and max_lat and longitude between min_lng and max_lng
            cur.execute('SELECT id, owner_id, name, phone, email, address, department, city, housing_type, size, features, image_path, latitude, longitude FROM parkings WHERE active = 1 AND latitude IS NOT NULL AND longitude IS NOT NULL AND latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?', (min_lat, max_lat, min_lng, max_lng))
            rows = cur.fetchall()
            conn.close()
            parkings = []
            for r in rows:
                parkings.append({
                    'id': r[0], 'owner_id': r[1], 'name': r[2], 'phone': r[3], 'email': r[4], 'address': r[5],
                    'department': r[6], 'city': r[7], 'housing_type': r[8], 'size': r[9], 'features': r[10], 'image_path': r[11],
                    'latitude': r[12], 'longitude': r[13]
                })
        else:
            parkings = get_active_parkings()
        # Para mejorar la precisión del mapa: intentar geocodificar y persistir coordenadas
        updated = False
        for p in parkings:
            lat = p.get('latitude')
            lon = p.get('longitude')
            if lat is None or lon is None:
                # Intentar geocodificar con address/city/department
                g_lat, g_lon = geocode_location(department=p.get('department'), city=p.get('city'), address=p.get('address'))
                if g_lat is not None and g_lon is not None:
                    try:
                        update_parking(p['id'], latitude=g_lat, longitude=g_lon)
                        p['latitude'] = g_lat
                        p['longitude'] = g_lon
                        updated = True
                    except Exception:
                        # si no se puede persistir, igual devolver las coordenadas calculadas
                        p['latitude'] = g_lat
                        p['longitude'] = g_lon
        # Si hubo actualizaciones, podríamos volver a obtener la lista; no es necesario
        return jsonify({'success': True, 'parkings': parkings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/import_locations', methods=['POST'])
def admin_import_locations():
    """
    Endpoint (privado) para importar un JSON de localidades (departamento -> ciudades).
    Recibe JSON body: { "url": "https://raw.../file.json" }
    Guarda el archivo en static/data/colombia_locations.json
    """
    if 'user_id' not in session:
        return jsonify({'error': 'not authenticated'}), 401
    # simple permiso: solo arrendadores (puedes ajustarlo)
    if session.get('role') != 'arrendador':
        return jsonify({'error': 'forbidden'}), 403
    data = request.get_json(silent=True) or {}
    url = data.get('url')
    if not url:
        return jsonify({'error': 'missing url'}), 400
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        js = r.json()
        # validar forma básica: debe ser un dict con listas
        if not isinstance(js, dict):
            return jsonify({'error': 'invalid json format'}), 400
        # guardar en static/data
        out_path = os.path.join(BASE_DIR, 'static', 'data', 'colombia_locations.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            import json
            json.dump(js, f, ensure_ascii=False, indent=2)
        return jsonify({'success': True, 'message': 'Imported file saved.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/driver/stats', methods=['GET'])
def api_driver_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'not authenticated'}), 401
    driver_id = session['user_id']
    try:
        reservations = get_reservations_count_by_driver(driver_id)
        rating_sum = get_rating_sum_for_driver(driver_id)
        return jsonify({'success': True, 'reservations_count': reservations, 'rating_sum': rating_sum})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reservations', methods=['POST'])
def create_reservation():
    if 'user_id' not in session:
        return jsonify({'error': 'not authenticated'}), 401
    data = request.get_json(silent=True) or {}
    if 'parking_id' not in data:
        return jsonify({'error': 'missing parking_id'}), 400
    try:
        driver_id = session['user_id']
        parking_id = data['parking_id']
        reservation = add_reservation(driver_id, parking_id)
        if not reservation:
            return jsonify({'error': 'could not create reservation'}), 500
        return jsonify({'success': True, 'reservation': reservation})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Ejecutar la app
if __name__ == '__main__':
    create_users_table()
    # Crear tabla parkings si no existe
    try:
        create_parkings_table()
    except Exception:
        pass
    # Crear tablas nuevas para reservas y reseñas
    try:
        create_reservations_table()
        create_reviews_table()
    except Exception:
        pass
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
