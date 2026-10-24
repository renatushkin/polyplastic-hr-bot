"""Requests for privileged access. A claimed phone is NOT identity verification."""
import os
from database import connect
from accounts import init_accounts, phone

PRIVILEGED = ('hr','admin')

def init_approvals():
    init_accounts()
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS role_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            max_user_id TEXT NOT NULL, phone TEXT NOT NULL,
            role TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT, reviewed_by TEXT,
            notified_at TEXT,
            UNIQUE(max_user_id,phone));
        CREATE INDEX IF NOT EXISTS ix_role_requests_status ON role_requests(status);
        ''')

def request_access(user_id, raw_phone):
    init_approvals()
    try: normalized = phone(raw_phone)
    except ValueError: return 'Неверный формат телефона. Пример: /request +79991234567'
    uid = str(user_id)
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        staff = c.execute('SELECT phone,name,role,max_user_id,active FROM staff_registry WHERE phone=?',(normalized,)).fetchone()
        if not staff or not staff['active'] or staff['role'] not in PRIVILEGED:
            return 'Заявка не может быть оформлена. Уточните данные у администратора.'
        if staff['max_user_id']:
            return 'Этот профиль уже привязан. Для переноса аккаунта обратитесь к администратору.'
        if c.execute('SELECT 1 FROM staff_registry WHERE max_user_id=?',(uid,)).fetchone():
            return 'Ваш MAX-аккаунт уже привязан к другому профилю.'
        existing=c.execute('SELECT id,status FROM role_requests WHERE max_user_id=? AND phone=?',(uid,normalized)).fetchone()
        if existing and existing['status']=='pending':
            return f"Заявка №{existing['id']} уже ожидает проверки."
        if existing:
            c.execute("UPDATE role_requests SET status='pending',created_at=CURRENT_TIMESTAMP,reviewed_at=NULL,reviewed_by=NULL,notified_at=NULL WHERE id=?",(existing['id'],))
            request_id=existing['id']
        else:
            request_id=c.execute('INSERT INTO role_requests(max_user_id,phone,role) VALUES(?,?,?)',(uid,normalized,staff['role'])).lastrowid
    return f'Заявка №{request_id} отправлена на проверку. До подтверждения привилегии закрыты.'

def pending():
    init_approvals()
    with connect() as c:
        return [dict(r) for r in c.execute('''SELECT r.id,r.max_user_id,r.phone,r.role,s.name
             FROM role_requests r JOIN staff_registry s ON s.phone=r.phone
             WHERE r.status='pending' ORDER BY r.id''')]

def mark_notified(request_id):
    with connect() as c:
        c.execute('UPDATE role_requests SET notified_at=CURRENT_TIMESTAMP WHERE id=?',(request_id,))

def unnotified():
    init_approvals()
    with connect() as c:
        return [dict(r) for r in c.execute('''SELECT r.id,r.max_user_id,r.phone,r.role,s.name
             FROM role_requests r JOIN staff_registry s ON s.phone=r.phone
             WHERE r.status='pending' AND r.notified_at IS NULL ORDER BY r.id''')]

def review(request_id, decision, admin_user_id):
    if decision not in ('approve','reject'): return 'Неизвестное действие.'
    init_approvals()
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        r=c.execute("SELECT * FROM role_requests WHERE id=? AND status='pending'",(request_id,)).fetchone()
        if not r:return 'Заявка не найдена или уже рассмотрена.'
        if r['max_user_id']==str(admin_user_id):return 'Нельзя одобрить собственную заявку.'
        if decision=='approve':
            staff=c.execute('SELECT * FROM staff_registry WHERE phone=? AND active=1',(r['phone'],)).fetchone()
            if not staff or staff['role']!=r['role'] or staff['max_user_id']:
                return 'Профиль изменён или уже привязан. Одобрение невозможно.'
            if c.execute('SELECT 1 FROM staff_registry WHERE max_user_id=?',(r['max_user_id'],)).fetchone():
                return 'Этот MAX ID уже принадлежит другому профилю.'
            c.execute('UPDATE staff_registry SET max_user_id=?,activated_at=CURRENT_TIMESTAMP,code_hash=NULL WHERE phone=? AND max_user_id IS NULL',(r['max_user_id'],r['phone']))
            if c.execute('SELECT changes()').fetchone()[0]!=1:return 'Не удалось привязать MAX ID.'
            c.execute("UPDATE role_requests SET status='rejected',reviewed_at=CURRENT_TIMESTAMP,reviewed_by=? WHERE phone=? AND status='pending' AND id!=?",(str(admin_user_id),r['phone'],request_id))
        c.execute('UPDATE role_requests SET status=?,reviewed_at=CURRENT_TIMESTAMP,reviewed_by=? WHERE id=?',('approved' if decision=='approve' else 'rejected',str(admin_user_id),request_id))
    return 'Одобрено' if decision=='approve' else 'Отклонено'

def revoke(phone_value):
    p=phone(phone_value)
    with connect() as c:
        c.execute('UPDATE staff_registry SET max_user_id=NULL,activated_at=NULL WHERE phone=?',(p,))
        return c.execute('SELECT changes()').fetchone()[0]
