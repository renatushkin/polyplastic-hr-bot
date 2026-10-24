import sqlite3
from pathlib import Path
DB_PATH = Path(__file__).with_name('employee_onboarding.db')
SCHEMA_PATH = Path(__file__).with_name('schema.sql')
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn
def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding='utf-8'))
        conn.execute('INSERT OR IGNORE INTO onboarding_templates(name, version, description) VALUES (?, ?, ?)',
                     ('базовый сценарий адаптации', 1, 'Сценарий из ТЗ'))
