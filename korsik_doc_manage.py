"""Safe HR management of uploaded knowledge documents only."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
from database import connect
from korsik_knowledge import DOC_DIR, ALLOWED, init


def _docs():
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    return sorted((p for p in DOC_DIR.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED and not p.is_symlink()), key=lambda p: p.name.casefold())


def _key(name):
    return sha256(name.encode('utf-8')).hexdigest()[:16]


def _find(key):
    return next((p for p in _docs() if _key(p.name) == key), None)


def show_list(action):
    files = _docs()
    if not files:
        return '📚 Загруженных HR-документов пока нет.\n\n1. 📚 База знаний'
    label='Удалить' if action=='delete' else 'Заменить'
    lines=[('🗑️ Удаление документов' if action=='delete' else '♻️ Замена документов'), 'Выбери документ из списка:']
    for index, item in enumerate(files[:35],1):
        lines.append(f'{index}. {label} №{index} — {item.name[:110]}')
    if len(files)>35:
        lines.append('Показаны первые 35 файлов.')
    return '\n'.join(lines)


def selected_by_number(number):
    try: i=int(number)
    except (TypeError, ValueError): return None
    docs=_docs()
    return docs[i-1] if 1<=i<=min(len(docs),35) else None


def begin(action, number):
    file=selected_by_number(number)
    if file is None:return None, 'Файл не найден в списке. Откройте список заново.'
    key=_key(file.name)
    if action=='delete':
        return f'knowledge_delete:{key}', f'⚠️ Удалить «{file.name}» из базы знаний?\n\n1. ✅ Подтвердить удаление\n2. ❌ Отменить'
    return f'knowledge_replace:{key}', f'♻️ Замена документа «{file.name}».\n\nОтправьте новую версию файлом с ТОЧНО ТАКИМ ЖЕ именем. После успешной обработки старая версия будет заменена.\n\nДля отмены нажмите «🏠 Главное меню».'


def current_file(state):
    try: action,key=state.split(':',1)
    except (ValueError,AttributeError):return None
    if action not in ('knowledge_delete','knowledge_replace') or len(key)!=16:return None
    return _find(key)


def remove(uid, state):
    file=current_file(state)
    if file is None:return 'Файл уже удалён или переименован. Откройте список заново.'
    init()
                                                                                      
    name=file.name
    file.unlink()
                                                                           
    try:
        from korsik_pdf_ocr import _cache_path
        _cache_path(file).unlink(missing_ok=True)
    except (ImportError, OSError):pass
    with connect() as c:
        c.execute('INSERT INTO knowledge_audit(uploader_id,filename,status) VALUES(?,?,?)', (str(uid),name,'удалено'))
    return f'✅ Документ удалён из базы знаний: {name}\nПоиск больше не будет использовать этот файл.\n\n1. 📚 База знаний'
