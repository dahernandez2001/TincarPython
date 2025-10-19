from flask import Blueprint, request, jsonify
from models import get_connection
from utils.security import hash_password, check_password

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['POST'])
def register():
    data = request.json
    nombre = data.get('nombre')
    correo = data.get('correo')
    contraseña = hash_password(data.get('contraseña'))
    telefono = data.get('telefono')
    rol = data.get('rol')

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO users (nombre, correo, contraseña, telefono, rol)
        VALUES (%s, %s, %s, %s, %s)
        """, (nombre, correo, contraseña, telefono, rol))
        conn.commit()
        return jsonify({'mensaje': 'Usuario registrado correctamente'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cur.close()
        conn.close()

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
