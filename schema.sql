-- сотрудники
CREATE TABLE IF NOT EXISTS employees (
    id TEXT PRIMARY KEY,
    name TEXT,
    tags TEXT NOT NULL DEFAULT '[]',  --JSON-массив тегов, [] = без тегов
    hr_id TEXT,
    step INTEGER DEFAULT 0
);

-- сообщения
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    employee_id TEXT REFERENCES employees(id),
    author TEXT,
    text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ответы на шаги (совместимость/аналитика)
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY,
    employee_id TEXT,
    step_id TEXT,
    answer TEXT,
    UNIQUE(employee_id, step_id)
);

-- обращения к HR
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY,
    employee_id TEXT REFERENCES employees(id),
    hr_id TEXT,
    question TEXT,
    status TEXT DEFAULT 'open',
    answer TEXT
);

-- профиль сотрудника
CREATE TABLE IF NOT EXISTS employee_profiles (
    employee_id TEXT PRIMARY KEY,
    max_user_id TEXT UNIQUE,
    position TEXT,
    department TEXT,
    start_date TEXT,
    preferred_address TEXT NOT NULL DEFAULT 'ты'
        CHECK(preferred_address IN ('ты', 'вы')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active', 'completed', 'paused')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

-- шаблоны адаптации
CREATE TABLE IF NOT EXISTS onboarding_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
    UNIQUE(name, version)
);

-- шаги адаптации
CREATE TABLE IF NOT EXISTS scenario_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    step_key TEXT NOT NULL,
    source_row INTEGER,
    step_order INTEGER NOT NULL,
    schedule_text TEXT,
    trigger_type TEXT NOT NULL DEFAULT 'manual',
    information_reason TEXT,
    employee_tags TEXT NOT NULL DEFAULT '[]',   -- '[]' = без ограничения
    audience_all INTEGER NOT NULL DEFAULT 0
        CHECK(audience_all IN (0,1)),           -- 1 = слать всем
    form_name TEXT,
    message_text TEXT NOT NULL,
    mandatory INTEGER NOT NULL DEFAULT 0 CHECK(mandatory IN (0,1)),
    attachment TEXT,
    extra_notes TEXT,
    FOREIGN KEY(template_id) REFERENCES onboarding_templates(id) ON DELETE CASCADE,
    UNIQUE(template_id, step_key),
    UNIQUE(template_id, step_order)
);

-- варианты ответов
CREATE TABLE IF NOT EXISTS step_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id INTEGER NOT NULL,
    option_order INTEGER NOT NULL,
    label TEXT NOT NULL,
    answer_value TEXT NOT NULL,
    FOREIGN KEY(step_id) REFERENCES scenario_steps(id) ON DELETE CASCADE,
    UNIQUE(step_id, option_order),
    UNIQUE(step_id, answer_value)
);

-- явные переходы между шагами по ответу
CREATE TABLE IF NOT EXISTS step_conditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id INTEGER NOT NULL,
    answer_value TEXT NOT NULL,
    next_step_id INTEGER NOT NULL,
    FOREIGN KEY(step_id) REFERENCES scenario_steps(id) ON DELETE CASCADE,
    FOREIGN KEY(next_step_id) REFERENCES scenario_steps(id) ON DELETE CASCADE,
    UNIQUE(step_id, answer_value)
);

-- условные тексты внутри шага
CREATE TABLE IF NOT EXISTS step_branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id INTEGER NOT NULL,
    condition_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    FOREIGN KEY(step_id) REFERENCES scenario_steps(id) ON DELETE CASCADE
);

-- назначение адаптации
CREATE TABLE IF NOT EXISTS employee_onboarding (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    template_id INTEGER NOT NULL,
    start_date TEXT,
    status TEXT NOT NULL DEFAULT 'in_progress'
        CHECK(status IN ('in_progress','completed','paused')),
    assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    FOREIGN KEY(template_id) REFERENCES onboarding_templates(id),
    UNIQUE(employee_id, template_id)
);

-- прогресс по шагам
CREATE TABLE IF NOT EXISTS employee_step_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    onboarding_id INTEGER NOT NULL,
    step_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_started'
        CHECK(status IN ('not_started','in_progress','completed','skipped')),
    answer_text TEXT,
    sent_at TEXT,
    completed_at TEXT,
    reminder_count INTEGER NOT NULL DEFAULT 0 CHECK(reminder_count >= 0),
    UNIQUE(onboarding_id, step_id),
    FOREIGN KEY(onboarding_id) REFERENCES employee_onboarding(id) ON DELETE CASCADE,
    FOREIGN KEY(step_id) REFERENCES scenario_steps(id)
);

-- индексы
CREATE INDEX IF NOT EXISTS idx_messages_employee ON messages(employee_id, id);
CREATE INDEX IF NOT EXISTS idx_tickets_hr_status ON tickets(hr_id, status);
CREATE INDEX IF NOT EXISTS idx_steps_template_order ON scenario_steps(template_id, step_order);
CREATE INDEX IF NOT EXISTS idx_progress_onboarding_status ON employee_step_state(onboarding_id, status);
CREATE INDEX IF NOT EXISTS idx_branches_step ON step_branches(step_id);
CREATE INDEX IF NOT EXISTS idx_options_step ON step_options(step_id, option_order);
CREATE INDEX IF NOT EXISTS idx_state_onb ON employee_step_state(onboarding_id, status);
CREATE INDEX IF NOT EXISTS idx_answers_emp ON answers(employee_id, step_id);