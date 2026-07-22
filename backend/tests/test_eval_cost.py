"""Coverage for Task 24.2: cost_of turns a Usage into a structured
QueryCostLine (not a bare float), with model resolution preferring
usage.model over an explicit model argument, falling back to the
literal "unpriced" when neither is available. Also covers Task 24.3:
query_cost sums a query's decompose + synthesize QueryCostLines,
handling the clarify path (synthesize never ran) and propagating
"unpriced" from either stage rather than showing a silently-partial
total.
"""

from __future__ import annotations

from eval.harness.cost import cost_of, query_cost
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


# --- Task 24.3: query_cost ---


def test_query_cost_sums_decompose_and_synthesize_when_both_ran() -> None:
    decompose_usage = Usage(input_tokens=200, output_tokens=50, model=_KNOWN_MODEL)
    synthesize_usage = Usage(input_tokens=800, output_tokens=150, model=_KNOWN_MODEL)

    result = query_cost(decompose_usage, synthesize_usage)

    expected_decompose = cost_of(decompose_usage)
    expected_synthesize = cost_of(synthesize_usage)
    assert result.decompose == expected_decompose
    assert result.synthesize == expected_synthesize
    assert result.unpriced is False
    assert result.total_cost == expected_decompose.total_cost + expected_synthesize.total_cost


def test_query_cost_handles_the_clarify_path_where_synthesize_never_ran() -> None:
    decompose_usage = Usage(input_tokens=200, output_tokens=50, model=_KNOWN_MODEL)

    result = query_cost(decompose_usage, None)

    assert result.synthesize is None
    assert result.unpriced is False
    assert result.total_cost == cost_of(decompose_usage).total_cost


def test_query_cost_is_unpriced_when_decompose_is_unpriced() -> None:
    decompose_usage = Usage(input_tokens=200, output_tokens=50, model="gpt-4o")
    synthesize_usage = Usage(input_tokens=800, output_tokens=150, model=_KNOWN_MODEL)

    result = query_cost(decompose_usage, synthesize_usage)

    assert result.unpriced is True
    assert result.total_cost is None


def test_query_cost_is_unpriced_when_synthesize_is_unpriced() -> None:
    decompose_usage = Usage(input_tokens=200, output_tokens=50, model=_KNOWN_MODEL)
    synthesize_usage = Usage(input_tokens=800, output_tokens=150, model="gpt-4o")

    result = query_cost(decompose_usage, synthesize_usage)

    assert result.unpriced is True
    assert result.total_cost is None


def test_query_cost_model_argument_applies_to_both_stages() -> None:
    decompose_usage = Usage(input_tokens=200, output_tokens=50, model=None)
    synthesize_usage = Usage(input_tokens=800, output_tokens=150, model=None)

    result = query_cost(decompose_usage, synthesize_usage, model=_KNOWN_MODEL)

    assert result.unpriced is False
    assert result.decompose.model == _KNOWN_MODEL
    assert result.synthesize.model == _KNOWN_MODEL
