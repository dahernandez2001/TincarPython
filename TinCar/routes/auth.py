from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import get_connection, add_notification
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
        # Obtener también el rol para redirigir según tipo de usuario
        cursor.execute("SELECT id, name, email, password, role FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password(password, user[3]):
            # Guardar claves de sesión consistentes con el resto de la app
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['name'] = user[1]
            session['email'] = user[2]
            session['role'] = user[4]
            flash(f'👋 Bienvenido, {user[1]}', 'success')
            # Redirigir según rol
            if user[4] == 'conductor':
                return redirect(url_for('driver_index'))
            return redirect(url_for('dashboard'))
        else:
            flash('❌ Credenciales incorrectas.', 'warning')
            return redirect(url_for('auth.login'))
    return render_template('login.html')

# Ejemplo de lógica para generar notificaciones al iniciar sesión
@auth.route('/generate_notifications', methods=['POST'])
def generate_notifications():
    user_id = session.get('user_id')
    if not user_id:
        flash('⚠️ Debes iniciar sesión para generar notificaciones.', 'warning')
        return redirect(url_for('auth.login'))

    # Notificación de ejemplo: reserva de garaje
    add_notification(user_id, "Tu garaje ha sido reservado. El conductor llegará en el tiempo estipulado.", "reservation")

    # Notificación de ejemplo: tiempo excedido
    add_notification(user_id, "El tiempo estipulado ha pasado y el conductor no ha llegado. Puedes esperar o cancelar el servicio.", "timeout")

    flash('✅ Notificaciones generadas.', 'success')
    return redirect(url_for('dashboard'))
