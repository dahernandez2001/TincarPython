import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from routes.auth import auth
from models import get_connection

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
    cursor.execute("SELECT name, role FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    # Si el usuario es arrendador, pasar una lista de parqueaderos (ejemplo/demo)
    if user[1] == 'arrendador':
        # Datos de ejemplo para mostrar en el mockup. En producción deberías
        # obtenerlos desde una tabla `parkings` o similar en la base de datos.
        parkings = [
            {'name': 'Parqueadero 1A', 'status': 'Ocupado', 'price': '$2.000', 'time': '00:10:45', 'active': True},
            {'name': 'Parqueadero 1B', 'status': 'Libre', 'price': '0', 'time': '00:00:00', 'active': True},
            {'name': 'Parqueadero 1C', 'status': 'Libre', 'price': '0', 'time': '00:00:00', 'active': False},
            {'name': 'Parqueadero 1D', 'status': 'Ocupado', 'price': '$80.000', 'time': '06:40:00', 'active': True},
        ]
        return render_template('dashboard_landlord.html', nombre=user[0], role=user[1], parkings=parkings)

    # Por defecto, renderizar dashboard genérico
    return render_template('dashboard.html', nombre=user[0], role=user[1])


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


# Ejecutar la app
if __name__ == '__main__':
    create_users_table()
    app.run(host='0.0.0.0', port=5000, debug=True)
