import json

from database import connect, add_message
from onboarding import get_current_step, submit_step_answer
from rag import answer_question
from hr import create_ticket


def ensure_employee(user_id):
    employee_id = f"max-{user_id}"

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

    return employee_id


def format_step(step):
    if step["done"]:
        return (
            "Адаптация завершена ✅\n"
            "Можно задать вопрос: /ask текст вопроса"
        )

    lines = [step["text"], ""]

    for number, label in enumerate(step["buttons"], start=1):
        lines.append(f"{number}. {label}")

    lines.append("\nОтветь номером или текстом варианта.")
    lines.append("Для вопроса: /ask текст вопроса")

    return "\n".join(lines)


def handle_question(employee_id, question):
    question = question.strip()

    if not question:
        return "Напиши вопрос после /ask."

    if len(question) > 2000:
        return "Сократи вопрос до 2000 символов."

    add_message(employee_id, "employee", question)

    result = answer_question(employee_id, question)
    answer = result.get("answer") or "Подтверждённый ответ не найден."

    sources = result.get("sources") or []

    if sources:
        answer += "\n\nИсточники:"

        for source in sources:
            name = source.get("source", "Без названия")
            location = source.get("location", "")
            answer += f"\n• {name}"

            if location:
                answer += f" — {location}"

    if result.get("needs_hr"):
        answer += "\n\nОтправку вопроса HR подключим следующим шагом."

    answer += "\n\nПродолжить адаптацию: /continue"

    add_message(employee_id, "bot", answer)

    return answer


def handle_message(user_id, text):
    employee_id = ensure_employee(user_id)
    text = text.strip()

    parts = text.split(maxsplit=1)
    command = parts[0].casefold() if parts else ""
    argument = parts[1] if len(parts) > 1 else ""

    if command == "/ask":
        return handle_question(employee_id, argument)

    if command == "/help":
        return (
            "/start — текущий шаг\n"
            "/continue — продолжить адаптацию\n"
            "/ask текст — вопрос по знаниям"
        )

    step = get_current_step(employee_id)

    if text.casefold() in ("/start", "/continue", "начать", "привет"):
        return format_step(step)

    if step["done"]:
        return format_step(step)

    selected = None

    if text.isascii() and text.isdigit() and len(text) <= 3:
        number = int(text)

        if 1 <= number <= len(step["buttons"]):
            selected = step["buttons"][number - 1]

    if selected is None:
        for label in step["buttons"]:
            if text.casefold() == label.casefold():
                selected = label
                break

    if selected is None:
        return "Выбери вариант или используй /ask.\n\n" + format_step(step)

    next_step = submit_step_answer(employee_id, selected)

    return format_step(next_step)