"""Baseline + regression diffing (Gap 2).

The point of the whole exercise (per the sketch, "the capability ADR-0001
exists to enable"): commit a baseline of per-stage scores, re-run on any
prompt/model change, diff, and flag per-stage drops beyond a threshold.
Because scores are per-stage, a regression localizes -- a Stage-1
variable-recall drop points straight at the decompose prompt.

Threshold guidance: set it ABOVE the measured run-to-run variance so
ordinary model noise doesn't trip it. We record each stage's observed
stdev in the baseline so the diff can compare a drop against that stage's
own noise floor.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass

from eval.harness.aggregate import AggregateReport


def build_baseline(report: AggregateReport) -> dict:
    """Serialize per-stage scores + observed variance to a baseline dict."""
    per_stage: dict[str, dict] = {}
    # group case-level aggregates by stage
    by_stage: dict[str, list] = {}
    for s in report.stages:
        if not s.ran:
            continue
        by_stage.setdefault(s.stage.value, []).append(s)

    for stage, aggs in by_stage.items():
        rates = [a.mean_pass_rate for a in aggs]
        # per-check stdev averaged across cases = this stage's noise floor
        stdevs = [c.stdev for a in aggs for c in a.checks.values()]
        per_stage[stage] = {
            "mean_pass_rate": round(statistics.mean(rates), 4),
            "cases": len(aggs),
            "noise_floor_stdev": round(statistics.mean(stdevs), 4) if stdevs else 0.0,
        }
    return {"stages": per_stage}


def save_baseline(report: AggregateReport, path: str) -> None:
    with open(path, "w") as f:
        json.dump(build_baseline(report), f, indent=2, sort_keys=True)


def load_baseline(path: str) -> dict | None:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


@dataclass
class Regression:
    stage: str
    baseline: float
    current: float
    drop: float
    threshold: float
    flagged: bool


def diff_against_baseline(
    report: AggregateReport, baseline: dict, *, min_threshold: float = 0.05
) -> list[Regression]:
    """Compare current per-stage scores to baseline. A stage is flagged
    when its score drops by more than max(min_threshold, 2*noise_floor) --
    i.e. the threshold sits above that stage's own measured variance.
    """
    current = build_baseline(report)["stages"]
    base_stages = baseline.get("stages", {})
    out: list[Regression] = []
    for stage, cur in current.items():
        if stage not in base_stages:
            continue
        b = base_stages[stage]
        base_rate = b["mean_pass_rate"]
        cur_rate = cur["mean_pass_rate"]
        noise = b.get("noise_floor_stdev", 0.0)
        threshold = max(min_threshold, 2.0 * noise)
        drop = base_rate - cur_rate
        out.append(
            Regression(
                stage=stage,
                baseline=base_rate,
                current=cur_rate,
                drop=round(drop, 4),
                threshold=round(threshold, 4),
                flagged=drop > threshold,
            )
        )
    return out
