"""HR registry, role-based access, one-time MAX activation codes. No third-party deps."""
import csv, hashlib, hmac, json, os, re, secrets, sqlite3, zipfile
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from database import connect

ROLES = {'employee','hr','admin'}
TAGS = {'GTP','GrPP','Luzhniki'}
HEADERS = ['ФИО','Телефон','Роль','Тег','Дата выхода','Телефон руководителя']

def phone(value):
    digits = re.sub(r'\D','',str(value or ''))
    if len(digits)==11 and digits[0] in '78': return '+7'+digits[1:]
    if len(digits)==10: return '+7'+digits
    if 10<=len(digits)<=15: return '+'+digits
    raise ValueError('Телефон должен содержать 10–15 цифр')

def init_accounts():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS staff_registry(
          phone TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
          tags TEXT NOT NULL DEFAULT '[]', start_date TEXT, manager_phone TEXT,
          code_hash TEXT, max_user_id TEXT UNIQUE, activated_at TEXT,
          active INTEGER NOT NULL DEFAULT 1);
        CREATE INDEX IF NOT EXISTS ix_staff_role ON staff_registry(role);
        CREATE TABLE IF NOT EXISTS onboarding_profiles(employee_id TEXT PRIMARY KEY,start_date TEXT,mode TEXT DEFAULT 'demo');
        ''')

def hash_code(code):
    return hashlib.sha256(code.encode('utf-8')).hexdigest()

def _xlsx_rows(path):
    ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
            strings=[''.join(n.text or '' for n in si.findall('.//m:t',ns)) for si in root.findall('m:si',ns)]
        workbook=ET.fromstring(z.read('xl/workbook.xml'))
        sheets=workbook.findall('m:sheets/m:sheet',ns)
        names=[s.attrib.get('name','') for s in sheets]
        idx=next((i for i,n in enumerate(names) if n.casefold()=='пользователи'),0)
        rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        relmap={r.attrib['Id']:r.attrib['Target'] for r in rels}
        relid=sheets[idx].attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        target=relmap[relid].lstrip('/')
        if not target.startswith('xl/'):target='xl/'+target
        root=ET.fromstring(z.read(target))
        for row in root.findall('.//m:sheetData/m:row',ns):
            result={}
            for cell in row.findall('m:c',ns):
                ref=cell.attrib.get('r','A1'); letters=re.match('[A-Z]+',ref).group()
                col=0
                for ch in letters:col=col*26+ord(ch)-64
                v=cell.find('m:v',ns)
                inline=cell.find('m:is',ns)
                raw=v.text if v is not None else ''.join(n.text or '' for n in inline.findall('.//m:t',ns)) if inline is not None else ''
                if cell.attrib.get('t')=='s' and raw:raw=strings[int(raw)]
                result[col-1]=raw or ''
            if result:yield [result.get(i,'') for i in range(max(result)+1)]

def read_registry(path):
    path=Path(path)
    if path.suffix.lower()=='.xlsx': rows=list(_xlsx_rows(path))
    elif path.suffix.lower()=='.csv':
        with path.open(encoding='utf-8-sig',newline='') as f:
            sample=f.read(4096);f.seek(0)
            delim=';' if sample.count(';')>sample.count(',') else ','
            rows=list(csv.reader(f,delimiter=delim))
    else:raise ValueError('Поддерживаются .xlsx и .csv')
    if not rows:raise ValueError('Пустой реестр')
    header=[str(x).strip().casefold() for x in rows[0]]
    aliases={'name':['фио','имя'], 'phone':['телефон','номер телефона'], 'role':['роль'], 'tags':['тег','теги'], 'start':['дата выхода','дата начала'], 'manager':['телефон руководителя','руководитель']}
    positions={k:next((header.index(a) for a in choices if a in header),None) for k,choices in aliases.items()}
    for k in ('name','phone','role'):
        if positions[k] is None:raise ValueError('Нет обязательного столбца: '+aliases[k][0])
    out=[]; seen=set()
    for rowno,row in enumerate(rows[1:],2):
        def val(key):
            p=positions[key];return str(row[p]).strip() if p is not None and p<len(row) else ''
        if not any(str(x).strip() for x in row):continue
        try:
            name=val('name');p=phone(val('phone'));role=val('role').lower() or 'employee'
            if not name or role not in ROLES:raise ValueError('ФИО или роль неверны')
            rawtags=[x.strip() for x in re.split('[,;/]',val('tags')) if x.strip()]
            tags=[]
            for tag in rawtags:
                match=next((t for t in TAGS if t.casefold()==tag.casefold()),None)
                if not match:raise ValueError('Неизвестный тег '+tag)
                if match not in tags:tags.append(match)
            start=val('start')
            if start:
                if re.fullmatch(r'\d{2}\.\d{2}\.\d{4}',start):start=datetime.strptime(start,'%d.%m.%Y').date().isoformat()
                elif re.fullmatch(r'\d+(?:\.0)?',start):
                    from datetime import timedelta
                    start=(date(1899,12,30)+timedelta(days=int(float(start)))).isoformat()
                else:start=date.fromisoformat(start).isoformat()
            manager=phone(val('manager')) if val('manager') else None
            if p in seen:raise ValueError('Дублирующийся телефон')
            seen.add(p);out.append({'name':name,'phone':p,'role':role,'tags':tags,'start':start or None,'manager':manager})
        except ValueError as e:raise ValueError(f'Строка {rowno}: {e}') from e
    return out

                              

def import_staff(path, allow_roles=False):
    """Полная синхронизация сотрудников с отзывом доступа отсутствующих."""
    rows = read_registry(path)

    if not rows:
        raise ValueError("Пустой реестр не принимается.")

    if not allow_roles and any(r["role"] != "employee" for r in rows):
        raise PermissionError(
            "HR может импортировать только обычных сотрудников."
        )

    init_accounts()
    created = []
    incoming = {r["phone"] for r in rows}

    with connect() as c:
        c.execute("BEGIN IMMEDIATE")

        current = c.execute(
            "SELECT phone FROM staff_registry "
            "WHERE active=1 AND role='employee'"
        ).fetchall()

        missing = [
            r["phone"] for r in current
            if r["phone"] not in incoming
        ]

                                                               
        if len(current) >= 5 and len(missing) * 4 > len(current) * 3:
            raise ValueError(
                f"Загрузка отклонена: отсутствует {len(missing)} "
                f"из {len(current)} сотрудников. "
                "Проверьте, что Excel содержит ПОЛНЫЙ реестр."
            )

        for r in rows:
            existing = c.execute(
                "SELECT role, active, max_user_id "
                "FROM staff_registry WHERE phone=?",
                (r["phone"],)
            ).fetchone()

                                                              
            if existing and not allow_roles and existing["role"] != "employee":
                raise PermissionError(
                    "HR не может изменять привилегированные роли: " + r["phone"]
                )

                                                                    
            need_code = existing is None or existing["active"] == 0
            code = (
                secrets.token_urlsafe(12)
                if need_code and r["role"] == "employee"
                else None
            )

            c.execute("""
                INSERT INTO staff_registry(
                    phone, name, role, tags, start_date,
                    manager_phone, code_hash, active
                )
                VALUES(?,?,?,?,?,?,?,1)
                ON CONFLICT(phone) DO UPDATE SET
                    name=excluded.name,
                    role=excluded.role,
                    tags=excluded.tags,
                    start_date=excluded.start_date,
                    manager_phone=excluded.manager_phone,
                    active=1,
                    code_hash=CASE
                        WHEN staff_registry.active=0
                        THEN excluded.code_hash
                        ELSE staff_registry.code_hash
                    END,
                    max_user_id=CASE
                        WHEN staff_registry.active=0
                        THEN NULL
                        ELSE staff_registry.max_user_id
                    END,
                    activated_at=CASE
                        WHEN staff_registry.active=0
                        THEN NULL
                        ELSE staff_registry.activated_at
                    END
            """, (
                r["phone"],
                r["name"],
                r["role"],
                json.dumps(r["tags"]),
                r["start"],
                r["manager"],
                hash_code(code) if code else None
            ))

            if code:
                created.append({
                    "name": r["name"],
                    "phone": r["phone"],
                    "role": r["role"],
                    "code": code
                })

            if existing and existing["active"] and existing["max_user_id"]:
                eid = "max-" + existing["max_user_id"]

                c.execute(
                    "UPDATE employees SET name=?, tags=? WHERE id=?",
                    (r["name"], json.dumps(r["tags"]), eid)
                )

                if r["start"] and r["role"] == "employee":
                    c.execute("""
                        INSERT INTO onboarding_profiles(
                            employee_id, start_date, mode
                        )
                        VALUES(?,?,'calendar')
                        ON CONFLICT(employee_id) DO UPDATE SET
                            start_date=excluded.start_date,
                            mode='calendar'
                    """, (eid, r["start"]))

                                                           
        for number in missing:
            c.execute("""
                UPDATE staff_registry
                SET active=0,
                    code_hash=NULL,
                    max_user_id=NULL,
                    activated_at=NULL
                WHERE phone=?
                  AND role='employee'
                  AND active=1
            """, (number,))

    print(
        f"[РЕЕСТР] загружено: {len(rows)}; "
        f"отключено: {len(missing)}"
    )
    return len(rows), created

def activate(max_user_id, code):
    init_accounts();code=code.strip()
    if len(code)>128 or len(code)<8:return None
    digest=hash_code(code)
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        existing=c.execute('SELECT phone FROM staff_registry WHERE max_user_id=?',(str(max_user_id),)).fetchone()
        if existing:return {'error':'Этот MAX-аккаунт уже привязан. Обратитесь к HR для смены.'}
        row=c.execute('SELECT * FROM staff_registry WHERE code_hash=? AND active=1',(digest,)).fetchone()
        if not row:return None
        if row['max_user_id']:return None
        if row['role']!='employee':return {'error':'Для HR и администратора используйте /request ТЕЛЕФОН и подтверждение администратором.'}
        c.execute('''UPDATE staff_registry SET max_user_id=?,activated_at=CURRENT_TIMESTAMP,code_hash=NULL
                     WHERE phone=? AND code_hash=? AND max_user_id IS NULL''',(str(max_user_id),row['phone'],digest))
        if c.execute('SELECT changes()').fetchone()[0]!=1:return None
        eid='max-'+str(max_user_id)
        c.execute('''INSERT INTO employees(id,name,tags,hr_id) VALUES(?,?,?,'hr-demo')
                     ON CONFLICT(id) DO UPDATE SET name=excluded.name,tags=excluded.tags''',
                  (eid,row['name'],row['tags']))
        if row['start_date'] and row['role']=='employee':
            c.execute('''INSERT INTO onboarding_profiles(employee_id,start_date,mode) VALUES(?,?,'calendar')
               ON CONFLICT(employee_id) DO UPDATE SET start_date=excluded.start_date,mode='calendar' ''',(eid,row['start_date']))
    return {'name':row['name'],'role':row['role'],'tags':json.loads(row['tags']),'start_date':row['start_date']}

def account(max_user_id):
    init_accounts()
    with connect() as c:
        r=c.execute('SELECT * FROM staff_registry WHERE max_user_id=? AND active=1',(str(max_user_id),)).fetchone()
    return dict(r) if r and r['role'] in ROLES else None

def tickets_for_hr():
    with connect() as c:
        return c.execute('''SELECT t.id,t.employee_id,t.question,t.status FROM tickets t
                             WHERE t.status='open' ORDER BY t.id DESC LIMIT 20''').fetchall()

def team_status(manager_phone):
    init_accounts()
    with connect() as c:
        return c.execute('''SELECT s.name,s.tags,s.start_date,s.max_user_id,e.step
            FROM staff_registry s LEFT JOIN employees e ON e.id='max-'||s.max_user_id
            WHERE s.manager_phone=? AND s.role='employee' AND s.active=1 ORDER BY s.name''',(manager_phone,)).fetchall()
