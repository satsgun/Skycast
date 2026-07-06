import asyncio

import pytest
from pydantic import BaseModel

from skycast.llm.client import LLMClient


class _Canned(BaseModel):
    value: str


class _FakeClient(LLMClient):
    async def get_structured(
        self, *, system: str, user: str, schema: type[BaseModel], tool_name: str
    ) -> BaseModel:
        return _Canned(value=f"{system}:{user}:{schema.__name__}:{tool_name}")


def test_llm_client_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        LLMClient()


def test_concrete_subclass_implementing_get_structured_can_be_instantiated() -> None:
    client = _FakeClient()
    assert isinstance(client, LLMClient)


def test_fake_client_get_structured_returns_validated_schema_instance() -> None:
    client = _FakeClient()
    result = asyncio.run(
        client.get_structured(
            system="sys prompt",
            user="user query",
            schema=_Canned,
            tool_name="emit_canned",
        )
    )
    assert isinstance(result, _Canned)
    assert result.value == "sys prompt:user query:_Canned:emit_canned"
