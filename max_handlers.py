"""Команды сотрудника. Файлы базы данных Анны не меняем."""
import json
from database import connect, add_message
from onboarding import get_current_step, submit_step_answer, reset_progress, set_tag, set_schedule, STEPS
from rag import answer_question
from hr import create_ticket


def ensure_employee(user_id):
    employee_id = f"max-{user_id}"
    with connect() as c:
        c.execute("INSERT OR IGNORE INTO employees (id,name,tags,hr_id) VALUES (?,?,?,?)",
                  (employee_id, f"Сотрудник MAX {user_id}", json.dumps(["GTP"]), "hr-demo"))
    return employee_id


def format_step(step):
    if step["done"]:
        return "Адаптация завершена ✅\n\nВопрос можно задать через главное меню."
    if step.get("waiting"):
        return "⏳ " + step["text"]
    lines = [f"📅 {step.get('time', '')} | Этап {step['index']+1}/{len(STEPS)}", step["text"], ""]
    for number, label in enumerate(step["buttons"], 1):
        lines.append(f"{number}. {label}")
    lines.extend(["", "Выбери кнопку или отправь номер.", "Чтобы задать вопрос, открой главное меню."])
    return "\n".join(lines)


def handle_question(employee_id, question):
    question = question.strip()
    if not question:
        return "Напиши вопрос после /ask. Например: /ask Как оформить отпуск?"
    if len(question) > 2000:
        return "Сократи вопрос до 2000 символов."
    add_message(employee_id, "employee", question)
    result = answer_question(employee_id, question)
    answer = result.get("answer") or "Подтверждённый ответ не найден."
    if result.get("needs_hr"):
        ticket_id = create_ticket(employee_id, question)
        answer += f"\n\n✅ Обращение №{ticket_id} зарегистрировано и будет направлено HR."
    else:
        sources = result.get("sources") or []
        if sources:
            answer += "\n\nИсточники:\n" + "\n".join(
                f"• {s.get('source', 'Документ')} — {s.get('location', '')}" for s in sources)
    answer += "\n\n1. 📋 Моя адаптация"
    add_message(employee_id, "bot", answer)
    return answer


def handle_message(user_id, text):
    employee_id = ensure_employee(user_id)
    text = text.strip()
    parts = text.split(maxsplit=1)
    command = parts[0].casefold() if parts else ""
    argument = parts[1] if len(parts) > 1 else ""
    if command in ('/tag','/startdate'):
        return 'Тег и дата выхода назначаются HR через реестр сотрудников.'
    if command == "/mode":
        if argument.strip().lower()=="demo":
            from datetime import date
            from korsik_demo_days import restart
            return restart(employee_id)
        return "Режимы: /mode demo; /startdate ГГГГ-ММ-ДД — календарный режим с автоуведомлениями"
    if command == "/startdate":
        try:return format_step(set_schedule(employee_id,argument.strip()))
        except ValueError:return "Укажи дату: /startdate 2026-10-24"
    if command == "/reset":
        return 'Реальный прогресс не сбрасывается через чат. Для демонстрации используй /mode demo.'
    if command == "/tag":
        if not argument.strip():return "Выбери тег: /tag GTP, /tag GrPP, /tag Luzhniki"
        return format_step(set_tag(employee_id,argument.strip()))
    if command == "/myid":return f"Ваш MAX ID: {user_id}"
                             
    if command == "/progress":
        from datetime import date

        current = get_current_step(employee_id)
        total = len(STEPS)

        if not total:
            return "📈 Прогресс пока недоступен."

        completed = (
            total
            if current.get("done")
            else max(0, min(int(current.get("index", 0)), total))
        )

        percent = round(completed * 100 / total)
        filled = round(percent / 10)
        bar = "🟩" * filled + "⬜" * (10 - filled)

        lines = [
            "📈 Мой прогресс адаптации",
            "",
            bar,
            f"✅ Пройдено этапов: {completed} из {total}",
            f"📊 Выполнено: {percent}%",
            "",
        ]

        if current.get("done"):
            lines.append("🎉 Поздравляем! Адаптация завершена.")

        elif current.get("waiting"):
            due = current.get("due")

            if due:
                try:
                    formatted = date.fromisoformat(due).strftime(
                        "%d.%m.%Y"
                    )
                except ValueError:
                    formatted = due

                lines.append(
                    f"⏳ Следующий этап откроется {formatted}."
                )
            else:
                lines.append(
                    "⏳ Следующий этап пока недоступен."
                )

        else:
            lines.extend([
                f"📍 Текущий этап: {completed + 1} из {total}",
                "▶️ Можно продолжать адаптацию.",
            ])

        lines.extend([
            "",
            "Нажми «📋 Моя адаптация», чтобы "
            "вернуться к текущему этапу.",
            "1. 📋 Моя адаптация",
        ])

        return "\n".join(lines)

    if command == "/status":
        s=get_current_step(employee_id)
        return "Адаптация завершена" if s["done"] else f"Этап {s['index']+1}/{len(STEPS)}; тег можно сменить: /tag GTP"
    if command == "/ask":
        return handle_question(employee_id, argument)
    if command == "/help":
        return "/start — адаптация\n/continue — продолжить\n/reset — начать заново\n/tag GTP — сменить маршрут\n/status — прогресс\n/startdate 2026-10-24 — календарь\n/mode demo — ускоренный показ\n/ask вопрос — спросить у бота или HR"
    step = get_current_step(employee_id)
                                                         
    if text.casefold() in ("/start", "/continue", "привет"):
        report = handle_message(user_id, '/progress')
        if step.get('waiting'):
            return report + '\n\n' + format_step(step) + '\n\n1. ▶️ Запустить демо'
        return report + '\n\n' + format_step(step) + '\n\n1. ▶️ Запустить демо'
    if step["done"]:
        return format_step(step)
    selected = None
    if text.isascii() and text.isdigit() and len(text) <= 3:
        number = int(text)
        if 1 <= number <= len(step["buttons"]):
            selected = step["buttons"][number - 1]
    if selected is None:
        selected = next((label for label in step["buttons"] if text.casefold() == label.casefold()), None)
    if selected is None:
        return "Выбери вариант ответа кнопкой.\n\n" + format_step(step)
    return format_step(submit_step_answer(employee_id, selected))
