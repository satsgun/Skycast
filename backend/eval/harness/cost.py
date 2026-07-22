"""Turns a Usage into a structured dollar cost (Task 24.2), and sums a
whole query's stage-level costs (Task 24.3).

Pure, deterministic, no I/O -- reads MODEL_PRICES (Task 24.1), never
calls out. Separate from pricing.py on purpose: pricing.py owns the
rate *data* (what a token costs), this module owns the *arithmetic*
(what a call -- or a whole query -- cost, given its token counts).
"""

from dataclasses import dataclass

from eval.harness.pricing import get_price
from skycast.llm.usage import Usage

UNPRICED = "unpriced"


@dataclass(frozen=True)
class QueryCostLine:
    """One Usage's cost, broken out by bucket.

    model is the resolved name cost_of used to look up pricing -- either
    a real model name (from usage.model or the model argument) or the
    UNPRICED sentinel when neither was available. unpriced is
    True whenever no price could be found for that name (whether the
    name is real-but-untabled, e.g. "gpt-4o", or the UNPRICED sentinel
    itself) -- the two cases stay distinguishable via `model`,
    since a report can still say *which* model went unpriced. The four
    cost fields are None together with unpriced=True (never a silent
    0.0 standing in for "we don't know"); cache_cost is a real 0.0, not
    None, when a Usage simply has no cache activity -- that's a known,
    computed answer, not a missing one.
    """

    model: str
    unpriced: bool
    input_cost: float | None
    output_cost: float | None
    cache_cost: float | None
    total_cost: float | None


def cost_of(usage: Usage, model: str | None = None) -> QueryCostLine:
    """Resolves the model to price against -- usage.model first (the
    call actually knows what it was), then the model argument (a
    caller's own fallback, e.g. the vendor's configured default), else
    the UNPRICED sentinel -- then prices each bucket at that model's
    rate. get_price(UNPRICED) naturally returns None (that string is
    never a real MODEL_PRICES key), so the no-name-at-all case needs no
    separate branch.
    """
    resolved_model = usage.model if usage.model is not None else (
        model if model is not None else UNPRICED
    )
    price = get_price(resolved_model)
    if price is None:
        return QueryCostLine(resolved_model, True, None, None, None, None)

    input_cost = usage.input_tokens * price.input_price
    output_cost = usage.output_tokens * price.output_price
    cache_cost = (
        usage.cache_read_tokens * price.cache_read_price
        + usage.cache_write_tokens * price.cache_write_price
    )
    return QueryCostLine(
        resolved_model, False, input_cost, output_cost, cache_cost,
        input_cost + output_cost + cache_cost,
    )


@dataclass(frozen=True)
class QueryCost:
    """One user query's cost -- the two LLM calls ADR-0001 splits a
    query into (decompose + synthesize; plan is deterministic, $0).

    synthesize is None when that stage never ran at all (the clarify
    path never synthesizes) -- a real, different case from it running
    but being unpriced. unpriced is True whenever any stage that DID
    run is unpriced, propagating QueryCostLine's own "don't silently
    show a partial number" rule up to the whole query.
    """

    decompose: QueryCostLine
    synthesize: QueryCostLine | None
    unpriced: bool
    total_cost: float | None


def query_cost(
    decompose_usage: Usage, synthesize_usage: Usage | None, model: str | None = None
) -> QueryCost:
    """Sums a query's decompose + synthesize QueryCostLines. `model` is
    a single fallback applied to both stages (one query runs against
    one active vendor/model, per this codebase's no-routing-yet
    design) -- each stage still independently prefers its own
    usage.model first, per cost_of's own resolution order. Retries need
    no handling here -- Task 22's last_usage already folds a repair
    retry into one Usage before this function ever sees it.
    """
    decompose_line = cost_of(decompose_usage, model)
    synthesize_line = cost_of(synthesize_usage, model) if synthesize_usage is not None else None

    unpriced = decompose_line.unpriced or (
        synthesize_line is not None and synthesize_line.unpriced
    )
    total_cost = None
    if not unpriced:
        total_cost = decompose_line.total_cost + (
            synthesize_line.total_cost if synthesize_line is not None else 0.0
        )
    return QueryCost(decompose_line, synthesize_line, unpriced, total_cost)
