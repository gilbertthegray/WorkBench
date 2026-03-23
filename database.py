"""
database.py — FlowDesk SQLite persistence layer
Handles all reads/writes to flowdesk.db.
JSON columns store nested structures (stages, custom_fields, members, history).
"""
import sqlite3, json, uuid
from contextlib import contextmanager
from datetime import datetime

DB_PATH = "flowdesk.db"


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@contextmanager
def _conn():
    """WAL-mode connection with Row factory. Auto-commits on success."""
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEMA
# ══════════════════════════════════════════════════════════════════════════════
def init_db():
    """Create all tables if they don't exist. Safe to call on every startup."""
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id       TEXT PRIMARY KEY,
            name     TEXT NOT NULL,
            email    TEXT UNIQUE NOT NULL,
            role     TEXT NOT NULL DEFAULT 'member',
            groups   TEXT NOT NULL DEFAULT '[]',
            active   INTEGER NOT NULL DEFAULT 1,
            created  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS groups (
            id          TEXT PRIMARY KEY,
            name        TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            color       TEXT NOT NULL DEFAULT '#3b82f6',
            members     TEXT NOT NULL DEFAULT '[]',
            email       TEXT NOT NULL DEFAULT '',
            created     TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workflows (
            id            TEXT PRIMARY KEY,
            name          TEXT UNIQUE NOT NULL,
            description   TEXT DEFAULT '',
            icon          TEXT DEFAULT '📋',
            sla_hours     INTEGER NOT NULL DEFAULT 72,
            active        INTEGER NOT NULL DEFAULT 1,
            stages        TEXT NOT NULL DEFAULT '[]',
            custom_fields TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id            TEXT PRIMARY KEY,
            title         TEXT NOT NULL,
            description   TEXT DEFAULT '',
            workflow_id   TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'New',
            priority      TEXT NOT NULL DEFAULT 'medium',
            stage_index   INTEGER NOT NULL DEFAULT 0,
            progress      INTEGER NOT NULL DEFAULT 0,
            created       TEXT NOT NULL,
            created_by    TEXT NOT NULL,
            due           TEXT DEFAULT '',
            closed_at     TEXT DEFAULT '',
            custom_fields TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (workflow_id) REFERENCES workflows(id)
        );

        CREATE TABLE IF NOT EXISTS history (
            id       TEXT PRIMARY KEY,
            task_id  TEXT NOT NULL,
            action   TEXT NOT NULL,
            by       TEXT NOT NULL,
            time     TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id   TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            msg  TEXT NOT NULL,
            time TEXT NOT NULL,
            read INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        INSERT OR IGNORE INTO settings (key, value) VALUES ('task_counter', '1000');
        """)

    # Migration: add email column to groups for existing databases
    with _conn() as con:
        cols = [row[1] for row in con.execute("PRAGMA table_info(groups)").fetchall()]
        if "email" not in cols:
            con.execute("ALTER TABLE groups ADD COLUMN email TEXT NOT NULL DEFAULT ''")


# ══════════════════════════════════════════════════════════════════════════════
#  TASK COUNTER
# ══════════════════════════════════════════════════════════════════════════════
def get_task_counter() -> int:
    with _conn() as con:
        row = con.execute("SELECT value FROM settings WHERE key='task_counter'").fetchone()
    return int(row["value"]) if row else 1000


def increment_task_counter() -> int:
    with _conn() as con:
        con.execute("UPDATE settings SET value = CAST(value AS INTEGER) + 1 WHERE key='task_counter'")
        row = con.execute("SELECT value FROM settings WHERE key='task_counter'").fetchone()
    return int(row["value"])


# ══════════════════════════════════════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
def get_settings() -> dict:
    with _conn() as con:
        rows = con.execute("SELECT key, value FROM settings").fetchall()
    raw = {r["key"]: r["value"] for r in rows}
    return {
        "sla_warn_hours":   int(raw.get("sla_warn_hours", 4)),
        "auto_escalate":    raw.get("auto_escalate", "1") == "1",
        "default_strategy": raw.get("default_strategy", "Manual"),
    }


def save_settings(cfg: dict):
    with _conn() as con:
        for k, v in cfg.items():
            val = "1" if v is True else ("0" if v is False else str(v))
            con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, val))


# ══════════════════════════════════════════════════════════════════════════════
#  USERS
# ══════════════════════════════════════════════════════════════════════════════
def _row_to_user(row) -> dict:
    d = dict(row)
    d["groups"] = json.loads(d["groups"])
    d["active"] = bool(d["active"])
    return d


def get_users() -> list:
    with _conn() as con:
        rows = con.execute("SELECT * FROM users ORDER BY created").fetchall()
    return [_row_to_user(r) for r in rows]


def upsert_user(u: dict):
    with _conn() as con:
        con.execute("""
            INSERT INTO users (id, name, email, role, groups, active, created)
            VALUES (:id, :name, :email, :role, :groups, :active, :created)
            ON CONFLICT(id) DO UPDATE SET
                name   = excluded.name,
                email  = excluded.email,
                role   = excluded.role,
                groups = excluded.groups,
                active = excluded.active
        """, {**u,
              "groups": json.dumps(u.get("groups", [])),
              "active": 1 if u.get("active", True) else 0})


def delete_user(uid: str):
    with _conn() as con:
        con.execute("DELETE FROM users WHERE id=?", (uid,))


# ══════════════════════════════════════════════════════════════════════════════
#  GROUPS
# ══════════════════════════════════════════════════════════════════════════════
def _row_to_group(row) -> dict:
    d = dict(row)
    d["members"] = json.loads(d["members"])
    d["email"]   = d.get("email") or ""
    return d


def get_groups() -> list:
    with _conn() as con:
        rows = con.execute("SELECT * FROM groups ORDER BY name").fetchall()
    return [_row_to_group(r) for r in rows]


def upsert_group(g: dict):
    with _conn() as con:
        con.execute("""
            INSERT INTO groups (id, name, description, color, members, email, created)
            VALUES (:id, :name, :description, :color, :members, :email, :created)
            ON CONFLICT(id) DO UPDATE SET
                name        = excluded.name,
                description = excluded.description,
                color       = excluded.color,
                members     = excluded.members,
                email       = excluded.email
        """, {**g,
              "members":     json.dumps(g.get("members", [])),
              "description": g.get("description", ""),
              "email":       g.get("email", ""),
              "created":     g.get("created", _now())})


def delete_group(gid: str):
    with _conn() as con:
        con.execute("DELETE FROM groups WHERE id=?", (gid,))


# ══════════════════════════════════════════════════════════════════════════════
#  WORKFLOWS
# ══════════════════════════════════════════════════════════════════════════════
def _row_to_workflow(row) -> dict:
    d = dict(row)
    d["stages"]        = json.loads(d["stages"])
    d["custom_fields"] = json.loads(d["custom_fields"])
    d["active"]        = bool(d["active"])
    return d


def get_workflows() -> list:
    with _conn() as con:
        rows = con.execute("SELECT * FROM workflows ORDER BY name").fetchall()
    return [_row_to_workflow(r) for r in rows]


def upsert_workflow(w: dict):
    with _conn() as con:
        con.execute("""
            INSERT INTO workflows
                (id, name, description, icon, sla_hours, active, stages, custom_fields)
            VALUES
                (:id, :name, :description, :icon, :sla_hours, :active, :stages, :custom_fields)
            ON CONFLICT(id) DO UPDATE SET
                name          = excluded.name,
                description   = excluded.description,
                icon          = excluded.icon,
                sla_hours     = excluded.sla_hours,
                active        = excluded.active,
                stages        = excluded.stages,
                custom_fields = excluded.custom_fields
        """, {**w,
              "stages":        json.dumps(w.get("stages", [])),
              "custom_fields": json.dumps(w.get("custom_fields", [])),
              "active":        1 if w.get("active", True) else 0,
              "description":   w.get("description", ""),
              "icon":          w.get("icon", "📋")})


def delete_workflow(wid: str):
    with _conn() as con:
        con.execute("DELETE FROM workflows WHERE id=?", (wid,))


# ══════════════════════════════════════════════════════════════════════════════
#  TASKS
# ══════════════════════════════════════════════════════════════════════════════
def _row_to_task(row, history_map) -> dict:
    d = dict(row)
    d["custom_fields"] = json.loads(d.get("custom_fields") or "{}")
    d["history"]       = history_map.get(d["id"], [])
    return d


def get_tasks() -> list:
    with _conn() as con:
        task_rows = con.execute("SELECT * FROM tasks ORDER BY created DESC").fetchall()
        hist_rows = con.execute("SELECT * FROM history ORDER BY time ASC").fetchall()

    hist_map: dict = {}
    for h in hist_rows:
        hist_map.setdefault(h["task_id"], []).append(dict(h))

    return [_row_to_task(r, hist_map) for r in task_rows]


def upsert_task(t: dict):
    with _conn() as con:
        con.execute("""
            INSERT INTO tasks
                (id, title, description, workflow_id, status, priority,
                 stage_index, progress, created, created_by, due, closed_at, custom_fields)
            VALUES
                (:id, :title, :description, :workflow_id, :status, :priority,
                 :stage_index, :progress, :created, :created_by, :due, :closed_at, :custom_fields)
            ON CONFLICT(id) DO UPDATE SET
                title         = excluded.title,
                description   = excluded.description,
                status        = excluded.status,
                priority      = excluded.priority,
                stage_index   = excluded.stage_index,
                progress      = excluded.progress,
                closed_at     = excluded.closed_at,
                due           = excluded.due,
                custom_fields = excluded.custom_fields
        """, {**t,
              "custom_fields": json.dumps(t.get("custom_fields", {})),
              "description":   t.get("description", ""),
              "due":           t.get("due") or "",
              "closed_at":     t.get("closed_at") or ""})


def delete_task(tid: str):
    with _conn() as con:
        con.execute("DELETE FROM history WHERE task_id=?", (tid,))
        con.execute("DELETE FROM tasks   WHERE id=?",      (tid,))


# ══════════════════════════════════════════════════════════════════════════════
#  HISTORY
# ══════════════════════════════════════════════════════════════════════════════
def add_history(task_id: str, action: str, by: str, time: str = None):
    with _conn() as con:
        con.execute(
            "INSERT INTO history (id, task_id, action, by, time) VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), task_id, action, by, time or _now()))


# ══════════════════════════════════════════════════════════════════════════════
#  NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════════
def get_notifications(limit: int = 100) -> list:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM notifications ORDER BY time DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) | {"read": bool(r["read"])} for r in rows]


def add_notification(ntype: str, msg: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO notifications (id, type, msg, time, read) VALUES (?,?,?,?,0)",
            (str(uuid.uuid4()), ntype, msg, _now()))


def clear_notifications():
    with _conn() as con:
        con.execute("DELETE FROM notifications")


def mark_notification_read(nid: str):
    with _conn() as con:
        con.execute("UPDATE notifications SET read=1 WHERE id=?", (nid,))


# ══════════════════════════════════════════════════════════════════════════════
#  SEED CHECK
# ══════════════════════════════════════════════════════════════════════════════
def needs_seed() -> bool:
    with _conn() as con:
        row = con.execute("SELECT COUNT(*) AS n FROM users").fetchone()
    return row["n"] == 0
