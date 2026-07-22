"""Cost summary artifact (Task 24.5).

A small, committable JSON snapshot of an eval run's measured cost --
"measured cost per query = $X", the same "measured, not assumed"
discipline as baseline.py's --save-baseline artifact (which this
mirrors: build_*(report) -> dict, save_*(report, path) -> None, no
load/diff -- this is a snapshot, not a regression gate). Reuses
report.py's per_query_costs/aggregate_usage rather than recomputing
the same numbers a second way (see eval/harness/cost.py's
feedback-pricing-same-path principle) -- and inherits per_query_costs'
own caveat: the per-query/per-model figures below are distributional
means over a run-index pairing proxy, not traced per-execution costs.

Every field is None/empty (never a fabricated 0) when there's nothing
to report -- e.g. a deterministic-only run captures no Usage at all.
"""

from __future__ import annotations

import json
import statistics

from eval.harness.aggregate import AggregateReport
from eval.harness.cost import UNPRICED
from eval.harness.report import aggregate_usage, per_query_costs


def build_cost_summary(report: AggregateReport) -> dict:
    queries = per_query_costs(report)
    priced = [q for q in queries if not q.unpriced]

    total_usage = aggregate_usage(report)
    token_totals = None
    cache_hit_rate = None
    if total_usage is not None:
        token_totals = {
            "input_tokens": total_usage.input_tokens,
            "output_tokens": total_usage.output_tokens,
            "cache_read_tokens": total_usage.cache_read_tokens,
            "cache_write_tokens": total_usage.cache_write_tokens,
            "total_tokens": total_usage.total_tokens,
        }
        cache_hit_rate = round(total_usage.cache_hit_rate, 4)

    mean_cost_per_query = None
    decompose_split = {"mean_cost_per_query": None, "n": 0}
    synthesize_split = {"mean_cost_per_query": None, "n": 0}
    per_model: dict[str, float] = {}
    if priced:
        mean_cost_per_query = round(statistics.mean(q.total_cost for q in priced), 6)
        decompose_costs = [q.decompose.total_cost for q in priced]
        decompose_split = {
            "mean_cost_per_query": round(statistics.mean(decompose_costs), 6),
            "n": len(decompose_costs),
        }
        synthesize_costs = [q.synthesize.total_cost for q in priced if q.synthesize is not None]
        if synthesize_costs:
            synthesize_split = {
                "mean_cost_per_query": round(statistics.mean(synthesize_costs), 6),
                "n": len(synthesize_costs),
            }
        by_model: dict[str, list[float]] = {}
        for q in priced:
            by_model.setdefault(q.decompose.model, []).append(q.total_cost)
        per_model = {model: round(statistics.mean(costs), 6) for model, costs in by_model.items()}

    unpriced_models = sorted(
        {
            line.model
            for q in queries
            for line in (q.decompose, q.synthesize)
            if line is not None and line.unpriced and line.model != UNPRICED
        }
    )

    return {
        "mean_cost_per_query": mean_cost_per_query,
        "stage_split": {"decompose": decompose_split, "synthesize": synthesize_split},
        "per_model_mean_query_cost": per_model,
        "unpriced_models": unpriced_models,
        "token_totals": token_totals,
        "cache_hit_rate": cache_hit_rate,
    }


def save_cost_summary(report: AggregateReport, path: str) -> None:
    with open(path, "w") as f:
        json.dump(build_cost_summary(report), f, indent=2, sort_keys=True)
