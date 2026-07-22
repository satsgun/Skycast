"""N-run driver (Gap 1 + Gap 3 capture).

Runs the stochastic stages N times per case and aggregates each check's
pass rate + variance; runs deterministic stages once (they're
deterministic -- InMemoryProvider). Latency (and tokens where available)
are captured per (case, stage) via InstrumentedLLMClient.

Produces an AggregateReport, which feeds reporting, baseline diffing
(Gap 2), and the cost note (Gap 3).

The entire stochastic pass (every case x stage x N-run iteration) runs
inside ONE event loop -- run_stochastic_aggregated makes exactly one
asyncio.run() call, not one per stage-runner call. A vendor SDK client
constructed once for the whole run (e.g. google-genai's Client, which
holds a persistent async HTTP session) binds that session to whichever
loop is running the first time it's used; a fresh asyncio.run() per
call would hand it a *different*, dead loop on every call after the
first, breaking with "Event loop is closed" (a real bug this fixes --
see run_decompose/run_synthesize/run_end_to_end's shared docstring
note in stochastic.py).
"""

from __future__ import annotations

import asyncio

from eval.harness.aggregate import AggregateReport, StageAggregate
from eval.harness.instrument import InstrumentedLLMClient
from eval.harness.types import Stage, Tier
from eval.harness.deterministic import run_plan, run_execute, _providers_for
from eval.harness.stochastic import (
    run_decompose, run_synthesize, run_end_to_end,
)
from eval.harness.judge import make_judge
from skycast.llm.usage import Usage
from skycast.providers.in_memory import InMemoryProvider


def _key(case_id: str, stage: Stage) -> str:
    return f"{case_id}::{stage.value}"


def _fold_single(agg: StageAggregate, stage_result) -> None:
    """Fold a single StageResult's checks into an aggregate (one observation)."""
    if not stage_result.ran:
        return
    if stage_result.error is not None:
        agg.errored_runs += 1
        if len(agg.error_samples) < 3:
            agg.error_samples.append(stage_result.error)
        return
    for c in stage_result.checks:
        agg.observe(c.name, c.passed, c.detail)


def run_deterministic_aggregated(cases, report: AggregateReport) -> None:
    """Deterministic tiers: one run each (N=1)."""
    for case in cases:
        providers = _providers_for(case)
        for stage, runner in ((Stage.PLAN, run_plan), (Stage.EXECUTE, run_execute)):
            sr = runner(case, providers)
            if not sr.ran:
                continue
            agg = StageAggregate(case.id, stage, Tier.DETERMINISTIC, runs=1)
            _fold_single(agg, sr)
            report.add(agg)


async def _run_stochastic_aggregated(
    cases, report: AggregateReport, llm, *, n: int, judge_enabled: bool, e2e: bool
) -> None:
    instrumented = InstrumentedLLMClient(llm)
    judge = make_judge(instrumented) if judge_enabled else None

    for case in cases:
        stages = [(Stage.DECOMPOSE, lambda c: run_decompose(c, instrumented)),
                  (Stage.SYNTHESIZE, lambda c: run_synthesize(c, instrumented, judge=judge))]
        if e2e:
            stages.append((Stage.END_TO_END, lambda c: run_end_to_end(c, instrumented)))

        for stage, runner in stages:
            agg = StageAggregate(case.id, stage, Tier.STOCHASTIC, runs=0)
            timings: list[float] = []
            usages: list[Usage] = []
            any_ran = False
            for _ in range(n):
                instrumented.snapshot_and_reset()  # clear before this run
                sr = await runner(case)
                if not sr.ran:
                    break  # this stage doesn't apply to this case
                any_ran = True
                agg.runs += 1
                _fold_single(agg, sr)
                lat, usage = instrumented.snapshot_and_reset()
                timings.append(lat)
                if usage is not None:
                    usages.append(usage)
            if any_ran:
                report.add(agg)
                report.timings_ms[_key(case.id, stage)] = timings
                if usages:
                    report.usages[_key(case.id, stage)] = usages


def run_stochastic_aggregated(
    cases, report: AggregateReport, llm, *, n: int, judge_enabled: bool, e2e: bool
) -> None:
    """Stochastic tiers: N runs each, aggregated with variance + timing.

    Exactly one asyncio.run() for the whole pass (see module docstring)
    -- never call run_decompose/run_synthesize/run_end_to_end (or wrap
    another asyncio.run()) outside of this, or a long-lived vendor
    client will see a different event loop per call again.
    """
    if llm is None:
        return
    asyncio.run(
        _run_stochastic_aggregated(cases, report, llm, n=n, judge_enabled=judge_enabled, e2e=e2e)
    )
