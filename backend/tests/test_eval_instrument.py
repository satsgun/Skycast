"""Regression coverage for Task 22.5: InstrumentedLLMClient reads the
structured Usage.total_tokens now that all three real LLMClients set
last_usage (Task 22.2-22.4), instead of the old int(usage) coercion
that only ever worked against a plain int no real client ever produced.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

from eval.harness.instrument import InstrumentedLLMClient
from skycast.llm.client import LLMClient
from skycast.llm.usage import Usage


class _Canned(BaseModel):
    value: str


class _StubClient(LLMClient):
    def __init__(self, *, last_usage: Usage | None = None) -> None:
        self.last_usage = last_usage

    async def get_structured(self, *, system, user, schema, tool_name) -> BaseModel:
        return _Canned(value="ok")


def _call(client: InstrumentedLLMClient) -> None:
    asyncio.run(
        client.get_structured(system="sys", user="query", schema=_Canned, tool_name="emit")
    )


def test_snapshot_and_reset_reports_usage_when_inner_client_sets_usage() -> None:
    inner = _StubClient(last_usage=Usage(input_tokens=10, output_tokens=5))
    client = InstrumentedLLMClient(inner)

    _call(client)
    _, usage = client.snapshot_and_reset()

    assert usage.input_tokens == 10
    assert usage.output_tokens == 5


def test_snapshot_and_reset_reports_none_usage_when_inner_client_has_no_usage() -> None:
    inner = _StubClient(last_usage=None)
    client = InstrumentedLLMClient(inner)

    _call(client)
    _, usage = client.snapshot_and_reset()

    assert usage is None


def test_snapshot_and_reset_accumulates_across_multiple_calls_before_reset() -> None:
    inner = _StubClient(last_usage=Usage(input_tokens=10, output_tokens=5))
    client = InstrumentedLLMClient(inner)

    _call(client)
    _call(client)
    _, usage = client.snapshot_and_reset()

    assert usage.input_tokens == 20
    assert usage.output_tokens == 10


def test_snapshot_and_reset_resets_usage_not_just_the_count() -> None:
    """A later snapshot with no new get_structured() call in between
    must report None, not a zeroed Usage -- otherwise a failed call
    following an earlier success in the same shared-instance session
    (nrun.py reuses one InstrumentedLLMClient across every case/stage/
    run) would silently contribute a phantom all-zero data point to the
    reported average instead of being excluded as unknown.
    """
    inner = _StubClient(last_usage=Usage(input_tokens=10, output_tokens=5))
    client = InstrumentedLLMClient(inner)

    _call(client)
    client.snapshot_and_reset()
    _, usage = client.snapshot_and_reset()

    assert usage is None


def test_snapshot_and_reset_preserves_cache_read_and_write_tokens() -> None:
    inner = _StubClient(
        last_usage=Usage(
            input_tokens=10, output_tokens=5, cache_read_tokens=900, cache_write_tokens=15
        )
    )
    client = InstrumentedLLMClient(inner)

    _call(client)
    _, usage = client.snapshot_and_reset()

    assert usage.cache_read_tokens == 900
    assert usage.cache_write_tokens == 15
