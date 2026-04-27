"""
api.dependencies
----------------
FastAPI dependencies. The Core Engine is constructed once and shared.
"""

from __future__ import annotations

from functools import lru_cache

from core.engine import InterviewEngine


@lru_cache(maxsize=1)
def get_engine() -> InterviewEngine:
    """Process-wide singleton engine."""
    return InterviewEngine()
