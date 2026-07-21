"""LLM-as-judge (gated tier).

Scores a synthesized answer against a case's rubric using a real LLM,
through the same LLMClient seam the pipeline uses -- so the judge is
vendor-agnostic too. Returns a pass/fail verdict + rationale.

Deliberately a SEPARATE model call from the one under test, and gated
behind --judge, because it adds cost + non-determinism. The property
floor (deterministic checks) always runs; the judge is the deeper,
optional tier for 'is this actually a good answer'.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


class JudgeVerdict(BaseModel):
    """Structured judge output -- via the same get_structured() seam."""
    passed: bool = Field(description="True if the answer satisfies the rubric.")
    rationale: str = Field(description="One or two sentences justifying the verdict.")


@dataclass
class Verdict:
    passed: bool
    detail: str


_JUDGE_SYSTEM = (
    "You are an impartial evaluator of a weather assistant's answers. "
    "Given a user query, the assistant's answer, and a rubric, decide "
    "whether the answer satisfies the rubric. Be strict about the "
    "answer-first property: the conclusion must come first, and the "
    "answer must be consistent with any forecast figures it cites. "
    "Return only the structured verdict."
)


def make_judge(llm):
    """Build a judge callable bound to an LLMClient. Returns None-safe:
    call it with (case, answer) -> Verdict.
    """
    def judge(case, answer) -> Verdict:
        import asyncio

        user = (
            f"User query:\n{case.query}\n\n"
            f"Assistant answer:\n{answer.text}\n\n"
            f"Rubric:\n{case.judge_rubric}\n\n"
            "Does the answer satisfy the rubric?"
        )
        verdict = asyncio.run(
            llm.get_structured(
                system=_JUDGE_SYSTEM,
                user=user,
                schema=JudgeVerdict,
                tool_name="emit_verdict",
            )
        )
        return Verdict(verdict.passed, verdict.rationale)

    return judge
