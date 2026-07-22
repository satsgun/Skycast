"""Coverage for Task 24.1: MODEL_PRICES is a live-verified price table
and get_price() resolves an unknown/untabled model to None, never a
crash or a guessed rate. See tests/test_eval_cost.py for cost_of/
QueryCostLine (Task 24.2), which is what actually turns a Usage into a
dollar figure -- that used to live here as compute_cost, now removed.
"""

from __future__ import annotations

from eval.harness.pricing import MODEL_PRICES, get_price


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
