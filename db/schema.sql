CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    parent_id   TEXT REFERENCES tasks(id),
    level       TEXT CHECK(level IN ('epic','feature','task','subtask')),
    status      TEXT CHECK(status IN ('pending','decomposing','ready',
                    'in_progress','in_review','testing','done',
                    'blocked','stuck')),
    title       TEXT NOT NULL,
    spec_ref    TEXT,
    assigned_to TEXT,
    model       TEXT,
    branch      TEXT,
    acceptance  JSON,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_edges (
    blocker_id  TEXT REFERENCES tasks(id),
    blocked_id  TEXT REFERENCES tasks(id),
    PRIMARY KEY (blocker_id, blocked_id)
);

CREATE TABLE IF NOT EXISTS decisions (
    id          TEXT PRIMARY KEY,
    task_id     TEXT REFERENCES tasks(id),
    type        TEXT,
    rapid_r     TEXT,
    rapid_a     TEXT,
    rapid_d     TEXT,
    status      TEXT CHECK(status IN ('proposed','agreed','vetoed',
                    'escalated','resolved')),
    context     JSON,
    resolved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id          TEXT PRIMARY KEY,
    task_id     TEXT REFERENCES tasks(id),
    agent_role  TEXT NOT NULL,
    model       TEXT NOT NULL,
    started_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    iterations  INTEGER,
    token_in    INTEGER,
    token_out   INTEGER,
    outcome     TEXT CHECK(outcome IN ('success','revise','bug',
                    'stuck','escalated','error')),
    output      JSON
);

CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    task_id     TEXT REFERENCES tasks(id),
    agent_role  TEXT,
    run_id      TEXT REFERENCES agent_runs(id),
    event_type  TEXT NOT NULL,
    event_data  JSON NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type, timestamp);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id);

CREATE VIEW IF NOT EXISTS epic_costs AS
SELECT
    t2.title as epic_title,
    t.parent_id as epic_id,
    SUM(ar.token_in) as total_tokens_in,
    SUM(ar.token_out) as total_tokens_out,
    COUNT(DISTINCT ar.id) as total_runs,
    COUNT(DISTINCT t.id) as total_tasks
FROM tasks t
JOIN agent_runs ar ON t.id = ar.task_id
LEFT JOIN tasks t2 ON t.parent_id = t2.id
GROUP BY t.parent_id;

CREATE VIEW IF NOT EXISTS cycle_hotspots AS
SELECT
    task_id,
    COUNT(*) as cycle_count,
    GROUP_CONCAT(DISTINCT json_extract(event_data, '$.reason')) as reasons
FROM events
WHERE event_type = 'task.cycle'
GROUP BY task_id
ORDER BY cycle_count DESC;

CREATE VIEW IF NOT EXISTS agent_efficiency AS
SELECT
    agent_role,
    model,
    COUNT(*) as total_runs,
    AVG(token_in + token_out) as avg_tokens,
    AVG(CAST((julianday(finished_at) - julianday(started_at)) * 86400000 AS INTEGER)) as avg_wall_clock_ms,
    SUM(CASE outcome WHEN 'success' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate_pct,
    AVG(iterations) as avg_ralph_iterations
FROM agent_runs
WHERE finished_at IS NOT NULL
GROUP BY agent_role, model;
