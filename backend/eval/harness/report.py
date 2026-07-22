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
from eval.harness.cost import UNPRICED, QueryCost, cost_of, query_cost
from eval.harness.types import Stage
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


def _per_query_costs(report: AggregateReport) -> list[QueryCost]:
    """Pairs each case's decompose Usage samples with that case's
    synthesize Usage samples by run-index -- nrun.py runs decompose's
    N-loop and synthesize's N-loop separately per case, so run i's
    decompose and run i's synthesize were never the same live query
    execution. This pairing is a cost *proxy*: treat only the mean
    over all returned QueryCosts as a meaningful distributional
    estimate of per-query cost -- no individual pair should be read as
    "this is what query i actually cost." A case with no
    f"{case_id}::synthesize" key at all (its dataset entry has no
    checks_synthesize -- the harness's equivalent of the clarify path)
    contributes queries with synthesize=None, not a missing/unpriced
    entry (Task 24.3).
    """
    decompose_suffix = f"::{Stage.DECOMPOSE.value}"
    case_ids = {
        key[: -len(decompose_suffix)] for key in report.usages if key.endswith(decompose_suffix)
    }
    queries: list[QueryCost] = []
    for case_id in sorted(case_ids):
        decompose_usages = report.usages[f"{case_id}::{Stage.DECOMPOSE.value}"]
        synthesize_usages = report.usages.get(f"{case_id}::{Stage.SYNTHESIZE.value}", [])
        for i, decompose_usage in enumerate(decompose_usages):
            synthesize_usage = synthesize_usages[i] if i < len(synthesize_usages) else None
            queries.append(query_cost(decompose_usage, synthesize_usage))
    return queries


def _print_per_query_costs(report: AggregateReport) -> None:
    queries = _per_query_costs(report)
    if not queries:
        return

    priced = [q for q in queries if not q.unpriced]
    if priced:
        total_costs = [q.total_cost for q in priced]
        print(
            f"  mean per-query cost (run-index paired, n={len(priced)}): "
            f"${statistics.mean(total_costs):.4f}/query"
        )
        decompose_costs = [q.decompose.total_cost for q in priced]
        print(f"    decompose: ${statistics.mean(decompose_costs):.4f}/query")
        synthesize_costs = [q.synthesize.total_cost for q in priced if q.synthesize is not None]
        if synthesize_costs:
            print(f"    synthesize: ${statistics.mean(synthesize_costs):.4f}/query")
        else:
            print("    synthesize: n/a (no query in this run reached synthesize)")

        by_model: dict[str, list[float]] = {}
        for q in priced:
            by_model.setdefault(q.decompose.model, []).append(q.total_cost)
        for model_name in sorted(by_model):
            print(f"    {model_name}: ${statistics.mean(by_model[model_name]):.4f}/query")
    else:
        print("  mean per-query cost (run-index paired): n/a (no priced queries in this run)")

    unpriced_models = sorted(
        {
            line.model
            for q in queries
            for line in (q.decompose, q.synthesize)
            if line is not None and line.unpriced and line.model != UNPRICED
        }
    )
    if unpriced_models:
        print(f"  unpriced models seen: {', '.join(unpriced_models)} (no pricing data)")


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
            priced_cost_lines = [c for c in (cost_of(u) for u in stage_usages) if not c.unpriced]
            if priced_cost_lines:
                line += (
                    f", ${statistics.mean(c.input_cost for c in priced_cost_lines):.4f} input"
                    f" / ${statistics.mean(c.output_cost for c in priced_cost_lines):.4f}"
                    " output cost"
                )
        else:
            line += ", tokens n/a (not exposed by seam)"
        print(line)

    _print_per_query_costs(report)

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

        # Task 23.6: cost_of is the SAME function regardless of whether
        # this run had SKYCAST_DISABLE_CACHE set -- a cache-off run's
        # Usage already has its cache fields zeroed by the client itself
        # (see anthropic/openai/gemini_client.py's cache_enabled
        # handling), so comparing this line across two runs isolates the
        # cache token mix as the only source of the delta, never a
        # difference in how the two runs were priced.
        cost_line = cost_of(total)
        if not cost_line.unpriced:
            print(f"  estimated cost (aggregate across this run): ${cost_line.total_cost:.4f}")

            # Within-run counterfactual (Task 24.4): reprice this run's
            # own cache tokens as if they'd been ordinary input, via the
            # SAME cost_of used above -- the only difference is the
            # Usage fed in (cache fields folded into input_tokens),
            # never the pricing arithmetic itself, so "saved by
            # caching" is genuinely what the price table would have
            # charged for those tokens as normal input.
            if total.cache_read_tokens or total.cache_write_tokens:
                counterfactual_usage = Usage(
                    input_tokens=(
                        total.input_tokens + total.cache_read_tokens + total.cache_write_tokens
                    ),
                    output_tokens=total.output_tokens,
                    model=total.model,
                )
                counterfactual_line = cost_of(counterfactual_usage)
                if not counterfactual_line.unpriced:
                    saved = counterfactual_line.total_cost - cost_line.total_cost
                    print(
                        "  counterfactual uncached cost (same tokens, no caching): "
                        f"${counterfactual_line.total_cost:.4f}"
                    )
                    print(f"  saved by caching (within this run): ${saved:.4f}")
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
