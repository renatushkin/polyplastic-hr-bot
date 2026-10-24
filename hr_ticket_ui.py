"""Открытые обращения HR и периодические напоминания."""
import time
from database import connect
from hr_export import allowed_tags, tags_of

_last_check = 0


def open_tickets(uid, admin_id):
    permitted = allowed_tags(uid, admin_id)

    with connect() as c:
        records = c.execute("""
            SELECT t.id, t.employee_id, t.question,
                   COALESCE(s.name,e.name,'Сотрудник') AS name,
                   COALESCE(s.tags,e.tags,'[]') AS tags,
                   s.phone AS active_phone
            FROM tickets t
            LEFT JOIN employees e ON e.id=t.employee_id
            LEFT JOIN staff_registry s
              ON s.max_user_id=substr(t.employee_id,5)
             AND s.active=1 AND s.role='employee'
            WHERE t.status='open'
            ORDER BY t.id DESC
        """).fetchall()

    return [
        dict(r) for r in records
        if permitted is None
        or (
            r["active_phone"]
            and set(tags_of(r["tags"])) & permitted
        )
    ]


def can_reply(uid, admin_id, number):
    if not str(number).isdigit():
        return False

    try:
        return any(
            r["id"] == int(number)
            for r in open_tickets(uid, admin_id)
        )
    except PermissionError:
        return False


def tickets_text(uid, admin_id):
    try:
        records = open_tickets(uid, admin_id)
    except PermissionError:
        return "Нет доступа."

    if not records:
        return "✅ Открытых обращений нет."

    parts = [
        f"📩 Открытых обращений: {len(records)}",
        ""
    ]

    for r in records[:9]:
        question = " ".join(
            str(r["question"] or "").split()
        )

        parts.extend([
            f"👤 {r['name']} · обращение №{r['id']}",
            "❓ " + question[:180],
            f"✍️ Ответить №{r['id']}",
            ""
        ])

    if len(records) > 9:
        parts.append(
            "Показаны 9 последних обращений. "
            "Остальные сохраняются в базе."
        )

    return "\n".join(parts)


def _init():
    with connect() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS hr_ticket_reminders(
                ticket_id INTEGER NOT NULL,
                recipient_id TEXT NOT NULL,
                first_seen INTEGER NOT NULL,
                last_sent INTEGER,
                PRIMARY KEY(ticket_id,recipient_id)
            )
        """)


def remind(api, admin_id):
    global _last_check

    now = int(time.time())

    if now - _last_check < 60:
        return

    _last_check = now
    _init()

    with connect() as c:
        hrs = c.execute("""
            SELECT max_user_id FROM staff_registry
            WHERE role='hr' AND active=1
              AND max_user_id IS NOT NULL
        """).fetchall()

    recipients = [r["max_user_id"] for r in hrs]

    if admin_id:
        recipients.append(str(admin_id))

    for uid in dict.fromkeys(recipients):
        try:
            records = open_tickets(uid, admin_id)
        except PermissionError:
            continue

        for item in records:
            tid = item["id"]

            with connect() as c:
                c.execute("""
                    INSERT OR IGNORE INTO hr_ticket_reminders(
                        ticket_id,recipient_id,first_seen,last_sent
                    ) VALUES(?,?,?,NULL)
                """, (tid,str(uid),now))

                state = c.execute("""
                    SELECT first_seen,last_sent
                    FROM hr_ticket_reminders
                    WHERE ticket_id=? AND recipient_id=?
                """, (tid,str(uid))).fetchone()

            if now - state["first_seen"] < 3600:
                continue

            if (
                state["last_sent"] is not None
                and now - state["last_sent"] < 10800
            ):
                continue

            message = (
                f"🔔 Напоминание: обращение №{tid} "
                "ожидает ответа.\n"
                f"👤 {item['name']}\n"
                f"❓ {str(item['question'] or '')[:400]}\n"
                f"✍️ Ответить №{tid}"
            )

            try:
                api.send_message(uid, message)
            except Exception as exc:
                print(
                    "[HR] Не удалось отправить напоминание:",
                    type(exc).__name__,
                    flush=True
                )
                continue

            with connect() as c:
                c.execute("""
                    UPDATE hr_ticket_reminders
                    SET last_sent=?
                    WHERE ticket_id=? AND recipient_id=?
                """, (now,tid,str(uid)))

    with connect() as c:
        c.execute("""
            DELETE FROM hr_ticket_reminders
            WHERE ticket_id NOT IN (
                SELECT id FROM tickets WHERE status='open'
            )
        """)
