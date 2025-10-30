from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import get_connection
from utils.security import hash_password

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        password = request.form['password']

        conn = get_connection()
        cursor = conn.cursor()

        # Verificar si el correo ya está registrado
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('⚠️ Este correo ya está registrado. Intenta iniciar sesión.', 'warning')
            conn.close()
            return redirect(url_for('auth.login'))

        # Crear nuevo usuario
        hashed_password = hash_password(password)
        cursor.execute("INSERT INTO users (nombre, email, password) VALUES (?, ?, ?)",
                       (nombre, email, hashed_password))
        conn.commit()
        conn.close()

        flash('✅ Registro exitoso. Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth.route('/login', methods=['POST'])
def login():
    data = request.json
    correo = data.get('correo')
    contraseña = data.get('contraseña')

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT contraseña FROM users WHERE correo=%s", (correo,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user and check_password(contraseña, user[0]):
        return jsonify({'mensaje': 'En reparación'}), 200
    else:
        return jsonify({'error': 'Usuario o contraseña incorrectos'}), 401
