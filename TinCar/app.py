from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'clave-secreta'  # cámbiala por una segura en producción
DB_NAME = 'tincar.db'

# --------- Funciones de Base de Datos ---------
def create_users_table():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL   -- "arrendador" o "conductor"
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

def insert_user(email, password, role):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT INTO users (email, password, role) VALUES (?, ?, ?)',
              (email, password, role))
    conn.commit()
    conn.close()

# --------- Rutas ---------
@app.route('/')
def home():
    # Muestra la landing page (index.html) en lugar de redirigir al login
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  # arrendador o conductor
        if get_user_by_email(email):
            flash('El correo ya está registrado', 'error')
        else:
            insert_user(email, password, role)
            flash('Cuenta creada exitosamente, ahora inicia sesión.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = get_user_by_email(email)
        if user and user[2] == password:
            session['user_id'] = user[0]
            session['email'] = user[1]
            session['role'] = user[3]
            return redirect(url_for('dashboard'))
        else:
            flash('Correo o contraseña incorrectos', 'error')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', email=session['email'], role=session['role'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --------- Punto de entrada ---------
if __name__ == '__main__':
    create_users_table()  # Crea la tabla automáticamente si no existe
    app.run(debug=True)
