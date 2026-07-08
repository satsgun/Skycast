from datetime import datetime, timezone

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import Forecast, HourlyReading, Units
from skycast.domain.location import Location
from skycast.sse.envelope import SSEEvent
from skycast.sse.payloads import AnswerCard, ErrorKind, PipelineStage
from skycast.sse.wire import serialize_sse_event


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


def _data_json(wire: str) -> str:
    first_line = wire.split("\n", 1)[0]
    return first_line.removeprefix("data: ")


def test_serialize_ends_with_blank_line() -> None:
    event = SSEEvent.step("Resolving location…", PipelineStage.DECOMPOSE)
    wire = serialize_sse_event(event)
    assert wire.endswith("\n\n")


def test_serialize_contains_exactly_one_data_line() -> None:
    event = SSEEvent.step("Resolving location…", PipelineStage.DECOMPOSE)
    wire = serialize_sse_event(event)
    data_lines = [line for line in wire.split("\n") if line.startswith("data:")]
    assert len(data_lines) == 1


def test_serialize_never_uses_named_event_field() -> None:
    event = SSEEvent.step("Resolving location…", PipelineStage.DECOMPOSE)
    wire = serialize_sse_event(event)
    assert "event:" not in wire


def test_step_event_round_trips_through_wire_format() -> None:
    event = SSEEvent.step("Fetching forecast…", PipelineStage.EXECUTE_FORECAST)
    wire = serialize_sse_event(event)
    restored = SSEEvent.model_validate_json(_data_json(wire))
    assert restored == event


def test_clarify_event_round_trips_through_wire_format() -> None:
    event = SSEEvent.clarify([_location("1"), _location("2")])
    wire = serialize_sse_event(event)
    restored = SSEEvent.model_validate_json(_data_json(wire))
    assert restored == event


def test_answer_event_round_trips_through_wire_format() -> None:
    event = SSEEvent.answer("Yes.", AnswerCard(forecasts=[_forecast()]))
    wire = serialize_sse_event(event)
    restored = SSEEvent.model_validate_json(_data_json(wire))
    assert restored == event


def test_error_event_round_trips_through_wire_format() -> None:
    event = SSEEvent.error(ErrorKind.PROVIDER_UNREACHABLE, "Down.")
    wire = serialize_sse_event(event)
    restored = SSEEvent.model_validate_json(_data_json(wire))
    assert restored == event


def test_embedded_newline_in_payload_still_yields_one_data_line() -> None:
    event = SSEEvent.step("line one\nline two", PipelineStage.DECOMPOSE)
    wire = serialize_sse_event(event)
    data_lines = [line for line in wire.split("\n") if line.startswith("data:")]
    assert len(data_lines) == 1
    assert wire.endswith("\n\n")
    restored = SSEEvent.model_validate_json(_data_json(wire))
    assert restored.data.label == "line one\nline two"
