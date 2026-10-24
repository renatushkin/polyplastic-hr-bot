"""Локальная перевыдача кода сотрудника. Запускать только администратору."""

import sys as _korsik_sys
from pathlib import Path as _korsik_Path
_korsik_root = _korsik_Path(__file__).resolve().parent.parent
if str(_korsik_root) not in _korsik_sys.path:
    _korsik_sys.path.insert(0, str(_korsik_root))
import getpass
import secrets
from accounts import init_accounts, phone, hash_code
from database import connect

def main():
    init_accounts()

    raw = input("Телефон тестового сотрудника из Excel: ").strip()

    try:
        number = phone(raw)
    except ValueError:
        print("❌ Неверный формат телефона.")
        return

    with connect() as c:
        row = c.execute(
            "SELECT name, role, max_user_id FROM staff_registry WHERE phone=? AND active=1",
            (number,)
        ).fetchone()

    if not row:
        print("❌ Сотрудник не найден в реестре.")
        return

    if row["role"] != "employee":
        print("❌ HR, руководителей и администраторов здесь сбрасывать нельзя.")
        return

    print(f"\nНайден сотрудник: {row['name']}")
    print(f"Текущий MAX ID: {row['max_user_id'] or 'не привязан'}")
    confirmation = input("Перевыпустить код и отвязать MAX? Напиши ДА: ").strip()

    if confirmation != "ДА":
        print("Отменено. Ничего не изменено.")
        return

    code = secrets.token_urlsafe(12)

    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        c.execute(
            """UPDATE staff_registry
               SET max_user_id=NULL,
                   activated_at=NULL,
                   code_hash=?
               WHERE phone=? AND role='employee' AND active=1""",
            (hash_code(code), number)
        )

        if c.execute("SELECT changes()").fetchone()[0] != 1:
            raise RuntimeError("Не удалось обновить сотрудника.")

    print("\n✅ Привязка сброшена. Новый одноразовый код:")
    print(code)
    print("\n⚠️ Сохрани код и не отправляй его в общий чат.")
    print("ФИО, телефон, роль и теги сотрудника сохранены.")

if __name__ == "__main__":
    main()
