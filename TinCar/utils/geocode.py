import requests
import sqlite3
import os
from models import get_connection


def _ensure_cache_table(conn):
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS geocode_cache (
            query TEXT PRIMARY KEY,
            lat REAL,
            lon REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()


def geocode_location(department=None, city=None, address=None, country_hint=None, timeout=5):
    """
    Intenta geocodificar usando Nominatim (OpenStreetMap) con un cache local en SQLite.

    Usa `department`, `city` y `address` para construir una query. Primero consulta
    la tabla `geocode_cache`; si no hay resultado, llama a Nominatim y guarda la respuesta.

    Devuelve (lat, lon) como floats o (None, None) si no pudo resolverse.
    """
    pieces = []
    if address:
        pieces.append(str(address).strip())
    if city:
        pieces.append(str(city).strip())
    if department:
        pieces.append(str(department).strip())
    if country_hint:
        pieces.append(str(country_hint).strip())

    if not pieces:
        return None, None

    q = ', '.join(pieces)

    # Consultar cache local en la DB
    try:
        conn = get_connection()
        _ensure_cache_table(conn)
        cur = conn.cursor()
        cur.execute('SELECT lat, lon FROM geocode_cache WHERE query = ?', (q,))
        row = cur.fetchone()
        if row and row[0] is not None and row[1] is not None:
            try:
                return float(row[0]), float(row[1])
            except Exception:
                pass
    except Exception:
        # No bloquear en caso de problemas con la DB cache
        pass

    # Si no está en cache, consultar Nominatim
    url = 'https://nominatim.openstreetmap.org/search'
    params = {
        'q': q,
        'format': 'json',
        'limit': 1,
    }
    headers = {
        'User-Agent': 'TinCar/1.0 (contact: support@tincar.local)'
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None, None
        d0 = data[0]
        lat = float(d0.get('lat'))
        lon = float(d0.get('lon'))
        # Guardar en cache
        try:
            conn = conn if 'conn' in locals() and conn is not None else get_connection()
            _ensure_cache_table(conn)
            cur = conn.cursor()
            cur.execute('INSERT OR REPLACE INTO geocode_cache (query, lat, lon) VALUES (?, ?, ?)', (q, lat, lon))
            conn.commit()
        except Exception:
            pass
        return lat, lon
    except Exception:
        # No hacer fallar la operación si el servicio externo no está disponible
        return None, None
