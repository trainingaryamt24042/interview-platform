"""
api.history_routes
------------------
/dashboard, /grades, /grades/{id}, /topic-stats — everything the
post-login UI needs to render the dashboard, history list, scoreboard,
and per-session drill-down.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from api.auth_routes import current_user
from core.auth import User
from core.history import (
    get_dashboard,
    get_grade_questions,
    get_grades,
    get_topic_stats,
)

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/dashboard")
def dashboard(user: User = Depends(current_user)) -> Dict[str, Any]:
    return get_dashboard(user.id)


@router.get("/grades")
def grades(user: User = Depends(current_user)) -> List[Dict[str, Any]]:
    return get_grades(user.id)


@router.get("/grades/{session_id}/questions")
def grade_questions(session_id: str, user: User = Depends(current_user)) -> List[Dict[str, Any]]:
    rows = get_grade_questions(user.id, session_id)
    if not rows:
        raise HTTPException(status_code=404, detail="No questions for this session")
    return rows


@router.get("/topic-stats")
def topic_stats(user: User = Depends(current_user)) -> List[Dict[str, Any]]:
    return get_topic_stats(user.id)
