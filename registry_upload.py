"""Safe HR roster preview, staging, and atomic import."""
import json
import os
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from database import connect
from accounts import read_registry, import_staff

MAX_BYTES = 50 * 1024 * 1024

def init_registry_upload():
    with connect() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS registry_uploads (
            max_user_id TEXT PRIMARY KEY, path TEXT NOT NULL, summary TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')

def registry_view(role='hr'):
    """Server-side role filter; never return privileged rows to HR."""
    if role not in ('hr', 'admin'):
        raise PermissionError('Нет доступа к реестру')
    where = "WHERE role='employee'" if role == 'hr' else ''
    with connect() as c:
        rows = c.execute(f'SELECT name,phone,role,active FROM staff_registry {where} ORDER BY name LIMIT 30').fetchall()
        count = c.execute(f'SELECT COUNT(*) FROM staff_registry {where}').fetchone()[0]
    heading = 'Реестр сотрудников' if role == 'hr' else 'Полный реестр'
    return (heading + ': ' + str(count) + ' записей\n' +
            '\n'.join(f"{r['name']} — {r['phone']}" + (f" ({r['role']})" if role == 'admin' else '') for r in rows) +
            ('\nПоказаны первые 30.' if count > 30 else '')) if count else 'Реестр пока пуст.'

def _download(url, destination):
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or '').lower()
    if parsed.scheme != 'https' or not (host == 'max.ru' or host.endswith('.max.ru') or host == 'oneme.ru' or host.endswith('.oneme.ru')):
        raise ValueError('Недопустимый адрес файла MAX')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            new = urllib.parse.urlparse(newurl)
            hostname = (new.hostname or '').lower()
            if new.scheme != 'https' or not (hostname == 'max.ru' or hostname.endswith('.max.ru') or hostname == 'oneme.ru' or hostname.endswith('.oneme.ru')):
                raise ValueError('Недопустимый адрес перенаправления')
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(urllib.request.Request(url), timeout=25) as response:
        if response.headers.get('Content-Length') and int(response.headers['Content-Length']) > MAX_BYTES:
            raise ValueError('Файл больше 50 МБ')
        with open(destination,'wb') as output:
            while True:
                block=response.read(65536)
                if not block: break
                if output.tell()+len(block)>MAX_BYTES: raise ValueError('Файл больше 50 МБ')
                output.write(block)

def attachment_url(body):
    for a in body.get('attachments') or []:
        if a.get('type') != 'file': continue
        p=a.get('payload') or {}
        name=str(p.get('filename') or p.get('name') or a.get('filename') or '')
        url=p.get('url') or p.get('download_url')
        if name.lower().endswith('.xlsx') and isinstance(url,str):return url
    return None

def stage(uid, url):
    init_registry_upload()
    fd,path=tempfile.mkstemp(prefix='korsik_roster_',suffix='.xlsx');os.close(fd)
    try:
        _download(url,path)
        rows=read_registry(path)
        if not rows:raise ValueError('В файле нет сотрудников')
                                                                                      
        with connect() as c:
            existing={r['phone']:r for r in c.execute('SELECT phone,name,role FROM staff_registry')}
        for r in rows:
            if r['role'] != 'employee':
                raise ValueError('Через HR можно загружать только роль employee. Роли HR и руководителя назначает администратор.')
            old=existing.get(r['phone'])
            if old and old['role'] != 'employee':
                raise ValueError('Нельзя изменять привилегированную запись: '+r['phone'])
        added=sum(r['phone'] not in existing for r in rows)
        changed=sum(r['phone'] in existing and r['name'] != existing[r['phone']]['name'] for r in rows)
        summary=f'Файл проверен. Записей: {len(rows)}. Новых: {added}. Изменений ФИО: {changed}. Отсутствующие в файле сотрудники не удаляются.'
        with connect() as c:
            old=c.execute('SELECT path FROM registry_uploads WHERE max_user_id=?',(str(uid),)).fetchone()
            c.execute('INSERT INTO registry_uploads(max_user_id,path,summary) VALUES(?,?,?) ON CONFLICT(max_user_id) DO UPDATE SET path=excluded.path,summary=excluded.summary,created_at=CURRENT_TIMESTAMP',(str(uid),path,summary))
        if old:
            try:os.unlink(old['path'])
            except OSError:pass
        return summary+'\n1. Подтвердить обновление\n2. Отменить обновление'
    except Exception:
        try:os.unlink(path)
        except OSError:pass
        raise

def confirm(uid):
    init_registry_upload()
    with connect() as c:
        row=c.execute('SELECT path FROM registry_uploads WHERE max_user_id=?',(str(uid),)).fetchone()
    if not row:return 'Нет файла для подтверждения.'
                                                                  
    rows=read_registry(row['path'])
    with connect() as c:
        roles={r['phone']:r['role'] for r in c.execute('SELECT phone,role FROM staff_registry')}
    if any(r['role']!='employee' or roles.get(r['phone'],'employee')!='employee' for r in rows):
        raise ValueError('Обнаружено изменение привилегированной роли. Обновление отменено.')
    count,_=import_staff(row['path'],allow_roles=False)
    cancel(uid)
    return f'Реестр обновлён. Обработано сотрудников: {count}. Новые номера доступны для регистрации.'

def cancel(uid):
    init_registry_upload()
    with connect() as c:
        row=c.execute('SELECT path FROM registry_uploads WHERE max_user_id=?',(str(uid),)).fetchone()
        c.execute('DELETE FROM registry_uploads WHERE max_user_id=?',(str(uid),))
    if row:
        try:os.unlink(row['path'])
        except OSError:pass
