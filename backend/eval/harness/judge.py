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

from skycast.domain.forecast import DailyReading, Forecast
from eval.harness.grounding import select_reading


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


def _render_forecast(forecast: Forecast) -> str:
    reading = select_reading(forecast, None)
    fields = [f"location={forecast.location.name}"]
    if isinstance(reading, DailyReading):
        temp_min, temp_max, wind = reading.temp_min, reading.temp_max, reading.wind_speed_max
        if temp_min is not None:
            fields.append(f"temp_min={temp_min}")
        if temp_max is not None:
            fields.append(f"temp_max={temp_max}")
    else:
        if reading.temperature is not None:
            fields.append(f"temperature={reading.temperature}")
        wind = reading.wind_speed
    if reading.precip_probability is not None:
        fields.append(f"precip_probability={reading.precip_probability}")
    if wind is not None:
        fields.append(f"wind_speed={wind}")
    fields.append(f"condition={reading.condition_code.value}")
    return ", ".join(fields)


def make_judge(llm):
    """Build a judge callable bound to an LLMClient. Returns None-safe:
    await it with (case, answer, forecasts) -> Verdict. Async (not
    asyncio.run()-wrapped internally) so it can be awaited from within
    the same event loop as the rest of a stochastic pass -- see
    stochastic.py's module docstring for why per-call asyncio.run()
    breaks a long-lived vendor client.
    """
    async def judge(case, answer, forecasts) -> Verdict:
        rendered = "\n".join(_render_forecast(f) for f in forecasts)
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
