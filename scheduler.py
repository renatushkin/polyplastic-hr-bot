import calendar
import json
import os
import re
import sqlite3
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from database import connect
from onboarding import STEPS, applicable
from calendar_groups import groups, clean_text

TZ = ZoneInfo(os.getenv('KORSIK_TIMEZONE', 'Europe/Moscow'))


def is_workday(day):
                                                                           
    holidays = {'2026-11-04'}
    holidays.update(x.strip() for x in os.getenv('KORSIK_HOLIDAYS', '').split(',') if x.strip())
    return day.weekday() < 5 and day.isoformat() not in holidays


def sendable(step):
                                                             
    value = (step.get('text') or '').strip().lower()
    if not value:
        return False
    if value.startswith(('варианты ответов:', 'отправить приветственное письмо',
                         '# приложить', '#приложить', 'ответы:')):
        return False
    if step.get('id') in ('excel-62', 'excel-69', 'excel-70'):
        return False
    if not clean_text(step):
        return False
    return True



def workday(start, n):
    day = start
    while not is_workday(day):
        day += timedelta(days=1)
    for _ in range(n - 1):
        day += timedelta(days=1)
        while not is_workday(day):
            day += timedelta(days=1)
    return day


def months_after(day, count):
    total = day.year * 12 + day.month - 1 + count
    year, month = divmod(total, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def scheduled_at(step, start):
    if step.get('conditional') or not sendable(step):
        return None
    raw = (step.get('time') or '').lower().replace('ё', 'е').strip()
    if not raw or raw.startswith(('если ', 'в случае')):
        return None
    if 'за 2-3 дня' in raw:
        day = start - timedelta(days=3)
    elif 'за день' in raw:
        day = start - timedelta(days=1)
    elif 'первый рабочий день' in raw:
        day = workday(start, 1)
    elif 'второй рабочий день' in raw:
        day = workday(start, 2)
    elif 'третий рабочий день' in raw:
        day = workday(start, 3)
    elif 'через 10 дней' in raw:
        day = start + timedelta(days=10)
    elif 'через 2 недели' in raw:
        day = start + timedelta(days=14)
    elif 'первый день второго месяца' in raw:
        day = months_after(start, 1)
    elif '1 месяц и 2 недели' in re.sub(r'\s+', ' ', raw):
        day = months_after(start, 1) + timedelta(days=14)
    elif '1 месяц и 3 недели' in re.sub(r'\s+', ' ', raw):
        day = months_after(start, 1) + timedelta(days=21)
    elif 'первый день третьего месяца' in raw:
        day = months_after(start, 2)
    elif '2 месяца и 2 недели' in raw:
        day = months_after(start, 2) + timedelta(days=14)
    elif 'последний день' in raw:
        day = start + timedelta(days=int(os.getenv('KORSIK_PROBATION_DAYS', '90')))
    else:
        return None
    match = re.search(r'(?<!\d)(\d{1,2})[:.](\d{2})(?!\d)', raw)
    hour, minute = (int(match.group(1)), int(match.group(2))) if match else (9, 0)
    if hour > 23 or minute > 59:
        hour, minute = 9, 0
    return datetime.combine(day, time(hour, minute), tzinfo=TZ)


def init_scheduler():
    with connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS scheduled_deliveries (
            employee_id TEXT NOT NULL, step_id TEXT NOT NULL,
            due_at TEXT NOT NULL, sent_at TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            PRIMARY KEY(employee_id, step_id))''')


def due_items(now=None):
    now = now or datetime.now(TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ)
    max_late_days = max(0, int(os.getenv('KORSIK_MAX_LATE_DAYS', '1')))
    with connect() as db:
        profiles = db.execute('''SELECT p.employee_id, p.start_date, e.tags
            FROM onboarding_profiles p
            JOIN employees e ON e.id = p.employee_id
            JOIN staff_registry s ON s.max_user_id = substr(p.employee_id, 5)
            WHERE p.mode = 'calendar' AND p.start_date IS NOT NULL
              AND s.active = 1 AND s.role = 'employee' ''').fetchall()
    items = []
    for profile in profiles:
        employee_id = profile['employee_id']
        if not employee_id.startswith('max-'):
            continue
        try:
            tags = json.loads(profile['tags'] or '[]')
            start = date.fromisoformat(profile['start_date'])
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
        for step in STEPS:
            if not applicable(step, {'tags': tags}):
                continue
            due = scheduled_at(step, start)
            if due is None or due > now:
                continue
                                                        
            if now - due > timedelta(days=max_late_days):
                continue
            items.append((due, employee_id, step))
    return sorted(items, key=lambda item: (item[0], item[1], int(item[2].get('source_row') or 0)))


def tick(api, now=None, dry_run=False):
    init_scheduler()
    now = now or datetime.now(TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ)
    limit = max(1, int(os.getenv('KORSIK_BATCH_SIZE', '3')))
    count = 0
    for group in groups(due_items(now)):
        if count >= limit:
            break
        due, employee_id = group['key']
        steps = group['steps']
        ids = [step['id'] for step in steps]
        placeholders = ','.join('?' for _ in ids)
        query = f'SELECT step_id,status FROM scheduled_deliveries WHERE employee_id=? AND step_id IN ({placeholders})'
        with connect() as db:
            rows = db.execute(query, [employee_id, *ids]).fetchall()
        statuses = {row['step_id']: row['status'] for row in rows}
        pending = [step for step in steps if statuses.get(step['id']) not in ('sent', 'sending')]
        if not pending:
            continue
        body = '\n\n'.join(clean_text(step) for step in pending)
        text = f"🐾 Корсик • План адаптации\n📅 {pending[0].get('time', '')}\n\n{body}"
        if group['interactive']:
            text += '\n\nЧтобы ответить на вопрос, открой /continue'
        if len(text) > 4000:
            print(f'слишком длинный блок: {employee_id} / {ids}', flush=True)
            continue
        if dry_run:
            print(f"тест: {due.isoformat()} -> {employee_id} / {', '.join(step['id'] for step in pending)}")
            count += 1
            continue
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            fresh = db.execute(query, [employee_id, *ids]).fetchall()
            fresh_statuses = {row['step_id']: row['status'] for row in fresh}
            if any(fresh_statuses.get(step['id']) in ('sent', 'sending') for step in pending):
                continue
            for step in pending:
                db.execute("""INSERT INTO scheduled_deliveries(employee_id,step_id,due_at,status)
                    VALUES(?,?,?,'sending')
                    ON CONFLICT(employee_id,step_id) DO UPDATE SET
                        due_at=excluded.due_at,status='sending',sent_at=NULL""",
                    (employee_id, step['id'], due.isoformat()))
        try:
            api.send_message(employee_id[4:], text)
        except Exception:
                                                             
            raise
        with connect() as db:
            for step in pending:
                db.execute("""UPDATE scheduled_deliveries SET status='sent',sent_at=?
                    WHERE employee_id=? AND step_id=? AND status='sending'""",
                    (now.isoformat(), employee_id, step['id']))
        count += 1
        print(f'автоуведомление: {len(pending)} шагов -> {employee_id}', flush=True)
    return count
