"""
core.db
-------
Persistence backend. Supports BOTH:

  - SQLite      (DATABASE_URL=sqlite:///./data/interview.db)   default for dev
  - PostgreSQL  (DATABASE_URL=postgresql://user:pw@host/db)    for free Supabase /
                                                                Neon hosting

The two engines disagree on: parameter placeholder ('?' vs '%s'),
auto-now (`datetime('now')` vs `now()`), upsert syntax, and the
return-value of INSERT. We hide all of that behind `cursor()` and
`run_returning()` so callers write portable SQL.

Schema is identical for both — we only use ANSI types plus TEXT/INTEGER/REAL.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator, List, Optional, Sequence
from urllib.parse import urlparse, parse_qs

from core.config import get_settings
from core.logging_setup import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------

def _backend() -> str:
    url = get_settings().storage.database_url
    if url.startswith("sqlite:"):
        return "sqlite"
    if url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
        return "postgres"
    raise RuntimeError(f"Unsupported DATABASE_URL scheme: {url!r}")


BACKEND = _backend()

# Parameter placeholder per backend — sqlite uses '?', psycopg uses '%s'.
_PH = "?" if BACKEND == "sqlite" else "%s"


def q(sql: str) -> str:
    """
    Translate a query written with '?' placeholders into the active backend's
    placeholder style. Lets every call site stay portable:

        cur.execute(q("SELECT 1 FROM users WHERE id=?"), (uid,))
    """
    return sql.replace("?", _PH) if _PH != "?" else sql


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

_CONN = None
_CONN_LOCK = threading.Lock()


def _open_sqlite():
    url = get_settings().storage.database_url
    path = url.replace("sqlite:///", "", 1)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _open_postgres():
    # Imported lazily so SQLite-only deployments don't need psycopg installed.
    import psycopg
    from psycopg.rows import dict_row

    url = get_settings().storage.database_url
    # psycopg accepts postgres:// and postgresql:// URIs natively.
    conn = psycopg.connect(url, autocommit=False, row_factory=dict_row)
    return conn


def _open():
    if BACKEND == "sqlite":
        return _open_sqlite()
    return _open_postgres()


def get_conn():
    global _CONN
    with _CONN_LOCK:
        if _CONN is None:
            _CONN = _open()
            _init_schema(_CONN)
        return _CONN


@contextmanager
def cursor() -> Iterator[Any]:
    """
    Yield a cursor whose `.fetchone()` / `.fetchall()` return mapping-style
    rows on BOTH backends (sqlite3.Row and psycopg dict_row both support
    `row["column"]`).

    Auto-commits on clean exit, rolls back on exception.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def insert_returning_id(cur, sql_with_qmarks: str, params: Sequence) -> int:
    """
    Run an INSERT and return the new row's primary key on either backend.
    The SQL must NOT include RETURNING — the helper appends it for Postgres
    and reads `lastrowid` for SQLite.
    """
    if BACKEND == "sqlite":
        cur.execute(q(sql_with_qmarks), params)
        return int(cur.lastrowid)
    cur.execute(q(sql_with_qmarks) + " RETURNING id", params)
    row = cur.fetchone()
    return int(row["id"])


# ---------------------------------------------------------------------------
# Schema — written in portable SQL.
# Differences:
#   - SERIAL vs INTEGER PRIMARY KEY AUTOINCREMENT
#   - now() vs datetime('now')
#   - JSON column: TEXT works on both (we serialize manually).
# ---------------------------------------------------------------------------

def _schema_sql() -> List[str]:
    pk = (
        "INTEGER PRIMARY KEY AUTOINCREMENT"
        if BACKEND == "sqlite"
        else "SERIAL PRIMARY KEY"
    )
    now = "datetime('now')" if BACKEND == "sqlite" else "NOW()"
    ts_default = f"DEFAULT ({now})" if BACKEND == "sqlite" else f"DEFAULT {now}"
    # Postgres rejects the parens around DEFAULT NOW().
    ts = "TEXT" if BACKEND == "sqlite" else "TIMESTAMPTZ"

    return [
        f"""
        CREATE TABLE IF NOT EXISTS users (
            id            {pk},
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    {ts} NOT NULL {ts_default}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS sessions (
            id              TEXT PRIMARY KEY,
            user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
            domain          TEXT,
            experience      TEXT,
            topics          TEXT,
            custom_topic    TEXT,
            target_questions INTEGER,
            started_at      {ts} NOT NULL {ts_default},
            ended_at        {ts},
            state_json      TEXT NOT NULL
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS questions (
            id              TEXT PRIMARY KEY,
            session_id      TEXT REFERENCES sessions(id) ON DELETE CASCADE,
            user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
            question_index  INTEGER,
            topic           TEXT,
            qtype           TEXT,
            question_text   TEXT,
            answer_text     TEXT,
            score_label     TEXT,
            score_value     INTEGER,
            feedback        TEXT,
            ideal_answer    TEXT,
            model_used      TEXT,
            asked_at        {ts} NOT NULL {ts_default}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS grades (
            id              {pk},
            session_id      TEXT UNIQUE REFERENCES sessions(id) ON DELETE CASCADE,
            user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
            domain          TEXT,
            experience      TEXT,
            topics          TEXT,
            total_questions INTEGER,
            overall_score   REAL,
            score_label     TEXT,
            strengths       TEXT,
            improvements    TEXT,
            recommendations TEXT,
            per_topic       TEXT,
            duration_seconds INTEGER,
            completed_at    {ts} NOT NULL {ts_default}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS topic_stats (
            user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
            topic           TEXT,
            total_questions INTEGER NOT NULL DEFAULT 0,
            total_score     INTEGER NOT NULL DEFAULT 0,
            avg_score       REAL    NOT NULL DEFAULT 0,
            last_updated    {ts}    NOT NULL {ts_default},
            PRIMARY KEY (user_id, topic)
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS custom_topics (
            id           {pk},
            user_id      INTEGER REFERENCES users(id) ON DELETE CASCADE,
            topic_name   TEXT NOT NULL,
            requested_at {ts} NOT NULL {ts_default}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS auth_tokens (
            token       TEXT PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at  {ts} NOT NULL {ts_default},
            expires_at  {ts} NOT NULL
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_grades_user ON grades(user_id, completed_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_questions_session ON questions(session_id, question_index);",
        "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, started_at DESC);",
    ]


def _init_schema(conn) -> None:
    cur = conn.cursor()
    try:
        for stmt in _schema_sql():
            cur.execute(stmt)
        conn.commit()
        log.info("DB schema ready (backend=%s)", BACKEND)
    finally:
        cur.close()


# ---------------------------------------------------------------------------
# Cross-DB helpers used by callers
# ---------------------------------------------------------------------------

def now_sql() -> str:
    """SQL fragment returning the current timestamp on this backend."""
    return "datetime('now')" if BACKEND == "sqlite" else "NOW()"


def upsert_topic_stats_sql() -> str:
    """
    INSERT-or-update for topic_stats. Returns a backend-specific UPSERT.
    Callers pass (user_id, topic, score_value, score_value_float).
    """
    if BACKEND == "sqlite":
        return """
        INSERT INTO topic_stats(user_id, topic, total_questions, total_score, avg_score)
        VALUES (?, ?, 1, ?, ?)
        ON CONFLICT(user_id, topic) DO UPDATE SET
            total_questions = total_questions + 1,
            total_score     = total_score + excluded.total_score,
            avg_score       = (total_score + excluded.total_score) * 1.0
                              / (total_questions + 1),
            last_updated    = datetime('now')
        """
    return """
    INSERT INTO topic_stats(user_id, topic, total_questions, total_score, avg_score)
    VALUES (%s, %s, 1, %s, %s)
    ON CONFLICT (user_id, topic) DO UPDATE SET
        total_questions = topic_stats.total_questions + 1,
        total_score     = topic_stats.total_score + EXCLUDED.total_score,
        avg_score       = (topic_stats.total_score + EXCLUDED.total_score) * 1.0
                          / (topic_stats.total_questions + 1),
        last_updated    = NOW()
    """


def insert_or_replace_sql(table: str, columns: List[str], conflict_keys: List[str]) -> str:
    """
    Build an INSERT … ON CONFLICT … DO UPDATE statement. Used for the
    `questions` and `grades` tables which are keyed on a primary key but
    we sometimes re-evaluate the same question and want to overwrite.
    """
    cols = ", ".join(columns)
    placeholders = ", ".join([_PH] * len(columns))
    updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in columns if c not in conflict_keys)
    keys = ", ".join(conflict_keys)
    return (
        f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT ({keys}) DO UPDATE SET {updates}"
    )
