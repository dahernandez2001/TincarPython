import os
import sqlite3
from time import time
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from routes.auth import auth
from models import get_connection, create_parkings_table, add_parking, get_parkings_by_owner
from models import get_parking, update_parking, delete_parking

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
        parking = add_parking(owner_id, name, phone, email, address, department, city, housing_type, size, features, image_path, 1)
        if not parking:
            return jsonify({'success': False, 'error': 'No se pudo crear el parqueadero'}), 500
        return jsonify({'success': True, 'parking': parking})
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
        conn.close()
        return {'success': True, 'id': parking_id, 'active': bool(active_value)}
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
        update_parking(parking_id, **data)
        p2 = get_parking(parking_id)
        return jsonify({'success': True, 'parking': p2})
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


# Ejecutar la app
if __name__ == '__main__':
    create_users_table()
    # Crear tabla parkings si no existe
    try:
        create_parkings_table()
    except Exception:
        pass
    app.run(host='0.0.0.0', port=5000, debug=True)
