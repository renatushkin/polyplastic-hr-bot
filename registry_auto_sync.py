"""Автоматическая синхронизация корпоративного Excel и уведомления HR."""
import json
import os
import secrets
import threading
import time
from pathlib import Path

from accounts import read_registry, hash_code
from database import connect

REGISTRY = Path(__file__).parent / 'data/registry/employees.xlsx'
ROUTES = Path(__file__).parent / 'data/registry/hr_routes.json'
TICK_SECONDS = 60
_started = False
_lock = threading.Lock()


def _initialize():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS registry_invite_queue (
            phone TEXT PRIMARY KEY,
            delivered INTEGER NOT NULL DEFAULT 0,
            assigned_hr TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            delivered_at TEXT
        )""")


def synchronize():
    rows = read_registry(REGISTRY)

    if not rows:
        raise ValueError('Пустой Excel: синхронизация отменена')

    if any(r['role'] != 'employee' for r in rows):
        raise ValueError(
            'В корпоративном Excel должна быть роль employee. '
            'Права HR назначает администратор отдельно.'
        )

    incoming = {r['phone'] for r in rows}
    _initialize()
    added = 0
    removed = 0

    with connect() as c:
        c.execute('BEGIN IMMEDIATE')

        old = c.execute(
            "SELECT phone FROM staff_registry "
            "WHERE active=1 AND role='employee'"
        ).fetchall()

        missing = [
            r['phone'] for r in old
            if r['phone'] not in incoming
        ]

        if len(old) >= 5 and len(missing) * 4 > len(old) * 3:
            raise ValueError(
                f'Из Excel исчезли {len(missing)} из {len(old)} '
                'сотрудников. Проверьте полный реестр.'
            )

        for r in rows:
            former = c.execute(
                'SELECT role, active, max_user_id '
                'FROM staff_registry WHERE phone=?',
                (r['phone'],)
            ).fetchone()

                                                                     
            if former and former['role'] != 'employee':
                continue

            restored = (
                (former is None or former['active'] == 0)
                and (former is None or former['role'] == 'employee')
            )

            c.execute("""
                INSERT INTO staff_registry(
                    phone, name, role, tags, start_date,
                    manager_phone, code_hash,
                    max_user_id, activated_at, active
                )
                VALUES(?,?,'employee',?,?,?,NULL,NULL,NULL,1)
                ON CONFLICT(phone) DO UPDATE SET
                    name=excluded.name,
                    tags=excluded.tags,
                    start_date=excluded.start_date,
                    manager_phone=excluded.manager_phone,
                    active=1,
                    code_hash=CASE
                        WHEN staff_registry.active=0 THEN NULL
                        ELSE staff_registry.code_hash
                    END,
                    max_user_id=CASE
                        WHEN staff_registry.active=0 THEN NULL
                        ELSE staff_registry.max_user_id
                    END,
                    activated_at=CASE
                        WHEN staff_registry.active=0 THEN NULL
                        ELSE staff_registry.activated_at
                    END
            """, (
                r['phone'], r['name'],
                json.dumps(r['tags'], ensure_ascii=False),
                r['start'], r['manager']
            ))

            if restored:
                added += 1
                c.execute("""
                    INSERT INTO registry_invite_queue(
                        phone, delivered, assigned_hr, delivered_at
                    )
                    VALUES(?,0,NULL,NULL)
                    ON CONFLICT(phone) DO UPDATE SET
                        delivered=0,
                        assigned_hr=NULL,
                        delivered_at=NULL,
                        created_at=CURRENT_TIMESTAMP
                """, (r['phone'],))

            if former and former['active'] and former['max_user_id']:
                eid = 'max-' + former['max_user_id']

                c.execute(
                    'UPDATE employees SET name=?, tags=? WHERE id=?',
                    (
                        r['name'],
                        json.dumps(r['tags'], ensure_ascii=False),
                        eid
                    )
                )

                if r['start'] and former['role'] == 'employee':
                    c.execute("""
                        INSERT INTO onboarding_profiles(
                            employee_id, start_date, mode
                        )
                        VALUES(?,?,'calendar')
                        ON CONFLICT(employee_id) DO UPDATE SET
                            start_date=excluded.start_date,
                            mode='calendar'
                    """, (eid, r['start']))

        for number in missing:
            c.execute("""
                UPDATE staff_registry
                SET active=0,
                    code_hash=NULL,
                    max_user_id=NULL,
                    activated_at=NULL
                WHERE phone=?
                  AND role='employee'
                  AND active=1
            """, (number,))

            c.execute(
                'DELETE FROM registry_invite_queue WHERE phone=?',
                (number,)
            )
            removed += 1

    if added or removed:
        print(
            f'[РЕЕСТР] Добавлено: {added}; '
            f'отключено: {removed}',
            flush=True
        )

    return added, removed


def _recipient(row, admin_getter):
    with connect() as c:
        hrs = c.execute("""
            SELECT phone, max_user_id
            FROM staff_registry
            WHERE role='hr'
              AND active=1
              AND max_user_id IS NOT NULL
        """).fetchall()

    by_phone = {
        r['phone']: r['max_user_id']
        for r in hrs
    }

    routes = (
        json.loads(ROUTES.read_text(encoding='utf-8'))
        if ROUTES.exists() else {}
    )

    choices = {
        by_phone[routes[tag]]
        for tag in json.loads(row['tags'])
        if tag in routes and routes[tag] in by_phone
    }

    if len(choices) == 1:
        return choices.pop()

    if not choices and len(hrs) == 1:
        return hrs[0]['max_user_id']

    try:
        admin_id = admin_getter()
    except (NameError, TypeError):
        admin_id = None

    return str(admin_id) if admin_id else None


def notify(api, admin_getter):
    _initialize()

    with connect() as c:
        pending = c.execute("""
            SELECT s.phone, s.name, s.tags,
                   s.start_date, s.max_user_id
            FROM registry_invite_queue q
            JOIN staff_registry s ON s.phone=q.phone
            WHERE q.delivered=0
              AND s.active=1
              AND s.role='employee'
              AND s.max_user_id IS NULL
            ORDER BY q.created_at
            LIMIT 15
        """).fetchall()

    for row in pending:
        recipient = _recipient(row, admin_getter)

        if not recipient:
            print(
                '[РЕЕСТР] Ожидается назначение HR',
                flush=True
            )
            continue

        code = secrets.token_urlsafe(18)

        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            result = c.execute("""
                UPDATE staff_registry
                SET code_hash=?
                WHERE phone=?
                  AND active=1
                  AND role='employee'
                  AND max_user_id IS NULL
            """, (hash_code(code), row['phone']))

            if result.rowcount != 1:
                continue

        try:
            tags = ', '.join(
                json.loads(row['tags'])
            ) or 'не указаны'

            bot_url = os.getenv(
                'KORSIK_BOT_URL', ''
            ).strip()

            message = (
                '🆕 Новый сотрудник в реестре!\n\n'
                f'ФИО: {row["name"]}\n'
                f'📱 Телефон для связи: {row["phone"]}\n'
                f'Подразделение: {tags}\n'
                f'Дата выхода: '
                f'{row["start_date"] or "не указана"}\n'
                f'Код активации: {code}\n'
                + (f'Бот: {bot_url}\n' if bot_url else '')
                + '\nПередайте код сотруднику после проверки '
                  'его личности. Код одноразовый. '
                  'Не публикуйте его в общих чатах.'
            )

            api.send_message(int(recipient), message)

        except Exception as e:
            print(
                '[РЕЕСТР] Ошибка доставки, будет повтор:',
                type(e).__name__,
                flush=True
            )
            continue

        with connect() as c:
            c.execute("""
                UPDATE registry_invite_queue
                SET delivered=1,
                    assigned_hr=?,
                    delivered_at=CURRENT_TIMESTAMP
                WHERE phone=?
            """, (str(recipient), row['phone']))

        print(
            '[РЕЕСТР] HR получил приглашение:',
            row['name'],
            flush=True
        )


def start(api, admin_getter=lambda: None):
    global _started

    with _lock:
        if _started:
            return
        _started = True

    def worker():
        time.sleep(3)

        while True:
            try:
                synchronize()
                notify(api, admin_getter)
            except Exception as e:
                print(
                    '[РЕЕСТР] Синхронизация отложена:',
                    str(e),
                    flush=True
                )

            time.sleep(TICK_SECONDS)

    threading.Thread(
        target=worker,
        name='korsik-registry-watch',
        daemon=True
    ).start()

    print(
        '[РЕЕСТР] Автоматическая синхронизация включена',
        flush=True
    )
