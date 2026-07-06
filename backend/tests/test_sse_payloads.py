from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import Forecast, HourlyReading, Units
from skycast.domain.location import Location
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


PIPELINE_STAGE_MEMBERS_AND_VALUES = {
    "DECOMPOSE": "decompose",
    "PLAN": "plan",
    "EXECUTE_GEOCODE": "execute_geocode",
    "EXECUTE_FORECAST": "execute_forecast",
    "SYNTHESIZE": "synthesize",
}

ERROR_KIND_MEMBERS_AND_VALUES = {
    "NOT_FOUND": "not_found",
    "PROVIDER_UNREACHABLE": "provider_unreachable",
    "BAD_INPUT": "bad_input",
    "INTERNAL": "internal",
}


def test_pipeline_stage_member_set_and_values() -> None:
    assert [member.name for member in PipelineStage] == list(
        PIPELINE_STAGE_MEMBERS_AND_VALUES
    )
    for member in PipelineStage:
        assert member.value == PIPELINE_STAGE_MEMBERS_AND_VALUES[member.name]


def test_error_kind_member_set_and_values() -> None:
    assert [member.name for member in ErrorKind] == list(
        ERROR_KIND_MEMBERS_AND_VALUES
    )
    for member in ErrorKind:
        assert member.value == ERROR_KIND_MEMBERS_AND_VALUES[member.name]


def test_step_payload_constructs_with_label_and_stage() -> None:
    payload = StepPayload(label="Resolving location…", stage=PipelineStage.DECOMPOSE)
    assert payload.label == "Resolving location…"
    assert payload.stage is PipelineStage.DECOMPOSE


def test_step_payload_is_frozen() -> None:
    payload = StepPayload(label="Planning…", stage=PipelineStage.PLAN)
    with pytest.raises(ValidationError):
        payload.label = "Changed"


def test_step_payload_round_trips_through_json() -> None:
    payload = StepPayload(label="Fetching forecast…", stage=PipelineStage.EXECUTE_FORECAST)
    restored = StepPayload.model_validate_json(payload.model_dump_json())
    assert restored == payload


def test_clarify_payload_constructs_with_two_candidates() -> None:
    payload = ClarifyPayload(candidates=[_location("1"), _location("2")])
    assert len(payload.candidates) == 2


def test_clarify_payload_rejects_zero_candidates() -> None:
    with pytest.raises(ValidationError):
        ClarifyPayload(candidates=[])


def test_clarify_payload_rejects_one_candidate() -> None:
    with pytest.raises(ValidationError):
        ClarifyPayload(candidates=[_location("1")])


def test_clarify_payload_is_frozen() -> None:
    payload = ClarifyPayload(candidates=[_location("1"), _location("2")])
    with pytest.raises(ValidationError):
        payload.candidates = [_location("3"), _location("4")]


def test_clarify_payload_round_trips_through_json() -> None:
    payload = ClarifyPayload(candidates=[_location("1"), _location("2")])
    restored = ClarifyPayload.model_validate_json(payload.model_dump_json())
    assert restored == payload


def test_answer_card_constructs_with_datetime_highlight() -> None:
    highlight = datetime(2024, 1, 1, 15, 0, tzinfo=timezone.utc)
    card = AnswerCard(forecast=_forecast(), highlight=highlight)
    assert card.highlight == highlight


def test_answer_card_constructs_with_date_highlight() -> None:
    card = AnswerCard(forecast=_forecast(), highlight=date(2024, 1, 1))
    assert card.highlight == date(2024, 1, 1)


def test_answer_card_constructs_with_no_highlight() -> None:
    card = AnswerCard(forecast=_forecast())
    assert card.highlight is None


def test_answer_card_is_frozen() -> None:
    card = AnswerCard(forecast=_forecast())
    with pytest.raises(ValidationError):
        card.highlight = date(2024, 1, 1)


def test_answer_card_round_trips_through_json_with_datetime_highlight() -> None:
    card = AnswerCard(
        forecast=_forecast(), highlight=datetime(2024, 1, 1, 15, 0, tzinfo=timezone.utc)
    )
    restored = AnswerCard.model_validate_json(card.model_dump_json())
    assert restored == card
    assert isinstance(restored.highlight, datetime)


def test_answer_card_round_trips_through_json_with_date_highlight() -> None:
    card = AnswerCard(forecast=_forecast(), highlight=date(2024, 1, 1))
    restored = AnswerCard.model_validate_json(card.model_dump_json())
    assert restored == card
    assert isinstance(restored.highlight, date) and not isinstance(
        restored.highlight, datetime
    )


def test_answer_card_round_trips_through_json_with_no_highlight() -> None:
    card = AnswerCard(forecast=_forecast())
    restored = AnswerCard.model_validate_json(card.model_dump_json())
    assert restored == card


def test_answer_payload_constructs_with_text_and_card() -> None:
    card = AnswerCard(forecast=_forecast())
    payload = AnswerPayload(text="Yes, bring an umbrella.", card=card)
    assert payload.text == "Yes, bring an umbrella."
    assert payload.card == card


def test_answer_payload_is_frozen() -> None:
    payload = AnswerPayload(text="Yes.", card=AnswerCard(forecast=_forecast()))
    with pytest.raises(ValidationError):
        payload.text = "No."


def test_answer_payload_round_trips_through_json() -> None:
    payload = AnswerPayload(
        text="Yes, bring an umbrella.", card=AnswerCard(forecast=_forecast())
    )
    restored = AnswerPayload.model_validate_json(payload.model_dump_json())
    assert restored == payload


def test_error_payload_constructs_with_kind_and_message() -> None:
    payload = ErrorPayload(kind=ErrorKind.NOT_FOUND, message="No such city.")
    assert payload.kind is ErrorKind.NOT_FOUND
    assert payload.message == "No such city."


def test_error_payload_rejects_invalid_kind() -> None:
    with pytest.raises(ValidationError):
        ErrorPayload(kind="not_a_real_kind", message="Oops.")


def test_error_payload_is_frozen() -> None:
    payload = ErrorPayload(kind=ErrorKind.INTERNAL, message="Oops.")
    with pytest.raises(ValidationError):
        payload.message = "Changed."


def test_error_payload_round_trips_through_json() -> None:
    payload = ErrorPayload(kind=ErrorKind.PROVIDER_UNREACHABLE, message="Down.")
    restored = ErrorPayload.model_validate_json(payload.model_dump_json())
    assert restored == payload
