from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import Forecast, HourlyReading, Units
from skycast.domain.location import Location
from skycast.sse.envelope import SSEEvent
from skycast.sse.events import SSEEventType
from skycast.sse.payloads import (
    AnswerCard,
    AnswerPayload,
    ClarifyPayload,
    ErrorKind,
    ErrorPayload,
    PipelineStage,
    StepPayload,
)


def _location(suffix: str = "1") -> Location:
    return Location(
        id=suffix, name=f"Springfield {suffix}", latitude=39.8, longitude=-89.6
    )


def _forecast() -> Forecast:
    return Forecast(
        location=_location(),
        units=Units(),
        current=HourlyReading(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            temperature=20.0,
            condition_code=ConditionCode.CLEAR,
        ),
    )


def test_step_constructor_produces_matching_type_and_payload() -> None:
    event = SSEEvent.step("Resolving location…", PipelineStage.DECOMPOSE)
    assert event.type is SSEEventType.STEP
    assert isinstance(event.data, StepPayload)
    assert event.data.label == "Resolving location…"
    assert event.data.stage is PipelineStage.DECOMPOSE


def test_clarify_constructor_produces_matching_type_and_payload() -> None:
    candidates = [_location("1"), _location("2")]
    event = SSEEvent.clarify(candidates)
    assert event.type is SSEEventType.CLARIFY
    assert isinstance(event.data, ClarifyPayload)
    assert event.data.candidates == candidates


def test_answer_constructor_produces_matching_type_and_payload() -> None:
    card = AnswerCard(forecast=_forecast())
    event = SSEEvent.answer("Yes, bring an umbrella.", card)
    assert event.type is SSEEventType.ANSWER
    assert isinstance(event.data, AnswerPayload)
    assert event.data.text == "Yes, bring an umbrella."
    assert event.data.card == card


def test_error_constructor_produces_matching_type_and_payload() -> None:
    event = SSEEvent.error(ErrorKind.NOT_FOUND, "No such city.")
    assert event.type is SSEEventType.ERROR
    assert isinstance(event.data, ErrorPayload)
    assert event.data.kind is ErrorKind.NOT_FOUND
    assert event.data.message == "No such city."


def test_mismatched_type_and_data_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        SSEEvent(
            type=SSEEventType.STEP,
            data=ClarifyPayload(candidates=[_location("1"), _location("2")]),
        )


def test_sse_event_is_frozen() -> None:
    event = SSEEvent.step("Planning…", PipelineStage.PLAN)
    with pytest.raises(ValidationError):
        event.type = SSEEventType.ANSWER


def test_step_event_round_trips_through_json() -> None:
    event = SSEEvent.step("Fetching forecast…", PipelineStage.EXECUTE_FORECAST)
    restored = SSEEvent.model_validate_json(event.model_dump_json())
    assert restored == event
    assert isinstance(restored.data, StepPayload)


def test_clarify_event_round_trips_through_json() -> None:
    event = SSEEvent.clarify([_location("1"), _location("2")])
    restored = SSEEvent.model_validate_json(event.model_dump_json())
    assert restored == event
    assert isinstance(restored.data, ClarifyPayload)


def test_answer_event_round_trips_through_json() -> None:
    event = SSEEvent.answer("Yes.", AnswerCard(forecast=_forecast()))
    restored = SSEEvent.model_validate_json(event.model_dump_json())
    assert restored == event
    assert isinstance(restored.data, AnswerPayload)


def test_error_event_round_trips_through_json() -> None:
    event = SSEEvent.error(ErrorKind.PROVIDER_UNREACHABLE, "Down.")
    restored = SSEEvent.model_validate_json(event.model_dump_json())
    assert restored == event
    assert isinstance(restored.data, ErrorPayload)
