import json

from database import connect
from onboarding import get_current_step, submit_step_answer


def format_step(step):
    if step["done"]:
        return (
            "Демонстрационный блок адаптации завершён ✅\n"
            "Прогресс сохранён."
        )

    lines = [step["text"], ""]

    for number, label in enumerate(step["buttons"], start=1):
        lines.append(f"{number}. {label}")

    lines.extend([
        "",
        "Отправь номер ответа или текст варианта.",
    ])

    return "\n".join(lines)


def handle_message(user_id, text):
    employee_id = f"max-{user_id}"

    # Тестовый профиль. Позже заменим привязкой к реальному сотруднику.
    with connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO employees
                (id, name, tags, hr_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                employee_id,
                f"Тестовый сотрудник MAX {user_id}",
                json.dumps(["GTP"]),
                "hr-demo",
            ),
        )

    step = get_current_step(employee_id)
    text = text.strip()

    if text.casefold() in (
        "/start",
        "/continue",
        "начать",
        "привет",
    ):
        return format_step(step)

    if step["done"]:
        return format_step(step)

    selected = None

    if text.isascii() and text.isdigit():
        number = int(text)

        if 1 <= number <= len(step["buttons"]):
            selected = step["buttons"][number - 1]

    if selected is None:
        selected = next(
            (
                label
                for label in step["buttons"]
                if text.casefold() == label.casefold()
            ),
            None,
        )

    if selected is None:
        return (
            "Выбери вариант текущего шага.\n\n"
            + format_step(step)
        )

    next_step = submit_step_answer(employee_id, selected)
    return format_step(next_step)