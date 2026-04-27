"""
core.history
------------
Persistence + read helpers for everything the user sees on the dashboard,
history page, and scoreboard.

Writes:
    save_question_score()  — one row per Q answered, updates topic_stats
    save_grade()           — one row per completed session
    save_custom_topic()    — track free-form topics users requested

Reads:
    get_grades(user_id)
    get_grade_questions(user_id, session_id)
    get_topic_stats(user_id)
    get_weak_topics(user_id, threshold)
    get_dashboard(user_id)
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from core.db import cursor, q, upsert_topic_stats_sql, insert_or_replace_sql, now_sql
from core.logging_setup import get_logger
from core.models import (
    Domain,
    Evaluation,
    ExperienceLevel,
    Question,
    SCORE_VALUES,
    ScoreLabel,
    Session,
    SessionSummary,
)

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Session persistence (sessions row + state_json blob)
# ---------------------------------------------------------------------------

def upsert_session(user_id: Optional[int], session: Session) -> None:
    """Insert/update a session. Called from the engine on every state change."""
    cfg = session.config
    state_json = session.model_dump_json()
    with cursor() as cur:
        cur.execute(
            q(
                """
                INSERT INTO sessions
                  (id, user_id, domain, experience, topics, custom_topic,
                   target_questions, started_at, ended_at, state_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  ended_at=EXCLUDED.ended_at,
                  state_json=EXCLUDED.state_json
                """
            ),
            (
                session.id, user_id,
                cfg.domain.value, cfg.experience.value,
                json.dumps(cfg.topics),
                cfg.custom_topic,
                cfg.target_questions,
                session.created_at,
                session.ended_at,
                state_json,
            ),
        )


def load_session_state(session_id: str) -> Optional[str]:
    with cursor() as cur:
        cur.execute(q("SELECT state_json FROM sessions WHERE id=?"), (session_id,))
        row = cur.fetchone()
    return row["state_json"] if row else None


# ---------------------------------------------------------------------------
# Per-question scores
# ---------------------------------------------------------------------------

def save_question_score(
    *,
    session_id: str,
    user_id: Optional[int],
    question_index: int,
    question: Question,
    answer: str,
    evaluation: Evaluation,
) -> None:
    with cursor() as cur:
        cur.execute(
            insert_or_replace_sql(
                "questions",
                columns=[
                    "id", "session_id", "user_id", "question_index", "topic", "qtype",
                    "question_text", "answer_text", "score_label", "score_value",
                    "feedback", "ideal_answer", "model_used",
                ],
                conflict_keys=["id"],
            ),
            (
                question.id, session_id, user_id, question_index,
                question.topic, question.qtype.value,
                question.text, answer,
                evaluation.score_label.value, evaluation.score_value,
                evaluation.feedback, evaluation.ideal_answer,
                evaluation.model_used,
            ),
        )

        # Aggregate topic stats — only if the user is logged in.
        if user_id is not None:
            score_value = evaluation.score_value
            cur.execute(
                upsert_topic_stats_sql(),
                (user_id, question.topic, score_value, float(score_value)),
            )


# ---------------------------------------------------------------------------
# Grades
# ---------------------------------------------------------------------------

def save_grade(
    *,
    session_id: str,
    user_id: Optional[int],
    session: Session,
    summary: SessionSummary,
) -> None:
    cfg = session.config
    with cursor() as cur:
        cur.execute(
            insert_or_replace_sql(
                "grades",
                columns=[
                    "session_id", "user_id", "domain", "experience", "topics",
                    "total_questions", "overall_score", "score_label",
                    "strengths", "improvements", "recommendations",
                    "per_topic", "duration_seconds",
                ],
                conflict_keys=["session_id"],
            ),
            (
                session_id, user_id,
                cfg.domain.value, cfg.experience.value,
                json.dumps(cfg.topics + ([cfg.custom_topic] if cfg.custom_topic else [])),
                summary.total_questions,
                float(summary.overall_score),
                summary.score_label.value,
                json.dumps(summary.strengths),
                json.dumps(summary.improvements),
                json.dumps(summary.recommendations),
                json.dumps(summary.per_topic_scores),
                summary.duration_seconds,
            ),
        )


# ---------------------------------------------------------------------------
# Custom topics
# ---------------------------------------------------------------------------

def save_custom_topic(user_id: int, topic_name: str) -> None:
    if not topic_name.strip():
        return
    with cursor() as cur:
        cur.execute(
            q("INSERT INTO custom_topics(user_id, topic_name) VALUES(?, ?)"),
            (user_id, topic_name.strip()),
        )


def get_custom_topics(user_id: int, limit: int = 20) -> List[str]:
    with cursor() as cur:
        cur.execute(
            q(
                """
                SELECT topic_name, MAX(requested_at) AS last_used
                FROM custom_topics
                WHERE user_id=?
                GROUP BY topic_name
                ORDER BY last_used DESC
                LIMIT ?
                """
            ),
            (user_id, limit),
        )
        return [r["topic_name"] for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Read helpers — used by /grades, /topic-stats, /dashboard
# ---------------------------------------------------------------------------

def _row_to_dict(r: Any) -> Dict[str, Any]:
    """Both backends now use mapping rows, but force a plain dict for JSON."""
    return dict(r)


def get_grades(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    with cursor() as cur:
        cur.execute(
            q(
                """
                SELECT * FROM grades
                WHERE user_id=?
                ORDER BY completed_at DESC
                LIMIT ?
                """
            ),
            (user_id, limit),
        )
        rows = [_row_to_dict(r) for r in cur.fetchall()]
    for r in rows:
        # JSON columns
        for k in ("topics", "strengths", "improvements", "recommendations", "per_topic"):
            if r.get(k):
                try:
                    r[k] = json.loads(r[k]) if isinstance(r[k], str) else r[k]
                except Exception:
                    r[k] = []
        # overall_score may come back as Decimal on Postgres.
        if r.get("overall_score") is not None:
            r["overall_score"] = float(r["overall_score"])
        # Stringify timestamps so the API response is JSON-stable.
        if r.get("completed_at") is not None and not isinstance(r["completed_at"], str):
            r["completed_at"] = r["completed_at"].isoformat()
    return rows


def get_last_grade(user_id: int) -> Optional[Dict[str, Any]]:
    grades = get_grades(user_id, limit=1)
    return grades[0] if grades else None


def get_grade_questions(user_id: int, session_id: str) -> List[Dict[str, Any]]:
    with cursor() as cur:
        cur.execute(
            q(
                """
                SELECT * FROM questions
                WHERE user_id=? AND session_id=?
                ORDER BY question_index ASC
                """
            ),
            (user_id, session_id),
        )
        rows = [_row_to_dict(r) for r in cur.fetchall()]
    for r in rows:
        if r.get("asked_at") is not None and not isinstance(r["asked_at"], str):
            r["asked_at"] = r["asked_at"].isoformat()
    return rows


def get_topic_stats(user_id: int) -> List[Dict[str, Any]]:
    with cursor() as cur:
        cur.execute(
            q(
                """
                SELECT topic, total_questions, total_score, avg_score, last_updated
                FROM topic_stats
                WHERE user_id=?
                ORDER BY avg_score ASC, total_questions DESC
                """
            ),
            (user_id,),
        )
        rows = [_row_to_dict(r) for r in cur.fetchall()]
    for r in rows:
        if r.get("avg_score") is not None:
            r["avg_score"] = float(r["avg_score"])
        if r.get("last_updated") is not None and not isinstance(r["last_updated"], str):
            r["last_updated"] = r["last_updated"].isoformat()
    return rows


def get_weak_topics(user_id: int, threshold: float = 1.8) -> List[str]:
    return [s["topic"] for s in get_topic_stats(user_id) if s["avg_score"] < threshold]


def get_dashboard(user_id: int) -> Dict[str, Any]:
    """Combined data the dashboard needs in one round trip."""
    last = get_last_grade(user_id)
    stats = get_topic_stats(user_id)
    weak = [s["topic"] for s in stats if s["avg_score"] < 1.8]
    strong = [s["topic"] for s in stats if s["avg_score"] >= 2.5]

    with cursor() as cur:
        cur.execute(
            q("SELECT COUNT(*) AS n FROM grades WHERE user_id=?"),
            (user_id,),
        )
        total_sessions = int(cur.fetchone()["n"])
        cur.execute(
            q("SELECT COALESCE(AVG(overall_score),0) AS s FROM grades WHERE user_id=?"),
            (user_id,),
        )
        career_avg = float(cur.fetchone()["s"])

    return {
        "has_history": total_sessions > 0,
        "total_sessions": total_sessions,
        "career_average": round(career_avg, 2),
        "last_grade": last,
        "topic_stats": stats,
        "weak_topics": weak,
        "strong_topics": strong,
        "custom_topics": get_custom_topics(user_id),
    }
