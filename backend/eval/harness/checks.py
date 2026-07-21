"""Reusable property checks.

Generic, composable assertions shared across cases. Case-specific checks
(e.g. "window is Tokyo-local evening") live inline in the dataset; these
are the common ones. Each returns a Check whose predicate yields
(passed, human-readable detail).
"""

from __future__ import annotations

import re

from skycast.domain.forecast import Forecast

from eval.harness.grounding import derive_facts
from eval.harness.types import Check

# ----- decompose (DataNeedsSpec) property checks -----
#
# Guard against circularity (Task E1.5): every `expected`/`expected_names`
# argument these checks take must be independently authored ground truth
# for what the model should extract from the query text, never read off
# the same case's `canned_spec` (which exists only to drive the
# deterministic plan/execute tiers) -- see eval/cases/dataset.py's module
# docstring for the full rationale.


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


def spec_variables_exact(expected: set[str]) -> Check:
    """Thin convenience wrapper over spec_variables_prf's exact-match
    default, for dataset readability where the exact-set case is the
    intent, not a deliberately relaxed threshold.
    """
    return spec_variables_prf(expected, min_precision=1.0, min_recall=1.0)


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


# ----- synthesize grounding checks (Task E4.2) -----
#
# Contradiction, not omission (the crux that keeps these from
# over-firing): an answer that's silent on a dimension always passes --
# only an answer that actively contradicts the fixture fails. Coarse
# property floor by design (same style as answer_leads_with_conclusion
# above); the LLM-judge tier (Task E4.3) reads subtler phrasing.
#
# Term lists are editorial ground truth (named + documented, same
# framing as grounding.py's thresholds), scoped to the sketch's own
# examples plus close variants -- not an attempt to catch every possible
# phrasing. Each check stays independently scoped to its own named
# dimension (e.g. "sunny" belongs to _CONDITION_WORDS, not the rain
# check, even though a sunny day implies no rain).

_RAIN_AFFIRMATIVE_TERMS = (
    "bring an umbrella", "bring your umbrella", "grab an umbrella", "take an umbrella",
    "rain likely", "rain is likely", "expect rain",
    "rain", "raining", "rainy", "rains",
    "umbrella", "wet", "shower", "showers", "drizzle", "drizzling",
    "downpour", "storm", "thunderstorm",
)
_RAIN_NEGATIVE_TERMS = (
    "no rain", "won't rain", "wont rain", "will not rain",
    "not going to rain", "isn't going to rain",
    "no need for an umbrella", "won't need an umbrella", "skip the umbrella",
    "leave the umbrella", "don't bring an umbrella", "no umbrella needed",
    "dry",
)
_TEMPERATURE_BAND_WORDS: dict[str, str] = {
    "freezing": "cold", "frigid": "cold", "cold": "cold", "chilly": "cold", "cool": "cold",
    "mild": "mild", "pleasant": "mild", "comfortable": "mild", "temperate": "mild",
    "warm": "warm", "balmy": "warm",
    "hot": "hot", "scorching": "hot", "sweltering": "hot", "boiling": "hot",
}
_CONDITION_WORDS: dict[str, str] = {
    "sunny": "clear", "clear": "clear", "bright": "clear",
    "cloudy": "cloud", "overcast": "cloud", "grey": "cloud", "gray": "cloud",
    "foggy": "cloud", "misty": "cloud",
    "rain": "rain", "raining": "rain", "rainy": "rain", "drizzle": "rain",
    "drizzling": "rain", "showers": "rain",
    "snow": "snow", "snowy": "snow", "snowing": "snow",
    "storm": "storm", "stormy": "storm", "thunderstorm": "storm", "thundery": "storm",
}


def _contains_word(text: str, phrase: str) -> bool:
    """Whole word/phrase match via regex boundaries -- not naive
    substring presence (so e.g. "rain" doesn't spuriously match inside
    an unrelated longer word); a multi-word phrase requires its words
    adjacent, in order.
    """
    pattern = r"\b" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"\b"
    return re.search(pattern, text.lower()) is not None


def _polarity(
    text: str, negative_terms: tuple[str, ...], affirmative_terms: tuple[str, ...]
) -> str | None:
    """Negative terms are checked first, so a phrase like "no rain"
    (which contains the affirmative keyword "rain" as a substring) is
    read as negative, not a false affirmative hit.
    """
    if any(_contains_word(text, t) for t in negative_terms):
        return "negative"
    if any(_contains_word(text, t) for t in affirmative_terms):
        return "affirmative"
    return None


def _mentioned_band(text: str, band_words: dict[str, str]) -> str | None:
    """First matching band word, by dict-iteration order. Mixed-band
    text ("cold in the morning but hot by afternoon") resolves to
    whichever is found first -- a known coarseness of a property floor,
    not a bug; the judge tier reads genuinely mixed answers.
    """
    for word, band in band_words.items():
        if _contains_word(text, word):
            return band
    return None


def answer_grounded_precip(forecast: Forecast) -> Check:
    """The sketch's headline case: the answer's rain/umbrella framing
    must not contradict the fixture's rain_likely fact.
    """
    facts = derive_facts(forecast)

    def p(ans):
        polarity = _polarity(ans.text or "", _RAIN_NEGATIVE_TERMS, _RAIN_AFFIRMATIVE_TERMS)
        if facts.rain_likely is True and polarity == "negative":
            return False, f"fixture rain_likely=True but answer denies rain: {ans.text!r}"
        if facts.rain_likely is False and polarity == "affirmative":
            return False, f"fixture rain_likely=False but answer claims rain: {ans.text!r}"
        return True, f"rain_likely={facts.rain_likely} answer_polarity={polarity}"
    return Check("answer_grounded_precip", p)


def answer_grounded_temperature(forecast: Forecast) -> Check:
    """The answer's temperature characterization, if any, must not
    contradict the fixture's temperature_band (e.g. doesn't call a 5C
    fixture "warm").
    """
    facts = derive_facts(forecast)

    def p(ans):
        mentioned = _mentioned_band(ans.text or "", _TEMPERATURE_BAND_WORDS)
        if mentioned is None:
            return True, f"no temperature characterization in answer (fixture band={facts.temperature_band})"
        ok = mentioned == facts.temperature_band
        return ok, f"answer implies {mentioned!r} but fixture band={facts.temperature_band!r}"
    return Check("answer_grounded_temperature", p)


def answer_grounded_condition(forecast: Forecast) -> Check:
    """The condition the answer describes, if any, must not contradict
    the fixture's condition_family (e.g. doesn't say "sunny" when the
    fixture is RAIN).
    """
    facts = derive_facts(forecast)

    def p(ans):
        mentioned = _mentioned_band(ans.text or "", _CONDITION_WORDS)
        if mentioned is None:
            return True, f"no condition description in answer (fixture family={facts.condition_family})"
        ok = mentioned == facts.condition_family
        return ok, f"answer implies {mentioned!r} but fixture condition_family={facts.condition_family!r}"
    return Check("answer_grounded_condition", p)
