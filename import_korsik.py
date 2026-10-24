import json, re, sys
from pathlib import Path
import pandas as pd
from database import connect, init_db


def clean(v):
    if pd.isna(v):
        return None
    s = str(v).replace("\r", "").strip()
    return s or None


def parse_tags(raw):
    if not raw:
        return []
    return [t.strip() for t in re.split(r"[,\s]+", raw) if t.strip()]


OPT_LINE = re.compile(r"^\s*(?:[-—•]|(?:\d+|[А-ЯA-Z])[\).])\s+(.+)$")


def extract_options(text):
    """Варианты ответов: [(label, value)] в порядке появления."""
    if not text:
        return []
    opts, started = [], False
    for line in text.split("\n"):
        low = line.lower().strip()
        if low.startswith("варианты ответов"):
            started = True
            continue
        m = OPT_LINE.match(line)
        if m and (started or low.startswith(("-", "1)", "2)", "3)", "а)", "б)", "в)"))):
            label = m.group(1).strip()
            code = chr(ord("A") + len(opts))
            opts.append((label, code))
    return opts


BRANCH = re.compile(r"Если\s+(?:ответ(?:или|ил|)\s*|ответ\s*)([А-ЯA-Z0-9\-\s,]+?)\s*:\s*(.+)", re.IGNORECASE)


def extract_branches(text):
    """Условные тексты «Если ответ X: …»."""
    if not text:
        return []
    branches, cur_cond, cur_buf = [], None, []
    for line in text.split("\n"):
        m = BRANCH.match(line.strip())
        if m:
            if cur_cond and cur_buf:
                branches.append((cur_cond, "\n".join(cur_buf).strip()))
            cur_cond, cur_buf = m.group(1).strip(), [m.group(2).strip()]
        elif cur_cond:
            cur_buf.append(line)
    if cur_cond and cur_buf:
        branches.append((cur_cond, "\n".join(cur_buf).strip()))
    return branches


def import_korsik(path, sheet_name="27.02.2026"):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_excel(path, sheet_name=sheet_name, header=1)
    init_db()

    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO onboarding_templates(name, version, description) VALUES(?,?,?)",
            ("базовый сценарий адаптации", 1, "Импорт из ТЗ Корсик"),
        )
        tid = conn.execute(
            "SELECT id FROM onboarding_templates WHERE name=? AND version=1",
            ("базовый сценарий адаптации",),
        ).fetchone()["id"]

        conn.execute("DELETE FROM step_conditions WHERE step_id IN (SELECT id FROM scenario_steps WHERE template_id=?)", (tid,))
        conn.execute("DELETE FROM step_options WHERE step_id IN (SELECT id FROM scenario_steps WHERE template_id=?)", (tid,))
        conn.execute("DELETE FROM step_branches WHERE step_id IN (SELECT id FROM scenario_steps WHERE template_id=?)", (tid,))
        conn.execute("DELETE FROM scenario_steps WHERE template_id=?", (tid,))

        imported = skipped = order = 0
        for idx, row in df.iterrows():
            msg = clean(row.get("Текст сообщения"))
            if not msg:
                skipped += 1
                continue
            order += 1

            schedule = clean(row.get("Месяц/день/время информирования"))
            reason = clean(row.get("Информационный повод"))
            tags = parse_tags(clean(row.get("Тег сотрудника")))
            audience_all = 1 if not tags else 0          #нет тега = всем
            form = clean(row.get("Форма/Макет"))
            mand_raw = (clean(row.get("Обязательный этап")) or "").lower()
            mandatory = int(mand_raw in ("да", "yes", "true", "1"))
            attachment = clean(row.get("Сопроводительное изображение"))

            extras = []
            for col in df.columns:
                if str(col).startswith("Unnamed") or col == "J":
                    val = clean(row.get(col))
                    if val:
                        extras.append(val)

            step_key = f"step_{order:03d}"
            cur = conn.execute(
                """INSERT INTO scenario_steps
                   (template_id, step_key, source_row, step_order, schedule_text,
                    trigger_type, information_reason, employee_tags, audience_all,
                    form_name, message_text, mandatory, attachment, extra_notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    tid, step_key, idx + 3, order,
                    schedule,
                    "scheduled" if schedule else "manual",
                    reason,
                    json.dumps(tags, ensure_ascii=False),
                    audience_all,
                    form, msg, mandatory, attachment,
                    " | ".join(extras) if extras else None,
                ),
            )
            step_id = cur.lastrowid
            imported += 1

            for i, (label, value) in enumerate(extract_options(msg), start=1):
                conn.execute(
                    "INSERT OR IGNORE INTO step_options(step_id, option_order, label, answer_value) VALUES(?,?,?,?)",
                    (step_id, i, label, value),
                )
            for cond, resp in extract_branches(msg):
                conn.execute(
                    "INSERT INTO step_branches(step_id, condition_text, response_text) VALUES(?,?,?)",
                    (step_id, cond, resp),
                )

        return {"sheet": sheet_name, "template_id": tid, "imported": imported, "skipped": skipped}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_korsik.py 'file.xlsx' [sheet]")
        raise SystemExit(2)
    print(import_korsik(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "27.02.2026"))