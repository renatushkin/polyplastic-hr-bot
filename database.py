import os, sqlite3, json
from pathlib import Path
DB = os.getenv("DATABASE_PATH", "runtime/korsik.db")
def connect():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS employees(id TEXT PRIMARY KEY, name TEXT, tags TEXT, hr_id TEXT, step INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, employee_id TEXT REFERENCES employees(id), author TEXT, text TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS answers(id INTEGER PRIMARY KEY, employee_id TEXT, step_id TEXT, answer TEXT, UNIQUE(employee_id,step_id));
        CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY, employee_id TEXT REFERENCES employees(id), hr_id TEXT, question TEXT, status TEXT DEFAULT 'open', answer TEXT);
        """)
                                                                                   
        schema_path = Path(__file__).with_name("schema.sql")
        if schema_path.exists():
            c.executescript(schema_path.read_text(encoding="utf-8"))
        c.executemany("INSERT OR IGNORE INTO employees(id,name,tags,hr_id) VALUES(?,?,?,?)", [
            ("demo-gtp", "Тестовый сотрудник GTP", json.dumps(["GTP"]), "hr-demo"),
            ("demo-office", "Тестовый сотрудник офиса", json.dumps(["GrPP"]), "hr-demo")])

def employee(employee_id):
    with connect() as c:
        r=c.execute("SELECT * FROM employees WHERE id=?",(employee_id,)).fetchone()
    if not r: raise ValueError("Сотрудник не найден")
    d=dict(r); d["tags"]=json.loads(d["tags"]); return d

def add_message(employee_id, author, text):
    with connect() as c:
        c.execute("INSERT INTO messages(employee_id,author,text) VALUES(?,?,?)",(employee_id,author,text))

def history(employee_id):
    employee(employee_id)
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM messages WHERE employee_id=? ORDER BY id",(employee_id,))]
