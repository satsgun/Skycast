import asyncio
import json
from pathlib import Path

import pytest

from skycast.domain.forecast import Forecast
from skycast.llm.fake_client import FakeLLMClient
from skycast.pipeline.data_needs import QueryIntent
from skycast.pipeline.prompts import SYNTHESIZE_SYSTEM_PROMPT
from skycast.pipeline.synthesis_output import SynthesisOutput
from skycast.pipeline.synthesize_stage import synthesize
from skycast.sse.payloads import Highlight

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthesize"


def _fixture_paths() -> list[Path]:
    return sorted(_FIXTURES_DIR.glob("*.json"))


def test_between_four_and_ten_fixtures_exist() -> None:
    assert 4 <= len(_fixture_paths()) <= 10


@pytest.mark.parametrize("fixture_path", _fixture_paths(), ids=lambda p: p.stem)
def test_fixture_replays_and_validates(fixture_path: Path) -> None:
    fixture = json.loads(fixture_path.read_text())

    assert fixture["system"] == SYNTHESIZE_SYSTEM_PROMPT, (
        f"{fixture_path.name} was recorded against a different system prompt; "
        "re-run scripts/record_synthesize_fixtures.py --live to refresh it"
    )

    forecasts = [Forecast.model_validate(f) for f in fixture["forecasts"]]
    intent = QueryIntent(fixture["intent"])
    recorded_output = SynthesisOutput.model_validate(fixture["response"])

    captured: dict = {}

    def responder(*, system, user, schema, tool_name):
        captured["system"] = system
        captured["user"] = user
        return recorded_output

    replay_client = FakeLLMClient(responder)

    payload = asyncio.run(synthesize(fixture["query"], forecasts, intent, replay_client))

    assert payload.text
    assert payload.card.forecasts == forecasts
    assert payload.card.highlight is None or isinstance(payload.card.highlight, Highlight)
    assert captured["system"] == SYNTHESIZE_SYSTEM_PROMPT
    assert captured["user"] == fixture["user"], (
        f"{fixture_path.name}'s recorded user message no longer matches "
        "synthesize's current message-building logic; re-run "
        "scripts/record_synthesize_fixtures.py"
    )
