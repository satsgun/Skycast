"""SkyCast evaluation harness -- CLI entry point.

Tiers:
  deterministic  plan + execute, exact/structural, no LLM       ALWAYS, N=1
  stochastic     decompose + synthesize, real LLM, N-run variance --live
  judge          LLM-as-judge over synthesized prose             --judge
  end-to-end     whole run_query terminal-event assertion        --e2e

Variance (Gap 1): stochastic stages run N times (--runs, default 5);
results reported as pass-rate +/- stdev.
Baseline/regression (Gap 2): --save-baseline writes per-stage scores;
--baseline diffs a fresh run against it, flagging drops beyond a
threshold set above measured variance.
Cost/latency (Gap 3): captured per stochastic run, reported per stage.

Usage:
  python -m eval.run_eval                                  # deterministic only
  python -m eval.run_eval --live                           # + N-run stochastic
  python -m eval.run_eval --live --runs 5 --judge --e2e    # full eval
  python -m eval.run_eval --live --save-baseline eval/baseline.json
  python -m eval.run_eval --live --baseline eval/baseline.json   # regression check

Vendor/model/key from env: LLM_VENDOR (anthropic|openai|gemini),
the vendor's *_API_KEY, optional LLM_MODEL.
"""

from __future__ import annotations

import argparse
import os
import sys

from eval.cases.dataset import DATASET
from eval.harness.aggregate import AggregateReport
from eval.harness.nrun import run_deterministic_aggregated, run_stochastic_aggregated
from eval.harness.report import print_variance, print_cost, print_regressions
from eval.harness.baseline import save_baseline, load_baseline, diff_against_baseline


def _build_llm():
    vendor = os.environ.get("LLM_VENDOR", "anthropic").lower()
    try:
        if vendor == "anthropic":
            # Anthropic SDK reads ANTHROPIC_API_KEY from env itself.
            if not os.environ.get("ANTHROPIC_API_KEY"):
                return None
            from skycast.llm.anthropic_client import AnthropicLLMClient
            return AnthropicLLMClient(model=os.environ.get("LLM_MODEL", "claude-sonnet-4-5"))
        if vendor == "openai":
            key = os.environ.get("OPENAI_API_KEY")
            if not key:
                return None
            from skycast.llm.openai_client import OpenAILLMClient
            # OpenAI client takes the key explicitly (keyword-only).
            return OpenAILLMClient(model=os.environ.get("LLM_MODEL", "gpt-4o"), api_key=key)
        if vendor == "gemini":
            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                return None
            from skycast.llm.gemini_client import GeminiLLMClient
            # Gemini client takes the key explicitly (keyword-only).
            return GeminiLLMClient(
                model=os.environ.get("LLM_MODEL", "gemini-2.0-flash"), api_key=key
            )
    except Exception as e:
        print(f"  ! could not construct {vendor} client: {e}", file=sys.stderr)
        return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="SkyCast evaluation harness")
    ap.add_argument("--live", action="store_true", help="run stochastic tiers (needs API key)")
    ap.add_argument("--runs", type=int, default=5, help="N runs per stochastic case (variance)")
    ap.add_argument("--judge", action="store_true", help="LLM-as-judge on prose (implies --live)")
    ap.add_argument("--e2e", action="store_true", help="end-to-end terminal-event checks")
    ap.add_argument("--save-baseline", metavar="PATH", help="write per-stage scores as baseline")
    ap.add_argument("--baseline", metavar="PATH", help="diff this run against a saved baseline")
    args = ap.parse_args()

    report = AggregateReport()
    run_deterministic_aggregated(DATASET, report)

    want_live = args.live or args.judge or args.e2e
    llm = _build_llm() if want_live else None
    if want_live and llm is None:
        print("  ! --live requested but no LLM configured (set LLM_VENDOR + API key). "
              "Stochastic tiers skipped.", file=sys.stderr)
    if llm is not None:
        run_stochastic_aggregated(
            DATASET, report, llm, n=args.runs, judge_enabled=args.judge, e2e=args.e2e
        )

    print_variance(report)
    print_cost(report)

    print("\n=== Stage scores (baseline unit) ===")
    for stage, score in sorted(report.stage_scores().items()):
        print(f"  {stage}: {score:.3f}")

    exit_code = 0
    if args.save_baseline:
        save_baseline(report, args.save_baseline)
        print(f"\nBaseline written to {args.save_baseline}")
    if args.baseline:
        base = load_baseline(args.baseline)
        if base is None:
            print(f"\n  ! baseline {args.baseline} not found; run --save-baseline first.",
                  file=sys.stderr)
        else:
            regs = diff_against_baseline(report, base)
            flagged = print_regressions(regs)
            if flagged:
                exit_code = 1

    # also fail on any deterministic check that outright failed/errored
    for s in report.stages:
        if s.ran and (s.errored_runs or not s.all_stable) and s.tier.value == "deterministic":
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
