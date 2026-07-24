"""Record (or refresh) the stage-4 synthesize replay fixtures (Task 17.5).

Fixtures live in backend/tests/fixtures/synthesize/*.json. In normal test
runs, `test_synthesize_fixtures_replay.py` replays them through a
fixture-backed FakeLLMClient -- no live model calls. This script is the
*record* half: it drives 4 representative scenarios (umbrella decision,
multi-day outlook, comparison, current-conditions) and writes each
result to its fixture file. Reuses Task 14's harness (see
record_decompose_fixtures.py), adapted for one real difference:
synthesize() doesn't just pass the LLM's output straight through -- it
validates the returned highlight against the real forecasts and
assembles an AnswerCard (Task 17.3). So this script records the *raw*
SynthesisOutput the model call itself produced (calling llm.get_structured
directly, not synthesize()), so the replay test can exercise synthesize's
own validation logic against genuine recorded model output.

Two modes:

    # Default: no network, no API key. Uses this script's own
    # hand-authored placeholder SynthesisOutput per scenario, tagged
    # "synthetic": true in the fixture. Use this until the real stage-4
    # prompt (Task 17.4's placeholder, skycast.pipeline.prompts) is
    # authored -- there's nothing genuine to record against yet.
    python scripts/record_synthesize_fixtures.py

    # Real recording: calls the actual Anthropic API via
    # AnthropicLLMClient, tags the fixture "synthetic": false. Requires
    # ANTHROPIC_API_KEY (and, optionally, ANTHROPIC_MODEL). Re-run this
    # whenever the real prompt changes -- test_synthesize_fixtures_replay.py
    # fails loudly if a committed fixture's `system` no longer matches
    # the current prompt, naming exactly which fixtures are stale.
    python scripts/record_synthesize_fixtures.py --live
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import DailyReading, Forecast, HourlyReading, Units
from skycast.domain.location import Location
from skycast.llm.anthropic_client import AnthropicLLMClient
from skycast.llm.client import LLMClient
from skycast.pipeline.data_needs import QueryIntent
from skycast.pipeline.prompts import SYNTHESIZE_SYSTEM_PROMPT
from skycast.pipeline.synthesis_output import SynthesisOutput
from skycast.pipeline.synthesize_stage import _TOOL_NAME, _build_user_message
from skycast.sse.payloads import ForecastBlock, Highlight, ReadingLocator

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "synthesize"

_NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def _hyderabad() -> Location:
    return Location(
        id="in-memory:hyderabad-in", name="Hyderabad", latitude=17.385, longitude=78.4867,
        country="India", country_code="IN", timezone="Asia/Kolkata",
    )


def _austin() -> Location:
    return Location(
        id="in-memory:austin-us", name="Austin", latitude=30.2672, longitude=-97.7431,
        country="United States", country_code="US", timezone="America/Chicago",
    )


def _dallas() -> Location:
    return Location(
        id="in-memory:dallas-us", name="Dallas", latitude=32.7767, longitude=-96.7970,
        country="United States", country_code="US", timezone="America/Chicago",
    )


def _seattle() -> Location:
    return Location(
        id="in-memory:seattle-us", name="Seattle", latitude=47.6062, longitude=-122.3321,
        country="United States", country_code="US", timezone="America/Los_Angeles",
    )


class _Scenario:
    def __init__(
        self,
        name: str,
        query: str,
        forecasts: list[Forecast],
        intent: QueryIntent,
        placeholder_response: SynthesisOutput,
    ) -> None:
        self.name = name
        self.query = query
        self.forecasts = forecasts
        self.intent = intent
        self.placeholder_response = placeholder_response


_SCENARIOS: list[_Scenario] = [
    _Scenario(
        name="umbrella_decision",
        query="Do I need an umbrella in Hyderabad this evening?",
        forecasts=[
            Forecast(
                location=_hyderabad(),
                units=Units(),
                current=HourlyReading(
                    timestamp=_NOW, temperature=29.0, feels_like=31.0,
                    precip_probability=20.0, wind_speed=10.0, condition_code=ConditionCode.CLOUDY,
                ),
                hourly=[
                    HourlyReading(
                        timestamp=datetime(2026, 7, 7, 15, 0, tzinfo=timezone.utc),
                        temperature=28.0, precip_probability=30.0, condition_code=ConditionCode.CLOUDY,
                    ),
                    HourlyReading(
                        timestamp=datetime(2026, 7, 7, 18, 0, tzinfo=timezone.utc),
                        temperature=25.0, precip_probability=80.0, condition_code=ConditionCode.RAIN,
                    ),
                    HourlyReading(
                        timestamp=datetime(2026, 7, 7, 21, 0, tzinfo=timezone.utc),
                        temperature=23.0, precip_probability=40.0, condition_code=ConditionCode.CLOUDY,
                    ),
                ],
            ),
        ],
        intent=QueryIntent.DECISION,
        placeholder_response=SynthesisOutput(
            text="Yes, bring an umbrella this evening -- rain is likely around 6pm.",
            highlight=Highlight(
                forecast_index=0, locator=ReadingLocator(block=ForecastBlock.HOURLY, index=1)
            ),
        ),
    ),
    _Scenario(
        name="multi_day_outlook",
        query="What's the outlook for Austin this week?",
        forecasts=[
            Forecast(
                location=_austin(),
                units=Units(),
                daily=[
                    DailyReading(
                        date=date(2026, 7, 11), temp_min=24.0, temp_max=35.0,
                        precip_probability=5.0, condition_code=ConditionCode.CLEAR,
                    ),
                    DailyReading(
                        date=date(2026, 7, 12), temp_min=24.0, temp_max=34.0,
                        precip_probability=10.0, condition_code=ConditionCode.CLEAR,
                    ),
                    DailyReading(
                        date=date(2026, 7, 13), temp_min=22.0, temp_max=29.0,
                        precip_probability=70.0, condition_code=ConditionCode.THUNDERSTORM,
                    ),
                    DailyReading(
                        date=date(2026, 7, 14), temp_min=23.0, temp_max=33.0,
                        precip_probability=15.0, condition_code=ConditionCode.CLEAR,
                    ),
                ],
            ),
        ],
        intent=QueryIntent.OUTLOOK,
        placeholder_response=SynthesisOutput(
            text="Mostly clear this week in Austin, but expect thunderstorms on the 13th.",
            highlight=Highlight(
                forecast_index=0, locator=ReadingLocator(block=ForecastBlock.DAILY, index=2)
            ),
        ),
    ),
    _Scenario(
        name="comparison",
        query="How does the weather in Dallas compare to Austin right now?",
        forecasts=[
            Forecast(
                location=_austin(), units=Units(),
                current=HourlyReading(timestamp=_NOW, temperature=30.0, condition_code=ConditionCode.CLEAR),
            ),
            Forecast(
                location=_dallas(), units=Units(),
                current=HourlyReading(timestamp=_NOW, temperature=34.0, condition_code=ConditionCode.CLEAR),
            ),
        ],
        intent=QueryIntent.COMPARISON,
        placeholder_response=SynthesisOutput(
            text="Dallas is warmer than Austin right now, by about 4 degrees.",
            highlight=Highlight(
                forecast_index=1, locator=ReadingLocator(block=ForecastBlock.CURRENT)
            ),
        ),
    ),
    _Scenario(
        name="current_conditions",
        query="What's the weather like in Seattle right now?",
        forecasts=[
            Forecast(
                location=_seattle(), units=Units(),
                current=HourlyReading(timestamp=_NOW, temperature=18.0, condition_code=ConditionCode.CLOUDY),
            ),
        ],
        intent=QueryIntent.CONDITIONS,
        placeholder_response=SynthesisOutput(
            text="It's cloudy and 18°C in Seattle right now.", highlight=None
        ),
    ),
]


async def _record_one(scenario: _Scenario, *, live: bool) -> dict:
    user = _build_user_message(scenario.query, scenario.forecasts, scenario.intent)

    if live:
        model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        llm: LLMClient = AnthropicLLMClient(model=model)
        response = await llm.get_structured(
            system=SYNTHESIZE_SYSTEM_PROMPT, user=user, schema=SynthesisOutput, tool_name=_TOOL_NAME
        )
    else:
        response = scenario.placeholder_response

    return {
        "name": scenario.name,
        "query": scenario.query,
        "intent": scenario.intent.value,
        "forecasts": [f.model_dump(mode="json") for f in scenario.forecasts],
        "system": SYNTHESIZE_SYSTEM_PROMPT,
        "user": user,
        "response": response.model_dump(mode="json"),
        "synthetic": not live,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call the real Anthropic API via AnthropicLLMClient instead of "
        "using this script's placeholder responses.",
    )
    args = parser.parse_args()

    _FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for scenario in _SCENARIOS:
        fixture = asyncio.run(_record_one(scenario, live=args.live))
        path = _FIXTURES_DIR / f"{scenario.name}.json"
        path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
