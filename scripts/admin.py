"""Admin: list employees, tickets, progress; no MAX connection required."""

import sys as _korsik_sys
from pathlib import Path as _korsik_Path
_korsik_root = _korsik_Path(__file__).resolve().parent.parent
if str(_korsik_root) not in _korsik_sys.path:
    _korsik_sys.path.insert(0, str(_korsik_root))
import argparse
from database import init_db,connect
from onboarding import STEPS
p=argparse.ArgumentParser();p.add_argument('command',choices=['employees','tickets','stats']);args=p.parse_args()
init_db()
with connect() as c:
    if args.command=='employees':
        for r in c.execute('SELECT id,name,tags,step FROM employees ORDER BY id'):print(dict(r))
    elif args.command=='tickets':
        for r in c.execute('SELECT id,employee_id,status,question,answer FROM tickets ORDER BY id DESC'):print(dict(r))
    else:
        print('Этапов из Excel:',len(STEPS))
        print('Сотрудников:',c.execute('SELECT COUNT(*) FROM employees').fetchone()[0])
        print('Обращений HR:',c.execute('SELECT COUNT(*) FROM tickets').fetchone()[0])
