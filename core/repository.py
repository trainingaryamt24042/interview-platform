"""
core.repository
---------------
Session storage abstraction. Default implementation is an in-process dict;
swap to Redis/Postgres for multi-worker production deployments without
changing any caller code.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Dict, Optional

from core.models import Session


class SessionRepository(ABC):
    @abstractmethod
    def save(self, session: Session) -> None: ...
    @abstractmethod
    def get(self, session_id: str) -> Optional[Session]: ...
    @abstractmethod
    def delete(self, session_id: str) -> None: ...


class InMemorySessionRepository(SessionRepository):
    """Thread-safe dict store. Fine for single-worker dev/CLI use."""

    def __init__(self) -> None:
        self._store: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def save(self, session: Session) -> None:
        with self._lock:
            self._store[session.id] = session

    def get(self, session_id: str) -> Optional[Session]:
        with self._lock:
            return self._store.get(session_id)

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._store.pop(session_id, None)


# Module-level singleton — same instance for CLI and FastAPI in dev.
_default_repo: Optional[SessionRepository] = None


def get_repository() -> SessionRepository:
    global _default_repo
    if _default_repo is None:
        _default_repo = InMemorySessionRepository()
    return _default_repo


def set_repository(repo: SessionRepository) -> None:
    """Override at startup, e.g. with a Redis-backed repo."""
    global _default_repo
    _default_repo = repo
