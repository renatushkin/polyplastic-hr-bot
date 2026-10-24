"""HR-issued one-time invitation codes for existing employees."""
import secrets
from accounts import init_accounts, hash_code, account, phone
from database import connect


def authorized_issuer(user_id):
    acc = account(user_id)
    return bool(acc and acc.get('role') in ('hr', 'admin'))


def available_employees(user_id):
    if not authorized_issuer(user_id):
        return None
    init_accounts()
    with connect() as c:
        rows = c.execute("""
            SELECT name, phone FROM staff_registry
            WHERE active=1 AND role='employee' AND max_user_id IS NULL
            ORDER BY name LIMIT 30
        """).fetchall()
    return [dict(r) for r in rows]


def issue_invite(user_id, supplied_phone):
    if not authorized_issuer(user_id):
        return {'error': 'Нет доступа к выдаче приглашений.'}
    try:
        number = phone(supplied_phone)
    except ValueError:
        return {'error': 'Неверный формат номера.'}
    init_accounts()
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute("""
            SELECT name, role, max_user_id FROM staff_registry
            WHERE phone=? AND active=1
        """, (number,)).fetchone()
        if not row:
            return {'error': 'Сотрудник не найден в реестре.'}
        if row['role'] != 'employee':
            return {'error': 'Выдавать приглашения можно только обычным сотрудникам.'}
        if row['max_user_id']:
            return {'error': 'Аккаунт уже привязан. Для переноса обратитесь к администратору.'}
        code = secrets.token_urlsafe(18)
        c.execute("""
            UPDATE staff_registry SET code_hash=?
            WHERE phone=? AND active=1 AND role='employee' AND max_user_id IS NULL
        """, (hash_code(code), number))
        if c.execute('SELECT changes()').fetchone()[0] != 1:
            raise RuntimeError('Не удалось создать приглашение.')
    return {'name': row['name'], 'phone': number, 'code': code}
