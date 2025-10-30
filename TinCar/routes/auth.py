from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import get_connection
from utils.security import hash_password, check_password

auth = Blueprint('auth', __name__)

# ---------- REGISTRO ----------
@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'conductor')  # valor por defecto si no se selecciona

        # Validar que todos los campos estén completos
        if not name or not email or not password:
            flash('⚠️ Por favor completa todos los campos.', 'warning')
            return redirect(url_for('auth.register'))

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
        cursor.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                       (name, email, hashed_password, role))
        conn.commit()
        conn.close()

        flash('✅ Registro exitoso. Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


# ---------- LOGIN ----------
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('⚠️ Por favor completa todos los campos.', 'warning')
            return redirect(url_for('auth.login'))
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, password FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password(password, user[3]):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            flash(f'👋 Bienvenido, {user[1]}', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('❌ Credenciales incorrectas.', 'warning')
            return redirect(url_for('auth.login'))
    return render_template('login.html')
