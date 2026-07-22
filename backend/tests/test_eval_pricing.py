"""Coverage for Task 23.6: compute_cost is the single pricing path used
for both cache-on and cache-off eval runs (see eval/harness/pricing.py's
module docstring) -- these tests pin its arithmetic and its two graceful
"can't price this" cases (no model, unrecognized model).
"""

from __future__ import annotations

from eval.harness.pricing import MODEL_PRICES, compute_cost, get_price
from skycast.llm.usage import Usage

_KNOWN_MODEL = "claude-haiku-4-5-20251001"


def test_compute_cost_multiplies_each_bucket_by_its_own_rate() -> None:
    usage = Usage(
        input_tokens=1000,
        output_tokens=200,
        cache_write_tokens=300,
        cache_read_tokens=5000,
        model=_KNOWN_MODEL,
    )
    rates = MODEL_PRICES[_KNOWN_MODEL]

    cost = compute_cost(usage)

    expected = (
        1000 * rates.input_price
        + 200 * rates.output_price
        + 300 * rates.cache_write_price
        + 5000 * rates.cache_read_price
    )
    assert cost == expected


def test_compute_cost_is_zero_not_none_for_an_all_zero_usage_with_a_known_model() -> None:
    usage = Usage(input_tokens=0, output_tokens=0, model=_KNOWN_MODEL)

    assert compute_cost(usage) == 0.0


def test_compute_cost_returns_none_when_usage_has_no_model() -> None:
    usage = Usage(input_tokens=10, output_tokens=5, model=None)

    assert compute_cost(usage) is None


def test_compute_cost_returns_none_for_an_unrecognized_model() -> None:
    usage = Usage(input_tokens=10, output_tokens=5, model="some-future-model-nobody-priced-yet")

    assert compute_cost(usage) is None


def test_get_price_returns_the_rate_for_a_known_model() -> None:
    assert get_price("claude-sonnet-4-5") == MODEL_PRICES["claude-sonnet-4-5"]


def test_get_price_returns_none_for_models_confirmed_absent_from_live_pricing() -> None:
    """gpt-4o/gpt-5-mini are off OpenAI's current pricing page entirely,
    and gemini-2.0-flash was shut down 2026-06-01 (see pricing.py's
    module docstring) -- all three must resolve to None, not a guessed
    or stale rate.
    """
    assert get_price("gpt-4o") is None
    assert get_price("gpt-5-mini") is None
    assert get_price("gemini-2.0-flash") is None
