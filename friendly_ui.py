"""Text-button navigation for MAX, persistent onboarding input state."""
import re
import time
from database import connect

MENU_EMPLOYEE = '🐾 Корсик — ваш помощник\n1. 🚀 Моя адаптация\n2. ❓ Задать вопрос'
MENU_HR = '👩‍💼 Кабинет HR\n1. 📋 Реестр сотрудников\n2. 📚 База знаний\n3. 🔑 Приглашения сотрудников\n4. 📊 Отчёт по адаптации сотрудников\n5. 📩 Обращения сотрудников'
MENU_ADMIN = '🛡 Кабинет администратора\n1. 📋 Реестр сотрудников\n2. 🔐 Заявки на доступ\n3. 📊 Статистика бота\n4. 📂 История загрузок'
WELCOME = '🐶 Привет! Я Корсик — твой помощник по адаптации в ПОЛИПЛАСТИКЕ.\n\nЧтобы начать, введи персональный одноразовый код приглашения, который тебе выдал HR.\n\nНет кода? Обратись к HR-специалисту.'
PHONE_PROMPT = 'Введи номер телефона. Например: 89991234567'
CODE_PROMPT = 'Введи персональный код.'
QUESTION_PROMPT = '❓ Напишите ваш вопрос одним сообщением.'

def init_ui():
    with connect() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS ui_states "
            "(max_user_id TEXT PRIMARY KEY, state TEXT NOT NULL)"
        )

        columns = {
            r["name"]
            for r in c.execute("PRAGMA table_info(ui_states)")
        }

        if "touched_at" not in columns:
            c.execute(
                "ALTER TABLE ui_states ADD COLUMN touched_at INTEGER"
            )


def get_state(uid):
    init_ui()

    with connect() as c:
        r = c.execute(
            "SELECT state, touched_at FROM ui_states "
            "WHERE max_user_id=?",
            (str(uid),)
        ).fetchone()

        if not r:
            return None

        if (
            r["touched_at"] is None
            or int(time.time()) - r["touched_at"] > 1800
        ):
            c.execute(
                "DELETE FROM ui_states WHERE max_user_id=?",
                (str(uid),)
            )
            return None

        return r["state"]


def set_state(uid, state):
    init_ui()

    with connect() as c:
        if state:
            c.execute(
                '''INSERT INTO ui_states(max_user_id,state,touched_at)
                   VALUES(?,?,?)
                   ON CONFLICT(max_user_id) DO UPDATE SET
                   state=excluded.state,
                   touched_at=excluded.touched_at''',
                (str(uid), state, int(time.time()))
            )
        else:
            c.execute(
                "DELETE FROM ui_states WHERE max_user_id=?",
                (str(uid),)
            )


def phone_like(text):
    return bool(re.fullmatch(r'[+\d\s()\-]{10,24}',text.strip()))

def menu(role):
    return {'employee':MENU_EMPLOYEE,'hr':MENU_HR,'admin':MENU_ADMIN}.get(role,WELCOME)
