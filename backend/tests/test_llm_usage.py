import pytest
from pydantic import ValidationError

from skycast.llm.usage import Usage


def test_total_tokens_is_input_plus_output() -> None:
    usage = Usage(input_tokens=10, output_tokens=5)
    assert usage.total_tokens == 15


def test_model_defaults_to_none() -> None:
    usage = Usage(input_tokens=10, output_tokens=5)
    assert usage.model is None


def test_model_can_be_set() -> None:
    usage = Usage(input_tokens=10, output_tokens=5, model="claude-haiku-4-5-20251001")
    assert usage.model == "claude-haiku-4-5-20251001"


def test_zero_tokens_is_valid() -> None:
    usage = Usage(input_tokens=0, output_tokens=0)
    assert usage.total_tokens == 0


@pytest.mark.parametrize("field", ["input_tokens", "output_tokens"])
def test_negative_tokens_is_rejected(field: str) -> None:
    kwargs = {"input_tokens": 10, "output_tokens": 5, field: -1}
    with pytest.raises(ValidationError):
        Usage(**kwargs)


def test_usage_is_frozen() -> None:
    usage = Usage(input_tokens=10, output_tokens=5)
    with pytest.raises(ValidationError):
        usage.input_tokens = 20


def test_usage_round_trips_through_json() -> None:
    usage = Usage(input_tokens=10, output_tokens=5, model="gpt-5")
    assert Usage.model_validate_json(usage.model_dump_json()) == usage


def test_total_tokens_not_included_in_serialization() -> None:
    usage = Usage(input_tokens=10, output_tokens=5)
    assert "total_tokens" not in usage.model_dump()
    assert "total_tokens" not in usage.model_dump(mode="json")
