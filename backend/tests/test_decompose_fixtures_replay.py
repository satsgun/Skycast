import asyncio
import json
from pathlib import Path

import pytest

from skycast.llm.fake_client import FakeLLMClient
from skycast.pipeline.data_needs import DataNeedsSpec
from skycast.pipeline.decompose import decompose
from skycast.pipeline.prompts import DECOMPOSE_SYSTEM_PROMPT
from skycast.pipeline.session_context import SessionContext

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "decompose"


def _fixture_paths() -> list[Path]:
    return sorted(_FIXTURES_DIR.glob("*.json"))


def test_between_five_and_ten_fixtures_exist() -> None:
    assert 5 <= len(_fixture_paths()) <= 10


@pytest.mark.parametrize("fixture_path", _fixture_paths(), ids=lambda p: p.stem)
def test_fixture_replays_and_validates(fixture_path: Path) -> None:
    fixture = json.loads(fixture_path.read_text())

    assert fixture["system"] == DECOMPOSE_SYSTEM_PROMPT, (
        f"{fixture_path.name} was recorded against a different system prompt; "
        "re-run scripts/record_decompose_fixtures.py --live to refresh it"
    )

    session_ctx = SessionContext.model_validate(fixture["session_ctx"])
    expected_spec = DataNeedsSpec.model_validate(fixture["response"])

    captured: dict = {}

    def responder(*, system, user, schema, tool_name):
        captured["system"] = system
        captured["user"] = user
        return expected_spec

    replay_client = FakeLLMClient(responder)

    result = asyncio.run(decompose(fixture["query"], session_ctx, replay_client))

    assert result == expected_spec
    assert captured["system"] == DECOMPOSE_SYSTEM_PROMPT
    assert captured["user"] == fixture["user"], (
        f"{fixture_path.name}'s recorded user message no longer matches "
        "decompose's current message-building logic; re-run "
        "scripts/record_decompose_fixtures.py"
    )
