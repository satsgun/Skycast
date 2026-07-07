"""Pipeline stage 1: decompose (Task 14.5).

Turns a natural-language query + SessionContext into a DataNeedsSpec via
the LLMClient seam. Imports only LLMClient + domain/pipeline types --
never aisuite/anthropic/any vendor SDK directly (ADR-0002-style seam
discipline, Task 14's stated constraint).
"""

from typing import cast

from skycast.llm.client import LLMClient
from skycast.pipeline.data_needs import DataNeedsSpec
from skycast.pipeline.prompts import DECOMPOSE_SYSTEM_PROMPT
from skycast.pipeline.session_context import SessionContext

_TOOL_NAME = "emit_data_needs"


async def decompose(
    query: str, session_ctx: SessionContext, llm: LLMClient
) -> DataNeedsSpec:
    """Raises LLMError / StructuredOutputError -- propagated from `llm`
    unchanged; the caller (orchestrator, Phase 5) maps them to SSE errors.
    """
    user = _build_user_message(query, session_ctx)
    result = await llm.get_structured(
        system=DECOMPOSE_SYSTEM_PROMPT,
        user=user,
        schema=DataNeedsSpec,
        tool_name=_TOOL_NAME,
    )
    return cast(DataNeedsSpec, result)


def _build_user_message(query: str, session_ctx: SessionContext) -> str:
    lines = [f"Query: {query}", f"Current time: {session_ctx.now.isoformat()}"]
    if session_ctx.default_location is not None:
        lines.append(
            f"Default location: {session_ctx.default_location.name} "
            f"(timezone: {session_ctx.default_location.timezone})"
        )
    if session_ctx.units_hint is not None:
        lines.append(f"Units hint: {session_ctx.units_hint}")
    if session_ctx.carried_location_name is not None:
        lines.append(
            f"Carried location from prior turn: {session_ctx.carried_location_name}"
        )
    if session_ctx.carried_window is not None:
        lines.append(
            "Carried time window from prior turn: "
            f"{session_ctx.carried_window.start.isoformat()} to "
            f"{session_ctx.carried_window.end.isoformat()}"
        )
    return "\n".join(lines)
