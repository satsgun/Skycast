"""Core eval-harness types.

Tiered evaluation (see eval/README.md and the eval-harness task spec):
- DETERMINISTIC tiers (plan, execute) assert exact/structural outcomes,
  need no LLM, run in ordinary CI.
- STOCHASTIC tiers (decompose, synthesize) need a real LLM; scored by
  property assertions (always) plus an optional gated LLM-judge.

This module holds only data types -- no scoring logic, no pipeline
imports -- so it stays trivially importable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class Tier(str, Enum):
    DETERMINISTIC = "deterministic"   # plan, execute -- exact/structural
    STOCHASTIC = "stochastic"         # decompose, synthesize -- real LLM


class Stage(str, Enum):
    DECOMPOSE = "decompose"
    PLAN = "plan"
    EXECUTE = "execute"
    SYNTHESIZE = "synthesize"
    END_TO_END = "end_to_end"


@dataclass(frozen=True)
class Check:
    """One named property assertion over a stage's output.

    `predicate` returns (passed, detail). Kept as a plain callable so a
    case can mix generic checks (leads-with-a-sentence) and case-specific
    ones (window is Tokyo-local evening) without a class hierarchy.
    """

    name: str
    predicate: Callable[[Any], tuple[bool, str]]


@dataclass(frozen=True)
class EvalCase:
    """One evaluation case.

    A case may assert at several stages -- it carries the query plus
    optional per-stage expectations. Deterministic stages (plan/execute)
    use exact/structural `expect_*`; stochastic stages (decompose/
    synthesize) use property `checks_*`. Not every case exercises every
    stage; unset expectations are skipped.
    """

    id: str
    query: str
    tags: tuple[str, ...] = ()

    # --- deterministic-tier expectations (exact / structural) ---
    # plan: asserted via checks over the produced ToolPlan
    checks_plan: tuple[Check, ...] = ()
    # execute: expected ExecutionResult variant name + checks over it
    expect_execute_variant: str | None = None   # "Success" | "NeedsClarification" | "Failed"
    checks_execute: tuple[Check, ...] = ()

    # --- stochastic-tier expectations (properties over real LLM output) ---
    checks_decompose: tuple[Check, ...] = ()
    checks_synthesize: tuple[Check, ...] = ()      # property floor
    judge_rubric: str | None = None                # gated LLM-judge, optional

    # --- end-to-end expectation ---
    expect_terminal: str | None = None   # "answer" | "clarify" | "error"
    checks_end_to_end: tuple[Check, ...] = ()

    # canned decompose output, so plan/execute can be exercised
    # deterministically without an LLM producing the spec first
    canned_spec: Any = None

    # optional per-case geocode data injected into InMemoryProvider, for
    # cases whose locations aren't in the built-in set (custom cities,
    # multi-match variants). name(lowercased) -> list[Location].
    provider_locations: Any = None

    # optional default location, for cases whose query names none (e.g.
    # "will it rain today?"). Threaded into QueryRequest by the
    # end-to-end runner, so plan() has somewhere to resolve a target from
    # when location_names comes back empty -- without it, such a case can
    # never reach a success terminal event, no matter how correct the
    # rest of the pipeline is.
    default_location: Any = None


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass
class StageResult:
    case_id: str
    stage: Stage
    tier: Tier
    ran: bool                      # False = skipped (e.g. no API key)
    error: str | None = None       # a raised exception, not a failed check
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.ran and self.error is None and all(c.passed for c in self.checks)
