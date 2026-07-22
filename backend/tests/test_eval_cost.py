"""Coverage for Task 24.2: cost_of turns a Usage into a structured
QueryCostLine (not a bare float), with model resolution preferring
usage.model over an explicit model argument, falling back to the
literal "unpriced" when neither is available.
"""

from __future__ import annotations

from eval.harness.cost import cost_of
from eval.harness.pricing import MODEL_PRICES
from skycast.llm.usage import Usage

_KNOWN_MODEL = "claude-sonnet-4-5"


def test_zero_cache_activity_reduces_to_plain_input_and_output_pricing() -> None:
    usage = Usage(input_tokens=1000, output_tokens=200, model=_KNOWN_MODEL)
    price = MODEL_PRICES[_KNOWN_MODEL]

    line = cost_of(usage)

    assert line.unpriced is False
    assert line.model == _KNOWN_MODEL
    assert line.input_cost == 1000 * price.input_price
    assert line.output_cost == 200 * price.output_price
    assert line.cache_cost == 0.0
    assert line.total_cost == line.input_cost + line.output_cost


def test_cache_read_and_write_tokens_priced_at_their_own_rates() -> None:
    usage = Usage(
        input_tokens=1000,
        output_tokens=200,
        cache_read_tokens=5000,
        cache_write_tokens=300,
        model=_KNOWN_MODEL,
    )
    price = MODEL_PRICES[_KNOWN_MODEL]

    line = cost_of(usage)

    expected_cache_cost = 5000 * price.cache_read_price + 300 * price.cache_write_price
    assert line.cache_cost == expected_cache_cost
    assert line.total_cost == line.input_cost + line.output_cost + line.cache_cost


def test_usage_model_is_preferred_over_the_model_argument() -> None:
    usage = Usage(input_tokens=10, output_tokens=5, model=_KNOWN_MODEL)

    line = cost_of(usage, model="gemini-2.5-flash")

    assert line.model == _KNOWN_MODEL


def test_model_argument_is_used_when_usage_has_no_model() -> None:
    usage = Usage(input_tokens=10, output_tokens=5, model=None)

    line = cost_of(usage, model="gemini-2.5-flash")

    assert line.model == "gemini-2.5-flash"
    assert line.unpriced is False


def test_no_model_anywhere_resolves_to_the_literal_unpriced_sentinel() -> None:
    usage = Usage(input_tokens=10, output_tokens=5, model=None)

    line = cost_of(usage)

    assert line.model == "unpriced"
    assert line.unpriced is True
    assert line.input_cost is None
    assert line.output_cost is None
    assert line.cache_cost is None
    assert line.total_cost is None


def test_named_but_untabled_model_keeps_its_name_and_is_marked_unpriced() -> None:
    """gpt-4o is confirmed absent from MODEL_PRICES (Task 24.1) -- this
    is a different "don't know" case from having no name at all: the
    real name is preserved rather than replaced by the "unpriced"
    sentinel, so a report can still say *which* model went unpriced.
    """
    usage = Usage(input_tokens=10, output_tokens=5, model="gpt-4o")

    line = cost_of(usage)

    assert line.model == "gpt-4o"
    assert line.unpriced is True
    assert line.total_cost is None
