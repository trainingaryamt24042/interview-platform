"""
api.routes
----------
Thin HTTP controllers. They:
    1. Validate input (Pydantic does most of it).
    2. Call ONE method on the Core Engine.
    3. Wrap the result in a response model.

NO business logic in this file.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth_routes import optional_user
from api.dependencies import get_engine
from api.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    EndSessionResponse,
    EvaluateAnswerRequest,
    EvaluateAnswerResponse,
    GenerateQuestionRequest,
    GenerateQuestionResponse,
    GenerateScenarioRequest,
    GenerateScenarioResponse,
    TopicCatalogResponse,
)
from core.auth import User
from core.engine import InterviewEngine
from core.llm.base import LLMProviderError
from core.logging_setup import get_logger
from core.models import SessionConfig, TOPIC_CATALOG

log = get_logger(__name__)
router = APIRouter()


@router.get("/topics", response_model=TopicCatalogResponse, tags=["meta"])
def get_topics() -> TopicCatalogResponse:
    """Return the domain → topic catalogue. The frontend uses this to render
    the setup screen."""
    return TopicCatalogResponse(
        domains={d.value: topics for d, topics in TOPIC_CATALOG.items()}
    )


@router.post(
    "/session",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["session"],
)
def create_session(
    body: CreateSessionRequest,
    engine: InterviewEngine = Depends(get_engine),
    user: User | None = Depends(optional_user),
) -> CreateSessionResponse:
    config = SessionConfig(**body.model_dump())
    session = engine.create_session(config, user_id=user.id if user else None)
    return CreateSessionResponse(session_id=session.id, config=session.config)


@router.post(
    "/generate-question",
    response_model=GenerateQuestionResponse,
    tags=["interview"],
)
def generate_question(
    body: GenerateQuestionRequest,
    engine: InterviewEngine = Depends(get_engine),
) -> GenerateQuestionResponse:
    try:
        question = engine.generate_question(body.session_id, qtype=body.qtype)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMProviderError as e:
        raise HTTPException(status_code=502, detail=f"LLM upstream failure: {e}")

    session = engine.get_session(body.session_id)
    return GenerateQuestionResponse(
        question=question,
        question_index=len(session.exchanges),
        total_so_far=len(session.exchanges),
    )


@router.post(
    "/evaluate-answer",
    response_model=EvaluateAnswerResponse,
    tags=["interview"],
)
def evaluate_answer(
    body: EvaluateAnswerRequest,
    engine: InterviewEngine = Depends(get_engine),
) -> EvaluateAnswerResponse:
    try:
        evaluation = engine.evaluate_answer(
            session_id=body.session_id,
            question_id=body.question_id,
            answer=body.answer,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMProviderError as e:
        raise HTTPException(status_code=502, detail=f"LLM upstream failure: {e}")
    return EvaluateAnswerResponse(evaluation=evaluation)


@router.post(
    "/generate-scenario",
    response_model=GenerateScenarioResponse,
    tags=["interview"],
)
def generate_scenario(
    body: GenerateScenarioRequest,
    engine: InterviewEngine = Depends(get_engine),
) -> GenerateScenarioResponse:
    try:
        scenario = engine.generate_scenario(body.session_id, topic=body.topic)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMProviderError as e:
        raise HTTPException(status_code=502, detail=f"LLM upstream failure: {e}")
    return GenerateScenarioResponse(scenario=scenario)


@router.post(
    "/session/{session_id}/end",
    response_model=EndSessionResponse,
    tags=["session"],
)
def end_session(
    session_id: str,
    engine: InterviewEngine = Depends(get_engine),
) -> EndSessionResponse:
    try:
        summary = engine.end_session(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LLMProviderError as e:
        raise HTTPException(status_code=502, detail=f"LLM upstream failure: {e}")
    return EndSessionResponse(summary=summary)


@router.get("/session/{session_id}", tags=["session"])
def get_session_state(
    session_id: str,
    engine: InterviewEngine = Depends(get_engine),
):
    """Useful for refresh / resume scenarios."""
    try:
        return engine.get_session(session_id).model_dump()
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
