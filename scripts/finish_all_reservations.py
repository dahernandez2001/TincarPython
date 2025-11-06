import sqlite3
from pathlib import Path
DB = Path(__file__).resolve().parents[1] / 'TinCar' / 'database' / 'tincar.db'
conn = sqlite3.connect(str(DB))
cur = conn.cursor()
print('DB:', DB)
print('Antes:')
cur.execute("SELECT status, COUNT(*) FROM reservations GROUP BY status")
for s,c in cur.fetchall():
    print(s, c)
cur.execute("UPDATE reservations SET status='completed' WHERE status NOT IN ('completed','cancelled')")
conn.commit()
# Reactivar parkings referenciados
cur.execute('SELECT DISTINCT parking_id FROM reservations')
for (pid,) in cur.fetchall():
    if pid is None: continue
    try:
        cur.execute('UPDATE parkings SET active = 1, occupied_since = NULL WHERE id = ?', (pid,))
    except Exception:
        pass
conn.commit()
print('\nDespués:')
cur.execute("SELECT status, COUNT(*) FROM reservations GROUP BY status")
for s,c in cur.fetchall():
    print(s, c)
conn.close()
