"""Offline trusted admin CLI. Never run from bot user messages."""

import sys as _korsik_sys
from pathlib import Path as _korsik_Path
_korsik_root = _korsik_Path(__file__).resolve().parent.parent
if str(_korsik_root) not in _korsik_sys.path:
    _korsik_sys.path.insert(0, str(_korsik_root))
import argparse, csv, os
from pathlib import Path
from database import init_db
from accounts import init_accounts, import_staff

def main():
    p=argparse.ArgumentParser(description='Корсик: безопасный импорт сотрудников и ролей')
    p.add_argument('file',help='Excel .xlsx или CSV с листом Пользователи')
    p.add_argument('--codes',default='activation_codes.csv',help='Файл выдачи новых кодов HR (НЕ публиковать)')
    a=p.parse_args()
    init_db();init_accounts()
    count,codes=import_staff(a.file,allow_roles=True)
    if codes:
        target=Path(a.codes)
        with target.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['name','phone','role','code'],delimiter=';')
            w.writeheader();w.writerows(codes)
        try:os.chmod(target,0o600)
        except OSError:pass
        print(f'Новые коды: {target.resolve()} (секретный файл, выдавайте персонально)')
    print(f'Импортировано записей: {count}; новых кодов: {len(codes)}')
if __name__=='__main__':main()
