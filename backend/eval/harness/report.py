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
from eval.harness.pricing import compute_cost
from skycast.llm.usage import Usage


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
    # aggregate latency + usage by stage name
    by_stage_lat: dict[str, list[float]] = {}
    by_stage_usage: dict[str, list[Usage]] = {}
    for key, samples in report.timings_ms.items():
        stage = key.split("::")[1]
        by_stage_lat.setdefault(stage, []).extend(samples)
    for key, samples in report.usages.items():
        stage = key.split("::")[1]
        by_stage_usage.setdefault(stage, []).extend(samples)

    all_usages: list[Usage] = []
    for stage in sorted(by_stage_lat):
        lat = by_stage_lat[stage]
        mean_ms = statistics.mean(lat) if lat else 0.0
        line = f"  {stage}: {mean_ms:.0f} ms/call-group (n={len(lat)})"
        stage_usages = by_stage_usage.get(stage)
        if stage_usages:
            all_usages.extend(stage_usages)
            line += (
                f", {statistics.mean(u.input_tokens for u in stage_usages):.0f} input"
                f" / {statistics.mean(u.output_tokens for u in stage_usages):.0f} output"
                f" / {statistics.mean(u.cache_read_tokens for u in stage_usages):.0f} cache-read"
                f" / {statistics.mean(u.cache_write_tokens for u in stage_usages):.0f} cache-write"
                " tokens"
            )
        else:
            line += ", tokens n/a (not exposed by seam)"
        print(line)

    if all_usages:
        total = all_usages[0]
        for u in all_usages[1:]:
            total = total + u
        # cache_hit_rate is exact for all three vendors as of Task 23.7,
        # which normalized OpenAI/Gemini's clients to report input_tokens
        # as the uncached remainder (matching Anthropic's already-
        # exclusive convention) -- prior to that fix, this understated
        # the true rate for OpenAI/Gemini specifically.
        print(f"  cache hit-rate (aggregate across this run): {total.cache_hit_rate:.2f}")

        # Task 23.6: compute_cost is the SAME function regardless of
        # whether this run had SKYCAST_DISABLE_CACHE set -- a cache-off
        # run's Usage already has its cache fields zeroed by the client
        # itself (see anthropic/openai/gemini_client.py's cache_enabled
        # handling), so comparing this line across two runs isolates the
        # cache token mix as the only source of the delta, never a
        # difference in how the two runs were priced.
        cost = compute_cost(total)
        if cost is not None:
            print(f"  estimated cost (aggregate across this run): ${cost:.4f}")
        else:
            print(f"  cost n/a (no pricing data for model {total.model!r})")

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
