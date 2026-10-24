"""Index previously uploaded scanned PDFs once; run with python -u korsik_ocr_reindex.py."""
from pathlib import Path
from document_search import DOCS_DIR,read_document

folders=[DOCS_DIR,DOCS_DIR.parent/'policy_docs']
files=sorted(p for folder in folders if folder.exists() for p in folder.rglob('*.pdf'))
print(f'PDF для проверки: {len(files)}',flush=True)
for idx,path in enumerate(files,1):
    print(f'\n[{idx}/{len(files)}] {path.name}',flush=True)
    try:
        pages=list(read_document(path))
        letters=sum(len(t) for _,t in pages)
        print(f'✅ Страниц с текстом: {len(pages)}, символов: {letters}',flush=True)
        if letters==0:
            print('⚠️ OCR не нашёл читаемого текста',flush=True)
    except Exception as e:
        print(f'❌ {type(e).__name__}: {e}',flush=True)
print('\nОбработка завершена.',flush=True)
