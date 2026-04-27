"""
api.schemas
-----------
HTTP-layer request/response models. We re-export Core models where they're
already a perfect fit and add small wrappers where the wire format differs.

Keeping these in their own file means the Core stays free of FastAPI/Pydantic
v2 idioms that don't belong in the business logic.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from core.models import (
    Domain,
    Evaluation,
    ExperienceLevel,
    Question,
    QuestionType,
    Scenario,
    SessionConfig,
    SessionSummary,
)

# ---- Re-exports (no wrapping needed) ----
__all__ = [
    "CreateSessionRequest",
    "CreateSessionResponse",
    "GenerateQuestionRequest",
    "GenerateQuestionResponse",
    "EvaluateAnswerRequest",
    "EvaluateAnswerResponse",
    "GenerateScenarioRequest",
    "GenerateScenarioResponse",
    "EndSessionResponse",
    "TopicCatalogResponse",
]


class CreateSessionRequest(BaseModel):
    domain: Domain
    experience: ExperienceLevel
    topics: List[str] = []
    custom_topic: Optional[str] = None
    target_questions: int = 10


class CreateSessionResponse(BaseModel):
    session_id: str
    config: SessionConfig


class GenerateQuestionRequest(BaseModel):
    session_id: str
    qtype: Optional[QuestionType] = None


class GenerateQuestionResponse(BaseModel):
    question: Question
    question_index: int
    total_so_far: int


class EvaluateAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str


class EvaluateAnswerResponse(BaseModel):
    evaluation: Evaluation


class GenerateScenarioRequest(BaseModel):
    session_id: str
    topic: Optional[str] = None


class GenerateScenarioResponse(BaseModel):
    scenario: Scenario


class EndSessionResponse(BaseModel):
    summary: SessionSummary


class TopicCatalogResponse(BaseModel):
    domains: dict[str, list[str]]
