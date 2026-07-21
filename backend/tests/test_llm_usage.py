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


@pytest.mark.parametrize(
    "field", ["input_tokens", "output_tokens", "cache_write_tokens", "cache_read_tokens"]
)
def test_negative_tokens_is_rejected(field: str) -> None:
    kwargs = {"input_tokens": 10, "output_tokens": 5, field: -1}
    with pytest.raises(ValidationError):
        Usage(**kwargs)


def test_cache_tokens_default_to_zero() -> None:
    usage = Usage(input_tokens=10, output_tokens=5)
    assert usage.cache_write_tokens == 0
    assert usage.cache_read_tokens == 0


def test_cache_tokens_can_be_set() -> None:
    usage = Usage(input_tokens=10, output_tokens=5, cache_write_tokens=100, cache_read_tokens=900)
    assert usage.cache_write_tokens == 100
    assert usage.cache_read_tokens == 900


def test_add_sums_cache_tokens() -> None:
    a = Usage(input_tokens=10, output_tokens=5, cache_write_tokens=100, cache_read_tokens=0)
    b = Usage(input_tokens=2, output_tokens=1, cache_write_tokens=0, cache_read_tokens=100)
    combined = a + b
    assert combined.cache_write_tokens == 100
    assert combined.cache_read_tokens == 100


def test_cache_hit_rate_computed_from_read_write_and_uncached_input() -> None:
    usage = Usage(input_tokens=0, output_tokens=5, cache_write_tokens=10, cache_read_tokens=90)
    assert usage.cache_hit_rate == pytest.approx(0.9)


def test_cache_hit_rate_is_zero_when_all_input_related_tokens_are_zero() -> None:
    usage = Usage(input_tokens=0, output_tokens=5)
    assert usage.cache_hit_rate == 0.0


def test_cache_hit_rate_not_included_in_serialization() -> None:
    usage = Usage(input_tokens=10, output_tokens=5, cache_read_tokens=5)
    assert "cache_hit_rate" not in usage.model_dump()
    assert "cache_hit_rate" not in usage.model_dump(mode="json")


def test_usage_is_frozen() -> None:
    usage = Usage(input_tokens=10, output_tokens=5)
    with pytest.raises(ValidationError):
        usage.input_tokens = 20


def test_usage_round_trips_through_json() -> None:
    usage = Usage(
        input_tokens=10, output_tokens=5, model="gpt-5",
        cache_write_tokens=100, cache_read_tokens=900,
    )
    assert Usage.model_validate_json(usage.model_dump_json()) == usage


def test_total_tokens_not_included_in_serialization() -> None:
    usage = Usage(input_tokens=10, output_tokens=5)
    assert "total_tokens" not in usage.model_dump()
    assert "total_tokens" not in usage.model_dump(mode="json")
