"""
core.engine
-----------
The Core Engine — the SINGLE brain of the platform.

Both the FastAPI controllers and the CLI call into this class. Nothing in
api/ or cli/ duplicates this logic; they only collect inputs, call methods,
and present outputs.

Responsibilities:
    - Create / load sessions.
    - Generate conceptual / coding / scenario questions appropriate to
      domain + experience + topic.
    - Evaluate candidate answers.
    - Produce the final session summary.
    - Track which questions have already been asked (no repeats).
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Optional

from core.llm.base import LLMProviderError
from core.llm.router import LLMRouter
from core.logging_setup import get_logger
from core.models import (
    Evaluation,
    ExperienceLevel,
    LLMRequest,
    QAExchange,
    Question,
    QuestionType,
    SCORE_VALUES,
    Scenario,
    ScoreLabel,
    Session,
    SessionConfig,
    SessionSummary,
    TOPIC_CATALOG,
)
from core.parsers import (
    parse_evaluation,
    parse_question,
    parse_scenario,
    parse_summary,
)
from core.prompts import (
    EVALUATION_SYSTEM_PROMPT,
    QUESTION_SYSTEM_PROMPT,
    SCENARIO_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    build_evaluation_user_prompt,
    build_question_user_prompt,
    build_scenario_user_prompt,
    build_summary_user_prompt,
)
from core.repository import SessionRepository, get_repository

log = get_logger(__name__)


# Question-type policy by experience. Tuned to the spec:
#   fresher  → mostly conceptual
#   junior   → mix of conceptual + coding
#   mid      → coding + scenarios
#   senior   → scenarios dominate (system design / failure modes)
_QTYPE_WEIGHTS: dict[ExperienceLevel, dict[QuestionType, int]] = {
    ExperienceLevel.FRESHER: {
        QuestionType.CONCEPTUAL: 7, QuestionType.CODING: 2, QuestionType.SCENARIO: 1,
    },
    ExperienceLevel.JUNIOR: {
        QuestionType.CONCEPTUAL: 4, QuestionType.CODING: 4, QuestionType.SCENARIO: 2,
    },
    ExperienceLevel.MID: {
        QuestionType.CONCEPTUAL: 2, QuestionType.CODING: 4, QuestionType.SCENARIO: 4,
    },
    ExperienceLevel.SENIOR: {
        QuestionType.CONCEPTUAL: 1, QuestionType.CODING: 3, QuestionType.SCENARIO: 6,
    },
}


def _weighted_pick(weights: dict[QuestionType, int]) -> QuestionType:
    """Random pick using the integer weight map."""
    types: list[QuestionType] = []
    for t, w in weights.items():
        types.extend([t] * w)
    return random.choice(types)


class InterviewEngine:
    """
    Construct ONCE per process and share across requests. Stateless w.r.t.
    sessions — all session state lives in the repository.
    """

    def __init__(
        self,
        router: Optional[LLMRouter] = None,
        repo: Optional[SessionRepository] = None,
    ) -> None:
        self.router = router or LLMRouter()
        self.repo = repo or get_repository()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, config: SessionConfig, user_id: Optional[int] = None) -> Session:
        # Validate topic list — fall back to the domain's first topic if empty.
        if not config.topics and not config.custom_topic:
            config = config.model_copy(update={"topics": [TOPIC_CATALOG[config.domain][0]]})

        session = Session(config=config, user_id=user_id)
        self.repo.save(session)

        # Persist to DB (best-effort — sessions still work even if DB write fails).
        try:
            from core.history import upsert_session, save_custom_topic
            upsert_session(user_id, session)
            if user_id and config.custom_topic:
                save_custom_topic(user_id, config.custom_topic)
        except Exception as e:
            log.warning("Could not persist session to DB: %s", e)

        log.info(
            "Session created id=%s user=%s domain=%s exp=%s topics=%s",
            session.id, user_id, config.domain.value, config.experience.value, config.topics,
        )
        return session

    def get_session(self, session_id: str) -> Session:
        s = self.repo.get(session_id)
        if not s:
            raise KeyError(f"Session not found: {session_id}")
        return s

    # ------------------------------------------------------------------
    # Question generation
    # ------------------------------------------------------------------

    def generate_question(
        self,
        session_id: str,
        qtype: Optional[QuestionType] = None,
    ) -> Question:
        session = self.get_session(session_id)
        cfg = session.config

        # Decide the question type if caller didn't force one.
        chosen_type = qtype or _weighted_pick(_QTYPE_WEIGHTS[cfg.experience])

        # Round-robin a topic so we cover everything the user asked for.
        all_topics = list(cfg.topics) + ([cfg.custom_topic] if cfg.custom_topic else [])
        idx = len(session.exchanges) % max(len(all_topics), 1)
        topic = all_topics[idx] if all_topics else "General"

        avoid = [e.question.text for e in session.exchanges]

        user_prompt = build_question_user_prompt(
            domain=cfg.domain,
            experience=cfg.experience,
            topic=topic,
            qtype=chosen_type,
            avoid=avoid,
        )

        try:
            resp = self.router.complete(
                LLMRequest(
                    system=QUESTION_SYSTEM_PROMPT,
                    user=user_prompt,
                    temperature=0.8,
                    max_tokens=320,
                ),
                purpose="question",
                session_id=session.id,
            )
        except LLMProviderError as e:
            log.error("Question generation failed: %s", e)
            raise

        question = parse_question(resp.text, fallback_topic=topic, fallback_qtype=chosen_type)
        session.add_question(question)
        self.repo.save(session)

        log.info(
            "Question generated session=%s type=%s topic=%s model=%s/%s",
            session.id, question.qtype.value, question.topic,
            resp.provider, resp.model,
        )
        return question

    # ------------------------------------------------------------------
    # Answer evaluation
    # ------------------------------------------------------------------

    def evaluate_answer(
        self,
        session_id: str,
        question_id: str,
        answer: str,
    ) -> Evaluation:
        session = self.get_session(session_id)
        exchange: Optional[QAExchange] = session.find_exchange(question_id)
        if not exchange:
            raise KeyError(f"Question not found in session: {question_id}")

        user_prompt = build_evaluation_user_prompt(
            experience=session.config.experience,
            question_text=exchange.question.text,
            expected_points=exchange.question.expected_points,
            answer=answer,
        )

        resp = self.router.complete(
            LLMRequest(
                system=EVALUATION_SYSTEM_PROMPT,
                user=user_prompt,
                temperature=0.3,    # low temp for graded output
                max_tokens=320,
            ),
            purpose="evaluation",
            session_id=session.id,
        )

        evaluation = parse_evaluation(
            resp.text,
            question_id=question_id,
            model_used=f"{resp.provider}/{resp.model}",
        )

        # Persist into session state.
        exchange.answer = answer
        exchange.evaluation = evaluation
        self.repo.save(session)

        # Persist to DB (history + topic stats). Best-effort.
        try:
            from core.history import save_question_score, upsert_session
            qindex = next(
                (i for i, e in enumerate(session.exchanges, 1) if e.question.id == question_id),
                len(session.exchanges),
            )
            save_question_score(
                session_id=session.id,
                user_id=session.user_id,
                question_index=qindex,
                question=exchange.question,
                answer=answer,
                evaluation=evaluation,
            )
            upsert_session(session.user_id, session)
        except Exception as e:
            log.warning("Could not persist question score: %s", e)

        log.info(
            "Answer evaluated session=%s q=%s rating=%s model=%s",
            session.id, question_id, evaluation.score_label.value, evaluation.model_used,
        )
        return evaluation

    # ------------------------------------------------------------------
    # Scenario generation (real-world / production)
    # ------------------------------------------------------------------

    def generate_scenario(self, session_id: str, topic: Optional[str] = None) -> Scenario:
        session = self.get_session(session_id)
        cfg = session.config

        if not topic:
            all_topics = list(cfg.topics) + ([cfg.custom_topic] if cfg.custom_topic else [])
            topic = random.choice(all_topics) if all_topics else "General"

        user_prompt = build_scenario_user_prompt(
            domain=cfg.domain,
            experience=cfg.experience,
            topic=topic,
        )

        resp = self.router.complete(
            LLMRequest(
                system=SCENARIO_SYSTEM_PROMPT,
                user=user_prompt,
                temperature=0.85,
                max_tokens=500,
            ),
            purpose="scenario",
            session_id=session.id,
        )

        scenario = parse_scenario(resp.text, fallback_topic=topic)
        log.info(
            "Scenario generated session=%s topic=%s title=%s",
            session.id, scenario.topic, scenario.title,
        )
        return scenario

    # ------------------------------------------------------------------
    # Final summary
    # ------------------------------------------------------------------

    def end_session(self, session_id: str) -> SessionSummary:
        session = self.get_session(session_id)
        if not session.exchanges:
            raise ValueError("Cannot summarise a session with zero questions.")

        # Build a compact transcript for the LLM.
        lines = []
        for i, ex in enumerate(session.exchanges, 1):
            ans = (ex.answer or "(skipped)")[:600]
            rating = ex.evaluation.score_label.value if ex.evaluation else "ungraded"
            lines.append(
                f"Q{i} [{ex.question.topic} / {ex.question.qtype.value}]: "
                f"{ex.question.text[:300]}\n"
                f"A{i}: {ans}\n"
                f"Rating: {rating}\n"
            )
        transcript = "\n".join(lines)

        user_prompt = build_summary_user_prompt(
            domain=session.config.domain,
            experience=session.config.experience,
            transcript=transcript,
        )

        resp = self.router.complete(
            LLMRequest(
                system=SUMMARY_SYSTEM_PROMPT,
                user=user_prompt,
                temperature=0.4,
                max_tokens=420,
            ),
            purpose="summary",
            session_id=session.id,
        )

        overall, strengths, improvements, recommendations = parse_summary(resp.text)

        # Compute deterministic per-topic averages from actual evaluations.
        per_topic_totals: dict[str, list[int]] = {}
        for ex in session.exchanges:
            if ex.evaluation:
                per_topic_totals.setdefault(ex.question.topic, []).append(ex.evaluation.score_value)
        per_topic = {
            t: round(sum(v) / len(v), 2) for t, v in per_topic_totals.items()
        }

        avg = session.average_score()
        # Override LLM's overall label using our deterministic average — more honest.
        if avg >= 2.5:
            overall = ScoreLabel.EXCELLENT
        elif avg >= 1.5:
            overall = ScoreLabel.GOOD
        else:
            overall = ScoreLabel.POOR

        session.ended_at = datetime.utcnow()
        self.repo.save(session)

        duration = int((session.ended_at - session.created_at).total_seconds())

        summary = SessionSummary(
            session_id=session.id,
            total_questions=len(session.exchanges),
            overall_score=avg,
            score_label=overall,
            strengths=strengths,
            improvements=improvements,
            recommendations=recommendations,
            per_topic_scores=per_topic,
            duration_seconds=duration,
        )

        # Persist final grade to DB. Best-effort.
        try:
            from core.history import save_grade, upsert_session
            upsert_session(session.user_id, session)
            save_grade(
                session_id=session.id,
                user_id=session.user_id,
                session=session,
                summary=summary,
            )
        except Exception as e:
            log.warning("Could not persist grade: %s", e)

        return summary
