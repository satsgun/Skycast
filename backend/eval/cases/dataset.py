"""The eval dataset.

One curated set of EvalCases covering the query taxonomy:
umbrella/decision, multi-day outlook, comparison, no-location->default,
ambiguous->clarify, not-found, provider-outage.

Each case carries a `canned_spec` (a real DataNeedsSpec) so the
deterministic tiers (plan/execute) run without an LLM, plus property
checks for the stochastic tiers (decompose/synthesize) that a real LLM
run scores. The InMemoryProvider's built-in dataset knows "hyderabad"
(single match) and "springfield" (multi-match); unknown names geocode
empty (not-found).

Guard against circularity (Task E1.5): a case's `checks_decompose`
arguments (`spec_locations_exact([...])`, `spec_variables_exact({...})`/
`spec_variables_prf({...}, ...)`) are independently authored ground
truth for what the real model *should* extract from the query text --
never derived from that same case's `canned_spec.location_names`/
`.variables`, even as a convenience (e.g.
`spec_locations_exact(canned_spec.location_names)` would let the model
pass by construction, since `canned_spec` exists only to drive the
deterministic plan/execute tiers, not to define what decompose is being
scored against). Where the two happen to agree -- they usually should,
for a well-behaved query -- that's a property of a good case, not the
source of truth; reason each set of expectations from the query text on
its own.
"""

from __future__ import annotations

from datetime import datetime, timezone

from skycast.domain.location import Location
from skycast.domain.provider import Granularity, WeatherVariable
from skycast.pipeline.data_needs import DataNeedsSpec, QueryIntent
from skycast.pipeline.relative_time import RelativeTimeKind, RelativeTimeSpec

from eval.harness.types import Check, EvalCase
from eval.harness import checks as C

_NOW = datetime(2026, 7, 18, 9, 0, tzinfo=timezone.utc)
# _spec()'s default: a generic "some part of today" descriptor for cases
# with no explicit time argument.
_DEFAULT_TIME = RelativeTimeSpec(kind=RelativeTimeKind.TODAY)
_MULTIDAY_TIME = RelativeTimeSpec(kind=RelativeTimeKind.NEXT_N_DAYS, day_count=3)
# A properly-resolved "this evening" descriptor, for a case that supplies
# one -- no more hand-computed 17:00-21:00 hours, THIS_EVENING is a
# first-class kind now (Task 21).
_EVENING_TIME = RelativeTimeSpec(kind=RelativeTimeKind.THIS_EVENING)


def _loc(name, lat, lon, admin1, country, cc, tz, pop=100000, suffix=""):
    key = (name + suffix).lower().replace(" ", "-")
    return Location(
        id=f"in-memory:{key}", name=name, latitude=lat, longitude=lon,
        country=country, country_code=cc, admin1=admin1, population=pop, timezone=tz,
    )


# Custom single-match cities the built-in InMemoryProvider set doesn't know.
_CITIES = {
    "são paulo": [_loc("São Paulo", -23.55, -46.63, "São Paulo", "Brazil", "BR", "America/Sao_Paulo", 12300000)],
    "reykjavík": [_loc("Reykjavík", 64.146, -21.94, "Capital Region", "Iceland", "IS", "Atlantic/Reykjavik", 131000)],
    "tokyo": [_loc("Tokyo", 35.6895, 139.6917, "Tokyo", "Japan", "JP", "Asia/Tokyo", 13960000)],
    "paris": [_loc("Paris", 48.8566, 2.3522, "Île-de-France", "France", "FR", "Europe/Paris", 2161000)],
    "seattle": [_loc("Seattle", 47.6062, -122.3321, "Washington", "United States", "US", "America/Los_Angeles", 737000)],
}
# A different multi-match name than "springfield", for ambiguous-case breadth.
_PORTLANDS = {
    "portland": [
        _loc("Portland", 45.5152, -122.6784, "Oregon", "United States", "US", "America/Los_Angeles", 652000, "-or"),
        _loc("Portland", 43.6591, -70.2568, "Maine", "United States", "US", "America/New_York", 68000, "-me"),
    ]
}

# The user's configured default location, for cases whose query names none.
# Mirrors InMemoryProvider's own built-in "hyderabad" entry exactly, so a
# default-location chain generates the same synthetic weather a geocoded
# one would.
_DEFAULT_LOCATION = _loc(
    "Hyderabad", 17.385, 78.4867, "Telangana", "India", "IN", "Asia/Kolkata",
    pop=6809970, suffix="-in",
)


def _spec(names, intent, grans, variables, time=_DEFAULT_TIME):
    return DataNeedsSpec(
        location_names=list(names),
        granularities=set(grans),
        time=time,
        variables=set(variables),
        intent=intent,
    )


# --- case-specific checks over a ToolPlan ---


def _plan_has_geocode_for(name: str) -> Check:
    def p(tp):
        got = [c.location_name for c in tp.calls if c.tool.value == "GEOCODE"]
        return name in got, f"geocode targets={got} want {name}"
    return Check(f"plan_geocodes[{name}]", p)


def _plan_forecast_depends_on_geocode(name: str) -> Check:
    """Dependency-ordering check (sketch: 'geocode-before-forecast
    rules') -- a geocode call existing somewhere in the plan isn't
    enough; the chain's FETCH_FORECAST call must actually depend_on it.
    """
    def p(tp):
        geocodes = [c for c in tp.calls if c.tool.value == "GEOCODE" and c.location_name == name]
        if not geocodes:
            return False, f"no GEOCODE call found for {name}"
        geocode_id = geocodes[0].call_id
        depending = [
            c for c in tp.calls
            if c.tool.value == "FETCH_FORECAST" and geocode_id in c.depends_on
        ]
        ok = len(depending) == 1
        return ok, (f"forecast calls depending on geocode[{name}]={len(depending)} "
                    f"expected 1")
    return Check(f"plan_forecast_depends_on_geocode[{name}]", p)


def _plan_forecast_count(n: int) -> Check:
    def p(tp):
        c = sum(1 for x in tp.calls if x.tool.value == "FETCH_FORECAST")
        return c == n, f"forecast calls={c} expected={n}"
    return Check(f"plan_forecast_count=={n}", p)


def _plan_skips_geocode() -> Check:
    def p(tp):
        geos = [c for c in tp.calls if c.tool.value == "GEOCODE"]
        return len(geos) == 0, f"geocode calls={len(geos)} expected 0"
    return Check("plan_skips_geocode", p)


def _exec_forecast_count(n: int) -> Check:
    def p(result):
        fc = len(getattr(result, "forecasts", []))
        return fc == n, f"forecasts={fc} expected={n}"
    return Check(f"exec_forecast_count=={n}", p)


def _exec_clarify_for(name: str) -> Check:
    def p(result):
        got = getattr(result, "for_location_name", None)
        return got == name, f"for_location_name={got} want {name}"
    return Check(f"clarify_for[{name}]", p)


def _exec_error_kind(kind: str) -> Check:
    def p(result):
        k = getattr(getattr(result, "kind", None), "value", None)
        return k == kind, f"kind={k} expected={kind}"
    return Check(f"error_kind[{kind}]", p)


def _grounded(*factories):
    """Builds a checks_synthesize_grounded factory (Task E4.4) from
    single-forecast grounding-check factories (answer_grounded_precip
    etc.), applied to the first forecast execute() produces -- the only
    one, for the single-location cases that use this.
    """
    def build(forecasts):
        return tuple(factory(forecasts[0]) for factory in factories)
    return build


DATASET: list[EvalCase] = [
    # 1. Umbrella / decision -- single known location, hourly, precip.
    EvalCase(
        id="umbrella_decision",
        query="Do I need an umbrella in Hyderabad this afternoon?",
        tags=("decision", "single", "hourly"),
        canned_spec=_spec(
            ["Hyderabad"], QueryIntent.DECISION,
            [Granularity.HOURLY],
            [WeatherVariable.PRECIP_PROBABILITY, WeatherVariable.CONDITION],
        ),
        checks_plan=(
            _plan_has_geocode_for("Hyderabad"),
            _plan_forecast_count(1),
            _plan_forecast_depends_on_geocode("Hyderabad"),
        ),
        expect_execute_variant="Success",
        checks_execute=(_exec_forecast_count(1),),
        checks_decompose=(
            C.spec_intent_is("DECISION"),
            C.spec_locations_exact(["Hyderabad"]),
            C.spec_variables_exact({"PRECIP_PROBABILITY", "CONDITION"}),
        ),
        checks_synthesize=(
            C.answer_nonempty(),
            C.answer_leads_with_conclusion(),
            C.answer_highlight_valid_or_none(),
        ),
        checks_synthesize_grounded=_grounded(C.answer_grounded_precip),
        judge_rubric=(
            "Does the answer lead with a clear yes/no-style decision about "
            "the umbrella, and is it consistent with the forecast's precipitation?"
        ),
        expect_terminal="answer",
    ),
    # 2. Multi-day outlook -- single known location, daily.
    EvalCase(
        id="multiday_outlook",
        query="What's the weather looking like in Hyderabad over the next few days?",
        tags=("outlook", "single", "daily"),
        canned_spec=_spec(
            ["Hyderabad"], QueryIntent.OUTLOOK,
            [Granularity.DAILY],
            [WeatherVariable.TEMPERATURE, WeatherVariable.CONDITION],
            time=_MULTIDAY_TIME,
        ),
        checks_plan=(_plan_has_geocode_for("Hyderabad"), _plan_forecast_count(1)),
        expect_execute_variant="Success",
        checks_execute=(_exec_forecast_count(1),),
        checks_decompose=(
            C.spec_intent_is("OUTLOOK"),
            C.spec_has_granularity("DAILY"),
            C.spec_locations_exact(["Hyderabad"]),
            C.spec_variables_exact({"TEMPERATURE", "CONDITION"}),
        ),
        checks_synthesize=(C.answer_nonempty(), C.answer_highlight_valid_or_none()),
        checks_synthesize_grounded=_grounded(
            C.answer_grounded_temperature, C.answer_grounded_condition
        ),
        expect_terminal="answer",
    ),
    # 3. Comparison -- two known locations. (InMemory knows hyderabad;
    #    springfield is multi-match, so we compare hyderabad vs itself-like
    #    single-match by using two single-match names is not possible with
    #    the built-in set; use hyderabad + a provided single-match second.)
    #    For the deterministic tier we assert the FAN-OUT shape at plan.
    EvalCase(
        id="comparison_two_cities",
        query="Is it warmer in Hyderabad or Springfield right now?",
        tags=("comparison", "multi"),
        canned_spec=_spec(
            ["Hyderabad", "Springfield"], QueryIntent.COMPARISON,
            [Granularity.CURRENT],
            [WeatherVariable.TEMPERATURE],
            time=None,
        ),
        checks_plan=(
            _plan_forecast_count(2),
            _plan_has_geocode_for("Hyderabad"),
            _plan_has_geocode_for("Springfield"),
            # Dependency ordering (sketch): each independent chain's
            # forecast call must depend on its OWN geocode call, not
            # get cross-wired with the other's in this two-city fan-out.
            _plan_forecast_depends_on_geocode("Hyderabad"),
            _plan_forecast_depends_on_geocode("Springfield"),
        ),
        # Springfield is multi-match in the InMemory set -> execute clarifies.
        expect_execute_variant="NeedsClarification",
        checks_execute=(_exec_clarify_for("Springfield"),),
        checks_decompose=(
            C.spec_intent_is("COMPARISON"),
            C.spec_locations_exact(["Hyderabad", "Springfield"]),
            C.spec_variables_exact({"TEMPERATURE"}),
        ),
        expect_terminal="clarify",
    ),
    # 4. No location -> uses default. (canned spec has empty names; plan
    #    needs a default_location, so the deterministic plan tier is
    #    exercised in a dedicated provider wiring below via checks only on
    #    decompose; here we assert decompose would flag default use.)
    EvalCase(
        id="no_location_default",
        query="Will it rain today?",
        tags=("default", "no-location"),
        # No canned_spec plan/execute here -- plan() needs default_location
        # wiring; this case's deterministic value is covered by case 6's
        # not-found and case 3's fan-out. We assert the decompose property.
        # default_location IS wired for the end-to-end tier below, since
        # run_end_to_end drives the real plan() and needs somewhere to
        # resolve a location-less query to.
        default_location=_DEFAULT_LOCATION,
        checks_decompose=(
            C.spec_names_default_location(),
            C.spec_location_count(0),
            C.spec_variables_exact({"PRECIP_PROBABILITY"}),
        ),
        checks_synthesize=(C.answer_nonempty(),),
        expect_terminal="answer",
    ),
    # 5. Ambiguous -> clarify. Single multi-match location.
    EvalCase(
        id="ambiguous_clarify",
        query="What's the weather in Springfield?",
        tags=("clarify", "single", "ambiguous"),
        canned_spec=_spec(
            ["Springfield"], QueryIntent.CONDITIONS,
            [Granularity.CURRENT],
            [WeatherVariable.TEMPERATURE, WeatherVariable.CONDITION],
            time=None,
        ),
        checks_plan=(_plan_has_geocode_for("Springfield"), _plan_forecast_count(1)),
        expect_execute_variant="NeedsClarification",
        checks_execute=(_exec_clarify_for("Springfield"),),
        checks_decompose=(
            C.spec_locations_exact(["Springfield"]),
            C.spec_variables_exact({"TEMPERATURE", "CONDITION"}),
        ),
        expect_terminal="clarify",
    ),
    # 6. Not found -- unknown location geocodes empty.
    EvalCase(
        id="not_found",
        query="What's the weather in Nowhereville?",
        tags=("error", "not-found"),
        canned_spec=_spec(
            ["Nowhereville"], QueryIntent.CONDITIONS,
            [Granularity.CURRENT],
            [WeatherVariable.TEMPERATURE],
            time=None,
        ),
        checks_plan=(_plan_has_geocode_for("Nowhereville"),),
        expect_execute_variant="Failed",
        checks_execute=(_exec_error_kind("not_found"),),
        expect_terminal="error",
    ),
    # 7. Skip-geocode -- a named location that matches the configured
    #    default location skips geocoding entirely (fix #94: plan()
    #    trusts the already-known default_location Location rather than
    #    re-geocoding a bare name that could be ambiguous worldwide).
    #    default_location is threaded through by run_plan/run_execute
    #    (eval/harness/deterministic.py) so this is exercised for real,
    #    not just asserted at decompose.
    EvalCase(
        id="skip_geocode_resolved",
        query="Weather in Hyderabad now (already resolved)",
        tags=("skip-geocode", "single"),
        canned_spec=_spec(
            ["Hyderabad"], QueryIntent.CONDITIONS,
            [Granularity.CURRENT],
            [WeatherVariable.TEMPERATURE],
            time=None,
        ),
        default_location=_DEFAULT_LOCATION,
        checks_plan=(_plan_skips_geocode(), _plan_forecast_count(1)),
        expect_execute_variant="Success",
        checks_execute=(_exec_forecast_count(1),),
    ),
    # 8. Simple current conditions -- the plainest query shape.
    EvalCase(
        id="simple_current",
        query="What's the weather in Hyderabad?",
        tags=("conditions", "single", "current"),
        canned_spec=_spec(
            ["Hyderabad"], QueryIntent.CONDITIONS,
            [Granularity.CURRENT],
            [WeatherVariable.TEMPERATURE, WeatherVariable.CONDITION],
            time=None,
        ),
        checks_plan=(_plan_has_geocode_for("Hyderabad"), _plan_forecast_count(1)),
        expect_execute_variant="Success",
        checks_execute=(_exec_forecast_count(1),),
        checks_decompose=(
            C.spec_intent_is("CONDITIONS"),
            C.spec_has_granularity("CURRENT"),
            C.spec_locations_exact(["Hyderabad"]),
            C.spec_variables_exact({"TEMPERATURE", "CONDITION"}),
        ),
        checks_synthesize=(C.answer_nonempty(), C.answer_highlight_valid_or_none()),
        checks_synthesize_grounded=_grounded(
            C.answer_grounded_temperature, C.answer_grounded_condition
        ),
        expect_terminal="answer",
    ),
    # 9. Time-window stress -- "this evening" must resolve to the
    #    THIS_EVENING descriptor kind. Task 21 landed the relative-time
    #    descriptor: decompose no longer computes hours itself, so this
    #    is an exact kind match, not a tolerance score.
    EvalCase(
        id="time_window_this_evening",
        query="Will it be cold in Hyderabad this evening?",
        tags=("time-window", "single", "hourly", "stress"),
        canned_spec=_spec(
            ["Hyderabad"], QueryIntent.DECISION,
            [Granularity.HOURLY],
            [WeatherVariable.TEMPERATURE],
        ),
        checks_plan=(_plan_forecast_count(1),),
        expect_execute_variant="Success",
        checks_decompose=(
            C.spec_has_granularity("HOURLY"),
            C.spec_time_kind_is("THIS_EVENING"),
            C.spec_locations_exact(["Hyderabad"]),
            C.spec_variables_exact({"TEMPERATURE"}),
        ),
        expect_terminal="answer",
    ),
    # 10. Code-gen-fallback class -- a computed query the generic tool set
    #     can't express. Even before the fallback exists, decompose/plan
    #     must route to fallback OR return an honest "can't answer", never
    #     fabricate. Asserted at decompose (intent not a plain lookup) --
    #     the property is: it does NOT silently produce a normal spec that
    #     would fabricate an answer. Documented as a taxonomy slot; the
    #     precise routing assertion firms up when the fallback lands.
    EvalCase(
        id="codegen_fallback_routing",
        query="How many hours next week in Hyderabad are above 35C with wind under 10 km/h?",
        tags=("codegen-fallback", "single", "computed"),
        # No canned_spec plan/execute assertion: the correct v1 behavior is
        # contested (route-to-fallback vs. honest refusal), so we assert the
        # decompose-level property that it recognized a computed/aggregate
        # need rather than a plain current-conditions lookup.
        checks_decompose=(
            C.spec_has_granularity("HOURLY"),
            C.spec_locations_exact(["Hyderabad"]),
            # Loose on precision: the aggregation/routing answer itself is
            # deliberately contested (see the case comment above), but the
            # two thresholds are explicit anchors in the query text either
            # way, so recall on them is still worth requiring.
            C.spec_variables_prf({"TEMPERATURE", "WIND_SPEED"}, min_precision=0.4),
        ),
        judge_rubric=(
            "The query asks for a COUNT of hours meeting a compound numeric "
            "condition, which the simple forecast tools can't compute directly. "
            "Does the answer either (a) honestly acknowledge it can't compute "
            "this precisely, or (b) reason correctly from the hourly data, "
            "rather than fabricating a confident number?"
        ),
    ),

    # ===================================================================
    # DEPTH VARIANTS -- concentrated where within-category variance and
    # breadth teach the most (decision, comparison, time-window,
    # ambiguous, simple-conditions with harder locations). Each authored
    # with real ground truth, not padded.
    # ===================================================================

    # --- DECISION category (high variance: many phrasings & variables) ---
    EvalCase(
        id="decision_jacket",
        query="Should I wear a jacket in Hyderabad this afternoon?",
        tags=("decision", "single", "hourly", "variant"),
        canned_spec=_spec(
            ["Hyderabad"], QueryIntent.DECISION, [Granularity.HOURLY],
            [WeatherVariable.TEMPERATURE, WeatherVariable.CONDITION],
        ),
        checks_plan=(_plan_forecast_count(1),),
        expect_execute_variant="Success",
        checks_decompose=(
            C.spec_intent_is("DECISION"),
            C.spec_locations_exact(["Hyderabad"]),
            C.spec_variables_exact({"TEMPERATURE", "CONDITION"}),
        ),
        checks_synthesize=(C.answer_nonempty(), C.answer_leads_with_conclusion()),
        checks_synthesize_grounded=_grounded(
            C.answer_grounded_temperature, C.answer_grounded_condition
        ),
        judge_rubric="Does the answer lead with a clear jacket yes/no consistent with the temperature?",
        expect_terminal="answer",
    ),
    EvalCase(
        id="decision_sunscreen",
        query="Do I need sunscreen in São Paulo today?",
        tags=("decision", "single", "custom-city", "variant"),
        provider_locations={"são paulo": _CITIES["são paulo"]},
        canned_spec=_spec(
            ["São Paulo"], QueryIntent.DECISION, [Granularity.DAILY],
            [WeatherVariable.CONDITION], time=_MULTIDAY_TIME,
        ),
        checks_plan=(_plan_has_geocode_for("São Paulo"), _plan_forecast_count(1)),
        expect_execute_variant="Success",
        checks_execute=(_exec_forecast_count(1),),
        checks_decompose=(
            C.spec_intent_is("DECISION"),
            C.spec_locations_exact(["São Paulo"]),
            C.spec_variables_exact({"CONDITION"}),
        ),
        expect_terminal="answer",
    ),
    EvalCase(
        id="decision_run_wind",
        query="Is it too windy to go for a run in Hyderabad right now?",
        tags=("decision", "single", "current", "wind", "variant"),
        canned_spec=_spec(
            ["Hyderabad"], QueryIntent.DECISION, [Granularity.CURRENT],
            [WeatherVariable.WIND_SPEED, WeatherVariable.CONDITION], time=None,
        ),
        checks_plan=(_plan_forecast_count(1),),
        expect_execute_variant="Success",
        checks_decompose=(
            C.spec_intent_is("DECISION"),
            C.spec_locations_exact(["Hyderabad"]),
            # Tolerates one companion variable (e.g. CONDITION) while
            # still requiring WIND_SPEED -- the query is laser-focused on
            # wind, but a model reasonably pulling in general condition
            # too shouldn't be penalized as a wrong extraction.
            C.spec_variables_prf({"WIND_SPEED"}, min_precision=0.5),
        ),
        checks_synthesize=(C.answer_nonempty(), C.answer_leads_with_conclusion()),
        expect_terminal="answer",
    ),

    # --- SIMPLE CONDITIONS with harder locations (non-ASCII, distant tz) ---
    EvalCase(
        id="simple_reykjavik",
        query="What's the weather in Reykjavík?",
        tags=("conditions", "single", "custom-city", "non-ascii", "variant"),
        provider_locations={"reykjavík": _CITIES["reykjavík"]},
        canned_spec=_spec(
            ["Reykjavík"], QueryIntent.CONDITIONS, [Granularity.CURRENT],
            [WeatherVariable.TEMPERATURE, WeatherVariable.CONDITION], time=None,
        ),
        checks_plan=(_plan_has_geocode_for("Reykjavík"), _plan_forecast_count(1)),
        expect_execute_variant="Success",
        checks_execute=(_exec_forecast_count(1),),
        checks_decompose=(
            C.spec_intent_is("CONDITIONS"),
            C.spec_locations_exact(["Reykjavík"]),
            C.spec_variables_exact({"TEMPERATURE", "CONDITION"}),
        ),
        expect_terminal="answer",
    ),
    EvalCase(
        id="simple_paris",
        query="weather in Paris",
        tags=("conditions", "single", "custom-city", "terse", "variant"),
        provider_locations={"paris": _CITIES["paris"]},
        canned_spec=_spec(
            ["Paris"], QueryIntent.CONDITIONS, [Granularity.CURRENT],
            [WeatherVariable.TEMPERATURE, WeatherVariable.CONDITION], time=None,
        ),
        checks_plan=(_plan_has_geocode_for("Paris"),),
        expect_execute_variant="Success",
        checks_decompose=(
            C.spec_locations_exact(["Paris"]),
            C.spec_variables_exact({"TEMPERATURE", "CONDITION"}),
        ),
        expect_terminal="answer",
    ),

    # --- MULTI-DAY OUTLOOK variants (phrasing + horizon breadth) ---
    EvalCase(
        id="outlook_weekend",
        query="What's the weather like in Hyderabad this weekend?",
        tags=("outlook", "single", "daily", "variant"),
        canned_spec=_spec(
            ["Hyderabad"], QueryIntent.OUTLOOK, [Granularity.DAILY],
            [WeatherVariable.TEMPERATURE, WeatherVariable.CONDITION], time=_MULTIDAY_TIME,
        ),
        checks_plan=(_plan_forecast_count(1),),
        expect_execute_variant="Success",
        checks_decompose=(
            C.spec_intent_is("OUTLOOK"),
            C.spec_has_granularity("DAILY"),
            C.spec_locations_exact(["Hyderabad"]),
            C.spec_variables_exact({"TEMPERATURE", "CONDITION"}),
        ),
        expect_terminal="answer",
    ),

    # --- COMPARISON variants (two single-match cities -> real Success;
    #     the built-in case 3 uses springfield->clarify, this one resolves) ---
    EvalCase(
        id="comparison_resolvable",
        query="Is it warmer in Tokyo or Paris right now?",
        tags=("comparison", "multi", "custom-city", "variant"),
        provider_locations={"tokyo": _CITIES["tokyo"], "paris": _CITIES["paris"]},
        canned_spec=_spec(
            ["Tokyo", "Paris"], QueryIntent.COMPARISON, [Granularity.CURRENT],
            [WeatherVariable.TEMPERATURE], time=None,
        ),
        checks_plan=(
            _plan_forecast_count(2),
            _plan_has_geocode_for("Tokyo"),
            _plan_has_geocode_for("Paris"),
        ),
        expect_execute_variant="Success",
        checks_execute=(_exec_forecast_count(2),),
        checks_decompose=(
            C.spec_intent_is("COMPARISON"),
            C.spec_locations_exact(["Tokyo", "Paris"]),
            C.spec_variables_exact({"TEMPERATURE"}),
        ),
        checks_synthesize=(C.answer_nonempty(), C.answer_card_forecast_count(2)),
        judge_rubric=(
            "Does the answer compare BOTH cities, state which is warmer, and "
            "is that claim consistent with the two forecasts' temperatures?"
        ),
        expect_terminal="answer",
    ),
    EvalCase(
        id="comparison_three_cities",
        query="Compare the weather in Tokyo, Paris, and Seattle.",
        tags=("comparison", "multi", "custom-city", "three-way", "variant"),
        provider_locations={
            "tokyo": _CITIES["tokyo"], "paris": _CITIES["paris"], "seattle": _CITIES["seattle"],
        },
        canned_spec=_spec(
            ["Tokyo", "Paris", "Seattle"], QueryIntent.COMPARISON, [Granularity.CURRENT],
            [WeatherVariable.TEMPERATURE, WeatherVariable.CONDITION], time=None,
        ),
        checks_plan=(_plan_forecast_count(3),),
        expect_execute_variant="Success",
        checks_execute=(_exec_forecast_count(3),),
        checks_decompose=(
            C.spec_intent_is("COMPARISON"),
            C.spec_locations_exact(["Tokyo", "Paris", "Seattle"]),
            C.spec_variables_exact({"TEMPERATURE", "CONDITION"}),
        ),
        expect_terminal="answer",
    ),

    # --- TIME-WINDOW stress variants (the genuinely fuzzy field) ---
    EvalCase(
        id="time_window_evening_resolved",
        query="Will it be cold in Hyderabad this evening?",
        tags=("time-window", "single", "hourly", "stress", "variant"),
        # Same query and same decompose-tier check as
        # time_window_this_evening above -- both just assert the model
        # classifies "this evening" as THIS_EVENING. The only real
        # difference is this case's canned_spec supplies an already-
        # resolved THIS_EVENING descriptor (_EVENING_TIME) rather than
        # the generic default, which matters for the deterministic
        # plan/execute tiers, not for what's checked here.
        canned_spec=_spec(
            ["Hyderabad"], QueryIntent.DECISION, [Granularity.HOURLY],
            [WeatherVariable.TEMPERATURE], time=_EVENING_TIME,
        ),
        checks_plan=(_plan_forecast_count(1),),
        expect_execute_variant="Success",
        checks_decompose=(
            C.spec_time_kind_is("THIS_EVENING"),
            C.spec_locations_exact(["Hyderabad"]),
            C.spec_variables_exact({"TEMPERATURE"}),
        ),
        expect_terminal="answer",
    ),
    EvalCase(
        id="time_window_tomorrow_morning",
        query="How's the weather tomorrow morning in Hyderabad?",
        tags=("time-window", "single", "hourly", "stress", "variant"),
        canned_spec=_spec(
            ["Hyderabad"], QueryIntent.CONDITIONS, [Granularity.HOURLY],
            [WeatherVariable.TEMPERATURE, WeatherVariable.CONDITION],
        ),
        checks_plan=(_plan_forecast_count(1),),
        expect_execute_variant="Success",
        checks_decompose=(
            C.spec_has_granularity("HOURLY"),
            C.spec_locations_exact(["Hyderabad"]),
            C.spec_variables_exact({"TEMPERATURE", "CONDITION"}),
        ),
        expect_terminal="answer",
    ),

    # --- AMBIGUOUS variants (a different multi-match name than springfield) ---
    EvalCase(
        id="ambiguous_portland",
        query="What's the weather in Portland?",
        tags=("clarify", "single", "ambiguous", "variant"),
        provider_locations=_PORTLANDS,
        canned_spec=_spec(
            ["Portland"], QueryIntent.CONDITIONS, [Granularity.CURRENT],
            [WeatherVariable.TEMPERATURE], time=None,
        ),
        checks_plan=(_plan_has_geocode_for("Portland"),),
        expect_execute_variant="NeedsClarification",
        checks_execute=(_exec_clarify_for("Portland"),),
        checks_decompose=(
            C.spec_locations_exact(["Portland"]),
            C.spec_variables_exact({"TEMPERATURE", "CONDITION"}),
        ),
        expect_terminal="clarify",
    ),

    # --- NOT-FOUND variant (different unknown name) ---
    EvalCase(
        id="not_found_atlantis",
        query="What's the weather in Atlantis?",
        tags=("error", "not-found", "variant"),
        canned_spec=_spec(
            ["Atlantis"], QueryIntent.CONDITIONS, [Granularity.CURRENT],
            [WeatherVariable.TEMPERATURE], time=None,
        ),
        checks_plan=(_plan_has_geocode_for("Atlantis"),),
        expect_execute_variant="Failed",
        checks_execute=(_exec_error_kind("not_found"),),
        expect_terminal="error",
    ),

    # --- DEFAULT-LOCATION variant (different phrasing, no city named) ---
    EvalCase(
        id="default_should_i_go_out",
        query="Is it a good day to go outside?",
        tags=("default", "no-location", "decision", "variant"),
        default_location=_DEFAULT_LOCATION,
        checks_decompose=(
            C.spec_names_default_location(),
            C.spec_location_count(0),
        ),
        expect_terminal="answer",
    ),
]
