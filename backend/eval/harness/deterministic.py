"""Deterministic-tier runner: plan + execute.

These stages need no LLM. plan() is pure; execute() runs against
InMemoryProvider (fixed weather -> stable, assertable outcomes). This
runner imports the REAL pipeline code -- it is an evaluation of the
committed implementation, not a reimplementation.

A case reaches these tiers via its `canned_spec` (a DataNeedsSpec built
in the dataset), so plan/execute are exercised without an LLM producing
the spec first. That is the whole point of separating the tiers: the
deterministic outcome of plan/execute is assertable exactly, offline.
"""

from __future__ import annotations

import asyncio

from skycast.pipeline.plan_stage import plan
from skycast.pipeline.execute_stage import execute
from skycast.pipeline.errors import NoLocationError, NoCapableProviderError
from skycast.providers.in_memory import InMemoryProvider

from eval.cases.dataset import _NOW
from eval.harness.types import (
    CheckResult,
    EvalCase,
    Stage,
    StageResult,
    Tier,
)


async def _noop_emit(label: str, stage) -> None:
    return None


def _run_checks(obj, checks) -> list[CheckResult]:
    out = []
    for c in checks:
        try:
            passed, detail = c.predicate(obj)
        except Exception as e:  # a check that blows up is a failed check, not a crash
            passed, detail = False, f"check raised {type(e).__name__}: {e}"
        out.append(CheckResult(c.name, passed, detail))
    return out


def run_plan(case: EvalCase, providers: dict) -> StageResult:
    res = StageResult(case.id, Stage.PLAN, Tier.DETERMINISTIC, ran=True)
    if case.canned_spec is None or not case.checks_plan:
        res.ran = False
        return res
    try:
        tool_plan = plan(case.canned_spec, providers, default_location=case.default_location)
    except (NoLocationError, NoCapableProviderError) as e:
        # A plan-stage typed error may be the expected outcome; expose it
        # to checks as the object under test.
        res.checks = _run_checks(e, case.checks_plan)
        return res
    except Exception as e:
        res.error = f"{type(e).__name__}: {e}"
        return res
    res.checks = _run_checks(tool_plan, case.checks_plan)
    return res


def run_execute(case: EvalCase, providers: dict) -> StageResult:
    res = StageResult(case.id, Stage.EXECUTE, Tier.DETERMINISTIC, ran=True)
    if case.canned_spec is None or case.expect_execute_variant is None:
        res.ran = False
        return res
    try:
        tool_plan = plan(case.canned_spec, providers, default_location=case.default_location)
        result = asyncio.run(execute(tool_plan, providers, emit=_noop_emit, now=_NOW))
    except Exception as e:
        res.error = f"{type(e).__name__}: {e}"
        return res

    variant = type(result).__name__
    res.checks.append(
        CheckResult(
            "execute_variant",
            variant == case.expect_execute_variant,
            f"variant={variant} expected={case.expect_execute_variant}",
        )
    )
    res.checks.extend(_run_checks(result, case.checks_execute))
    return res


def _providers_for(case: EvalCase) -> dict:
    """Fresh provider registry per case. If the case injects custom
    geocode data, merge it over the built-in set so custom cities resolve.
    """
    if case.provider_locations:
        return {"in-memory": InMemoryProvider(locations=case.provider_locations)}
    return {"in-memory": InMemoryProvider()}
