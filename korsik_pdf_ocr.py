"""Local, cached OCR for scan-based PDF pages. No external service calls."""
from pathlib import Path
import hashlib, json, os, shutil, subprocess, tempfile
from pypdf import PdfReader

CACHE_ROOT = Path(__file__).resolve().parent / 'data' / 'ocr_cache'
MAX_OCR_PAGES = 250

def _cache_path(path):
    key = hashlib.sha256(str(Path(path).resolve()).encode('utf-8')).hexdigest()
    return CACHE_ROOT / (key+'.json')

def _metadata(path):
    stat=Path(path).stat()
    return {'size':stat.st_size,'mtime_ns':stat.st_mtime_ns}

def cache_pdf_pages(path, pages):
    path=Path(path)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    value={'metadata':_metadata(path),'pages':[[loc, text] for loc,text in pages]}
    dest=_cache_path(path)
    fd,tmp=tempfile.mkstemp(prefix='ocr_',suffix='.tmp',dir=CACHE_ROOT)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:
            json.dump(value,out,ensure_ascii=False)
        os.replace(tmp,dest)
    finally:
        Path(tmp).unlink(missing_ok=True)

def _cached(path):
    cache=_cache_path(path)
    if not cache.exists(): return None
    try:
        value=json.loads(cache.read_text(encoding='utf-8'))
        if value.get('metadata')==_metadata(path):
            return [(loc,text) for loc,text in value['pages']]
    except (OSError,ValueError,KeyError,TypeError): pass
    return None

def _ocr_page(path, number):
    if not shutil.which('pdftoppm') or not shutil.which('tesseract'):
        raise RuntimeError('Установите OCR: sudo apt-get install -y tesseract-ocr tesseract-ocr-rus poppler-utils')
    with tempfile.TemporaryDirectory(prefix='korsik_ocr_') as folder:
        prefix=str(Path(folder)/'page')
        render=subprocess.run(['pdftoppm','-f',str(number),'-l',str(number),'-singlefile',
                               '-scale-to','1700','-gray','-png',str(path),prefix],
                               capture_output=True,timeout=50)
        if render.returncode:
            raise RuntimeError('Не удалось открыть страницу PDF для OCR: '+render.stderr.decode('utf-8','replace')[:160])
        pic=prefix+'.png'
        result=subprocess.run(['tesseract',pic,'stdout','-l','rus+eng','--psm','3'],
                              capture_output=True,timeout=75)
        if result.returncode:
            raise RuntimeError('Tesseract не распознал страницу: '+result.stderr.decode('utf-8','replace')[:160])
        return result.stdout.decode('utf-8','replace').strip()

def pdf_pages_with_ocr(path):
    path=Path(path)
    previous=_cached(path)
    if previous is not None:
        yield from previous
        return
    reader=PdfReader(str(path))
    total=len(reader.pages)
    if total>MAX_OCR_PAGES:
        raise ValueError(f'PDF содержит {total} страниц. Лимит OCR: {MAX_OCR_PAGES} страниц; разбейте документ на части.')
    pages=[]
    for number,page in enumerate(reader.pages,1):
        text=(page.extract_text() or '').strip()
        if len(text)<40:
            print(f'[OCR] Страница {number}/{total}: распознавание...',flush=True)
            recognized=_ocr_page(path,number)
            if len(recognized)>len(text): text=recognized
        if text:
            pages.append((f'страница {number}',text))
    cache_pdf_pages(path,pages)
    yield from pages
