import json
from database import connect, employee


def get_onboarding_id(employee_id, template_id):
    with connect() as c:
        r = c.execute(
            "SELECT id FROM employee_onboarding WHERE employee_id=? AND template_id=?",
            (employee_id, template_id),
        ).fetchone()
        return r["id"] if r else None


def ensure_onboarding(employee_id, template_id, start_date=None):
    with connect() as c:
        c.execute(
            """INSERT OR IGNORE INTO employee_onboarding(employee_id, template_id, start_date)
               VALUES(?,?,?)""",
            (employee_id, template_id, start_date),
        )
        return get_onboarding_id(employee_id, template_id)


def steps_for(employee_id, template_id):
    """Все релевантные шаги: без тега (audience_all=1) ИЛИ с пересечением тегов."""
    with connect() as c:
        onb = get_onboarding_id(employee_id, template_id)
        rows = c.execute(
            """
            SELECT s.id, s.step_key, s.step_order, s.message_text,
                   s.mandatory, s.attachment, s.audience_all,
                   COALESCE(es.status,'not_started') AS status,
                   es.answer_text
            FROM scenario_steps s
            JOIN employees e ON e.id = ?
            LEFT JOIN employee_step_state es
                   ON es.step_id = s.id AND es.onboarding_id = ?
            WHERE s.template_id = ?
              AND (
                    s.audience_all = 1
                 OR EXISTS (
                      SELECT 1 FROM json_each(s.employee_tags) jt
                      JOIN json_each(e.tags) et ON et.value = jt.value
                 )
              )
            ORDER BY s.step_order
            """,
            (employee_id, onb, template_id),
        ).fetchall()
        return [dict(r) for r in rows]


def next_mandatory_step(employee_id, template_id):
    with connect() as c:
        onb = get_onboarding_id(employee_id, template_id)
        r = c.execute(
            """
            SELECT s.*
            FROM scenario_steps s
            JOIN employees e ON e.id = ?
            LEFT JOIN employee_step_state es
                   ON es.step_id = s.id AND es.onboarding_id = ?
            WHERE s.template_id = ?
              AND s.mandatory = 1
              AND COALESCE(es.status,'not_started') IN ('not_started','in_progress')
              AND (
                    s.audience_all = 1
                 OR EXISTS (
                      SELECT 1 FROM json_each(s.employee_tags) jt
                      JOIN json_each(e.tags) et ON et.value = jt.value
                 )
              )
            ORDER BY s.step_order
            LIMIT 1
            """,
            (employee_id, onb, template_id),
        ).fetchone()
        return dict(r) if r else None


def start_step(employee_id, template_id, step_id):
    onb = get_onboarding_id(employee_id, template_id)
    with connect() as c:
        c.execute(
            """INSERT INTO employee_step_state(onboarding_id, step_id, status, sent_at)
               VALUES(?,?,'in_progress',CURRENT_TIMESTAMP)
               ON CONFLICT(onboarding_id, step_id) DO UPDATE
               SET status='in_progress', sent_at=CURRENT_TIMESTAMP""",
            (onb, step_id),
        )


def save_answer(employee_id, template_id, step_key, step_id, answer):
    onb = get_onboarding_id(employee_id, template_id)
    with connect() as c:
        c.execute(
            """UPDATE employee_step_state
               SET answer_text=?, status='completed', completed_at=CURRENT_TIMESTAMP
               WHERE onboarding_id=? AND step_id=?""",
            (answer, onb, step_id),
        )
        c.execute(
            """INSERT INTO answers(employee_id, step_id, answer)
               VALUES(?,?,?)
               ON CONFLICT(employee_id, step_id) DO UPDATE SET answer=excluded.answer""",
            (employee_id, step_key, answer),
        )


def next_step_after(employee_id, template_id, current_step_id, answer_value=None):
    """Переход: сначала step_conditions, иначе следующий по step_order."""
    with connect() as c:
        if answer_value is not None:
            r = c.execute(
                "SELECT next_step_id FROM step_conditions WHERE step_id=? AND answer_value=?",
                (current_step_id, answer_value),
            ).fetchone()
            if r:
                return r["next_step_id"]
        cur = c.execute(
            "SELECT step_order FROM scenario_steps WHERE id=?", (current_step_id,)
        ).fetchone()
        if not cur:
            return None
        r = c.execute(
            """SELECT id FROM scenario_steps
               WHERE template_id=? AND step_order > ?
               ORDER BY step_order LIMIT 1""",
            (template_id, cur["step_order"]),
        ).fetchone()
        return r["id"] if r else None


def reminders_due():
    with connect() as c:
        return [dict(r) for r in c.execute(
            """SELECT es.id AS state_id, es.step_id, es.onboarding_id, s.message_text
               FROM employee_step_state es
               JOIN scenario_steps s ON s.id = es.step_id
               WHERE es.status = 'in_progress'
                 AND es.sent_at <= datetime('now', '-1 day')
                 AND es.reminder_count < 2
               ORDER BY es.sent_at"""
        )]


def bump_reminder(state_id):
    with connect() as c:
        c.execute(
            "UPDATE employee_step_state SET reminder_count = reminder_count + 1 WHERE id=? AND reminder_count < 2",
            (state_id,),
        )


def upsert_profile(employee_id, max_user_id=None, position=None, department=None,
                   start_date=None, address="ты"):
    with connect() as c:
        c.execute(
            """INSERT INTO employee_profiles(employee_id, max_user_id, position, department, start_date, preferred_address)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(employee_id) DO UPDATE SET
                 max_user_id=COALESCE(excluded.max_user_id, max_user_id),
                 position=COALESCE(excluded.position, position),
                 department=COALESCE(excluded.department, department),
                 start_date=COALESCE(excluded.start_date, start_date),
                 preferred_address=excluded.preferred_address""",
            (employee_id, max_user_id, position, department, start_date, address),
        )


def open_ticket(employee_id, question):
    emp = employee(employee_id)
    with connect() as c:
        cur = c.execute(
            "INSERT INTO tickets(employee_id, hr_id, question, status) VALUES(?,?,?,'open')",
            (employee_id, emp.get("hr_id"), question),
        )
        return cur.lastrowid


def hr_tickets(hr_id):
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM tickets WHERE hr_id=? AND status='open' ORDER BY id",
            (hr_id,),
        )]


def answer_ticket(ticket_id, answer):
    with connect() as c:
        c.execute(
            "UPDATE tickets SET answer=?, status='answered' WHERE id=?",
            (answer, ticket_id),
        )