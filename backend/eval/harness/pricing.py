"""Per-token USD pricing for eval cost reporting (Task 23.6).

Not part of the LLMClient seam -- Usage stays vendor-agnostic token
counts (skycast.llm.usage.Usage); dollar pricing is a reporting-layer
concern layered on top here, looked up by model name.

Rates are approximate, illustrative $/token figures reflecting each
vendor's published order-of-magnitude cache-discount structure (e.g.
Anthropic cache reads ~10% of base input, cache writes ~125%; OpenAI
cached input ~50% of base, no write premium; Gemini implicit-cache reads
~25% of base, no write premium) -- not a live pricing feed, and not
billing-accurate. The point is a believable, internally-consistent
comparison between two eval runs of the *same* model (one with
SKYCAST_DISABLE_CACHE set, one without), not absolute dollar accuracy.
Update _RATES if real accuracy is ever needed.

compute_cost is the single pricing path for both cache-on and cache-off
runs (Task 23.6's own requirement) -- it does no vendor branching at
all. The cache-off Usage it's given already has its cache fields zeroed
correctly per-vendor by the client itself (see anthropic_client.py /
openai_client.py / gemini_client.py's cache_enabled handling), so this
function only ever does one thing: multiply each bucket by its rate.
"""

from dataclasses import dataclass

from skycast.llm.usage import Usage


@dataclass(frozen=True)
class ModelRates:
    input: float
    output: float
    cache_write: float
    cache_read: float


_RATES: dict[str, ModelRates] = {
    # Anthropic -- wiring.py's default + run_eval.py's default.
    "claude-haiku-4-5-20251001": ModelRates(
        input=1.00e-6, output=5.00e-6, cache_write=1.25e-6, cache_read=0.10e-6
    ),
    "claude-sonnet-4-5": ModelRates(
        input=3.00e-6, output=15.00e-6, cache_write=3.75e-6, cache_read=0.30e-6
    ),
    # OpenAI -- no write premium (Task 23.3's own finding).
    "gpt-5-mini": ModelRates(input=0.25e-6, output=2.00e-6, cache_write=0.0, cache_read=0.125e-6),
    "gpt-4o": ModelRates(input=2.50e-6, output=10.00e-6, cache_write=0.0, cache_read=1.25e-6),
    # Gemini -- implicit caching, no write-side field at all (Task 23.4).
    "gemini-2.5-flash": ModelRates(
        input=0.30e-6, output=2.50e-6, cache_write=0.0, cache_read=0.075e-6
    ),
    "gemini-2.0-flash": ModelRates(
        input=0.10e-6, output=0.40e-6, cache_write=0.0, cache_read=0.025e-6
    ),
}


def compute_cost(usage: Usage) -> float | None:
    """USD cost of one Usage record, or None when it can't be priced
    (no model attributed, or a model string not in _RATES -- e.g. a
    LLM_MODEL override to something newer than this table). Not an
    error: an unpriced model is a normal, expected gap, not a bug.
    """
    if usage.model is None:
        return None
    rates = _RATES.get(usage.model)
    if rates is None:
        return None
    return (
        usage.input_tokens * rates.input
        + usage.output_tokens * rates.output
        + usage.cache_write_tokens * rates.cache_write
        + usage.cache_read_tokens * rates.cache_read
    )
