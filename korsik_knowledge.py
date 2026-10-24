"""Загрузка HR-документов, статистика и журнал загрузок Корсика."""
from pathlib import Path
from datetime import datetime
from database import connect
from registry_upload import _download
import re, tempfile, os

DOC_DIR = Path(__file__).resolve().parent/'data'/'knowledge_docs'
ALLOWED = {'.pdf','.docx','.pptx','.txt','.md'}

def init():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS knowledge_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uploader_id TEXT NOT NULL, filename TEXT NOT NULL,
            status TEXT NOT NULL, uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")

def knowledge_menu():
    DOC_DIR.mkdir(parents=True,exist_ok=True)
    items=[p.name for p in sorted(DOC_DIR.iterdir()) if p.is_file() and p.suffix.lower() in ALLOWED]
    return ('📚 База знаний\n\nДокументов: '+str(len(items))+'\n'+
            ('\n'.join('• '+x for x in items[:30]) if items else 'Пока нет загруженных документов.')+
            '\n\n1. 📤 Загрузить документ\n2. 🗑️ Удалить документ\n3. ♻️ Заменить документ')

def upload_knowledge(uid, body):
    init()
    attachments=body.get('attachments') or []
    item=next((x for x in attachments if x.get('type')=='file'),None)
    if not item: return 'Пришлите документ файлом.'
    payload=item.get('payload') or {}
    raw=str(payload.get('filename') or payload.get('name') or item.get('filename') or '')
    filename=Path(raw.replace('\\','/')).name
    suffix=Path(filename).suffix.lower()
    if suffix not in ALLOWED or not filename or len(filename)>180:
        return 'Поддерживаются только PDF, DOCX, PPTX, TXT, MD (имя до 180 символов).'
    url=payload.get('url') or payload.get('download_url')
    if not isinstance(url,str):
        return 'MAX не передал прямую ссылку на файл. Попробуйте отправить его как документ.'
    DOC_DIR.mkdir(parents=True,exist_ok=True)
    safe=re.sub(r'[^a-zA-Zа-яА-ЯёЁ0-9_. -]','_',filename)
    target=DOC_DIR/safe
    fd,tmp=tempfile.mkstemp(prefix='korsik_doc_',suffix=suffix)
    os.close(fd)
    try:
        _download(url,tmp)
                                                                      
        from document_search import read_document
        pages=list(read_document(Path(tmp)))
        content=' '.join(text for _,text in pages)
        searchable = bool(content.strip())
        replacing_existing = target.exists()
        os.replace(tmp,target)
        if suffix == '.pdf' and searchable:
            from korsik_pdf_ocr import cache_pdf_pages
            try:
                cache_pdf_pages(target,pages)
            except OSError as cache_error:
                print('[OCR CACHE]',cache_error,flush=True)
        with connect() as c:
            c.execute('INSERT INTO knowledge_audit(uploader_id,filename,status) VALUES(?,?,?)',(str(uid),safe,('заменено' if replacing_existing else ('успешно' if searchable else 'без текста'))))
        if not searchable:
            return ('✅ Файл сохранён: '+safe+'\n⚠️ Извлекаемого текста нет: для поиска по скану понадобится OCR.')
        return '✅ Документ добавлен в базу знаний: '+safe+'\nТеперь Корсик сможет искать в нём ответы.'
    except Exception:
        with connect() as c:
            c.execute('INSERT INTO knowledge_audit(uploader_id,filename,status) VALUES(?,?,?)',(str(uid),safe,'ошибка'))
        raise
    finally:
        Path(tmp).unlink(missing_ok=True)

def statistics():
    init()
    with connect() as c:
        registered=c.execute("SELECT COUNT(*) FROM staff_registry WHERE role='employee' AND active=1").fetchone()[0]
        activated=c.execute("SELECT COUNT(*) FROM staff_registry WHERE role='employee' AND active=1 AND max_user_id IS NOT NULL").fetchone()[0]
        docs=c.execute("SELECT COUNT(*) FROM knowledge_audit WHERE status='успешно'").fetchone()[0]
        tickets=c.execute("SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0]
    return (f'📊 Статистика Корсика\n\nВ реестре сотрудников: {registered}\nАктивировали бота: {activated}\n'
            f'Открытых обращений: {tickets}\nУспешных загрузок документов: {docs}\n\n'
            'Завершение адаптации подробно доступно HR в Excel-отчёте.')

def audit_history():
    init()
    with connect() as c:
        rows=c.execute("""SELECT k.uploaded_at,k.filename,k.status,k.uploader_id,
            COALESCE(s.name, 'MAX '+k.uploader_id) AS person
            FROM knowledge_audit k LEFT JOIN staff_registry s ON s.max_user_id=k.uploader_id
            ORDER BY k.id DESC LIMIT 30""").fetchall()
    if not rows:return '📂 История загрузок\n\nПока нет записей. Новые загрузки будут фиксироваться автоматически.'
    return '📂 История загрузок (последние 30)\n\n'+'\n\n'.join(
        f"{r['uploaded_at']} · {r['person']}\n{r['filename']} · {r['status']}" for r in rows)
