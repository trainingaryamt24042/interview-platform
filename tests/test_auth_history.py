"""
End-to-end tests for auth + history. Uses an isolated SQLite file so it
can't pollute the dev DB. The LLM router is replaced with a fake.
"""

import importlib
import os
import sys
import tempfile

import pytest


# ---------------------------------------------------------------------------
# Per-test isolated DB + cached singletons reset
# ---------------------------------------------------------------------------

@pytest.fixture()
def app_client(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("OPENROUTER_AUTO_DISCOVER", "0")

    # Wipe ALL cached project state so the new env vars take effect.
    for mod_name in list(sys.modules):
        if mod_name == "core" or mod_name.startswith(("core.", "api.")):
            del sys.modules[mod_name]

    # Now reimport with fresh state.
    from core import config
    config.get_settings.cache_clear()

    # Build a fake LLM router that returns canned responses.
    from core.llm.base import LLMProvider
    from core.models import LLMRequest, LLMResponse
    from core.llm.router import LLMRouter
    from core.engine import InterviewEngine

    class _Canned(LLMProvider):
        name = "canned"
        def is_configured(self): return True
        def models(self): return ["c1"]
        def generate(self, req: LLMRequest, model: str) -> LLMResponse:
            sys_lower = req.system.lower()
            if "interview question" in sys_lower or "question_type" in sys_lower:
                text = (
                    "QUESTION_TYPE: conceptual\n"
                    "TOPIC: SQL\n"
                    "QUESTION:\nExplain primary keys.\n"
                    "EXPECTED_POINTS:\n- uniqueness\n- not null\n- one per table"
                )
            elif "evaluating a candidate" in sys_lower:
                text = (
                    "RATING: Good\n"
                    "STRENGTHS:\n- clear definition\n"
                    "GAPS:\n- did not mention composite keys\n"
                    "IDEAL_ANSWER:\nA primary key uniquely identifies each row.\n"
                    "FEEDBACK:\nSolid baseline answer."
                )
            elif "post-interview report" in sys_lower:
                text = (
                    "OVERALL: Good\n"
                    "STRENGTHS:\n- understands fundamentals\n"
                    "IMPROVEMENTS:\n- depth on advanced topics\n"
                    "RECOMMENDATIONS:\n- read SQL window functions"
                )
            else:
                text = "ok"
            return LLMResponse(text=text, model=model, provider=self.name, latency_ms=1)

    fake_engine = InterviewEngine(router=LLMRouter(providers=[_Canned()]))

    # Replace get_engine BEFORE api.main / api.routes are imported, so
    # Depends(get_engine) at decoration time captures our fake.
    import api.dependencies as deps
    deps.get_engine = lambda: fake_engine     # type: ignore[assignment]

    from fastapi.testclient import TestClient
    from api.main import app

    # Belt and braces: also register an override.
    app.dependency_overrides[deps.get_engine] = lambda: fake_engine

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_register_login_logout_cycle(app_client):
    # Register
    r = app_client.post("/api/v1/auth/register", json={"username": "alice", "password": "secret123"})
    assert r.status_code == 201
    assert r.json()["username"] == "alice"
    # Cookie set
    assert "ip_session" in app_client.cookies

    # /me works while logged in
    r = app_client.get("/api/v1/auth/me")
    assert r.status_code == 200

    # Logout clears cookie
    app_client.post("/api/v1/auth/logout")
    r = app_client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_register_duplicate_username(app_client):
    app_client.post("/api/v1/auth/register", json={"username": "bob", "password": "abcd"})
    r = app_client.post("/api/v1/auth/register", json={"username": "bob", "password": "abcd"})
    assert r.status_code == 409


def test_full_interview_flow_persists_grade(app_client):
    # Register & log in
    app_client.post("/api/v1/auth/register", json={"username": "charlie", "password": "abcd"})

    # Create session
    r = app_client.post(
        "/api/v1/session",
        json={
            "domain": "data_engineering",
            "experience": "mid",
            "topics": ["SQL"],
            "target_questions": 2,
        },
    )
    assert r.status_code == 201
    session_id = r.json()["session_id"]

    # 2 questions answered
    for _ in range(2):
        r = app_client.post("/api/v1/generate-question", json={"session_id": session_id})
        assert r.status_code == 200
        qid = r.json()["question"]["id"]
        r = app_client.post(
            "/api/v1/evaluate-answer",
            json={"session_id": session_id, "question_id": qid, "answer": "A primary key is unique."},
        )
        assert r.status_code == 200

    # End session
    r = app_client.post(f"/api/v1/session/{session_id}/end")
    assert r.status_code == 200
    s = r.json()["summary"]
    assert s["total_questions"] == 2
    assert s["score_label"] in ("poor", "good", "excellent")

    # History endpoints reflect the session
    r = app_client.get("/api/v1/history/grades")
    assert r.status_code == 200
    grades = r.json()
    assert len(grades) == 1
    assert grades[0]["total_questions"] == 2

    r = app_client.get(f"/api/v1/history/grades/{session_id}/questions")
    assert r.status_code == 200
    assert len(r.json()) == 2

    r = app_client.get("/api/v1/history/topic-stats")
    assert r.status_code == 200
    stats = r.json()
    assert any(s["topic"] == "SQL" for s in stats)

    r = app_client.get("/api/v1/history/dashboard")
    assert r.status_code == 200
    dash = r.json()
    assert dash["has_history"] is True
    assert dash["total_sessions"] == 1


def test_history_endpoints_require_auth(app_client):
    r = app_client.get("/api/v1/history/dashboard")
    assert r.status_code == 401
    r = app_client.get("/api/v1/history/grades")
    assert r.status_code == 401
