import sys
from pathlib import Path
import pandas as pd
from db import connect, init_db

def clean(value):
    if pd.isna(value): return None
    value = str(value).strip()
    return value or None

def import_excel(path, sheet_name=None):
    path = Path(path)
    if not path.exists(): raise FileNotFoundError(f'Файл не найден: {path}')
    book = pd.ExcelFile(path)
    if sheet_name is None:
        sheet_name = next((s for s in book.sheet_names if '24.10.2026' in s), book.sheet_names[0])
    df = pd.read_excel(path, sheet_name=sheet_name, header=1)
    init_db(); imported = skipped = 0
    with connect() as conn:
        template_id = conn.execute('SELECT id FROM onboarding_templates WHERE name=? AND version=1',
            ('базовый сценарий адаптации',)).fetchone()['id']
        conn.execute('DELETE FROM scenario_steps WHERE template_id=?', (template_id,))
        for idx, row in df.iterrows():
            msg = clean(row.get('Текст сообщения'))
            if not msg:
                skipped += 1; continue
            schedule = clean(row.get('Месяц/день/время информирования'))
            reason = clean(row.get('Информационный повод'))
            tags = clean(row.get('Тег сотрудника'))
            form = clean(row.get('Форма/Макет'))
            mandatory_raw = (clean(row.get('Обязательный этап')) or '').lower()
            mandatory = int(mandatory_raw in ('да','yes','true','1'))
            attachment = clean(row.get('Сопроводительное изображение'))
            extras = ' | '.join(f'{c}: {clean(row.get(c))}' for c in df.columns if str(c).startswith('Unnamed:') and clean(row.get(c))) or None
            imported += 1
            conn.execute('''INSERT INTO scenario_steps
              (template_id, source_row, step_order, schedule_text, trigger_type, information_reason, employee_tags, form_name, message_text, mandatory, attachment, extra_notes)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (template_id, idx + 3, imported, schedule, 'scheduled' if schedule else 'manual', reason, tags, form, msg, mandatory, attachment, extras))
    return {'sheet': sheet_name, 'imported': imported, 'skipped_without_message': skipped, 'template_id': template_id}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python import_excel.py "/path/to/workbook.xlsx"'); raise SystemExit(2)
    print(import_excel(sys.argv[1]))
