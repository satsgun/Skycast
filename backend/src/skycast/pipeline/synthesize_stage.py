"""Pipeline stage 4: synthesize (Task 17.3).

Turns the stage-3 Forecast(s) + query intent into an answer-first
AnswerPayload via the LLMClient seam -- the second and last LLM call in
the pipeline (ADR-0001-style: kept separate from decompose/plan).
Imports only LLMClient + domain/pipeline/sse types -- never a vendor SDK
(same seam discipline as decompose.py). The LLM never sees or returns
forecast data itself, only prose + a highlight pointer (SynthesisOutput,
Task 17.2); this module assembles the actual AnswerCard from the
trusted, unmodified `forecasts` argument, so provider data can't be
altered by round-tripping through the model.
"""

import logging
from typing import cast

from skycast.domain.forecast import DailyReading, Forecast, HourlyReading
from skycast.llm.client import LLMClient
from skycast.pipeline.data_needs import QueryIntent
from skycast.pipeline.prompts import SYNTHESIZE_SYSTEM_PROMPT
from skycast.pipeline.synthesis_output import SynthesisOutput
from skycast.sse.payloads import AnswerCard, AnswerPayload, ForecastBlock, Highlight

logger = logging.getLogger(__name__)

_TOOL_NAME = "emit_synthesis"


async def synthesize(
    query: str, forecasts: list[Forecast], intent: QueryIntent, llm: LLMClient
) -> AnswerPayload:
    """Raises LLMError / StructuredOutputError -- propagated from `llm`
    unchanged; the caller (orchestrator, Phase 5) maps them to SSE errors.
    """
    user = _build_user_message(query, forecasts, intent)
    output = cast(
        SynthesisOutput,
        await llm.get_structured(
            system=SYNTHESIZE_SYSTEM_PROMPT,
            user=user,
            schema=SynthesisOutput,
            tool_name=_TOOL_NAME,
        ),
    )
    highlight = _validate_highlight(output.highlight, forecasts)
    card = AnswerCard(forecasts=forecasts, highlight=highlight)
    return AnswerPayload(text=output.text, card=card)


def _validate_highlight(
    highlight: Highlight | None, forecasts: list[Forecast]
) -> Highlight | None:
    """Checks `highlight` against the real `forecasts` -- forecast_index
    in range, and the locator's block/index exists on that forecast.
    Drops to None (never raises) on any mismatch: a good answer with no
    highlight beats no answer. Logged so prompt quality stays visible.
    """
    if highlight is None:
        return None
    if not 0 <= highlight.forecast_index < len(forecasts):
        logger.warning(
            "synthesize: dropping highlight, forecast_index=%d out of range for %d forecast(s)",
            highlight.forecast_index, len(forecasts),
        )
        return None

    forecast = forecasts[highlight.forecast_index]
    locator = highlight.locator
    if locator.block == ForecastBlock.CURRENT:
        valid = forecast.current is not None
    elif locator.block == ForecastBlock.HOURLY:
        valid = forecast.hourly is not None and locator.index < len(forecast.hourly)
    else:
        valid = forecast.daily is not None and locator.index < len(forecast.daily)

    if not valid:
        logger.warning(
            "synthesize: dropping highlight, locator %r not valid for forecast %d",
            locator, highlight.forecast_index,
        )
        return None
    return highlight


def _build_user_message(query: str, forecasts: list[Forecast], intent: QueryIntent) -> str:
    lines = [f"Query: {query}", f"Intent: {intent.value}"]
    for i, forecast in enumerate(forecasts):
        lines.extend(render_forecast_lines(i, forecast))
    return "\n".join(lines)


def render_forecast_lines(index: int, forecast: Forecast) -> list[str]:
    """Renders one forecast's full data -- every current/hourly/daily
    reading, not a single selected one -- exactly as synthesize's own
    user message does. Public so eval/harness/judge.py can show the
    judge the same complete data the model had (a truncated
    single-reading render there previously caused false 'unfaithful'
    verdicts whenever the model correctly cited a real reading other
    than the first).
    """
    lines = [f"Forecast {index}: {forecast.location.name}"]
    if forecast.current is not None:
        lines.append(f"  current: {_render_hourly(forecast.current)}")
    if forecast.hourly is not None:
        for j, reading in enumerate(forecast.hourly):
            lines.append(f"  hourly[{j}]: {_render_hourly(reading)}")
    if forecast.daily is not None:
        for j, reading in enumerate(forecast.daily):
            lines.append(f"  daily[{j}]: {_render_daily(reading)}")
    return lines


def _render_hourly(reading: HourlyReading) -> str:
    return (
        f"{reading.condition_code.value}, {reading.temperature}C "
        f"(feels like {_or_na(reading.feels_like)}), "
        f"precip {_or_na(reading.precip_probability)}%, "
        f"wind {_or_na(reading.wind_speed)} km/h, at {reading.timestamp.isoformat()}"
    )


def _render_daily(reading: DailyReading) -> str:
    return (
        f"{reading.condition_code.value}, {reading.temp_min}-{reading.temp_max}C, "
        f"precip {_or_na(reading.precip_probability)}%, date {reading.date.isoformat()}"
    )


def _or_na(value: float | None) -> str:
    return "n/a" if value is None else str(value)
