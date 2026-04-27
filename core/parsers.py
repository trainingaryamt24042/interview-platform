"""
core.parsers
------------
Convert structured LLM text output into Pydantic models. We ask the LLM to
follow a strict format (see core.prompts), and these parsers tolerate small
deviations (extra whitespace, missing sections) without crashing the engine.

If parsing genuinely fails, parsers return a best-effort fallback so the
end user still sees something useful.
"""

from __future__ import annotations

import re
from typing import List, Tuple

from core.models import (
    Evaluation,
    Question,
    QuestionType,
    Scenario,
    ScoreLabel,
    SCORE_VALUES,
)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _grab_section(text: str, key: str, *, until: List[str]) -> str:
    """
    Extract content under `KEY:` until the next section header in `until`
    (or end of text). Headers are matched case-insensitively at line start.
    """
    pattern = rf"(?im)^{re.escape(key)}\s*:\s*(.*?)(?=^(?:{'|'.join(re.escape(u) for u in until)})\s*:|\Z)"
    m = re.search(pattern, text, re.DOTALL | re.MULTILINE)
    return m.group(1).strip() if m else ""


def _grab_inline(text: str, key: str) -> str:
    """Extract a single-line value: `KEY: value`."""
    m = re.search(rf"(?im)^{re.escape(key)}\s*:\s*(.+)$", text)
    return m.group(1).strip() if m else ""


def _bullets(block: str) -> List[str]:
    """Pull bullet list items from a block of text."""
    items: List[str] = []
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        # Accept -, *, • prefixes (and numbered lists).
        m = re.match(r"^(?:[-*•]|\d+[.)])\s+(.*)", line)
        if m:
            items.append(m.group(1).strip())
        elif items:
            # continuation line — append to last bullet
            items[-1] += " " + line
    return items


# ---------------------------------------------------------------------------
# Question parser
# ---------------------------------------------------------------------------

_QUESTION_SECTIONS = ["QUESTION_TYPE", "TOPIC", "QUESTION", "EXPECTED_POINTS"]


def parse_question(raw: str, *, fallback_topic: str, fallback_qtype: QuestionType) -> Question:
    qtype_str = _grab_inline(raw, "QUESTION_TYPE").lower()
    try:
        qtype = QuestionType(qtype_str)
    except ValueError:
        qtype = fallback_qtype

    topic = _grab_inline(raw, "TOPIC") or fallback_topic

    q_block = _grab_section(raw, "QUESTION", until=["EXPECTED_POINTS"])
    points_block = _grab_section(raw, "EXPECTED_POINTS", until=[])
    points = _bullets(points_block)

    if not q_block:
        # Last-resort fallback: use the whole response as the question text.
        q_block = raw.strip()

    return Question(
        qtype=qtype,
        topic=topic,
        text=q_block.strip(),
        expected_points=points,
    )


# ---------------------------------------------------------------------------
# Evaluation parser
# ---------------------------------------------------------------------------

_RATING_RE = re.compile(r"(?im)^RATING\s*:\s*(poor|good|excellent)\b")


def _rating_from(raw: str) -> ScoreLabel:
    m = _RATING_RE.search(raw)
    if m:
        return ScoreLabel(m.group(1).lower())
    # Heuristic fallback: scan first 200 chars.
    head = raw[:200].lower()
    if "excellent" in head:
        return ScoreLabel.EXCELLENT
    if "poor" in head:
        return ScoreLabel.POOR
    return ScoreLabel.GOOD


def parse_evaluation(raw: str, *, question_id: str, model_used: str) -> Evaluation:
    label = _rating_from(raw)

    strengths_block = _grab_section(raw, "STRENGTHS", until=["GAPS", "IDEAL_ANSWER", "FEEDBACK"])
    gaps_block = _grab_section(raw, "GAPS", until=["IDEAL_ANSWER", "FEEDBACK"])
    ideal_block = _grab_section(raw, "IDEAL_ANSWER", until=["FEEDBACK"])
    feedback_block = _grab_section(raw, "FEEDBACK", until=[])

    if not feedback_block:
        # If model didn't separate FEEDBACK, fall back to the whole response.
        feedback_block = raw.strip()

    return Evaluation(
        question_id=question_id,
        score_label=label,
        score_value=SCORE_VALUES[label],
        feedback=feedback_block.strip(),
        strengths=_bullets(strengths_block),
        gaps=_bullets(gaps_block),
        ideal_answer=ideal_block.strip() or None,
        model_used=model_used,
    )


# ---------------------------------------------------------------------------
# Scenario parser
# ---------------------------------------------------------------------------

def parse_scenario(raw: str, *, fallback_topic: str) -> Scenario:
    title = _grab_inline(raw, "TITLE") or "Production Scenario"
    topic = _grab_inline(raw, "TOPIC") or fallback_topic
    context = _grab_section(raw, "CONTEXT", until=["PROBLEM", "EXPECTED_APPROACH"])
    problem = _grab_section(raw, "PROBLEM", until=["EXPECTED_APPROACH"])
    approach_block = _grab_section(raw, "EXPECTED_APPROACH", until=[])

    if not (context or problem):
        # Best-effort fallback: dump the raw text into context.
        context = raw.strip()
        problem = "Discuss your approach."

    return Scenario(
        title=title.strip(),
        topic=topic.strip(),
        context=context.strip(),
        problem=problem.strip(),
        expected_approach=_bullets(approach_block),
    )


# ---------------------------------------------------------------------------
# Summary parser — returns a tuple so the engine builds the final model.
# ---------------------------------------------------------------------------

def parse_summary(raw: str) -> Tuple[ScoreLabel, List[str], List[str], List[str]]:
    overall_str = _grab_inline(raw, "OVERALL").lower()
    try:
        overall = ScoreLabel(overall_str)
    except ValueError:
        overall = ScoreLabel.GOOD

    strengths = _bullets(_grab_section(raw, "STRENGTHS", until=["IMPROVEMENTS", "RECOMMENDATIONS"]))
    improvements = _bullets(_grab_section(raw, "IMPROVEMENTS", until=["RECOMMENDATIONS"]))
    recommendations = _bullets(_grab_section(raw, "RECOMMENDATIONS", until=[]))

    return overall, strengths, improvements, recommendations
