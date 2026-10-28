"""SQLite storage for tasks, approvals, and pairing tokens."""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from forge.config import DB_PATH


def _get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a SQLite database connection with row factory enabled."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None):
    """Initialize database tables."""
    conn = _get_connection(db_path)
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            prompt TEXT NOT NULL,
            provider TEXT,
            model TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            result TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY,
            task_id TEXT,
            action_type TEXT NOT NULL,
            action_summary TEXT NOT NULL,
            action_payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            decided_at TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pairing_tokens (
            token TEXT PRIMARY KEY,
            client_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            revoked INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
        CREATE INDEX IF NOT EXISTS idx_approvals_task_id ON approvals(task_id);
        """)
    conn.close()


# --- Task Operations ---

def create_task(
    prompt: str,
    provider: str = "",
    model: str = "",
    task_id: str | None = None,
    db_path: Path | None = None,
) -> str:
    """Insert a new task into the database."""
    tid = task_id or str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO tasks (id, prompt, provider, model, status, result, created_at)
            VALUES (?, ?, ?, ?, 'pending', '', ?)
            """,
            (tid, prompt, provider, model, now),
        )
    conn.close()
    return tid


def update_task_status(
    task_id: str,
    status: str,
    result: str = "",
    db_path: Path | None = None,
):
    """Update status and result of a task."""
    now = datetime.now(timezone.utc).isoformat() if status in ("done", "error", "cancelled") else None
    conn = _get_connection(db_path)
    with conn:
        if now:
            conn.execute(
                """
                UPDATE tasks SET status = ?, result = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, result, now, task_id),
            )
        else:
            conn.execute(
                """
                UPDATE tasks SET status = ?, result = ?
                WHERE id = ?
                """,
                (status, result, task_id),
            )
    conn.close()


def get_task(task_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    """Get task details by ID."""
    conn = _get_connection(db_path)
    cur = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def list_tasks(limit: int = 50, db_path: Path | None = None) -> list[dict[str, Any]]:
    """List recent tasks."""
    conn = _get_connection(db_path)
    cur = conn.execute(
        "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Approval Operations ---

def create_approval(
    action_type: str,
    action_summary: str,
    action_payload: dict,
    task_id: str = "",
    db_path: Path | None = None,
) -> str:
    """Insert a new approval request."""
    aid = f"appr_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc).isoformat()
    payload_str = json.dumps(action_payload, ensure_ascii=False)
    conn = _get_connection(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO approvals (id, task_id, action_type, action_summary, action_payload, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """,
            (aid, task_id, action_type, action_summary, payload_str, now),
        )
    conn.close()
    return aid


def get_approval(approval_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    """Get an approval by ID."""
    conn = _get_connection(db_path)
    cur = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    data["action_payload"] = json.loads(data["action_payload"])
    return data


def list_pending_approvals(db_path: Path | None = None) -> list[dict[str, Any]]:
    """List all pending approval requests."""
    conn = _get_connection(db_path)
    cur = conn.execute(
        "SELECT * FROM approvals WHERE status = 'pending' ORDER BY created_at ASC"
    )
    rows = cur.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["action_payload"] = json.loads(d["action_payload"])
        results.append(d)
    return results


def list_approvals(limit: int = 50, db_path: Path | None = None) -> list[dict[str, Any]]:
    """List recent approvals."""
    conn = _get_connection(db_path)
    cur = conn.execute(
        "SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["action_payload"] = json.loads(d["action_payload"])
        results.append(d)
    return results


def update_approval_status(
    approval_id: str,
    status: str,
    db_path: Path | None = None,
) -> bool:
    """Update approval status (approved, rejected, expired)."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection(db_path)
    with conn:
        cur = conn.execute(
            """
            UPDATE approvals SET status = ?, decided_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (status, now, approval_id),
        )
        updated = cur.rowcount > 0
    conn.close()
    return updated


# --- Pairing Token Operations ---

def create_pairing_token(client_name: str = "Android Device", db_path: Path | None = None) -> str:
    """Generate a new pairing token for remote clients."""
    token = f"frg_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO pairing_tokens (token, client_name, created_at, revoked)
            VALUES (?, ?, ?, 0)
            """,
            (token, client_name, now),
        )
    conn.close()
    return token


def verify_pairing_token(token: str, db_path: Path | None = None) -> bool:
    """Verify if a pairing token is valid and unrevoked."""
    if not token:
        return False
    conn = _get_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    valid = False
    try:
        with conn:
            cur = conn.execute(
                "SELECT token FROM pairing_tokens WHERE token = ? AND revoked = 0",
                (token,),
            )
            row = cur.fetchone()
            if row:
                conn.execute(
                    "UPDATE pairing_tokens SET last_used_at = ? WHERE token = ?",
                    (now, token),
                )
                valid = True
    finally:
        conn.close()
    return valid


def revoke_pairing_token(token: str, db_path: Path | None = None) -> bool:
    """Revoke a pairing token."""
    conn = _get_connection(db_path)
    with conn:
        cur = conn.execute(
            "UPDATE pairing_tokens SET revoked = 1 WHERE token = ?", (token,)
        )
        revoked = cur.rowcount > 0
    conn.close()
    return revoked
