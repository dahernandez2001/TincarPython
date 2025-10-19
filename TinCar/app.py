import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash

# === Configuración de rutas absolutas ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, 'static'),
    template_folder=os.path.join(BASE_DIR, 'templates')
)

# ⚙️ Configuración especial para GitHub Codespaces
app.config['SERVER_NAME'] = 'dahernandez2001-tincar-5000.app.github.dev'
app.config['PREFERRED_URL_SCHEME'] = 'https'

# === Configuración general ===
app.secret_key = 'clave-secreta'
DB_NAME = os.path.join(BASE_DIR, 'tincar.db')


# === Funciones de base de datos ===
def create_users_table():
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE email = ?', (email,))
    user = c.fetchone()
    conn.close()
    return user


def insert_user(name, email, password, role):
    conn = sqlite3.connect(DB_NAME)
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
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        if get_user_by_email(email):
            flash('El correo ya está registrado', 'error')
        else:
            insert_user(name, email, password, role)
            flash('Cuenta creada exitosamente. Ahora inicia sesión.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = get_user_by_email(email)

        if user and user[3] == password:  # password es el índice correcto
            session['user_id'] = user[0]
            session['name'] = user[1]
            session['email'] = user[2]
            session['role'] = user[4]  # todavía se guarda por si quieres usarlo más adelante
            return redirect(url_for('dashboard'))
        else:
            flash('Correo o contraseña incorrectos', 'error')

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', name=session['name'])


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# === Ruta de prueba para verificar CSS ===
@app.route('/test_static')
def test_static():
    return '''
    <html>
        <head>
            <link rel="stylesheet" href="/static/style.css">
        </head>
        <body>
            <h1>✅ CSS cargado correctamente desde static!</h1>
        </body>
    </html>
    '''


# === Ejecutar la app ===
if __name__ == '__main__':
    create_users_table()
    app.run(host='0.0.0.0', port=5000, debug=True)
