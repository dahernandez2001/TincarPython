"""Script E2E mínimo para probar flujo de notificaciones:
- login conductor (conductor1@example.com / password)
- crear reserva corta (duration_minutes=0)
- marcar arrived
- login arrendador (arrendador1@example.com / password)
- esperar y comprobar que existe notification reservation_expired
- finalizar reserva con rating
- comprobar que notificaciones previas fueron eliminadas

Ejecutar con: python3 scripts/e2e_notifications_flow.py
"""

import requests
import time

BASE = 'http://127.0.0.1:5000'

# Credenciales de debug_populate
DRIVER = ('conductor1@example.com', 'password')
OWNER = ('arrendador1@example.com', 'password')
PARKING_ID = 1

s = requests.Session()
print('Login driver...')
res = s.post(f'{BASE}/login', data={'email': DRIVER[0], 'password': DRIVER[1]})
if res.status_code not in (200,302):
    print('Login driver falló', res.status_code, res.text); raise SystemExit(1)

print('Crear reserva (duration=0)...')
j = s.post(f'{BASE}/api/reservations', json={'parking_id': PARKING_ID, 'duration_minutes': 0, 'eta_minutes': 0}).json()
print('create reservation response:', j)
if not j.get('success'):
    print('Error creando reserva'); raise SystemExit(1)
resv = j.get('reservation')
rid = resv.get('id')
print('Reserva creada id=', rid)

print('Marcar arrived...')
r = s.post(f'{BASE}/api/reservations/{rid}/arrived')
print('arrived status', r.status_code, r.text)
if r.status_code != 200:
    print('Error arrived'); raise SystemExit(1)

# ahora el hilo background debería crear reservation_expired casi instantáneamente
print('Esperando 5s para que el worker genere expiración...')
time.sleep(5)

# Cambiar a cliente del owner
so = requests.Session()
print('Login owner...')
r = so.post(f'{BASE}/login', data={'email': OWNER[0], 'password': OWNER[1]})
print('owner login status', r.status_code)

print('Comprobando notificaciones owner...')
r = so.get(f'{BASE}/api/notifications').json()
print('owner notifications:', r.get('notifications'))
found_expired = any(n.get('type')=='reservation_expired' and n.get('reservation_id')==rid for n in r.get('notifications', []))
print('found_expired=', found_expired)

print('Finalizando reserva con rating...')
r2 = so.post(f'{BASE}/api/reservations/{rid}/finish', json={'rating':5, 'comment':'Buen servicio'})
print('finish resp', r2.status_code, r2.text)

print('Comprobando notificaciones finales...')
r3 = so.get(f'{BASE}/api/notifications').json()
print('after finish owner notifications:', r3.get('notifications'))

print('Comprobando notificaciones driver...')
r4 = s.get(f'{BASE}/api/notifications').json()
print('driver notifications:', r4.get('notifications'))

print('E2E script finalizado')
