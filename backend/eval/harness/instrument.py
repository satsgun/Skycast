"""Instrumented LLMClient wrapper (Gap 3: cost/latency).

Wraps any LLMClient and records per-call wall-clock latency. Token counts
don't cross the LLMClient seam (get_structured returns only the validated
model -- correct seam design), so tokens are captured only if the wrapped
client chooses to expose a `last_usage: Usage | None` attribute (Task 22
-- all three real clients do, as of 22.2-22.4); otherwise latency alone
is recorded. This keeps the committed clients untouched: the harness
instruments from outside the seam, it doesn't reach through it.

The sketch frames this as "nearly free" -- captured on runs that happen
anyway -- and as the empirical validation of ADR-0001's two-call cost.
"""

from __future__ import annotations

import time

from pydantic import BaseModel

from skycast.llm.client import LLMClient


class InstrumentedLLMClient(LLMClient):
    def __init__(self, inner: LLMClient) -> None:
        self._inner = inner
        self.call_count = 0
        self.total_latency_ms = 0.0
        self.total_tokens = 0
        self._has_tokens = False

    async def get_structured(
        self, *, system: str, user: str, schema: type[BaseModel], tool_name: str
    ) -> BaseModel:
        start = time.perf_counter()
        result = await self._inner.get_structured(
            system=system, user=user, schema=schema, tool_name=tool_name
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        self.call_count += 1
        self.total_latency_ms += elapsed_ms
        usage = getattr(self._inner, "last_usage", None)
        if usage is not None:
            self._has_tokens = True
            self.total_tokens += usage.total_tokens
        return result

    def snapshot_and_reset(self) -> tuple[float, int | None]:
        """Return (latency_ms, tokens_or_None) accumulated since last
        reset. _has_tokens resets here too, not just the count -- it
        must reflect only calls since the last reset, or a failed call
        following an earlier success would report 0 tokens instead of
        None (the caller, nrun.py, reuses one instance across every
        case/stage/run, so this instance's "ever" and "since last
        reset" are not the same thing).
        """
        lat = self.total_latency_ms
        tok = self.total_tokens if self._has_tokens else None
        self.total_latency_ms = 0.0
        self.total_tokens = 0
        self._has_tokens = False
        return lat, tok
