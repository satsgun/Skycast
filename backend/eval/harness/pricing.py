"""Per-token USD pricing for eval cost reporting (Task 24.1).

Not part of the LLMClient seam -- Usage stays vendor-agnostic token
counts (skycast.llm.usage.Usage); dollar pricing is a reporting-layer
concern layered on top here, looked up by model name.

MODEL_PRICES is live-verified, never guessed from memory (rates go
stale, and vendors deprecate models outright) -- each entry below
carries a `# verified against <url> on <date>` comment. As of the last
verification (2026-07-22), only 3 of the 6 models actually configured
in this codebase (wiring.py's _DEFAULT_MODELS, run_eval.py's per-vendor
fallbacks) have live official pricing: claude-haiku-4-5-20251001,
claude-sonnet-4-5, and gemini-2.5-flash. gemini-2.0-flash was shut down
2026-06-01 (Google's own docs); gpt-5-mini and gpt-4o are both absent
from OpenAI's current pricing page entirely -- all three are simply
absent from MODEL_PRICES below, not present with a guessed or stale
rate. get_price() resolves that absence to None, never a crash or a
silent 0-rate ModelPrice.

Turning a price + Usage into an actual dollar cost is cost.py's job
(Task 24.2's cost_of), not this module's -- this module only owns the
rate data and its lookup.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    input_price: float
    output_price: float
    cache_write_price: float
    cache_read_price: float


MODEL_PRICES: dict[str, ModelPrice] = {
    # verified against https://platform.claude.com/docs/en/about-claude/pricing
    # on 2026-07-22. cache_write_price uses the 5-minute cache-write rate,
    # matching AnthropicLLMClient's default cache_ttl="5m" (the 1h rate is
    # $2/MTok for Haiku 4.5, $6/MTok for Sonnet 4.5 -- not tabled separately
    # since this codebase doesn't run with cache_ttl="1h" by default).
    "claude-haiku-4-5-20251001": ModelPrice(
        input_price=1.00e-6, output_price=5.00e-6,
        cache_write_price=1.25e-6, cache_read_price=0.10e-6,
    ),
    "claude-sonnet-4-5": ModelPrice(
        input_price=3.00e-6, output_price=15.00e-6,
        cache_write_price=3.75e-6, cache_read_price=0.30e-6,
    ),
    # verified against https://ai.google.dev/gemini-api/docs/pricing on
    # 2026-07-22 (standard tier, text/image/video input). Gemini's implicit
    # caching has no write-side charge at all -- no cache-write field even
    # exists on the SDK response (see gemini_client.py's Task 23.4 note).
    "gemini-2.5-flash": ModelPrice(
        input_price=0.30e-6, output_price=2.50e-6,
        cache_write_price=0.0, cache_read_price=0.03e-6,
    ),
    # verified against https://ai.google.dev/gemini-api/docs/pricing on
    # 2026-07-22 (standard/paid tier, text/image/video input). Not
    # configured as a default anywhere in this codebase yet -- added so
    # MODEL_PRICES can price whichever of these an LLM_MODEL override
    # points at.
    "gemini-3.6-flash": ModelPrice(
        input_price=1.50e-6, output_price=7.50e-6,
        cache_write_price=0.0, cache_read_price=0.15e-6,
    ),
    "gemini-3.5-flash": ModelPrice(
        input_price=1.50e-6, output_price=9.00e-6,
        cache_write_price=0.0, cache_read_price=0.15e-6,
    ),
    # cache_read_price is 0.0 because context caching is "Not available"
    # for this model per the pricing page (confirmed via a second,
    # targeted fetch after an initial pass wrongly suggested $0.03/MTok,
    # likely bleeding over from gemini-2.5-flash's real rate above) --
    # this model simply never returns cache activity, so the rate is
    # never actually charged, unlike the "no write premium" 0.0s below
    # which are a real, always-applicable rate of zero.
    "gemini-3.5-flash-lite": ModelPrice(
        input_price=0.30e-6, output_price=2.50e-6,
        cache_write_price=0.0, cache_read_price=0.0,
    ),
    "gemini-3.1-flash-lite": ModelPrice(
        input_price=0.25e-6, output_price=1.50e-6,
        cache_write_price=0.0, cache_read_price=0.025e-6,
    ),
    # gemini-2.0-flash (run_eval.py's default): confirmed shut down
    # 2026-06-01 per Google's own docs -- deliberately absent, not priced.
    # gpt-5-mini (wiring.py's default) / gpt-4o (run_eval.py's default):
    # both absent from https://developers.openai.com/api/docs/pricing as of
    # 2026-07-22 (superseded by the gpt-5.4/5.5/5.6 family) -- deliberately
    # absent rather than priced against an unrelated successor model.
}


def get_price(model: str) -> ModelPrice | None:
    """None for anything not in MODEL_PRICES -- an unpriced model, never
    a crash or a silent 0-rate ModelPrice. See the module docstring for
    which of this codebase's configured models currently resolve here.
    """
    return MODEL_PRICES.get(model)
