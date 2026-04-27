"""
cli.main
--------
CLI for the AI Interview Platform.

Calls the SAME core.engine.InterviewEngine that the FastAPI controllers use.
Zero duplicated business logic. Two modes:

    Interactive:   full mock interview with feedback + final summary
    Quick:         one question only, then exit (great for daily practice)

Usage:
    python -m cli.main interactive
    python -m cli.main quick --domain data_engineering --experience mid \\
                              --topics SQL Spark --qtype scenario
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from typing import List, Optional

from core.engine import InterviewEngine
from core.llm.base import LLMProviderError
from core.logging_setup import setup_logging
from core.models import (
    Domain,
    ExperienceLevel,
    QuestionType,
    SessionConfig,
    TOPIC_CATALOG,
)


# ---------------------------------------------------------------------------
# Pretty printing helpers (no external deps so the CLI stays light)
# ---------------------------------------------------------------------------

def _hr(char: str = "─", width: int = 70) -> str:
    return char * width


def _wrap(text: str, indent: str = "  ") -> str:
    out = []
    for para in text.splitlines():
        if not para.strip():
            out.append("")
            continue
        out.append(textwrap.fill(para, width=78, initial_indent=indent, subsequent_indent=indent))
    return "\n".join(out)


def _ask(prompt: str, default: Optional[str] = None) -> str:
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    val = input(prompt).strip()
    return val or (default or "")


def _menu(title: str, options: List[str]) -> int:
    print(f"\n{title}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        raw = input(f"Choose 1-{len(options)}: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print("Invalid choice — try again.")


# ---------------------------------------------------------------------------
# Setup wizard
# ---------------------------------------------------------------------------

def _wizard() -> SessionConfig:
    domains = list(Domain)
    d_idx = _menu("Pick a DOMAIN", [d.value for d in domains])
    domain = domains[d_idx]

    levels = list(ExperienceLevel)
    e_idx = _menu(
        "Pick an EXPERIENCE level",
        [f"{l.value}  ({_level_hint(l)})" for l in levels],
    )
    experience = levels[e_idx]

    catalog = TOPIC_CATALOG[domain]
    print("\nAvailable topics:")
    for i, t in enumerate(catalog, 1):
        print(f"  {i:2d}. {t}")
    raw = _ask("Pick topics (comma-separated numbers, or blank for first 3)", "1,2,3")
    try:
        idxs = [int(x.strip()) - 1 for x in raw.split(",") if x.strip()]
        topics = [catalog[i] for i in idxs if 0 <= i < len(catalog)]
    except ValueError:
        topics = catalog[:3]

    custom = _ask("Custom topic (optional, leave blank to skip)", "")
    target = _ask("How many questions in this session?", "5")
    try:
        target_n = max(1, min(50, int(target)))
    except ValueError:
        target_n = 5

    return SessionConfig(
        domain=domain,
        experience=experience,
        topics=topics or [catalog[0]],
        custom_topic=custom or None,
        target_questions=target_n,
    )


def _level_hint(l: ExperienceLevel) -> str:
    return {
        ExperienceLevel.FRESHER: "0 yrs, fundamentals",
        ExperienceLevel.JUNIOR: "1-3 yrs, practical",
        ExperienceLevel.MID: "3-5 yrs, trade-offs",
        ExperienceLevel.SENIOR: "5+ yrs, system design",
    }[l]


# ---------------------------------------------------------------------------
# Interactive interview loop
# ---------------------------------------------------------------------------

def run_interactive(engine: InterviewEngine) -> None:
    print(_hr("═"))
    print("  AI Interview Platform — Interactive Mode")
    print(_hr("═"))

    config = _wizard()
    session = engine.create_session(config)

    print(f"\n✓ Session started ({session.id[:8]}...)")
    print(f"  Domain: {config.domain.value} | Experience: {config.experience.value}")
    print(f"  Topics: {', '.join(config.topics)}"
          + (f" | Custom: {config.custom_topic}" if config.custom_topic else ""))
    print(f"  Plan: {config.target_questions} questions\n")
    print("Tip: type 'skip' to skip, 'scenario' to force a scenario, 'end' to finish early.\n")

    asked = 0
    while asked < config.target_questions:
        try:
            question = engine.generate_question(session.id)
        except LLMProviderError as e:
            print(f"❌ Could not generate a question: {e}")
            return

        asked += 1
        print(_hr())
        print(f"Q{asked}/{config.target_questions} [{question.qtype.value} • {question.topic}]")
        print(_hr())
        print(_wrap(question.text, indent=""))
        print()

        answer = input("Your answer (or 'skip' / 'end' / 'scenario'): ").strip()

        if answer.lower() == "end":
            break
        if answer.lower() == "scenario":
            try:
                sc = engine.generate_scenario(session.id, topic=question.topic)
                print(f"\n📦 Scenario: {sc.title}\n")
                print(_wrap(sc.context))
                print("\nProblem:")
                print(_wrap(sc.problem))
                if sc.expected_approach:
                    print("\nExpected approach:")
                    for p in sc.expected_approach:
                        print(f"  • {p}")
            except LLMProviderError as e:
                print(f"❌ Scenario failed: {e}")
            continue   # don't count this as the answered question
        if answer.lower() == "skip" or not answer:
            answer = "(skipped)"

        try:
            ev = engine.evaluate_answer(session.id, question.id, answer)
        except LLMProviderError as e:
            print(f"❌ Evaluation failed: {e}")
            continue

        print(f"\n  Rating: {ev.score_label.value.upper()}")
        if ev.strengths:
            print("  Strengths:")
            for s in ev.strengths:
                print(f"    • {s}")
        if ev.gaps:
            print("  Gaps:")
            for g in ev.gaps:
                print(f"    • {g}")
        if ev.ideal_answer:
            print("\n  Ideal answer:")
            print(_wrap(ev.ideal_answer, indent="    "))
        print()

    # ------- Final summary -------
    print(_hr("═"))
    print("  Generating final summary…")
    print(_hr("═"))
    try:
        summary = engine.end_session(session.id)
    except (ValueError, LLMProviderError) as e:
        print(f"❌ Could not end session: {e}")
        return

    print(f"\nOverall: {summary.score_label.value.upper()} "
          f"({summary.overall_score}/3 across {summary.total_questions} questions)\n")

    if summary.per_topic_scores:
        print("By topic:")
        for t, s in sorted(summary.per_topic_scores.items(), key=lambda x: x[1]):
            print(f"  {t:30s} {s:.2f}/3")
        print()

    for label, items in [
        ("Strengths", summary.strengths),
        ("Areas to improve", summary.improvements),
        ("Recommended next steps", summary.recommendations),
    ]:
        if items:
            print(f"{label}:")
            for it in items:
                print(f"  • {it}")
            print()


# ---------------------------------------------------------------------------
# Quick (one-shot) mode
# ---------------------------------------------------------------------------

def run_quick(engine: InterviewEngine, args: argparse.Namespace) -> None:
    config = SessionConfig(
        domain=Domain(args.domain),
        experience=ExperienceLevel(args.experience),
        topics=args.topics or [TOPIC_CATALOG[Domain(args.domain)][0]],
        custom_topic=args.custom_topic,
        target_questions=1,
    )
    session = engine.create_session(config)

    qtype = QuestionType(args.qtype) if args.qtype else None
    question = engine.generate_question(session.id, qtype=qtype)

    print(_hr())
    print(f"[{question.qtype.value} • {question.topic}]")
    print(_hr())
    print(question.text)
    if question.expected_points and args.show_hints:
        print("\nKey points to cover:")
        for p in question.expected_points:
            print(f"  • {p}")


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="interview",
        description="AI Interview Platform — CLI",
    )
    sub = p.add_subparsers(dest="mode", required=True)

    sub.add_parser("interactive", help="Full mock interview with summary")

    q = sub.add_parser("quick", help="Generate ONE question and exit")
    q.add_argument("--domain", required=True, choices=[d.value for d in Domain])
    q.add_argument("--experience", required=True, choices=[e.value for e in ExperienceLevel])
    q.add_argument("--topics", nargs="*", default=[])
    q.add_argument("--custom-topic", default=None)
    q.add_argument("--qtype", choices=[t.value for t in QuestionType])
    q.add_argument("--show-hints", action="store_true",
                   help="Print the expected-points list (for self-grading).")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    setup_logging()
    args = build_parser().parse_args(argv)

    engine = InterviewEngine()

    if args.mode == "interactive":
        run_interactive(engine)
    elif args.mode == "quick":
        run_quick(engine, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
