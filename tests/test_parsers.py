"""
Parser tests — no LLM needed. These prove the strict-format contracts.
"""

from core.models import QuestionType, ScoreLabel
from core.parsers import (
    parse_evaluation,
    parse_question,
    parse_scenario,
    parse_summary,
)


def test_parse_question_happy_path():
    raw = """\
QUESTION_TYPE: coding
TOPIC: SQL
QUESTION:
Write a query that returns the second-highest salary.
EXPECTED_POINTS:
- Use DENSE_RANK or LIMIT/OFFSET
- Handle NULLs / ties
- Discuss performance on large tables
"""
    q = parse_question(raw, fallback_topic="SQL", fallback_qtype=QuestionType.CONCEPTUAL)
    assert q.qtype == QuestionType.CODING
    assert q.topic == "SQL"
    assert "second-highest" in q.text
    assert len(q.expected_points) == 3


def test_parse_evaluation_rating_extraction():
    raw = """\
RATING: Excellent
STRENGTHS:
- Correct use of window function
- Mentioned ties
GAPS:
- Did not discuss indexes
IDEAL_ANSWER:
Use DENSE_RANK over salary DESC, filter rank=2.
FEEDBACK:
Solid answer. Add a note about the index on the salary column.
"""
    ev = parse_evaluation(raw, question_id="q1", model_used="gemini/x")
    assert ev.score_label == ScoreLabel.EXCELLENT
    assert ev.score_value == 3
    assert ev.strengths and ev.gaps
    assert "DENSE_RANK" in (ev.ideal_answer or "")


def test_parse_scenario_strict_format():
    raw = """\
TITLE: Spark OOM at 02:00
TOPIC: Spark
CONTEXT:
Hourly job joining 600 GB of clickstream with users.
PROBLEM:
One executor OOMs every night. Fix it.
EXPECTED_APPROACH:
- Identify the skewed key
- Apply salting or AQE skew join
- Tune executor memory as a safety net
"""
    sc = parse_scenario(raw, fallback_topic="Spark")
    assert sc.title == "Spark OOM at 02:00"
    assert sc.topic == "Spark"
    assert "clickstream" in sc.context
    assert len(sc.expected_approach) == 3


def test_parse_summary_strict_format():
    raw = """\
OVERALL: Good
STRENGTHS:
- Strong on SQL
IMPROVEMENTS:
- Spark internals are weak
RECOMMENDATIONS:
- Read the AQE docs and try a salting exercise
"""
    overall, strengths, improvements, recs = parse_summary(raw)
    assert overall == ScoreLabel.GOOD
    assert strengths == ["Strong on SQL"]
    assert improvements == ["Spark internals are weak"]
    assert recs == ["Read the AQE docs and try a salting exercise"]


def test_parse_question_falls_back_gracefully():
    """Even if the LLM ignores the format, we get something."""
    raw = "Here is a question: explain CAP theorem."
    q = parse_question(raw, fallback_topic="Distributed Systems", fallback_qtype=QuestionType.CONCEPTUAL)
    assert q.topic == "Distributed Systems"
    assert q.qtype == QuestionType.CONCEPTUAL
    assert "CAP" in q.text
