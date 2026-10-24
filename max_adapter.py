                             
"""MAX long polling + кнопки + обмен сообщениями с HR."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import ssl
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_settings():
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
    token = os.getenv("MAX_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Укажи MAX_BOT_TOKEN в .env")
    return token, os.getenv("MAX_API_URL", "https://platform-api2.max.ru").rstrip("/")


def make_keyboard(text):
    import re

    buttons = []

    for line in text.splitlines():
        line = line.strip()
        parts = line.split(". ", 1)

        if (
            len(parts) == 2
            and parts[0].isdigit()
            and parts[1].strip()
        ):
            buttons.append([
                {
                    "type": "message",
                    "text": parts[1].strip()[:128]
                }
            ])

        elif re.match(r'^\d+\. (?:Удалить|Заменить) №\d+ — ', line):
            action = re.search(r'(?:Удалить|Заменить) №\d+', line).group(0)
            buttons.append([{"type": "message", "text": action}])

        elif line.startswith((
            "✍️ Ответить №",
            "Одобрить №",
            "Отклонить №",
            "🔑 Выдать код: ",
            "📄 Приглашения — страница ",
            "▶️ Запустить демо",
            "▶️ Запустить демо заново",
            "➡️ Следующий день",
            "⏭️ Пропустить вопрос",
            "📤 Загрузить документ"
        )):
            buttons.append([
                {
                    "type": "message",
                    "text": line[:128]
                }
            ])

    if "Привет! Я Корсик" in text:
        buttons.insert(0, [{
            "type": "message",
            "text": "👩‍💼 Я HR или руководитель"
        }])

    ticket = re.search(
        r"Новый вопрос HR, обращение №(\d+)",
        text
    )

    if ticket:
        buttons.insert(0, [{
            "type": "message",
            "text": "✍️ Ответить №" + ticket.group(1)
        }])

    if text.startswith("✍️ Напишите ответ"):
        buttons.insert(0, [{
            "type": "message",
            "text": "❌ Отменить ответ"
        }])

    buttons = buttons[:11]

    buttons.append([{
        "type": "message",
        "text": "🏠 Главное меню"
    }])

    return [{
        "type": "inline_keyboard",
        "payload": {"buttons": buttons}
    }]





                            
def _humanize_hr_notice(text):
    """Добавляет ФИО из базы и убирает инструкции со слешем."""
    import re
    from database import connect

    if "Новый вопрос HR, обращение №" not in text:
        return text

    def employee_name(match):
        uid = match.group(2)

        try:
            with connect() as c:
                row = c.execute(
                    "SELECT name FROM staff_registry "
                    "WHERE max_user_id=? AND role='employee'",
                    (uid,)
                ).fetchone()

                if not row:
                    row = c.execute(
                        "SELECT name FROM employees WHERE id=?",
                        ("max-" + uid,)
                    ).fetchone()

            if row and row["name"]:
                return match.group(1) + row["name"]
        except Exception:
            pass

        return match.group(1) + "сотрудник MAX " + uid

    text = re.sub(
        r"(?m)^(Сотрудник:\s*)max-(\d+)",
        employee_name,
        text
    )

    text = re.sub(
        r"(?m)^Ответить:\s*/reply\s+\d+[^\n]*",
        "Нажмите кнопку ниже, чтобы ответить сотруднику.",
        text
    )

    return text

class MaxAPI:
    def __init__(self, token, base_url):
        self.token, self.base_url = token, base_url

    def request(self, method, path, params=None, body=None):
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {"Authorization": self.token}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=35) as response:
                    return json.load(response)
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt==2:raise
                time.sleep(2*(attempt+1))

    def get_updates(self, marker=None):
        params = {"timeout": 25, "limit": 20, "types": "message_created,bot_started"}
        if marker is not None:
            params["marker"] = marker
        return self.request("GET", "/updates", params=params)

    def send_message(self, user_id, text):
        text = _humanize_hr_notice(text)
        body = {"text": text[:4000]}
        keyboard = make_keyboard(text)
        if keyboard:
            body["attachments"] = keyboard
        return self.request("POST", "/messages", params={"user_id": user_id}, body=body)


    def send_file(self, user_id, path, caption='Шаблон реестра сотрудников'):
        """MAX file upload: get upload URL, POST binary, then attach token."""
        info = self.request('POST', '/uploads', params={'type': 'file'})
        upload_url = info.get('url') or info.get('upload_url')
        if not upload_url or not upload_url.startswith('https://'):
            raise RuntimeError('MAX не предоставил адрес загрузки файла')
        from urllib.parse import urlparse
        parsed = urlparse(upload_url)
        hostname = (parsed.hostname or '').lower()

                                                                 
                                                              
        print("MAX upload hostname:", hostname)

                                           
        if parsed.scheme != 'https' or not hostname:
            raise RuntimeError('MAX вернул некорректный адрес загрузки')

                                                  
                                                   
                                                              
                                                 
        allowed_hosts = (
            hostname == "max.ru"
            or hostname.endswith(".max.ru")
            or hostname == "fu.oneme.ru"
        )

        if not allowed_hosts:
            raise RuntimeError(
                "Недопустимый сервер загрузки MAX: " + hostname
            )
        data = Path(path).read_bytes()
        boundary = '----KorsikFileBoundary'
        filename = Path(path).name
        payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="data"; filename="{filename}"\r\nContent-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n'.encode() + data + f'\r\n--{boundary}--\r\n'.encode())
        req = urllib.request.Request(upload_url, data=payload, headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}, method='POST')
        with urllib.request.urlopen(req, timeout=45) as response:
            uploaded = json.load(response)
        token = uploaded.get('token') or (uploaded.get('file') or {}).get('token')
        if not token:
            raise RuntimeError('MAX не вернул токен загруженного файла')
        return self.request('POST','/messages',params={'user_id':user_id},body={'text':caption,'attachments':[{'type':'file','payload':{'token':token}}]})


def hr_command(api, hr_id, text):
    """HR видит только свои команды; номер HR задаётся в .env."""
    from database import connect
    from hr import reply_ticket
    if text.strip() in ("/start", "/help", "/continue"):
        return "👤 Меню HR\n/tickets — открытые обращения\n/reply НОМЕР Текст — ответ сотруднику\n/myid — мой MAX ID"
    if text.strip() == "/tickets":
        with connect() as c:
            tickets = c.execute("SELECT id, employee_id, question FROM tickets WHERE status='open' ORDER BY id DESC LIMIT 15").fetchall()
        if not tickets:
            return "Открытых обращений нет."
        return "Открытые обращения:\n" + "\n\n".join(
            f"№{t['id']} от {t['employee_id']}: {t['question']}" for t in tickets)
    if text.startswith("/reply "):
        parts = text.split(maxsplit=2)
        if len(parts) < 3 or not parts[1].isdigit() or not parts[2].strip():
            return "Формат: /reply НОМЕР Текст ответа"
        ticket_id, answer = int(parts[1]), parts[2].strip()
        with connect() as c:
            ticket = c.execute("SELECT employee_id, status FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if not ticket or ticket["status"] != "open":
            return "Обращение не найдено или уже закрыто."
                                                                                                
        employee_id = ticket["employee_id"]
        if not employee_id.startswith("max-"):
            return "У обращения нет MAX-получателя."
        api.send_message(employee_id[4:], f"👤 Ответ HR по обращению №{ticket_id}:\n\n{answer}")
        reply_ticket(ticket_id, answer)
        return f"✅ Ответ по обращению №{ticket_id} отправлен сотруднику."
    return "HR-команды: /tickets, /reply НОМЕР Текст ответа, /myid"


def notify_hr(api, hr_id, notified):
    if not hr_id:
        return
    from database import connect
    with connect() as c:
        tickets = c.execute("SELECT id, employee_id, question FROM tickets WHERE status='open' ORDER BY id").fetchall()
    for ticket in tickets:
        ticket_id = ticket["id"]
        if ticket_id in notified:
            continue
        api.send_message(hr_id, f"📩 Новый вопрос HR, обращение №{ticket_id}\n"
                                   f"Сотрудник: {ticket['employee_id']}\n\n{ticket['question']}\n\n"
                                   f"Ответить: /reply {ticket_id} Текст ответа")
        notified.add(ticket_id)
        print(f"Обращение №{ticket_id} отправлено HR")


def role_command(api, user_id, text, acc):
    from accounts import tickets_for_hr
    from database import connect
    from hr import reply_ticket
    role=acc['role']; cmd=text.strip()
    if cmd in ('/start','/help'):
        return '👤 '+role.upper()+'\n/tickets — обращения HR\n/reply НОМЕР ответ — ответить сотруднику\n/myid — мой MAX ID'
    if cmd=='/tickets' and role in ('hr','admin'):
        rows=tickets_for_hr()
        return 'Открытые обращения:\n'+('\n\n'.join(f"№{r['id']} от {r['employee_id']}: {r['question']}" for r in rows) or 'Нет обращений.')
    if cmd.startswith('/reply ') and role in ('hr','admin'):
        parts=cmd.split(maxsplit=2)
        if len(parts)!=3 or not parts[1].isdigit() or not parts[2].strip():return 'Формат: /reply НОМЕР ответ'
        with connect() as c:
            t=c.execute('SELECT employee_id,status FROM tickets WHERE id=?',(int(parts[1]),)).fetchone()
        if not t or t['status']!='open':return 'Обращение не найдено или закрыто.'
        if not t['employee_id'].startswith('max-'):return 'Сотрудник не привязан к MAX.'
        api.send_message(t['employee_id'][4:],f"👤 Ответ HR по обращению №{parts[1]}:\n\n{parts[2]}")
        reply_ticket(int(parts[1]),parts[2]);return 'Ответ отправлен.'
    return 'Команда недоступна для вашей роли. /help'


def run():
    token, base_url = load_settings()
    from database import init_db, connect
    from accounts import init_accounts, account, activate
    from approvals import init_approvals, request_access, unnotified, mark_notified, pending, review, revoke
    from staff_invites import available_employees, issue_invite
    from hr_ticket_ui import tickets_text, can_reply, remind
    from max_handlers import handle_message
    from friendly_ui import init_ui, get_state, set_state, menu, WELCOME, CODE_PROMPT, QUESTION_PROMPT
    from scheduler import init_scheduler, tick
    from registry_upload import init_registry_upload, registry_view, attachment_url, stage, confirm, cancel
    init_db();init_accounts();init_scheduler();init_approvals();init_ui();init_registry_upload()
    api=MaxAPI(token,base_url)
                                  
    from registry_auto_sync import start as _start_registry_watcher
    _start_registry_watcher(api, lambda: admin_id)
    marker=None;seen_messages=set();notified={}
    admin_id=os.getenv('ADMIN_MAX_USER_ID','').strip()
    if not admin_id: print('ВНИМАНИЕ: ADMIN_MAX_USER_ID не задан — заявки нельзя одобрить',flush=True)
    print('Корсик запущен: меню с кнопками и автоуведомления включены',flush=True)
    while True:
        try:
            tick(api)
            try:
                remind(api, admin_id)
            except Exception as exc:
                print('[HR REMINDER]', type(exc).__name__, flush=True)
            response=api.get_updates(marker)
            for update in response.get('updates',[]):
                                            
                if update.get("update_type") in (
                    "bot_started", "message_created"
                ):
                    print(
                        "[MAX] Событие:",
                        update.get("update_type"),
                        flush=True
                    )

                if update.get("update_type") == "bot_started":
                    started_user = (
                        (update.get("user") or {}).get("user_id")
                        or update.get("chat_id")
                    )

                    if started_user is not None:
                        started_acc = account(started_user)
                        is_owner = bool(
                            admin_id
                            and str(started_user) == admin_id
                        )

                        set_state(
                            started_user,
                            None if started_acc or is_owner else "code"
                        )

                        welcome = (
                            menu(started_acc["role"])
                            if started_acc
                            else menu("admin") if is_owner
                            else WELCOME
                        )

                        api.send_message(started_user, welcome)
                        print(
                            "[MAX] Приветствие отправлено после «Начать»",
                            flush=True
                        )

                    continue

                if update.get("update_type") != "message_created":
                    continue
                msg=update.get('message') or {}
                sender=msg.get('sender') or {};recipient=msg.get('recipient') or {};body=msg.get('body') or {}
                if recipient.get('chat_type')!='dialog' or sender.get('is_bot'):continue
                user_id=sender.get('user_id');text=body.get('text');mid=body.get('mid')
                if user_id is None or (mid and mid in seen_messages):continue
                if not isinstance(text,str):text=''
                if not text.strip() and not (body.get('attachments') or []):continue
                text=text.strip();acc=account(user_id)
                state=get_state(user_id)
                                                                 
                is_hr = bool(acc and acc['role']=='hr')
                is_registry_admin = bool(admin_id and str(user_id)==admin_id) or bool(acc and acc['role']=='admin' and admin_id and str(user_id)==admin_id)
                can_view_registry = is_hr or is_registry_admin
                is_admin = bool(admin_id and str(user_id)==admin_id)
                if state and state.startswith('knowledge_replace:') and (body.get('attachments') or []):
                    if not (is_hr or is_admin):
                        set_state(user_id,None)
                        answer='Нет доступа.'
                    else:
                        from korsik_doc_manage import current_file
                        item=current_file(state)
                        attached=next((a for a in body.get('attachments',[]) if a.get('type')=='file'),{})
                        payload=attached.get('payload') or {}
                        raw=str(payload.get('filename') or payload.get('name') or attached.get('filename') or '')
                        filename=Path(raw.replace(chr(92),'/')).name
                        if item is None:
                            set_state(user_id,None)
                            answer='Документ для замены не найден. Откройте базу знаний.'
                        elif filename != item.name:
                            answer=f'Имя файла должно совпадать: {item.name}\nОтправьте файл с этим именем или откройте главное меню для отмены.'
                        else:
                            from korsik_knowledge import upload_knowledge
                            try:
                                answer=upload_knowledge(user_id,body)
                                if answer.startswith('✅'):
                                    set_state(user_id,None)
                                    answer='♻️ Версия документа обновлена.\n'+answer
                            except Exception as exc:
                                print('[DOC REPLACE]',type(exc).__name__,str(exc),flush=True)
                                answer='❌ Замена не удалась; предыдущая версия сохранена: '+str(exc)[:250]
                elif state=='knowledge_file' and (body.get('attachments') or []):
                    set_state(user_id,None)
                    if not (is_hr or is_admin):
                        answer='Нет доступа.'
                    else:
                        from korsik_knowledge import upload_knowledge
                        try:
                            answer=upload_knowledge(user_id,body)
                        except Exception as exc:
                            print('[KNOWLEDGE UPLOAD]',type(exc).__name__,str(exc),flush=True)
                            answer='❌ Не удалось загрузить документ: '+str(exc)[:250]
                elif state=='registry_file' and (body.get('attachments') or []):
                    set_state(user_id,None)
                    answer='Excel обновляется автоматически. HR не загружает реестр.'
                elif text in ('Реестр сотрудников','📋 Реестр сотрудников'):
                    answer=('Реестр сотрудников\n1. Посмотреть список\n(обновляется автоматически)' if is_hr else 'Полный реестр\n1. Посмотреть список' if is_registry_admin else 'Нет доступа.')
                elif text in ('Посмотреть список','📋 Посмотреть список'):
                    answer=registry_view('admin' if is_registry_admin else 'hr') if can_view_registry else 'Нет доступа.'
                elif text in ('Обновить реестр','📤 Обновить реестр'):
                    answer='Реестр автоматически читается из data/registry/employees.xlsx.'
                elif text in ('Скачать шаблон Excel', 'Шаблон Excel'):
                    answer = 'Excel-реестр обновляется автоматически.'
                elif text=='Подтвердить обновление':
                    answer='Реестр автоматически синхронизируется с Excel.'
                elif text=='Отменить обновление':
                    cancel(user_id);set_state(user_id,None);answer='Обновление отменено.'
                elif (
                    text in (
                        '/start', '/help', 'Меню',
                        '↩️ В главное меню', '🏠 Главное меню'
                    )
                    or (
                        not acc
                        and text in ('Начать', '▶️ Начать', 'Старт')
                    )
                ):
                    set_state(user_id,None if acc else 'code')
                    answer=menu(acc['role'] if acc else None) if acc else WELCOME
                    if admin_id and str(user_id)==admin_id and not acc: answer=menu('admin')
                elif text in (
                    "📊 Отчёт по адаптации сотрудников",
                    "Отчёт по адаптации сотрудников"
                ):
                    from hr_export import build_report
                    from tempfile import TemporaryDirectory

                    try:
                        with TemporaryDirectory(
                            prefix="korsik_hr_report_"
                        ) as folder:
                            file = (
                                Path(folder)
                                / "Отчет_по_адаптации_сотрудников.xlsx"
                            )

                            stats = build_report(
                                user_id, admin_id, file
                            )

                            api.send_file(
                                user_id, file,
                                caption="Отчёт по адаптации сотрудников"
                            )

                        answer = (
                            "✅ Excel-отчёт отправлен.\n"
                            f"Сотрудников: {stats['employees']}\n"
                            f"Активировали бота: {stats['activated']}\n"
                            f"Открытых обращений: {stats['open_tickets']}"
                        )

                    except PermissionError:
                        answer = "Нет доступа к отчётам."

                    except Exception as exc:
                        print(
                            "[HR EXPORT]",
                            type(exc).__name__,
                            str(exc),
                            flush=True
                        )
                        answer = (
                            "Не удалось отправить отчёт. "
                            "Проверьте терминал."
                        )

                elif text in ('🗑️ Удалить документ','Удалить документ'):
                    if not (is_hr or is_admin):
                        answer='Нет доступа.'
                    else:
                        from korsik_doc_manage import show_list
                        set_state(user_id,None)
                        answer=show_list('delete')
                elif text in ('♻️ Заменить документ','Заменить документ'):
                    if not (is_hr or is_admin):
                        answer='Нет доступа.'
                    else:
                        from korsik_doc_manage import show_list
                        set_state(user_id,None)
                        answer=show_list('replace')
                elif text.startswith(('Удалить №','Заменить №')):
                    if not (is_hr or is_admin):
                        answer='Нет доступа.'
                    else:
                        from korsik_doc_manage import begin
                        action='delete' if text.startswith('Удалить №') else 'replace'
                        number=text.split('№',1)[1].split(' ',1)[0].strip()
                        next_state,answer=begin(action,number)
                        if next_state:set_state(user_id,next_state)
                elif text == '✅ Подтвердить удаление':
                    if not (is_hr or is_admin) or not (state or '').startswith('knowledge_delete:'):
                        answer='Нет ожидающего подтверждения удаления.'
                    else:
                        from korsik_doc_manage import remove
                        answer=remove(user_id,state)
                        set_state(user_id,None)
                elif text in ('❌ Отменить','Отменить удаление'):
                    set_state(user_id,None)
                    answer=menu(acc['role'] if acc else 'admin')
                elif text in ('📚 База знаний','База знаний'):
                    if not (is_hr or is_admin):
                        answer='Нет доступа.'
                    else:
                        from korsik_knowledge import knowledge_menu
                        answer=knowledge_menu()
                elif text in ('📤 Загрузить документ','Загрузить документ'):
                    if not (is_hr or is_admin):
                        answer='Нет доступа.'
                    else:
                        set_state(user_id,'knowledge_file')
                        answer='📤 Отправьте документ PDF, DOCX, PPTX, TXT или MD следующим сообщением (до 50 МБ).'
                elif text in ('📊 Статистика бота','Статистика бота'):
                    if not is_admin:
                        answer='Нет доступа.'
                    else:
                        from korsik_knowledge import statistics
                        answer=statistics()
                elif text in ('📂 История загрузок','История загрузок'):
                    if not is_admin:
                        answer='Нет доступа.'
                    else:
                        from korsik_knowledge import audit_history
                        answer=audit_history()
                elif text in ('🆔 Мой MAX ID','/myid'):
                    answer=f'Ваш MAX ID: {user_id}'
                elif text in ('📱 Указать номер телефона','Указать номер телефона'):
                    if acc:
                        answer=menu(acc['role'])
                    else:
                        set_state(user_id,'code')
                        answer=WELCOME
                elif text in ('❓ Задать вопрос','Задать вопрос') and acc and acc['role']=='employee':
                    set_state(user_id,'question');answer=QUESTION_PROMPT
                elif text in ('📋 Моя адаптация','🚀 Моя адаптация','Моя адаптация') and acc and acc['role']=='employee':
                    answer=handle_message(user_id,'/start')
                elif text in ('▶️ Запустить демо', 'Запустить демо', '▶️ Запустить демо заново') and acc and acc['role']=='employee':
                    from korsik_demo_days import restart
                    answer=restart('max-'+str(user_id))
                elif text in ('📩 Обращения сотрудников','Обращения сотрудников') and (acc and acc['role'] in ('hr','admin') or admin_id and str(user_id)==admin_id):
                    answer=tickets_text(user_id,admin_id)
                elif text in ('🔐 Заявки на доступ','Заявки на доступ','/requests') and admin_id and str(user_id)==admin_id:
                    rows=pending()
                    answer='🔐 Заявки на доступ:\n'+('\n'.join(f"№{r['id']} {r['name']} / {r['phone']} / {r['role']} / MAX ID {r['max_user_id']}\nОдобрить №{r['id']}\nОтклонить №{r['id']}" for r in rows) or 'Заявок пока нет.')
                elif admin_id and str(user_id)==admin_id and (text.startswith('/approve ') or text.startswith('/reject ') or text.startswith('Одобрить №') or text.startswith('Отклонить №')):
                    if text.startswith('Одобрить №'):parts=['/approve',text.split('№',1)[1]]
                    elif text.startswith('Отклонить №'):parts=['/reject',text.split('№',1)[1]]
                    else:parts=text.split()
                    if len(parts)!=2 or not parts[1].isdigit():answer='Укажите номер заявки.'
                    else:
                        request_id=int(parts[1]);action=parts[0][1:]
                        matches=[r for r in pending() if r['id']==request_id]
                        answer=review(request_id,action,user_id)
                        if matches and answer in ('Одобрено','Отклонено'):
                            api.send_message(matches[0]['max_user_id'],'Ваша заявка: '+answer+'. Откройте главное меню командой /start.')
                elif admin_id and str(user_id)==admin_id and text.startswith('/revoke '):
                    try:answer='Доступ отозван.' if revoke(text.split(maxsplit=1)[1]) else 'Телефон не найден.'
                    except ValueError:answer='Укажите номер телефона.'
                                      
                                      
                elif (
                    text in (
                        "🔑 Приглашения сотрудников",
                        "Приглашения сотрудников",
                        "/invites"
                    )
                    or text.startswith("📄 Приглашения — страница ")
                ):
                    rows = available_employees(user_id)

                    if rows is None:
                        answer = "Нет доступа к приглашениям."

                    elif not rows:
                        answer = (
                            "✅ Все сотрудники уже активированы. "
                            "Новых приглашений нет."
                        )

                    else:
                        page = 0

                        if text.startswith("📄 Приглашения — страница "):
                            try:
                                page = int(text.rsplit(" ", 1)[-1]) - 1
                            except ValueError:
                                page = 0

                        page_count = (len(rows) + 5) // 6
                        page = min(max(page, 0), page_count - 1)
                        current = rows[page * 6:(page + 1) * 6]

                        answer = (
                            f"🔑 Приглашения сотрудников "
                            f"· страница {page + 1}/{page_count}\\n\\n"
                        )

                        for r in current:
                            answer += (
                                f"👤 {r['name']} — {r['phone']}\\n"
                                f"🔑 Выдать код: {r['phone']}\\n\\n"
                            )

                        if page > 0:
                            answer += (
                                f"📄 Приглашения — страница {page}\\n"
                            )

                        if page + 1 < page_count:
                            answer += (
                                f"📄 Приглашения — страница {page + 2}\\n"
                            )

                        answer += (
                            "Передайте код только после проверки "
                            "личности сотрудника."
                        )
                elif text.startswith('🔑 Выдать код: ') or text.casefold().startswith('/invite '):
                    result = issue_invite(user_id, text.rsplit(' ', 1)[-1])
                    if result.get('error'):
                        answer = result['error']
                    else:
                        answer = (f"🔑 Приглашение для {result['name']}\n"
                                  f"Код: {result['code']}\n\n"
                                  'Передайте код лично или через проверенный корпоративный канал. '
                                  'Не публикуйте в общих чатах.')
                elif text == "👩‍💼 Я HR или руководитель":
                    set_state(user_id, "request_phone")
                    answer = (
                        "Введите свой телефон из корпоративного "
                        "реестра. Заявку проверит администратор."
                    )

                elif state == "request_phone":
                    set_state(user_id, None)
                    answer = request_access(user_id, text)

                elif (
                    text.startswith("✍️ Ответить №")
                    and not can_reply(
                        user_id, admin_id,
                        text.split("№", 1)[-1].strip()
                    )
                ):
                    answer = (
                        "Обращение закрыто или недоступно."
                    )

                elif text.startswith("✍️ Ответить №"):
                    if not (
                        (acc and acc["role"] in ("hr", "admin"))
                        or is_admin
                    ):
                        answer = "Нет доступа."

                    else:
                        ticket_number = text.split("№", 1)[-1].strip()

                        if not ticket_number.isdigit():
                            answer = "Не удалось определить обращение."
                        else:
                            set_state(
                                user_id,
                                "hr_reply:" + ticket_number
                            )
                            answer = (
                                "✍️ Напишите ответ на обращение №"
                                + ticket_number
                                + " одним сообщением.\n\n"
                                + "Для отмены нажмите кнопку ниже."
                            )

                elif text == "❌ Отменить ответ":
                    set_state(user_id, None)
                    answer = (
                        menu(acc["role"])
                        if acc
                        else menu("admin")
                        if is_admin
                        else WELCOME
                    )

                elif state and state.startswith("hr_reply:"):
                    if not (
                        (acc and acc["role"] in ("hr", "admin"))
                        or is_admin
                    ):
                        set_state(user_id, None)
                        answer = "Нет доступа."

                    else:
                        ticket_number = state.split(":", 1)[1]

                        if not ticket_number.isdigit():
                            set_state(user_id, None)
                            answer = "Ошибка выбора обращения."

                        elif not text.strip():
                            answer = "Напишите текст ответа."

                        else:
                            reply_result = role_command(
                                api,
                                user_id,
                                "/reply " + ticket_number + " " + text,
                                acc or {"role": "admin", "phone": ""}
                            )
                            answer = reply_result

                            if reply_result == "Ответ отправлен.":
                                set_state(user_id, None)
                                answer = (
                                    "✅ Ответ сотруднику отправлен!\n\n"
                                    + "1. 📩 Обращения сотрудников"
                                )

                elif text.casefold().startswith('/request '):
                    answer=request_access(user_id,text.split(maxsplit=1)[1])
                elif text.casefold().startswith('/activate '):
                    result=activate(user_id,text.split(maxsplit=1)[1])
                    if result and result.get('error'):answer=result['error']
                    elif result:answer=f"✅ Добро пожаловать, {result['name']}!\n"+menu(result['role'])
                    else:answer='Код не найден или уже использован. Обратитесь к HR.'
                elif state=='code':
                    result=activate(user_id,text)
                    if result and result.get('error'):answer=result['error']
                    elif result:
                        set_state(user_id,None)
                        answer=f"✅ Добро пожаловать, {result['name']}!\n"+menu(result['role'])
                    else:answer='Код неверен. Проверьте код, полученный от HR.'
                elif state and state.startswith('knowledge_replace:'):
                    answer='Ожидаю новую версию документа файлом с тем же именем. Для отмены — «🏠 Главное меню».'
                elif state and state.startswith('knowledge_delete:'):
                    answer='Подтвердите удаление кнопкой или отмените через главное меню.'
                elif state=='knowledge_file':
                    answer='Ожидаю документ файлом. Для отмены нажмите «🏠 Главное меню».'
                elif state=='question' and acc and acc['role']=='employee':
                    set_state(user_id,None)
                    answer=handle_message(user_id,'/ask '+text)
                elif acc and acc['role']=='employee' and __import__('korsik_demo_days').state('max-'+str(user_id)) and __import__('korsik_demo_days').state('max-'+str(user_id))['active']:
                    from korsik_demo_days import advance
                    answer=advance('max-'+str(user_id),text)
                elif not acc:
                    set_state(user_id,'code')
                    answer=WELCOME
                elif acc['role']=='employee':answer=handle_message(user_id,text)
                else:answer=role_command(api,user_id,text,acc)
                api.send_message(user_id,answer)
                if mid:seen_messages.add(mid)
            marker=response.get('marker',marker)
            if admin_id:
                for r in unnotified():
                    notice=(f"🔐 Заявка №{r['id']} на роль {r['role']}\n"
                            f"ФИО по реестру: {r['name']}\nТелефон по реестру: {r['phone']}\n"
                            f"MAX ID заявителя: {r['max_user_id']}\n"
                            "⚠️ Номер введён самим заявителем, это НЕ доказательство личности. "
                            "Позвоните по номеру ИЗ РЕЕСТРА и уточните MAX ID через /myid. "
                            "Профиль MAX и номер профиля сами по себе не подтверждают владельца.\n"
                            f"После проверки: /approve {r['id']}\nЕсли не совпало: /reject {r['id']}")
                    api.send_message(admin_id,notice)
                    mark_notified(r['id'])
            with connect() as c:
                hrs=c.execute("SELECT max_user_id FROM staff_registry WHERE role IN ('hr','admin') AND active=1 AND max_user_id IS NOT NULL").fetchall()
            for hr in hrs:
                notify_hr(api,hr['max_user_id'],notified.setdefault(hr['max_user_id'],set()))
        except urllib.error.HTTPError as error:
            print('HTTP MAX:',error.code,flush=True)
            if error.code in (401,403,405):return
            time.sleep(5)
        except (urllib.error.URLError,TimeoutError) as error:
            print('Сеть MAX:',error,flush=True);time.sleep(3)
        except (ValueError,KeyError) as error:
            print('Ошибка обработки:',error,flush=True);time.sleep(1)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nБот остановлен")
    except RuntimeError as error:
        print("Ошибка запуска:", error)
