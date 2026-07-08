"""Shared HTTP fetch + error mapping for Open-Meteo endpoints.

Both geocode() (19.3) and fetch_forecast() (19.4) hit a GET endpoint
and need identical handling: transport failures, the documented
{"error": true} body, malformed JSON, and any other non-2xx response
all become ProviderError. Centralized so that mapping exists once.
"""

import httpx

from skycast.providers.errors import ProviderError


async def get_json(client: httpx.AsyncClient, url: str, *, params: dict) -> dict:
    try:
        response = await client.get(url, params=params)
    except httpx.HTTPError as exc:
        raise ProviderError(
            f"Open-Meteo request failed: {exc}", reason=type(exc).__name__
        ) from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise ProviderError(
            "Open-Meteo returned a malformed response", reason="malformed_response"
        ) from exc

    if body.get("error"):
        raise ProviderError(
            body.get("reason", "Open-Meteo returned an error"), reason="provider_error"
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ProviderError(
            f"Open-Meteo returned HTTP {response.status_code}", reason="http_error"
        ) from exc

    return body
