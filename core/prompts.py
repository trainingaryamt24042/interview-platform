"""
core.prompts
------------
All prompt templates live here. ONE place to change wording. The Core Engine
calls these — UI and CLI never touch prompts directly.

Difficulty escalates with experience level:
    fresher  → fundamentals & definitions
    junior   → practical + simple coding
    mid      → trade-offs, optimisation, deeper coding
    senior   → system design, failure scenarios, architectural reasoning
"""

from __future__ import annotations

from typing import List

from core.models import Domain, ExperienceLevel, QuestionType


# Human-readable labels for the model. Keep concise; LLMs follow short
# directives more reliably than long ones.
EXPERIENCE_DESCRIPTORS: dict[ExperienceLevel, str] = {
    ExperienceLevel.FRESHER: (
        "FRESHER (0 yrs). Focus on fundamentals, definitions, syntax, "
        "and textbook concepts. Avoid system design or production scenarios."
    ),
    ExperienceLevel.JUNIOR: (
        "JUNIOR (1-3 yrs). Practical questions: basic SQL/coding, common "
        "pitfalls, simple debugging, day-2 ops. One small twist per question."
    ),
    ExperienceLevel.MID: (
        "MID-LEVEL (3-5 yrs). Trade-offs, optimisation, design choices, "
        "concurrent failure modes, mid-complexity coding. Push for the WHY."
    ),
    ExperienceLevel.SENIOR: (
        "SENIOR (5+ yrs). System design at scale, real production failure "
        "scenarios, architectural trade-offs, leadership decisions, "
        "performance tuning, distributed-system edge cases. Demand depth."
    ),
}


DOMAIN_DESCRIPTORS: dict[Domain, str] = {
    Domain.DATA_ENGINEERING: "Data Engineering (SQL, Spark, Kafka, Airflow, Lakehouse)",
    Domain.BACKEND: "Backend Engineering (APIs, databases, caching, services)",
    Domain.AI_ML: "AI/ML Engineering (modelling, training, MLOps, LLMs)",
    Domain.DEVOPS: "DevOps / Platform Engineering (Docker, K8s, CI/CD, cloud)",
    Domain.FRONTEND: "Frontend Engineering (JS, React, performance, UX)",
    Domain.SYSTEM_DESIGN: "System Design (architecture, scalability, trade-offs)",
}


# ---------------------------------------------------------------------------
# Question generation
# ---------------------------------------------------------------------------

QUESTION_SYSTEM_PROMPT = """\
You are a senior technical interviewer. Your job is to generate ONE
high-quality interview question that exactly matches the candidate's domain,
experience level, and the requested topic.

You always respond in this STRICT format and nothing else:

QUESTION_TYPE: <conceptual|coding|scenario>
TOPIC: <one of the allowed topics>
QUESTION:
<the question itself, multi-line allowed>
EXPECTED_POINTS:
- <bullet 1>
- <bullet 2>
- <bullet 3>
- <bullet 4>

Rules:
- Do NOT include preamble, greetings, or sign-offs.
- Do NOT ask the candidate to introduce themselves.
- Coding questions must include sample input/output if relevant.
- Scenario questions must describe a concrete real-world situation
  (numbers, services, failure modes), not an abstract one.
- EXPECTED_POINTS must list 3-5 ideal-answer keypoints, in your own words.
"""


def build_question_user_prompt(
    *,
    domain: Domain,
    experience: ExperienceLevel,
    topic: str,
    qtype: QuestionType,
    avoid: List[str] | None = None,
) -> str:
    """Per-call user message for question generation."""
    avoid = avoid or []
    avoid_block = ""
    if avoid:
        joined = "\n".join(f"- {a[:200]}" for a in avoid[-5:])
        avoid_block = (
            "\nAlready-asked questions (DO NOT repeat or paraphrase):\n" + joined + "\n"
        )

    return (
        f"Domain: {DOMAIN_DESCRIPTORS[domain]}\n"
        f"Experience level: {EXPERIENCE_DESCRIPTORS[experience]}\n"
        f"Topic: {topic}\n"
        f"Required question type: {qtype.value}\n"
        f"{avoid_block}\n"
        f"Generate the question now in the strict format."
    )


# ---------------------------------------------------------------------------
# Answer evaluation
# ---------------------------------------------------------------------------

EVALUATION_SYSTEM_PROMPT = """\
You are a strict but fair technical interviewer evaluating a candidate's
answer. You always respond in this STRICT format and nothing else:

RATING: <Poor|Good|Excellent>
STRENGTHS:
- <bullet>
- <bullet>
GAPS:
- <bullet>
- <bullet>
IDEAL_ANSWER:
<2-6 sentences describing what an excellent answer looks like.>
FEEDBACK:
<2-4 sentences of direct, constructive coaching to the candidate.>

Rules:
- Use Excellent ONLY if the answer is correct, complete, and well-reasoned.
- Use Poor if the answer is wrong, missing the core idea, or empty.
- Use Good for partial / mostly-correct answers.
- Be honest. Do NOT inflate scores.
- Never repeat the question text.
"""


def build_evaluation_user_prompt(
    *,
    experience: ExperienceLevel,
    question_text: str,
    expected_points: List[str],
    answer: str,
) -> str:
    points = "\n".join(f"- {p}" for p in expected_points) or "- (not provided)"
    return (
        f"Experience level: {experience.value}\n\n"
        f"Question asked:\n{question_text}\n\n"
        f"Expected key points the answer should cover:\n{points}\n\n"
        f"Candidate's answer:\n\"\"\"\n{answer.strip() or '(no answer given)'}\n\"\"\"\n\n"
        f"Evaluate now in the strict format."
    )


# ---------------------------------------------------------------------------
# Scenario generation (real-world / production failure problems)
# ---------------------------------------------------------------------------

SCENARIO_SYSTEM_PROMPT = """\
You are a senior architect writing realistic production failure scenarios for
interview practice. You always respond in this STRICT format and nothing else:

TITLE: <short scenario title>
TOPIC: <one of the allowed topics>
CONTEXT:
<3-6 sentences setting up the scenario: the system, the team, the scale,
metrics, what was working before. Include concrete numbers (QPS, GB, users).>
PROBLEM:
<2-4 sentences describing what just went wrong and what the candidate must
solve / explain / decide.>
EXPECTED_APPROACH:
- <bullet 1>
- <bullet 2>
- <bullet 3>
- <bullet 4>

Rules:
- Scenario must be specific (real numbers, real services), not abstract.
- For senior level, include multi-system interactions and trade-offs.
- For fresher/junior, keep it to a single component with a clear failure.
- Do NOT include the answer in PROBLEM — only in EXPECTED_APPROACH.
"""


def build_scenario_user_prompt(
    *,
    domain: Domain,
    experience: ExperienceLevel,
    topic: str,
) -> str:
    return (
        f"Domain: {DOMAIN_DESCRIPTORS[domain]}\n"
        f"Experience level: {EXPERIENCE_DESCRIPTORS[experience]}\n"
        f"Topic: {topic}\n\n"
        f"Generate the scenario now in the strict format."
    )


# ---------------------------------------------------------------------------
# Final session summary
# ---------------------------------------------------------------------------

SUMMARY_SYSTEM_PROMPT = """\
You are an interview coach producing a concise post-interview report. You
always respond in this STRICT format and nothing else:

OVERALL: <Poor|Good|Excellent>
STRENGTHS:
- <bullet>
- <bullet>
IMPROVEMENTS:
- <bullet>
- <bullet>
RECOMMENDATIONS:
- <concrete next step / topic to study>
- <concrete next step / topic to study>

Rules:
- Be specific. Reference actual topics from the session.
- Recommendations must be actionable (a concept, a doc page, a hands-on lab).
- Do not exceed 4 bullets per section.
"""


def build_summary_user_prompt(
    *,
    domain: Domain,
    experience: ExperienceLevel,
    transcript: str,
) -> str:
    return (
        f"Domain: {DOMAIN_DESCRIPTORS[domain]}\n"
        f"Experience level: {EXPERIENCE_DESCRIPTORS[experience]}\n\n"
        f"Interview transcript (Q, candidate answer, rating):\n{transcript}\n\n"
        f"Produce the report now in the strict format."
    )
