"""Record (or refresh) the stage-1 decompose replay fixtures (Task 14.7).

Fixtures live in backend/tests/fixtures/decompose/*.json. In normal test
runs, `test_decompose_fixtures_replay.py` replays them through a
fixture-backed FakeLLMClient -- no live model calls. This script is the
*record* half: it drives decompose() for 5 representative queries
(umbrella decision, multi-day outlook, comparison, no-location,
ambiguous-location phrasing) and writes each result to its fixture file.

Two modes:

    # Default: no network, no API key. Uses this script's own
    # hand-authored placeholder DataNeedsSpec per scenario, tagged
    # "synthetic": true in the fixture. Use this until the real stage-1
    # prompt (Task 14.6's placeholder, skycast.pipeline.prompts) is
    # authored -- there's nothing genuine to record against yet.
    python scripts/record_decompose_fixtures.py

    # Real recording: calls the actual Anthropic API via
    # AnthropicLLMClient, tags the fixture "synthetic": false. Requires
    # ANTHROPIC_API_KEY (and, optionally, ANTHROPIC_MODEL). Re-run this
    # whenever the real prompt changes -- test_decompose_fixtures_replay.py
    # fails loudly if a committed fixture's `system` no longer matches
    # the current prompt, naming exactly which fixtures are stale.
    python scripts/record_decompose_fixtures.py --live
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from skycast.domain.location import Location
from skycast.domain.provider import Granularity, TimeWindow, WeatherVariable
from skycast.llm.anthropic_client import AnthropicLLMClient
from skycast.llm.client import LLMClient
from skycast.pipeline.data_needs import DataNeedsSpec, QueryIntent
from skycast.pipeline.decompose import _build_user_message, decompose
from skycast.pipeline.prompts import DECOMPOSE_SYSTEM_PROMPT
from skycast.pipeline.session_context import SessionContext

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "decompose"

_NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


class _Scenario:
    def __init__(
        self,
        name: str,
        query: str,
        session_ctx: SessionContext,
        placeholder_response: DataNeedsSpec,
    ) -> None:
        self.name = name
        self.query = query
        self.session_ctx = session_ctx
        self.placeholder_response = placeholder_response


_SCENARIOS: list[_Scenario] = [
    _Scenario(
        name="umbrella_decision",
        query="Do I need an umbrella this evening?",
        session_ctx=SessionContext(
            now=_NOW,
            default_location=Location(
                id="in-memory:hyderabad-in",
                name="Hyderabad",
                latitude=17.385,
                longitude=78.4867,
                country="India",
                country_code="IN",
                timezone="Asia/Kolkata",
            ),
        ),
        placeholder_response=DataNeedsSpec(
            use_default_location=True,
            granularities={Granularity.HOURLY},
            window=TimeWindow(
                start=datetime(2026, 7, 7, 12, 30, tzinfo=timezone.utc),
                end=datetime(2026, 7, 7, 17, 30, tzinfo=timezone.utc),
            ),
            variables={WeatherVariable.PRECIP_PROBABILITY},
            intent=QueryIntent.DECISION,
        ),
    ),
    _Scenario(
        name="multi_day_outlook",
        query="What's the weather like in Austin this weekend?",
        session_ctx=SessionContext(now=_NOW),
        placeholder_response=DataNeedsSpec(
            location_name="Austin",
            use_default_location=False,
            granularities={Granularity.DAILY},
            window=TimeWindow(
                start=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
                end=datetime(2026, 7, 12, 23, 59, tzinfo=timezone.utc),
            ),
            variables={
                WeatherVariable.TEMPERATURE,
                WeatherVariable.PRECIP_PROBABILITY,
                WeatherVariable.CONDITION,
            },
            intent=QueryIntent.OUTLOOK,
        ),
    ),
    _Scenario(
        name="comparison",
        query="Is it warmer in Miami or Seattle today?",
        session_ctx=SessionContext(now=_NOW),
        # NOTE: DataNeedsSpec.location_name is a single optional string --
        # there's no field for multiple locations even though
        # QueryIntent.COMPARISON exists. This placeholder picks one
        # location, matching what the current schema can actually hold;
        # true multi-location comparison needs a DataNeedsSpec revision.
        placeholder_response=DataNeedsSpec(
            location_name="Miami",
            use_default_location=False,
            granularities={Granularity.CURRENT},
            variables={WeatherVariable.TEMPERATURE},
            intent=QueryIntent.COMPARISON,
        ),
    ),
    _Scenario(
        name="no_location",
        query="Will it rain today?",
        session_ctx=SessionContext(now=_NOW),
        placeholder_response=DataNeedsSpec(
            use_default_location=False,
            granularities={Granularity.CURRENT},
            variables={WeatherVariable.PRECIP_PROBABILITY},
            intent=QueryIntent.CONDITIONS,
        ),
    ),
    _Scenario(
        name="ambiguous_location",
        query="What's the weather in Springfield tomorrow?",
        session_ctx=SessionContext(now=_NOW),
        placeholder_response=DataNeedsSpec(
            location_name="Springfield",
            use_default_location=False,
            granularities={Granularity.DAILY},
            window=TimeWindow(
                start=datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc),
                end=datetime(2026, 7, 8, 23, 59, tzinfo=timezone.utc),
            ),
            variables={WeatherVariable.TEMPERATURE, WeatherVariable.CONDITION},
            intent=QueryIntent.OUTLOOK,
        ),
    ),
]


async def _record_one(scenario: _Scenario, *, live: bool) -> dict:
    user = _build_user_message(scenario.query, scenario.session_ctx)

    if live:
        model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        llm: LLMClient = AnthropicLLMClient(model=model)
        response = await decompose(scenario.query, scenario.session_ctx, llm)
    else:
        response = scenario.placeholder_response

    response_json = response.model_dump(mode="json")
    # granularities/variables are Python sets -- dumped as lists in
    # whatever order the set happens to iterate, which varies run to run
    # under hash randomization. Sort them so regenerating a fixture with
    # unchanged inputs produces byte-identical JSON.
    response_json["granularities"] = sorted(response_json["granularities"])
    response_json["variables"] = sorted(response_json["variables"])

    return {
        "name": scenario.name,
        "query": scenario.query,
        "session_ctx": scenario.session_ctx.model_dump(mode="json"),
        "system": DECOMPOSE_SYSTEM_PROMPT,
        "user": user,
        "response": response_json,
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
