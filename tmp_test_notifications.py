import requests
from pprint import pprint

BASE = 'http://127.0.0.1:5000'
users = [ ('juan1@gmail.com','123456'), ('juan2@gmail.com','123456') ]

for email,password in users:
    s = requests.Session()
    print('\n===', email, '===')
    # login
    r = s.post(BASE+'/login', data={'email':email,'password':password}, allow_redirects=True, timeout=5)
    print('login status', r.status_code)
    # get notifications before
    try:
        r = s.get(BASE+'/api/notifications', timeout=5)
        print('GET before:', r.status_code)
        pprint(r.json())
    except Exception as e:
        print('GET before error', e)
    # clear
    try:
        r = s.post(BASE+'/api/notifications/clear', timeout=5)
        print('POST clear:', r.status_code)
        pprint(r.json())
    except Exception as e:
        print('POST clear error', e)
    # get after
    try:
        r = s.get(BASE+'/api/notifications', timeout=5)
        print('GET after:', r.status_code)
        pprint(r.json())
    except Exception as e:
        print('GET after error', e)
