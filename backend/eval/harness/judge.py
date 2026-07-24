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

from skycast.domain.forecast import Forecast
from skycast.pipeline.synthesize_stage import render_forecast_lines


class JudgeVerdict(BaseModel):
    """Structured judge output -- via the same get_structured() seam."""
    well_formed: bool = Field(description="True if the answer leads with the conclusion, answer-first.")
    faithful: bool = Field(description="True if the answer is consistent with the forecast data shown.")
    rationale: str = Field(description="One or two sentences justifying the verdict.")


@dataclass
class Verdict:
    well_formed: bool
    faithful: bool
    detail: str


_JUDGE_SYSTEM = (
    "You are an impartial evaluator of a weather assistant's answers. "
    "Given a user query, the assistant's answer, a rubric, and the "
    "forecast data behind the answer, judge two separate dimensions. "
    "First, well-formedness: be strict about the answer-first property "
    "-- the conclusion must come first -- and whether the answer "
    "satisfies the rubric. Second, faithfulness: the answer must be "
    "consistent with the forecast data shown; flag any claim that "
    "contradicts it. Return only the structured verdict."
)


def _render_forecasts(forecasts: list[Forecast]) -> str:
    """Renders every reading of every forecast -- reusing synthesize's own
    renderer (`render_forecast_lines`) so the judge sees exactly the same
    complete data the model had, not a single cherry-picked reading. A
    prior version used `select_reading(forecast, None)`, whose fallback
    precedence (current -> hourly[0] -> daily[0]) meant the judge only
    ever saw the FIRST reading -- so a model correctly citing a real,
    later reading (e.g. an afternoon hour, for a query about "this
    afternoon") got flagged as unfaithful purely because the judge was
    never shown that reading at all.
    """
    lines: list[str] = []
    for i, forecast in enumerate(forecasts):
        lines.extend(render_forecast_lines(i, forecast))
    return "\n".join(lines)


def make_judge(llm):
    """Build a judge callable bound to an LLMClient. Returns None-safe:
    await it with (case, answer, forecasts) -> Verdict. Async (not
    asyncio.run()-wrapped internally) so it can be awaited from within
    the same event loop as the rest of a stochastic pass -- see
    stochastic.py's module docstring for why per-call asyncio.run()
    breaks a long-lived vendor client.
    """
    async def judge(case, answer, forecasts) -> Verdict:
        rendered = _render_forecasts(forecasts)
        user = (
            f"User query:\n{case.query}\n\n"
            f"Assistant answer:\n{answer.text}\n\n"
            f"Rubric:\n{case.judge_rubric}\n\n"
            f"Forecast data behind the answer:\n{rendered}\n\n"
            "Does the answer satisfy the rubric, and is it faithful to the forecast data?"
        )
        verdict = await llm.get_structured(
            system=_JUDGE_SYSTEM,
            user=user,
            schema=JudgeVerdict,
            tool_name="emit_verdict",
        )
        return Verdict(verdict.well_formed, verdict.faithful, verdict.rationale)

    return judge
