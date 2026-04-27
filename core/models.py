"""
core.models
-----------
Shared data models used by every layer (Core Engine, API, CLI, persistence).
Pydantic gives us validation + JSON serialization for free.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums — keep magic strings out of the codebase
# ---------------------------------------------------------------------------

class Domain(str, Enum):
    DATA_ENGINEERING = "data_engineering"
    BACKEND = "backend"
    AI_ML = "ai_ml"
    DEVOPS = "devops"
    FRONTEND = "frontend"
    SYSTEM_DESIGN = "system_design"


class ExperienceLevel(str, Enum):
    FRESHER = "fresher"             # 0 yrs
    JUNIOR = "junior"               # 1-3 yrs
    MID = "mid"                     # 3-5 yrs
    SENIOR = "senior"               # 5+ yrs


class QuestionType(str, Enum):
    CONCEPTUAL = "conceptual"
    CODING = "coding"
    SCENARIO = "scenario"


class ScoreLabel(str, Enum):
    POOR = "poor"
    GOOD = "good"
    EXCELLENT = "excellent"


SCORE_VALUES: Dict[ScoreLabel, int] = {
    ScoreLabel.POOR: 1,
    ScoreLabel.GOOD: 2,
    ScoreLabel.EXCELLENT: 3,
}


# ---------------------------------------------------------------------------
# Domain → topics catalogue
# ---------------------------------------------------------------------------

TOPIC_CATALOG: Dict[Domain, List[str]] = {
    Domain.DATA_ENGINEERING: [
        "SQL", "Python", "Spark", "Kafka", "Airflow",
        "Databricks", "Snowflake", "Data Modeling", "ETL/ELT", "Data Lakes",
    ],
    Domain.BACKEND: [
        "REST APIs", "Databases", "Caching", "Microservices",
        "Authentication", "Message Queues", "Concurrency", "Testing",
    ],
    Domain.AI_ML: [
        "Classical ML", "Deep Learning", "NLP", "Computer Vision",
        "Feature Engineering", "Model Evaluation", "MLOps", "LLMs",
    ],
    Domain.DEVOPS: [
        "Docker", "Kubernetes", "CI/CD", "Terraform",
        "Monitoring", "Linux", "Cloud (AWS/GCP/Azure)", "Networking",
    ],
    Domain.FRONTEND: [
        "JavaScript", "React", "TypeScript", "CSS",
        "State Management", "Performance", "Accessibility", "Testing",
    ],
    Domain.SYSTEM_DESIGN: [
        "Scalability", "Caching", "Load Balancing", "Sharding",
        "Consistency", "Message Queues", "Database Selection", "Trade-offs",
    ],
}


# ---------------------------------------------------------------------------
# Request / Response models — these are the API contracts
# ---------------------------------------------------------------------------

class SessionConfig(BaseModel):
    """Configuration for a new interview session."""
    domain: Domain
    experience: ExperienceLevel
    topics: List[str] = Field(default_factory=list, description="Selected topics from catalog")
    custom_topic: Optional[str] = Field(default=None, description="Free-form topic")
    target_questions: int = Field(default=10, ge=1, le=50)


class GenerateQuestionRequest(BaseModel):
    session_id: str
    qtype: Optional[QuestionType] = Field(
        default=None,
        description="Force a question type. If None, engine picks based on experience."
    )


class Question(BaseModel):
    """A single generated question."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    qtype: QuestionType
    topic: str
    text: str
    expected_points: List[str] = Field(
        default_factory=list,
        description="Key points an ideal answer should hit (used for evaluation)."
    )


class EvaluateAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str


class Evaluation(BaseModel):
    """Evaluation of a candidate answer."""
    model_config = {"protected_namespaces": ()}

    question_id: str
    score_label: ScoreLabel
    score_value: int                        # 1..3
    feedback: str                           # Markdown-ready text
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    ideal_answer: Optional[str] = None
    model_used: Optional[str] = None        # Which model produced the eval


class GenerateScenarioRequest(BaseModel):
    session_id: str
    topic: Optional[str] = None             # Pick from session topics if None


class Scenario(BaseModel):
    """A real-world scenario / production-failure problem statement."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    topic: str
    title: str
    context: str                            # The scenario narrative
    problem: str                            # What the candidate must solve
    expected_approach: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Session state (kept server-side, also used by CLI)
# ---------------------------------------------------------------------------

class QAExchange(BaseModel):
    """One Q&A pair within a session — the unit we score on."""
    question: Question
    answer: Optional[str] = None
    evaluation: Optional[Evaluation] = None
    asked_at: datetime = Field(default_factory=datetime.utcnow)


class Session(BaseModel):
    """Server-side session state."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    config: SessionConfig
    user_id: Optional[int] = None         # logged-in user (None = anonymous CLI)
    exchanges: List[QAExchange] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None

    # Helpers used by the engine
    def add_question(self, q: Question) -> None:
        self.exchanges.append(QAExchange(question=q))

    def find_exchange(self, question_id: str) -> Optional[QAExchange]:
        for e in self.exchanges:
            if e.question.id == question_id:
                return e
        return None

    def average_score(self) -> float:
        scored = [e.evaluation.score_value for e in self.exchanges if e.evaluation]
        return round(sum(scored) / len(scored), 2) if scored else 0.0

    def topics_seen(self) -> List[str]:
        return list({e.question.topic for e in self.exchanges})


class SessionSummary(BaseModel):
    """Final report emitted at end of session."""
    session_id: str
    total_questions: int
    overall_score: float                    # 0..3
    score_label: ScoreLabel
    strengths: List[str]
    improvements: List[str]
    recommendations: List[str]
    per_topic_scores: Dict[str, float]
    duration_seconds: int


# ---------------------------------------------------------------------------
# LLM-router contracts
# ---------------------------------------------------------------------------

class LLMRequest(BaseModel):
    system: str
    user: str
    temperature: float = 0.7
    max_tokens: int = 800


class LLMResponse(BaseModel):
    text: str
    model: str                              # Which concrete model produced this
    provider: str                           # "gemini" or "openrouter"
    latency_ms: int
    attempts: int = 1                       # How many providers/models we tried


class LLMUsageLog(BaseModel):
    """Persisted to logs/DB for cost & reliability analysis."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: Optional[str] = None
    purpose: str                            # 'question' | 'evaluation' | 'scenario' | 'summary'
    provider: str
    model: str
    success: bool
    latency_ms: int
    error: Optional[str] = None
