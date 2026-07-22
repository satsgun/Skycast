"""N-run aggregation types (Gap 1: variance).

The sketch's central statistical point: a single run of a stochastic
stage is noise. Each stochastic case runs N times; we report the
*distribution* of each check's pass rate, not a single pass/fail. A
metric is `mean ± stdev over N runs` (e.g. "variable-recall 0.95 ±
0.04"). Deterministic tiers (plan/execute) are exempt -- they run once,
N=1, stdev=0, because InMemoryProvider makes them deterministic.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from eval.harness.types import SCORED_STAGES, Stage, Tier
from skycast.llm.usage import Usage


@dataclass
class CheckAggregate:
    """One check's outcome aggregated over N runs."""

    name: str
    observations: list[bool] = field(default_factory=list)   # per-run pass/fail
    details: list[str] = field(default_factory=list)         # per-run detail (for failures)

    @property
    def n(self) -> int:
        return len(self.observations)

    @property
    def pass_rate(self) -> float:
        return (sum(self.observations) / self.n) if self.n else 0.0

    @property
    def stdev(self) -> float:
        # stdev of the 0/1 outcomes across runs -- the run-to-run variance
        if self.n < 2:
            return 0.0
        return statistics.stdev(1.0 if o else 0.0 for o in self.observations)

    @property
    def stable_pass(self) -> bool:
        return self.n > 0 and all(self.observations)

    def failing_details(self) -> list[str]:
        return [d for o, d in zip(self.observations, self.details) if not o]


@dataclass
class StageAggregate:
    """A (case, stage) aggregated over N runs."""

    case_id: str
    stage: Stage
    tier: Tier
    runs: int
    errored_runs: int = 0
    error_samples: list[str] = field(default_factory=list)
    checks: dict[str, CheckAggregate] = field(default_factory=dict)

    def observe(self, check_name: str, passed: bool, detail: str) -> None:
        agg = self.checks.setdefault(check_name, CheckAggregate(check_name))
        agg.observations.append(passed)
        agg.details.append(detail)

    @property
    def ran(self) -> bool:
        return self.runs > 0

    @property
    def mean_pass_rate(self) -> float:
        """Mean over checks of their pass rates -- the stage's headline score."""
        if not self.checks:
            return 0.0
        return statistics.mean(c.pass_rate for c in self.checks.values())

    @property
    def all_stable(self) -> bool:
        return bool(self.checks) and all(c.stable_pass for c in self.checks.values())


@dataclass
class AggregateReport:
    stages: list[StageAggregate] = field(default_factory=list)
    # per-(case,stage) latency + usage samples, filled by instrumentation (Gap 3)
    timings_ms: dict[str, list[float]] = field(default_factory=dict)
    usages: dict[str, list[Usage]] = field(default_factory=dict)

    def add(self, s: StageAggregate) -> None:
        self.stages.append(s)

    def stage_scores(self) -> dict[str, float]:
        """Averaged pass-rate per stage name across all its cases -- the
        baseline unit (Gap 2). Deterministic + stochastic both included,
        except EXECUTE (see SCORED_STAGES); keyed 'stage' -> mean pass rate.
        """
        by_stage: dict[str, list[float]] = {}
        for s in self.stages:
            if not s.ran or s.stage not in SCORED_STAGES:
                continue
            by_stage.setdefault(s.stage.value, []).append(s.mean_pass_rate)
        return {k: statistics.mean(v) for k, v in by_stage.items() if v}
