"""Full source-plan onboarding with tagged routes and optional calendar gating."""
import json, os, re
from datetime import date, timedelta
from pathlib import Path
from database import connect, employee
STEPS=json.loads((Path(__file__).parent/'data/corsik_scenario.json').read_text(encoding='utf-8'))
TAGS=('GTP','GrPP','Luzhniki')

def applicable(s,p):
    return not s['tags'] or bool({x.casefold() for x in s['tags']} & {x.casefold() for x in p['tags']})

def due_date(s, start):
    from scheduler import scheduled_at
    due = scheduled_at(s, start)
    return due.date() if due else start

def _profile(employee_id):
    p=employee(employee_id)
    with connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS onboarding_profiles(employee_id TEXT PRIMARY KEY,start_date TEXT,mode TEXT DEFAULT 'demo')")
        r=c.execute('SELECT start_date,mode FROM onboarding_profiles WHERE employee_id=?',(employee_id,)).fetchone()
    p['start_date']=r['start_date'] if r else None
    p['mode']=r['mode'] if r else 'demo'
    return p

def _conditional_trigger(s,previous):
    if not s.get('conditional'):return True
                                                                                      
    return s['id'] in ('excel-26','excel-27','excel-28') and previous=='Да!'

def _next(p):
    with connect() as c:
        answers={r['step_id']:r['answer'] for r in c.execute('SELECT step_id,answer FROM answers WHERE employee_id=?',(p['id'],))}
    for i in range(p['step'],len(STEPS)):
        s=STEPS[i]
        if not applicable(s,p) or not _conditional_trigger(s,answers.get('excel-25')):continue
        if p['mode']=='calendar' and p['start_date']:
            due=due_date(s,date.fromisoformat(p['start_date']))
            if due>date.today():
                return {'waiting':True,'done':False,'due':due.isoformat(),'text':f'Следующий этап будет доступен {due:%d.%m.%Y}.','buttons':[]}
        return {**s,'index':i,'done':False}
    return {'done':True,'text':'🎉 План адаптации завершён! /ask — задать вопрос HR','buttons':[]}

def get_current_step(employee_id):return _next(_profile(employee_id))

def submit_step_answer(employee_id,answer):
    p=_profile(employee_id);s=_next(p)
    if s.get('done') or s.get('waiting'):return s
    if answer not in s['buttons']:raise ValueError('Выбери вариант ответа текущего этапа')
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        current=c.execute('SELECT step FROM employees WHERE id=?',(employee_id,)).fetchone()
        if current['step']!=p['step']:raise ValueError('Этап уже изменился. Нажми /continue')
        c.execute('INSERT INTO answers(employee_id,step_id,answer) VALUES(?,?,?) ON CONFLICT(employee_id,step_id) DO UPDATE SET answer=excluded.answer',(employee_id,s['id'],answer))
        c.execute('UPDATE employees SET step=? WHERE id=?',(s['index']+1,employee_id))
        c.execute('INSERT INTO messages(employee_id,author,text) VALUES(?,?,?)',(employee_id,'employee',answer))
    return get_current_step(employee_id)

def reset_progress(employee_id):
    with connect() as c:
        c.execute('UPDATE employees SET step=0 WHERE id=?',(employee_id,))
        c.execute("DELETE FROM answers WHERE employee_id=? AND step_id LIKE 'excel-%'",(employee_id,))
    return get_current_step(employee_id)

def set_tag(employee_id,tag):
    tag=next((t for t in TAGS if t.casefold()==tag.casefold()),None)
    if not tag:raise ValueError('Теги: GTP, GrPP, Luzhniki')
    with connect() as c:
        c.execute('UPDATE employees SET tags=?,step=0 WHERE id=?',(json.dumps([tag]),employee_id))
        c.execute("DELETE FROM answers WHERE employee_id=? AND step_id LIKE 'excel-%'",(employee_id,))
    return get_current_step(employee_id)

def set_schedule(employee_id,start_date,mode='calendar'):
    d=date.fromisoformat(start_date)
    if mode not in ('demo','calendar'):raise ValueError('Режим demo или calendar')
    _profile(employee_id)
    with connect() as c:
        c.execute('INSERT INTO onboarding_profiles(employee_id,start_date,mode) VALUES(?,?,?) ON CONFLICT(employee_id) DO UPDATE SET start_date=excluded.start_date,mode=excluded.mode',(employee_id,d.isoformat(),mode))
    return get_current_step(employee_id)
