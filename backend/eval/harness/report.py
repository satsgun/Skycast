"""Reporting (Gaps 1, 2, 3 output).

Renders the AggregateReport as:
  - per-stage variance table (pass rate ± stdev over N runs)
  - cost/latency note (mean latency per stage, tokens if available)
  - regression diff vs. a committed baseline, when provided
"""

from __future__ import annotations

import statistics

from eval.harness.aggregate import AggregateReport
from eval.harness.baseline import Regression


def print_variance(report: AggregateReport) -> None:
    print("\n=== Per-stage results (pass rate ± stdev over N runs) ===")
    for s in report.stages:
        if not s.ran:
            continue
        n = max((c.n for c in s.checks.values()), default=0)
        head = (f"{s.case_id} :: {s.stage.value}  "
                f"[{s.tier.value}, N={n}, mean={s.mean_pass_rate:.2f}]")
        if s.errored_runs:
            head += f"  ERRORS={s.errored_runs}"
        print(head)
        for name, c in s.checks.items():
            flag = " " if c.stable_pass else "!"
            line = f"  {flag} {name}: {c.pass_rate:.2f} ± {c.stdev:.2f}"
            if not c.stable_pass:
                sample = next(iter(c.failing_details()), "")
                line += f"   (e.g. {sample})"
            print(line)
        for e in s.error_samples:
            print(f"    !! {e}")


def print_cost(report: AggregateReport) -> None:
    if not report.timings_ms:
        return
    print("\n=== Cost / latency (per stage, mean over runs) ===")
    # aggregate latency by stage name
    by_stage_lat: dict[str, list[float]] = {}
    by_stage_tok: dict[str, list[int]] = {}
    for key, samples in report.timings_ms.items():
        stage = key.split("::")[1]
        by_stage_lat.setdefault(stage, []).extend(samples)
    for key, samples in report.tokens.items():
        stage = key.split("::")[1]
        by_stage_tok.setdefault(stage, []).extend(samples)

    for stage in sorted(by_stage_lat):
        lat = by_stage_lat[stage]
        mean_ms = statistics.mean(lat) if lat else 0.0
        line = f"  {stage}: {mean_ms:.0f} ms/call-group (n={len(lat)})"
        if stage in by_stage_tok and by_stage_tok[stage]:
            line += f", {statistics.mean(by_stage_tok[stage]):.0f} tokens"
        else:
            line += ", tokens n/a (not exposed by seam)"
        print(line)

    # ADR-0001 evidence: decompose + plan are the two-call split; if plan
    # is deterministic (no latency captured), note the LLM-call cost is the
    # decompose+synthesize pair.
    print("  (ADR-0001 note: decompose and synthesize are the real LLM "
          "round-trips; plan is deterministic, so its LLM cost is zero.)")


def print_regressions(regs: list[Regression]) -> int:
    if not regs:
        return 0
    print("\n=== Regression vs. baseline ===")
    flagged = 0
    for r in regs:
        arrow = "DOWN" if r.drop > 0 else "up  "
        mark = "  REGRESSION" if r.flagged else ""
        if r.flagged:
            flagged += 1
        print(f"  {r.stage}: {r.baseline:.2f} -> {r.current:.2f} "
              f"({arrow} {abs(r.drop):.2f}, threshold {r.threshold:.2f}){mark}")
    return flagged
