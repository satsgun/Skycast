"""Regression coverage: run_stochastic_aggregated must run an entire
N-run stochastic pass inside ONE persistent event loop, not one
asyncio.run() per stage-runner call.

A vendor SDK client that creates a persistent async resource on first
use and binds it to whichever event loop is running at the time (e.g.
google-genai's Client, which holds a persistent AsyncHttpxClient/aiohttp
ClientSession -- confirmed by reading the installed SDK's
_api_client.py) breaks the moment a *different* event loop tries to
reuse it: "RuntimeError: Event loop is closed". Before this fix, each
run_decompose()/run_synthesize() call wrapped its own work in a fresh
asyncio.run(), so a client instance reused across N runs would see a
new, different loop every time. Reproduced here with a stub client that
raises exactly that if it's ever awaited from a different event loop
than its first call.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

from eval.cases.dataset import DATASET
from eval.harness.aggregate import AggregateReport
from eval.harness.nrun import run_stochastic_aggregated
from eval.harness.types import Stage
from skycast.domain.provider import Granularity, WeatherVariable
from skycast.llm.client import LLMClient
from skycast.pipeline.data_needs import DataNeedsSpec, QueryIntent
from skycast.pipeline.synthesis_output import SynthesisOutput

_CASE = next(c for c in DATASET if c.id == "simple_current")

_CANNED_SPEC = DataNeedsSpec(
    location_names=["Hyderabad"],
    granularities={Granularity.CURRENT},
    variables={WeatherVariable.TEMPERATURE},
    intent=QueryIntent.CONDITIONS,
)
_CANNED_ANSWER = SynthesisOutput(text="It's clear right now.", highlight=None)


class _LoopBoundClient(LLMClient):
    """Simulates a vendor client that binds a persistent async resource
    to whichever event loop is running the first time it's used --
    raises the real-world error if a second, different event loop ever
    reuses it.
    """

    def __init__(self) -> None:
        self._bound_loop: asyncio.AbstractEventLoop | None = None
        self.call_count = 0

    async def get_structured(self, *, system, user, schema, tool_name) -> BaseModel:
        loop = asyncio.get_running_loop()
        if self._bound_loop is None:
            self._bound_loop = loop
        elif loop is not self._bound_loop:
            raise RuntimeError("Event loop is closed")
        self.call_count += 1
        return _CANNED_SPEC if schema is DataNeedsSpec else _CANNED_ANSWER


def test_run_stochastic_aggregated_reuses_one_event_loop_across_n_runs() -> None:
    """simple_current has both checks_decompose and checks_synthesize +
    canned_spec populated, so both stages call the client -- 3 decompose
    + 3 synthesize = 6 calls. Before the fix, each of those 6 calls
    would have gotten a fresh, different event loop (one asyncio.run()
    per run_decompose()/run_synthesize() call), so the stub client
    would raise starting on the 2nd call. After the fix, the whole pass
    -- both stages, all N runs each -- shares one loop, so it never
    mismatches.
    """
    client = _LoopBoundClient()
    report = AggregateReport()

    run_stochastic_aggregated([_CASE], report, client, n=3, judge_enabled=False, e2e=False)

    assert client.call_count == 6
    decompose_stage = next(s for s in report.stages if s.stage == Stage.DECOMPOSE)
    synthesize_stage = next(s for s in report.stages if s.stage == Stage.SYNTHESIZE)
    assert decompose_stage.errored_runs == 0
    assert synthesize_stage.errored_runs == 0
