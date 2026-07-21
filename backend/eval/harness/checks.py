"""Reusable property checks.

Generic, composable assertions shared across cases. Case-specific checks
(e.g. "window is Tokyo-local evening") live inline in the dataset; these
are the common ones. Each returns a Check whose predicate yields
(passed, human-readable detail).
"""

from __future__ import annotations

import re

from eval.harness.types import Check

# ----- decompose (DataNeedsSpec) property checks -----


def spec_intent_is(expected: str) -> Check:
    def p(spec):
        actual = getattr(spec.intent, "value", str(spec.intent))
        return actual == expected, f"intent={actual} expected={expected}"
    return Check(f"intent=={expected}", p)


def spec_location_count(n: int) -> Check:
    def p(spec):
        c = len(spec.location_names)
        return c == n, f"location_names count={c} expected={n}"
    return Check(f"location_count=={n}", p)


def spec_locations_exact(expected_names: list[str], *, case_insensitive: bool = True) -> Check:
    """Exact/set-match location check (sketch: "location extraction
    accuracy"), catching a wrong city, an extra city, or a missing one
    -- spec_location_count's blind spot (right count, wrong city still
    passes). Unordered set equality: order rarely carries meaning for a
    single location or an unordered comparison. Case-insensitive by
    default so "Paris" vs "paris" isn't a spurious fail; additive to
    spec_location_count, not a replacement (that one stays useful for
    cases with no name to pin, e.g. the default-location case).
    """
    def _key(name: str) -> str:
        name = name.strip()
        return name.lower() if case_insensitive else name

    expected_keys = {_key(n) for n in expected_names}

    def p(spec):
        extracted = list(spec.location_names)
        extracted_keys = {_key(n) for n in extracted}
        wrong_or_extra = extracted_keys - expected_keys
        missing = expected_keys - extracted_keys
        ok = not wrong_or_extra and not missing
        return ok, (
            f"extracted={extracted} expected={expected_names} "
            f"wrong/extra={sorted(wrong_or_extra)} missing={sorted(missing)}"
        )
    return Check(f"locations_exact{expected_names}", p)


def spec_names_default_location() -> Check:
    def p(spec):
        return spec.use_default_location, (
            f"use_default_location={spec.use_default_location} "
            f"(location_names={spec.location_names})"
        )
    return Check("uses_default_location", p)


def spec_has_variable(var: str) -> Check:
    def p(spec):
        vals = {getattr(v, "value", str(v)) for v in spec.variables}
        return var in vals, f"variables={sorted(vals)} want {var}"
    return Check(f"has_variable[{var}]", p)


def spec_variables_prf(
    expected: set[str], *, min_precision: float = 1.0, min_recall: float = 1.0
) -> Check:
    """Set precision/recall check (sketch: "variables as set precision/
    recall"), closing spec_has_variable's blind spot: one expected
    variable present passes even with extra unwanted ones (over-
    requesting) or other expected variables missing (under-requesting).
    precision = |extracted & expected| / |extracted| penalizes over-
    requesting; recall = |extracted & expected| / |expected| penalizes
    under-requesting. Default 1.0/1.0 is exact set match; relax either
    threshold to let a case tolerate e.g. a harmless extra variable.
    DataNeedsSpec.variables is never empty (Field(min_length=1)), so the
    zero-denominator case below is defensive, not a real path.
    """
    def p(spec):
        extracted = {getattr(v, "value", str(v)) for v in spec.variables}
        intersection = extracted & expected
        precision = (len(intersection) / len(extracted)) if extracted else 0.0
        recall = (len(intersection) / len(expected)) if expected else 0.0
        ok = precision >= min_precision and recall >= min_recall
        extra = sorted(extracted - expected)
        missing = sorted(expected - extracted)
        return ok, (
            f"precision={precision:.2f} (want >={min_precision:.2f}) "
            f"recall={recall:.2f} (want >={min_recall:.2f}) "
            f"extra={extra} missing={missing}"
        )
    return Check(f"variables_prf{sorted(expected)}", p)


def spec_has_granularity(g: str) -> Check:
    def p(spec):
        vals = {getattr(x, "value", str(x)) for x in spec.granularities}
        return g in vals, f"granularities={sorted(vals)} want {g}"
    return Check(f"has_granularity[{g}]", p)


def spec_time_kind_is(expected: str) -> Check:
    """Exact-match check on the descriptor's kind (post-Task 21): decompose
    emits a RelativeTimeSpec now, not absolute timestamps, so there's no
    window left to tolerance-score -- it either named the right kind or
    it didn't.
    """
    def p(spec):
        t = getattr(spec, "time", None)
        if t is None:
            return False, "no time on spec"
        actual = getattr(t.kind, "value", str(t.kind))
        return actual == expected, f"time.kind={actual} expected={expected}"
    return Check(f"time_kind=={expected}", p)


# ----- synthesize (AnswerPayload) property checks -----


def answer_nonempty() -> Check:
    def p(ans):
        t = (ans.text or "").strip()
        return len(t) > 0, f"text length={len(t)}"
    return Check("answer_nonempty", p)


def answer_leads_with_conclusion() -> Check:
    """Answer-first: the first sentence should read as a conclusion, not
    a hedge or a restatement of the question. Heuristic property floor --
    the LLM-judge tier assesses this more deeply.
    """
    def p(ans):
        t = (ans.text or "").strip()
        if not t:
            return False, "empty"
        first = re.split(r"(?<=[.!?])\s", t, maxsplit=1)[0]
        # a conclusion tends to be a short declarative opener, not a
        # question and not prefixed with a hedge
        hedges = ("it depends", "i'm not sure", "there are many", "weather is")
        low = first.lower()
        is_question = first.strip().endswith("?")
        hedged = any(low.startswith(h) for h in hedges)
        ok = not is_question and not hedged and len(first) <= 200
        return ok, f"first sentence={first!r}"
    return Check("leads_with_conclusion", p)


def answer_mentions_any(*substrings: str) -> Check:
    def p(ans):
        t = (ans.text or "").lower()
        hit = [s for s in substrings if s.lower() in t]
        return bool(hit), f"matched={hit} of {list(substrings)}"
    return Check(f"mentions_any{list(substrings)}", p)


def answer_highlight_valid_or_none() -> Check:
    """Highlight, if present, must point at a real forecast + reading --
    the 'degrade to None, never crash' contract from synthesize.
    """
    def p(ans):
        card = ans.card
        hl = card.highlight
        if hl is None:
            return True, "highlight=None (valid)"
        fi = hl.forecast_index
        if not (0 <= fi < len(card.forecasts)):
            return False, f"forecast_index={fi} out of range({len(card.forecasts)})"
        return True, f"highlight -> forecast[{fi}]"
    return Check("highlight_valid_or_none", p)


def answer_card_forecast_count(n: int) -> Check:
    def p(ans):
        c = len(ans.card.forecasts)
        return c == n, f"card.forecasts={c} expected={n}"
    return Check(f"card_forecast_count=={n}", p)
