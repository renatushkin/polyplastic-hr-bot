"""Отчёт об адаптации сотрудников для HR и администратора."""
import json
import zipfile
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

from database import connect
from onboarding import STEPS, get_current_step


def allowed_tags(uid, admin_id):
    if admin_id and str(uid) == str(admin_id):
        return None

    with connect() as c:
        hr = c.execute("""
            SELECT phone FROM staff_registry
            WHERE max_user_id=? AND role='hr' AND active=1
        """, (str(uid),)).fetchone()

        if not hr:
            raise PermissionError("Только для HR.")

        count = c.execute("""
            SELECT count(*) FROM staff_registry
            WHERE role='hr' AND active=1
              AND max_user_id IS NOT NULL
        """).fetchone()[0]

    if count == 1:
        return {"GTP", "GrPP", "Luzhniki"}

    path = Path(__file__).parent / "data/registry/hr_routes.json"
    routes = json.loads(path.read_text()) if path.exists() else {}

    if not isinstance(routes, dict):
        raise ValueError("Некорректные настройки HR.")

    return {
        tag for tag, phone in routes.items()
        if str(phone) == hr["phone"]
    }


def tags_of(raw):
    try:
        data = json.loads(raw or "[]")
        return data if isinstance(data, list) else []
    except (TypeError, ValueError):
        return []


def _letter(n):
    value = ""
    while n:
        n, remainder = divmod(n - 1, 26)
        value = chr(65 + remainder) + value
    return value


def _sheet(rows):
    result = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/'
        'spreadsheetml/2006/main">',
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/>'
        '</sheetView></sheetViews>',
        '<cols>'
    ]

    for col in range(1, len(rows[0]) + 1):
        width = 34 if col == 1 else 23
        result.append(
            f'<col min="{col}" max="{col}" '
            f'width="{width}" customWidth="1"/>'
        )

    result.append('</cols><sheetData>')

    for n, row in enumerate(rows, 1):
        result.append(f'<row r="{n}">')

        for column, value in enumerate(row, 1):
            address = f"{_letter(column)}{n}"
            value = str(value if value is not None else "")

                                                                
            value = "".join(
                ch for ch in value
                if ord(ch) >= 32 or ch in "\t\n\r"
            )

            value = escape(value)

            result.append(
                f'<c r="{address}" t="inlineStr">'
                f'<is><t>{value}</t></is></c>'
            )

        result.append('</row>')

    result.append('</sheetData>')
    result.append('</worksheet>')
    return "".join(result)


def _write_xlsx(path, employees, summary):
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/'
        'package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.'
        'openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        'spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        'spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet2.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        'spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/'
        'package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '</Relationships>'
    )

    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/'
        'spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships">'
        '<sheets>'
        '<sheet name="Сотрудники" sheetId="1" r:id="rId1"/>'
        '<sheet name="Сводка" sheetId="2" r:id="rId2"/>'
        '</sheets></workbook>'
    )

    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/'
        'package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet2.xml"/>'
        '</Relationships>'
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        z.writestr("xl/worksheets/sheet1.xml", _sheet(employees))
        z.writestr("xl/worksheets/sheet2.xml", _sheet(summary))


def build_report(uid, admin_id, path):
    permitted = allowed_tags(uid, admin_id)
    total_steps = len(STEPS)

    with connect() as c:
        people = c.execute("""
            SELECT s.phone, s.name, s.tags, s.start_date,
                   s.max_user_id, e.step
            FROM staff_registry s
            LEFT JOIN employees e
              ON e.id='max-' || s.max_user_id
            WHERE s.active=1 AND s.role='employee'
            ORDER BY s.name
        """).fetchall()

        ticket_stats = {
            row["employee_id"]: (
                row["total"], row["opened"]
            )
            for row in c.execute("""
                SELECT employee_id,
                       count(*) AS total,
                       sum(CASE WHEN status='open'
                           THEN 1 ELSE 0 END) AS opened
                FROM tickets
                GROUP BY employee_id
            """)
        }

    rows = [[
        "ФИО", "Телефон", "Подразделение",
        "Дата выхода", "Активация",
        "Текущий этап", "Пройдено этапов",
        "Прогресс", "Следующий этап",
        "Всего обращений", "Открытых обращений"
    ]]

    counts = Counter()
    departments = {}

    for person in people:
        tags = tags_of(person["tags"])

        if permitted is not None and not (
            set(tags) & permitted
        ):
            continue

        active = bool(person["max_user_id"])
        eid = "max-" + str(person["max_user_id"]) if active else None

        completed = 0
        current = "Ожидает активации"
        next_date = ""

        if active:
            completed = max(
                0,
                min(int(person["step"] or 0), total_steps)
            )

            step = get_current_step(eid)

            if step.get("done"):
                completed = total_steps
                current = "Адаптация завершена"

            elif step.get("waiting"):
                current = "Ожидает следующего этапа"
                next_date = step.get("due") or ""

            else:
                current = f"Этап {completed + 1} из {total_steps}"

        percentage = (
            round(completed * 100 / total_steps)
            if total_steps else 0
        )

        total_tickets, opened = ticket_stats.get(
            eid, (0, 0)
        )

        rows.append([
            person["name"], person["phone"],
            ", ".join(tags),
            person["start_date"] or "",
            "Да" if active else "Нет",
            current, completed, f"{percentage}%",
            next_date, total_tickets, opened
        ])

        counts["employees"] += 1
        counts["activated"] += int(active)
        counts["completed"] += int(
            active and completed == total_steps
        )
        counts["open_tickets"] += opened

        for tag in tags or ["Без подразделения"]:
            g = departments.setdefault(tag, Counter())
            g["employees"] += 1
            g["activated"] += int(active)
            g["completed"] += int(
                active and completed == total_steps
            )
            g["open_tickets"] += opened

    summary = [[
        "Подразделение", "Сотрудников",
        "Активировали", "Завершили",
        "Открытых обращений"
    ], [
        "ИТОГО",
        counts["employees"],
        counts["activated"],
        counts["completed"],
        counts["open_tickets"]
    ]]

    for tag, data in sorted(departments.items()):
        summary.append([
            tag, data["employees"], data["activated"],
            data["completed"], data["open_tickets"]
        ])

    _write_xlsx(path, rows, summary)
    return dict(counts)
