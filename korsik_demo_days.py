"""Демонстрация первых десяти рабочих дней без изменения календарного прогресса."""
import json
from pathlib import Path
from database import connect

SCENARIO = json.loads((Path(__file__).parent / 'data' / 'corsik_scenario.json').read_text(encoding='utf-8'))
BY_ID = {item['id']: item for item in SCENARIO}

                                                                           
                                                                          
DAYS = {
    1: [
        ('excel-18', None), ('excel-20', None), ('excel-21', None),
        ('excel-22', ('✅ Всё есть', '❌ Не хватает доступов или материалов')),
        ('excel-23', ('✅ Всё есть', '❌ Не хватает доступов или материалов')),
        ('excel-25', ('🍽️ Да, расскажи', 'Нет, спасибо')),
        ('excel-29', None), ('excel-30', None), ('excel-31', None),
        ('excel-32', None), ('excel-33', None),
    ],
    2: [('excel-34', ('✅ Готов(а)', '⏭️ Пропустить'))],
    3: [
        ('excel-35', None), ('excel-36', None), ('excel-37', ('Да, интересно', 'Не сейчас')),
        ('excel-38', None),
        ('excel-39', ('✅ Всё отлично', '❓ Остались вопросы', '📄 Трудности с документами')),
        ('excel-40', ('😊 Отлично', '🤝 Пока присматриваюсь', '😕 Пока не познакомился(лась)')),
        ('excel-41', ('✅ Всё понятно', '⏳ Жду объяснений', '❓ Пока непонятно')),
        ('excel-42', None),
    ],
    10: [('excel-43', None), ('excel-44', None), ('excel-46', None)],
}

INTRO = {
    4: 'В исходном сценарии нет отдельного сообщения на четвёртый рабочий день.',
    5: 'В исходном сценарии нет отдельного сообщения на пятый рабочий день.',
    6: 'В исходном сценарии нет отдельного сообщения на шестой рабочий день.',
    7: 'В исходном сценарии нет отдельного сообщения на седьмой рабочий день.',
    8: 'В исходном сценарии нет отдельного сообщения на восьмой рабочий день.',
    9: 'В исходном сценарии нет отдельного сообщения на девятый рабочий день.',
}

PROMPTS = {
    'excel-18': 'Поздравляю с первым рабочим днём! 🥳 Добро пожаловать в команду ПОЛИПЛАСТИК.',
    'excel-20': 'Территория предприятия довольно большая. Если нужна карта, запроси её через базу знаний Корсика.',
    'excel-21': 'Наш офис довольно большой. Если нужна карта, запроси её через базу знаний Корсика.',
    'excel-22': 'Есть ли у тебя необходимые доступы и материалы для начала работы?',
    'excel-23': 'Всё ли необходимое оборудование и материалы у тебя есть?',
    'excel-25': 'Хочешь, подскажу, где пообедать?',
    'excel-29': 'В команде ПОЛИПЛАСТИК более 8500 человек! Познакомимся с полезными контактами.',
    'excel-30': 'Корпоративный справочник: https://my.polyplastic.ru/employees/Pages/address-book.aspx\nДоступ возможен только с рабочего устройства или корпоративной учётной записью.',
    'excel-31': 'Корпоративный справочник: http://ats/\nДоступ возможен только из корпоративной сети.',
    'excel-32': 'Ты — часть команды ПОЛИПЛАСТИК. Наша миссия — улучшать качество жизни, создавая надёжную инфраструктуру.',
    'excel-33': 'Первый рабочий день позади! 🐾 Ты сделал(а) первые шаги на новом месте.',
    'excel-34': 'В исходном плане есть необязательное задание: подготовить краткое описание опыта и навыков для знакомства с коллегами. В демо отметь готовность или пропусти.',
    'excel-35': 'Наступил третий рабочий день! Как быстро летит время.',
    'excel-36': 'Руководитель подготовил адаптационный план. Его детали можно уточнить у руководителя.',
    'excel-37': 'На территории предприятия есть спортивный комплекс. Хочешь узнать о расписании?',
    'excel-38': 'Первые дни на новом месте могут быть непростыми. Пройди короткий опрос.',
    'excel-39': 'Были ли вопросы при оформлении?',
    'excel-40': 'Как тебя встретили новые коллеги?',
    'excel-41': 'Понятны ли тебе задачи на испытательный срок?',
    'excel-42': 'Спасибо за обратную связь! 🐾',
    'excel-43': 'Сегодня познакомимся с корпоративными мероприятиями.',
    'excel-44': 'В ПОЛИПЛАСТИКЕ проходят праздники, спортивные и профессиональные мероприятия.',
    'excel-46': 'Надеемся увидеть тебя на ближайших мероприятиях! 🎊',
}

PROBLEM_CHOICES = {
    ('excel-22','❌ Не хватает доступов или материалов'),
    ('excel-23','❌ Не хватает доступов или материалов'),
    ('excel-39','❓ Остались вопросы'),
    ('excel-39','📄 Трудности с документами'),
    ('excel-40','😕 Пока не познакомился(лась)'),
    ('excel-41','❓ Пока непонятно'),
}


def init():
    with connect() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS korsik_demo_state (
            employee_id TEXT PRIMARY KEY, day INTEGER NOT NULL DEFAULT 1,
            position INTEGER NOT NULL DEFAULT 0, awaiting_question INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1)''')
        c.execute('''CREATE TABLE IF NOT EXISTS korsik_demo_answers (
            employee_id TEXT NOT NULL, day INTEGER NOT NULL,
            step_id TEXT NOT NULL, answer TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(employee_id,day,step_id))''')


def state(employee_id):
    init()
    with connect() as c:
        row = c.execute('SELECT * FROM korsik_demo_state WHERE employee_id=?',(employee_id,)).fetchone()
    return dict(row) if row else None


def restart(employee_id):
    init()
    with connect() as c:
        c.execute('INSERT INTO korsik_demo_state(employee_id,day,position,awaiting_question,active) VALUES(?,1,0,0,1) ON CONFLICT(employee_id) DO UPDATE SET day=1,position=0,awaiting_question=0,active=1',(employee_id,))
        c.execute('DELETE FROM korsik_demo_answers WHERE employee_id=?',(employee_id,))
    return '▶️ Демо начинается с первого рабочего дня. Реальный прогресс не изменён.\n\n' + show(employee_id)


def _items(day, employee_id):
    from database import employee
    from onboarding import applicable
    profile=employee(employee_id)
    return [(BY_ID[id_],opts) for id_,opts in DAYS.get(day,[]) if applicable(BY_ID[id_],profile)]


def show(employee_id):
    s=state(employee_id)
    if not s or not s['active']:
        return 'Демо не запущено. Нажми «▶️ Запустить демо».'
    day=s['day']
    if day > 10:
        return '🎉 Демо первых десяти дней завершено!\n\nРеальная адаптация не изменена.\n1. ▶️ Запустить демо заново'
    if s['awaiting_question']:
        return '✍️ Опиши вопрос или проблему одним сообщением. Корсик сначала проверит базу знаний и при отсутствии ответа создаст обращение HR.\n\n1. ⏭️ Пропустить вопрос'
    items=_items(day,employee_id)
    if not items:
        text=INTRO.get(day, 'Для твоего подразделения на этот день отдельных этапов нет.')
        return f'📅 Демо · День {day}/10\n\n{text}\n\n1. ➡️ Следующий день'
    if s['position'] >= len(items):
        return f'✅ День {day} пройден!\n\n1. ➡️ Следующий день'
    entry, options=items[s['position']]
    description=PROMPTS.get(entry['id'],entry['text'])
    buttons=options or ('Далее',)
    return f'📅 Демо · День {day}/10 · Шаг {s["position"]+1}/{len(items)}\n\n{description}\n\n' + '\n'.join(f'{i}. {opt}' for i,opt in enumerate(buttons,1))


def advance(employee_id,text):
    s=state(employee_id)
    if not s or not s['active']:return None
    raw=text.strip()
    if not raw:return show(employee_id)
    if s['awaiting_question']:
        if raw in ('⏭️ Пропустить вопрос','Пропустить вопрос','1'):
            result='Вопрос пропущен.'
        else:
            from max_handlers import handle_question
            result=handle_question(employee_id,raw)
        with connect() as c:
            c.execute('UPDATE korsik_demo_state SET awaiting_question=0,position=position+1 WHERE employee_id=?',(employee_id,))
        return result+'\n\n'+show(employee_id)
    items=_items(s['day'],employee_id)
    if s['position']>=len(items):
        options=('➡️ Следующий день',)
    else:
        options=items[s['position']][1] or ('Далее',)
    if raw.isascii() and raw.isdigit() and 1<=int(raw)<=len(options):
        choice=options[int(raw)-1]
    else:
        choice=next((o for o in options if raw.casefold()==o.casefold()),None)
    if choice is None:return 'Выбери один из вариантов кнопкой.\n\n'+show(employee_id)
    if s['position']>=len(items):
        with connect() as c:
            c.execute('UPDATE korsik_demo_state SET day=day+1,position=0 WHERE employee_id=?',(employee_id,))
        return show(employee_id)
    entry,_=items[s['position']]
    with connect() as c:
        c.execute('INSERT INTO korsik_demo_answers(employee_id,day,step_id,answer) VALUES(?,?,?,?) ON CONFLICT(employee_id,day,step_id) DO UPDATE SET answer=excluded.answer',(employee_id,s['day'],entry['id'],choice))
        if (entry['id'],choice) in PROBLEM_CHOICES:
            c.execute('UPDATE korsik_demo_state SET awaiting_question=1 WHERE employee_id=?',(employee_id,))
        else:
            c.execute('UPDATE korsik_demo_state SET position=position+1 WHERE employee_id=?',(employee_id,))
    if (entry['id'],choice) in PROBLEM_CHOICES:
        return 'Спасибо, что рассказал(а). Опиши, пожалуйста, ситуацию подробнее.\n\n'+show(employee_id)
    if entry['id']=='excel-25' and choice=='🍽️ Да, расскажи':
        return '🍽️ Информация о местах питания в исходном плане предусмотрена отдельным PDF, но сам PDF не приложен. Его можно добавить через HR.\n\n'+show(employee_id)
    if entry['id'] in ('excel-22','excel-23') and choice=='✅ Всё есть':
        return 'Замечательно! Хорошего первого дня!\n\n'+show(employee_id)
    return show(employee_id)
