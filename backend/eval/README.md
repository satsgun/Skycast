# SkyCast Evaluation Harness

Evaluates the agent's correctness by importing the **real pipeline stages
directly** — no deployment. Weather is always `InMemoryProvider` (fixed →
assertable); the LLM is real only for the stochastic tiers, gated by key.

Conforms to the wiki sketch [Skycast — Minimum Evaluation Harness](https://github.com/satsgun/Skycast/wiki/Skycast-%E2%80%94-Minimum-Evaluation-Harness-(Sketch)): per-stage
scoring, real-model/mocked-provider split, N-run variance, baseline regression
detection, and cost/latency instrumentation.

## Tiers

| Tier | Stages | LLM | Runs | Scoring | When |
|---|---|---|---|---|---|
| Deterministic | plan, execute | no | 1 | exact / structural | every run (offline) |
| Stochastic | decompose, synthesize | yes | **N** | property floor + variance | `--live` |
| Judge | synthesize prose | yes | N | LLM-as-judge rubric | `--judge` |
| End-to-end | run_query | yes | N | terminal-event | `--e2e` |

Deterministic stages run once (InMemoryProvider makes them deterministic —
the sketch exempts them). Stochastic stages run **N times** (default 5) and
report `pass_rate ± stdev`, because a single run of a probabilistic system is
noise, not a score.

## Running

```bash
# deterministic only — offline, free, CI on every push
python -m eval.run_eval

# + N-run stochastic (needs API key), full eval
python -m eval.run_eval --live --runs 5 --judge --e2e

# build a baseline, then regression-check later runs -- name it after the
# model that produced it (see "Baseline workflow" below for the full loop)
python -m eval.run_eval --live --save-baseline eval/baseline-<model>.json
python -m eval.run_eval --live --baseline eval/baseline-<model>.json

# write a committable cost-summary artifact (mean $/query, cache hit-rate, ...)
python -m eval.run_eval --live --save-cost-summary eval/cost_summary.json

# write which checks failed on which cases, + per-stage cache activity
python -m eval.run_eval --live --save-failures eval/failures.json
```

### One command for the real eval

```bash
LLM_VENDOR=anthropic ANTHROPIC_API_KEY=sk-... \
  python -m eval.run_eval --live --runs 5 --judge --e2e \
  --baseline eval/baseline-claude-sonnet-4-5.json
```

Vendor-swappable via the `LLMClient` seam: `LLM_VENDOR=openai|gemini` + that
vendor's `*_API_KEY`, optional `LLM_MODEL`.

### A/B cache validation

Set `SKYCAST_DISABLE_CACHE` (any non-empty value) to run with prompt
caching off, then diff the printed cost note against a normal `--live`
run for the cache-on vs. cache-off delta:

```bash
python -m eval.run_eval --live                       # cache on (default)
SKYCAST_DISABLE_CACHE=1 python -m eval.run_eval --live  # cache off
```

## Baseline workflow: establish, change, compare

The full loop for "edit a prompt, find out if it actually helped":

1. **Establish the baseline**, labeled by model (never a bare
   `baseline.json` -- a diff against an unlabeled or differently-labeled
   baseline can't tell "the prompt regressed" apart from "this is just a
   different model," see the `"model"` field on `build_baseline`'s
   output):
   ```bash
   LLM_VENDOR=gemini GEMINI_API_KEY=... LLM_MODEL=gemini-3.5-flash \
     python -m eval.run_eval --live --runs 5 \
     --save-baseline eval/baseline-gemini-3.5-flash.json \
     --save-failures eval/failures-gemini-3.5-flash-before.json
   ```
   `--save-baseline` records each stage's pass rate + noise floor (the
   regression-detection threshold). `--save-failures` records which
   checks failed on which cases, and cache-activity stats -- the detail
   that tells you *what* to edit, not just that something's imperfect.

2. **Make the change** -- edit the decompose/synthesize prompt (or
   whatever's under test).

3. **Re-run the same way** (same model, same env) and diff against the
   baseline:
   ```bash
   python -m eval.run_eval --live --runs 5 \
     --baseline eval/baseline-gemini-3.5-flash.json \
     --save-failures eval/failures-gemini-3.5-flash-after.json
   ```
   Prints a `=== Regression vs. baseline ===` table and exits 1 if any
   stage dropped by more than its noise floor allows (see the Gap 2
   bullet below for the threshold math). This only catches *regressions*
   above noise -- it won't tell you a change helped, just that it didn't
   measurably hurt.

4. **Diff the two `--save-failures` files** to see exactly which checks
   flipped:
   ```bash
   diff eval/failures-gemini-3.5-flash-before.json eval/failures-gemini-3.5-flash-after.json
   ```
   A check that disappears from `after` (and was in `before`) passed for
   the first time since the edit; a check newly present in `after`
   regressed. This is the concrete, diffable answer to "which checks
   fail on which cases" -- no more comparing two terminal scrollbacks by
   eye.

5. **Once satisfied it's an improvement, overwrite the baseline** with
   the new run's `--save-baseline` output. Regression-diffing always
   compares against whatever's currently saved on disk, so updating it
   is a deliberate step, not automatic.

## What each gap-closure does

- **Variance (Gap 1):** N runs per stochastic case → `mean ± stdev`. A stage's
  score is the mean of its checks' pass rates. Unstable checks are marked `!`.
- **Baseline / regression (Gap 2):** `--save-baseline` writes per-stage scores +
  each stage's observed noise floor (stdev). `--baseline` diffs a run and flags
  any stage whose score drops beyond `max(0.05, 2×noise_floor)` — the threshold
  sits above the stage's own measured variance, so noise doesn't trip it.
  Regressions **localize** to a stage (a decompose drop points at the decompose
  prompt, not the planner). Exit code 1 on a flagged regression → CI gate.
- **Cost / latency (Gap 3):** per-stage wall-clock + mean input/output/
  cache-read/cache-write tokens (where the client exposes `last_usage`)
  captured on runs that happen anyway. Empirically validates ADR-0001's
  two-call cost (plan is deterministic → zero LLM cost). Also reports an
  aggregate cache hit-rate and an estimated dollar cost — the same
  pricing path regardless of `SKYCAST_DISABLE_CACHE`, so the two runs'
  costs are directly comparable (see "A/B cache validation" above) —
  plus a within-run counterfactual ("what would this have cost
  uncached") so a caching saving is visible from a single run.

  A 0.00 cache hit-rate is not automatically a caching bug: implicit
  caching only engages above a minimum prompt size (live-verified against
  ai.google.dev/gemini-api/docs/caching: **2,048 tokens for Gemini 2.5
  Flash, 4,096 for Gemini 3.5 Flash**), and this harness's decompose/
  synthesize prompts are typically well under that. `--save-failures`
  (below) records each stage's mean full-prompt token size next to its
  cache stats, so you can tell "never reached the model's floor" apart
  from "actually broken."
- **Failure + cache detail:** `--save-failures` writes which checks
  failed on which cases -- every failing run's detail, not just the one
  sample the terminal prints -- plus, per (case, stage), call count,
  mean prompt tokens, and cache read/write totals + hit rate
  (`harness/failures.py`). A snapshot like `--save-cost-summary`, not a
  gated regression check like `--baseline`; meant to be diffed by hand
  or `diff`'d between a before/after run (see "Baseline workflow" above).
- **Unit economics (Task 24):** `harness/pricing.py`'s `MODEL_PRICES` are
  rates verified against each vendor's live pricing page (never
  guessed), looked up via `get_price()`. `harness/cost.py`'s `cost_of`/
  `query_cost` turn a stage's `Usage` (and a whole query's
  decompose+synthesize pair) into a structured cost, distinguishing
  "unpriced" (no rate found) from a real $0. The cost note adds a
  per-query section — mean $/query with the decompose/synthesize split,
  a per-model $/query breakdown (the number that would inform model
  routing), and any untabled model named explicitly — built by pairing
  each case's decompose/synthesize `Usage` samples **by run-index**
  (nrun.py runs their N-sample loops separately per case, so this is a
  distributional proxy: only the *mean* over paired queries is
  meaningful, never an individual pair). `--save-cost-summary` writes
  the same numbers as a committable JSON snapshot (`harness/
  cost_summary.py`), mirroring `--save-baseline`'s "measured, not
  assumed" discipline.
- **Dataset (Gap 4):** 23 cases across the taxonomy — simple conditions,
  decision/umbrella, multi-day outlook, comparison fan-out, no-location→default,
  ambiguous→clarify, not-found, skip-geocode, time-window stress, and
  codegen-fallback routing. Decompose-tier expectations
  (`spec_locations_exact`/`spec_variables_exact`/`spec_variables_prf`) are
  authored independently from each case's `canned_spec` — never derived
  from it — so a check can't trivially pass by comparing the model's
  output to a spec built from the same source (see `dataset.py`'s module
  docstring).

## Notes on live behavior

One case is *designed* to surface a real gap rather than pass trivially:
- `codegen_fallback_routing` checks the agent routes a computed query correctly
  or refuses honestly, rather than fabricating.

`time_window_this_evening` used to be a second such case — it
tolerance-scored "this evening" against 17:00–21:00 ±1h and failed by
design until relative-time-after-geocode (Task 21, ADR-0006) landed.
That's done now: decompose emits a `RelativeTimeSpec` descriptor instead
of computing hours itself, so the check is an exact kind match
(`spec_time_kind_is("THIS_EVENING")`), not a tolerance score, and the
case passes like any other.

## Layout

```
eval/
  run_eval.py            CLI: tier gating, N-run, baseline, cost, env→LLMClient
  baseline-<model>.json  committed baseline, one file per model (after --save-baseline)
  cases/dataset.py       23-case dataset (taxonomy + canned specs + checks)
  harness/
    types.py             EvalCase, Check, single-run Report
    aggregate.py         N-run aggregation: CheckAggregate, StageAggregate
    checks.py            reusable property assertions (+ window tolerance)
    deterministic.py     plan + execute runners (real code + InMemoryProvider)
    stochastic.py        decompose + synthesize + end-to-end runners
    nrun.py              N-run driver + timing capture
    instrument.py        InstrumentedLLMClient (latency/usage capture)
    judge.py             LLM-as-judge via the LLMClient seam
    baseline.py          baseline save + regression diff
    pricing.py           live-verified per-model $/token rates + get_price()
    cost.py              cost_of/QueryCostLine, query_cost/QueryCost
    cost_summary.py      cost-summary JSON artifact (mirrors baseline.py)
    failures.py          failing-check + cache-activity JSON artifact
    report.py            variance table, cost note, regression output
```
