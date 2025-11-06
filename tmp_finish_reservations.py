import sys
sys.path.insert(0, '/workspaces/Tincar/TinCar')
from models import get_connection, finish_reservation
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id, status FROM reservations")
rows = cur.fetchall()
all_ids = [ (r[0], r[1]) for r in rows ]
print('Total reservas encontradas:', len(all_ids))
count=0
for rid, status in all_ids:
    if status in ('completed','cancelled'):
        continue
    ok = finish_reservation(rid, 0)
    print('Finalizando', rid, '(previo:', status, ')->', ok)
    count += 1
print('Reservas procesadas:', count)
# Ahora mostrar conteo por estado
cur.execute("SELECT status, COUNT(*) FROM reservations GROUP BY status")
for s,c in cur.fetchall():
    print('status=', s, 'count=', c)
conn.close()
