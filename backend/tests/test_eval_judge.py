"""Tests for eval/harness/judge.py's grounding dimension (Task E4.3)."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import Forecast, HourlyReading, Units
from skycast.domain.location import Location

from eval.harness.judge import _JUDGE_SYSTEM, _render_forecast, JudgeVerdict, make_judge

_NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


def _forecast(
    *,
    name: str = "Hyderabad",
    temperature: float = 29.4,
    precip_probability: float | None = 80.0,
    wind_speed: float | None = None,
    condition_code: ConditionCode = ConditionCode.RAIN,
) -> Forecast:
    return Forecast(
        location=Location(id=f"test:{name.lower()}", name=name, latitude=0.0, longitude=0.0),
        units=Units(),
        current=HourlyReading(
            timestamp=_NOW,
            temperature=temperature,
            precip_probability=precip_probability,
            wind_speed=wind_speed,
            condition_code=condition_code,
        ),
    )


def _case() -> SimpleNamespace:
    return SimpleNamespace(
        query="Do I need an umbrella in Hyderabad this afternoon?",
        judge_rubric="Does the answer lead with a clear yes/no umbrella decision?",
    )


def _answer() -> SimpleNamespace:
    return SimpleNamespace(text="Yes, bring an umbrella -- rain is likely this afternoon.")


class _FakeJudgeClient:
    def __init__(self, verdict: JudgeVerdict) -> None:
        self._verdict = verdict
        self.calls: list[dict] = []

    async def get_structured(self, *, system, user, schema, tool_name) -> BaseModel:
        self.calls.append(dict(system=system, user=user, schema=schema, tool_name=tool_name))
        return self._verdict


def test_judge_returns_well_formed_and_faithful_from_verdict() -> None:
    fake_verdict = JudgeVerdict(well_formed=True, faithful=False, rationale="Leads with yes, but denies rain.")
    client = _FakeJudgeClient(fake_verdict)
    judge = make_judge(client)

    verdict = judge(_case(), _answer(), [_forecast()])

    assert verdict.well_formed is True
    assert verdict.faithful is False
    assert verdict.detail == "Leads with yes, but denies rain."


def test_judge_user_message_includes_rendered_forecast_data() -> None:
    fake_verdict = JudgeVerdict(well_formed=True, faithful=True, rationale="ok")
    client = _FakeJudgeClient(fake_verdict)
    judge = make_judge(client)

    judge(_case(), _answer(), [_forecast(precip_probability=80.0)])

    user = client.calls[0]["user"]
    assert "precip_probability=80.0" in user
    assert "Hyderabad" in user
    assert "RAIN" in user


def test_judge_system_prompt_includes_faithfulness_clause() -> None:
    assert "consistent with the forecast data" in _JUDGE_SYSTEM
    assert "contradicts" in _JUDGE_SYSTEM


def test_render_forecast_uses_current_reading() -> None:
    rendering = _render_forecast(_forecast(name="Tokyo", temperature=15.0, precip_probability=20.0))
    assert "Tokyo" in rendering
    assert "temperature=15.0" in rendering
    assert "precip_probability=20.0" in rendering


def test_render_forecast_omits_none_fields() -> None:
    rendering = _render_forecast(_forecast(precip_probability=None, wind_speed=None))
    assert "precip_probability" not in rendering
    assert "wind_speed" not in rendering
