"""Turns a Usage into a structured dollar cost (Task 24.2).

Pure, deterministic, no I/O -- reads MODEL_PRICES (Task 24.1), never
calls out. Separate from pricing.py on purpose: pricing.py owns the
rate *data* (what a token costs), this module owns the *arithmetic*
(what a call cost, given its token counts).
"""

from dataclasses import dataclass

from eval.harness.pricing import get_price
from skycast.llm.usage import Usage


@dataclass(frozen=True)
class QueryCostLine:
    """One Usage's cost, broken out by bucket.

    model is the resolved name cost_of used to look up pricing -- either
    a real model name (from usage.model or the model argument) or the
    literal string "unpriced" when neither was available. unpriced is
    True whenever no price could be found for that name (whether the
    name is real-but-untabled, e.g. "gpt-4o", or the "unpriced"
    sentinel itself) -- the two cases stay distinguishable via `model`,
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
    the literal "unpriced" -- then prices each bucket at that model's
    rate. get_price("unpriced") naturally returns None (that string is
    never a real MODEL_PRICES key), so the no-name-at-all case needs no
    separate branch.
    """
    resolved_model = usage.model if usage.model is not None else (
        model if model is not None else "unpriced"
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
