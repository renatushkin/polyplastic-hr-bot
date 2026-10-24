PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS employees (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 max_user_id TEXT UNIQUE,
 full_name TEXT NOT NULL,
 position TEXT,
 department TEXT,
 start_date TEXT NOT NULL,
 preferred_address TEXT NOT NULL DEFAULT 'ты' CHECK(preferred_address IN ('ты','вы')),
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed','paused')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS onboarding_templates (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1,
 description TEXT,
 is_active INTEGER NOT NULL DEFAULT 1,
 UNIQUE(name, version)
);
CREATE TABLE IF NOT EXISTS scenario_steps (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 template_id INTEGER NOT NULL,
 source_row INTEGER,
 step_order INTEGER NOT NULL,
 schedule_text TEXT,
 trigger_type TEXT NOT NULL DEFAULT 'manual',
 information_reason TEXT,
 employee_tags TEXT,
 form_name TEXT,
 message_text TEXT NOT NULL,
 mandatory INTEGER NOT NULL DEFAULT 0,
 attachment TEXT,
 extra_notes TEXT,
 FOREIGN KEY(template_id) REFERENCES onboarding_templates(id) ON DELETE CASCADE,
 UNIQUE(template_id, step_order)
);
CREATE TABLE IF NOT EXISTS step_conditions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 step_id INTEGER NOT NULL,
 answer_value TEXT NOT NULL,
 next_step_id INTEGER NOT NULL,
 FOREIGN KEY(step_id) REFERENCES scenario_steps(id) ON DELETE CASCADE,
 FOREIGN KEY(next_step_id) REFERENCES scenario_steps(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS employee_onboarding (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 employee_id INTEGER NOT NULL,
 template_id INTEGER NOT NULL,
 start_date TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'in_progress' CHECK(status IN ('in_progress','completed','paused')),
 assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE,
 FOREIGN KEY(template_id) REFERENCES onboarding_templates(id)
);
CREATE TABLE IF NOT EXISTS employee_step_state (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 onboarding_id INTEGER NOT NULL,
 step_id INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'not_started' CHECK(status IN ('not_started','in_progress','completed','skipped')),
 answer_text TEXT,
 sent_at TEXT,
 completed_at TEXT,
 reminder_count INTEGER NOT NULL DEFAULT 0,
 UNIQUE(onboarding_id, step_id),
 FOREIGN KEY(onboarding_id) REFERENCES employee_onboarding(id) ON DELETE CASCADE,
 FOREIGN KEY(step_id) REFERENCES scenario_steps(id)
);
CREATE INDEX IF NOT EXISTS idx_steps_template_order ON scenario_steps(template_id, step_order);
CREATE INDEX IF NOT EXISTS idx_progress_onboarding_status ON employee_step_state(onboarding_id, status);
