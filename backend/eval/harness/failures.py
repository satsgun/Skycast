"""Failure-detail + cache-activity artifact.

A small, committable JSON snapshot of two things print_variance/
print_cost (eval/harness/report.py) only ever print to the terminal:

  - which checks failed, on which cases, with what detail (every
    failing run's detail, not just the one truncated sample
    print_variance prints) -- so it survives past the terminal session,
    to target a prompt edit at an actual observed failure pattern
    instead of guessing, and to diff two runs' failures against each
    other afterward.
  - per (case, stage) cache activity -- call count, mean full prompt
    size, and cache read/write token totals + hit rate. A 0.00 cache
    hit-rate is NOT necessarily a caching bug: Gemini's implicit caching
    (ai.google.dev/gemini-api/docs/caching, live-verified) only engages
    above a minimum prompt size -- 2,048 tokens for Gemini 2.5 Flash,
    4,096 for Gemini 3.5 Flash -- and this harness's decompose/
    synthesize prompts are typically well under that. mean_prompt_tokens
    is what lets you tell "caching is broken" apart from "this prompt
    never reached the model's floor."

Mirrors baseline.py/cost_summary.py's shape (build_*(report) -> dict,
save_*(report, path) -> None) but, like cost_summary.py, is a snapshot
to read or diff by hand -- not a gated regression check like
baseline.py's --baseline diff.
"""

from __future__ import annotations

import json
import statistics

from eval.harness.aggregate import AggregateReport
from skycast.llm.usage import Usage


def _cache_stats(usages: list[Usage]) -> dict:
    total = usages[0]
    for u in usages[1:]:
        total = total + u
    return {
        "calls": len(usages),
        "mean_prompt_tokens": round(
            statistics.mean(
                u.input_tokens + u.cache_read_tokens + u.cache_write_tokens for u in usages
            ),
            1,
        ),
        "cache_read_tokens_total": total.cache_read_tokens,
        "cache_write_tokens_total": total.cache_write_tokens,
        "cache_hit_rate": round(total.cache_hit_rate, 4),
    }


def build_failure_report(report: AggregateReport) -> dict:
    stages = []
    for s in report.stages:
        if not s.ran:
            continue
        failing_checks = {
            name: {
                "pass_rate": round(c.pass_rate, 4),
                "stdev": round(c.stdev, 4),
                "failing_details": c.failing_details(),
            }
            for name, c in s.checks.items()
            if not c.stable_pass
        }
        if not failing_checks and not s.errored_runs:
            continue
        stages.append(
            {
                "case_id": s.case_id,
                "stage": s.stage.value,
                "tier": s.tier.value,
                "runs": s.runs,
                "errored_runs": s.errored_runs,
                "error_samples": list(s.error_samples),
                "failing_checks": failing_checks,
            }
        )

    caching = None
    if report.usages:
        caching = {
            "overall": _cache_stats([u for usages in report.usages.values() for u in usages]),
            "by_case_stage": {
                key: _cache_stats(usages) for key, usages in sorted(report.usages.items())
            },
        }

    return {"stages": stages, "caching": caching}


def save_failure_report(report: AggregateReport, path: str) -> None:
    with open(path, "w") as f:
        json.dump(build_failure_report(report), f, indent=2, sort_keys=True)
