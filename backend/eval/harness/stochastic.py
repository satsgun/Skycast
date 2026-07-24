"""Stochastic-tier runner: decompose + synthesize (+ end-to-end).

These need a REAL LLM (the whole point is to score prompt quality, which
a fake can't measure). Weather stays fixed via InMemoryProvider, so the
only variable under test is the model's output. Scoring is:
  - property floor: always-run deterministic checks over the output
  - LLM-judge: optional, gated behind --judge, a second model call
    scoring the prose against the case's rubric.

Gated behind a provided LLMClient. If none is supplied (no API key),
every stochastic result is marked skipped -- ordinary CI stays green and
offline; the real eval is one flag away.

run_decompose/run_synthesize/run_end_to_end are async and MUST be
awaited from within a single event loop shared across an entire
stochastic pass (see nrun.py's run_stochastic_aggregated) -- never
wrapped in their own per-call asyncio.run(). A vendor SDK client (e.g.
google-genai's) can hold a persistent async HTTP session bound to
whichever loop is running when it's first used; a fresh asyncio.run()
per call would hand a long-lived client instance a *different* loop on
every call after the first, breaking with "Event loop is closed".
"""

from __future__ import annotations

from skycast.pipeline.decompose import decompose
from skycast.pipeline.synthesize_stage import synthesize
from skycast.pipeline.plan_stage import plan
from skycast.pipeline.execute_stage import execute
from skycast.pipeline.execute_result import Success
from skycast.pipeline.session_context import SessionContext
from skycast.providers.in_memory import InMemoryProvider
from eval.harness.deterministic import _providers_for

from eval.harness.types import (
    CheckResult, EvalCase, Stage, StageResult, Tier,
)
from eval.cases.dataset import _NOW


def _run_checks(obj, checks):
    out = []
    for c in checks:
        try:
            passed, detail = c.predicate(obj)
        except Exception as e:
            passed, detail = False, f"check raised {type(e).__name__}: {e}"
        out.append(CheckResult(c.name, passed, detail))
    return out


async def _noop_emit(label, stage):
    return None


def _ctx():
    return SessionContext(now=_NOW)


async def run_decompose(case: EvalCase, llm) -> StageResult:
    res = StageResult(case.id, Stage.DECOMPOSE, Tier.STOCHASTIC, ran=llm is not None)
    if llm is None or not case.checks_decompose:
        res.ran = False
        return res
    try:
        spec = await decompose(case.query, _ctx(), llm)
    except Exception as e:
        res.error = f"{type(e).__name__}: {e}"
        return res
    res.checks = _run_checks(spec, case.checks_decompose)
    return res


async def run_synthesize(case: EvalCase, llm, judge=None) -> StageResult:
    res = StageResult(case.id, Stage.SYNTHESIZE, Tier.STOCHASTIC, ran=llm is not None)
    if llm is None or not case.checks_synthesize:
        res.ran = False
        return res
    if case.canned_spec is None:
        res.ran = False
        return res
    providers = _providers_for(case)
    try:
        tool_plan = plan(case.canned_spec, providers)
        result = await execute(tool_plan, providers, emit=_noop_emit, now=_NOW)
        if not isinstance(result, Success):
            res.error = f"execute did not Succeed ({type(result).__name__}); cannot synthesize"
            return res
        answer = await synthesize(result.forecasts, case.canned_spec.intent, llm)
    except Exception as e:
        res.error = f"{type(e).__name__}: {e}"
        return res

    checks = list(case.checks_synthesize)
    if case.checks_synthesize_grounded is not None:
        checks.extend(case.checks_synthesize_grounded(result.forecasts))
    res.checks = _run_checks(answer, checks)

    # gated LLM-judge tier
    if judge is not None and case.judge_rubric:
        try:
            verdict = await judge(case, answer, result.forecasts)
            label = case.judge_rubric[:40]
            res.checks.append(
                CheckResult(f"judge_well_formed::{label}", verdict.well_formed, verdict.detail)
            )
            res.checks.append(
                CheckResult(f"judge_faithful::{label}", verdict.faithful, verdict.detail)
            )
        except Exception as e:
            res.checks.append(
                CheckResult("judge", False, f"judge raised {type(e).__name__}: {e}")
            )
    return res


async def run_end_to_end(case: EvalCase, llm) -> StageResult:
    """Run the whole run_query generator; assert the terminal event type."""
    res = StageResult(case.id, Stage.END_TO_END, Tier.STOCHASTIC, ran=llm is not None)
    if llm is None or case.expect_terminal is None:
        res.ran = False
        return res

    from skycast.api.query_request import QueryRequest
    from skycast.orchestrator.run_query import run_query

    providers = _providers_for(case)
    req = QueryRequest(
        query=case.query, now=_NOW, default_location=case.default_location
    )

    async def _drive():
        terminal = None
        payload = None
        async for ev in run_query(req, providers, llm):
            terminal = ev.type.value if hasattr(ev.type, "value") else str(ev.type)
            payload = ev.data
        return terminal, payload

    try:
        terminal, payload = await _drive()
    except Exception as e:
        res.error = f"{type(e).__name__}: {e}"
        return res

    detail = f"terminal={terminal} expected={case.expect_terminal}"
    if terminal == "error":
        kind = getattr(payload, "kind", None)
        kind = getattr(kind, "value", str(kind))
        detail += f" ({kind}: {getattr(payload, 'message', '?')})"

    res.checks.append(
        CheckResult("terminal_event", terminal == case.expect_terminal, detail)
    )
    return res
