import asyncio

import httpx
import pytest

from skycast.domain.location import Location
from skycast.providers.errors import ProviderError
from skycast.providers.open_meteo.geocode import geocode


def _run(coro):
    return asyncio.run(coro)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _json_handler(status_code: int, body: dict | list):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    return handler


def test_multi_result_response_maps_to_locations() -> None:
    body = {
        "results": [
            {
                "id": 1850147,
                "name": "Tokyo",
                "latitude": 35.6895,
                "longitude": 139.69171,
                "country": "Japan",
                "country_code": "JP",
                "admin1": "Tokyo",
                "admin2": None,
                "population": 8336599,
                "timezone": "Asia/Tokyo",
            },
            {
                "id": 5128581,
                "name": "New York",
                "latitude": 40.71427,
                "longitude": -74.00597,
            },
        ]
    }
    client = _client(_json_handler(200, body))

    result = _run(geocode(client, "Tokyo"))

    assert result == [
        Location(
            id="1850147",
            name="Tokyo",
            latitude=35.6895,
            longitude=139.69171,
            country="Japan",
            country_code="JP",
            admin1="Tokyo",
            admin2=None,
            population=8336599,
            timezone="Asia/Tokyo",
        ),
        Location(
            id="5128581",
            name="New York",
            latitude=40.71427,
            longitude=-74.00597,
        ),
    ]


def test_minimal_result_leaves_optional_fields_none() -> None:
    body = {"results": [{"id": 1, "name": "Nowhere", "latitude": 0.0, "longitude": 0.0}]}
    client = _client(_json_handler(200, body))

    result = _run(geocode(client, "Nowhere"))

    assert result == [Location(id="1", name="Nowhere", latitude=0.0, longitude=0.0)]


def test_missing_results_key_returns_empty_list() -> None:
    client = _client(_json_handler(200, {"generationtime_ms": 0.1}))

    assert _run(geocode(client, "Nowhereville")) == []


def test_empty_results_list_returns_empty_list() -> None:
    client = _client(_json_handler(200, {"results": []}))

    assert _run(geocode(client, "Nowhereville")) == []


def test_documented_error_body_raises_provider_error_with_api_reason() -> None:
    client = _client(
        _json_handler(400, {"error": True, "reason": "Cannot initialize name"})
    )

    with pytest.raises(ProviderError) as exc_info:
        _run(geocode(client, ""))

    assert "Cannot initialize name" in str(exc_info.value)


def test_non_json_body_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    client = _client(handler)

    with pytest.raises(ProviderError):
        _run(geocode(client, "Tokyo"))


def test_non_2xx_without_documented_error_shape_raises_provider_error() -> None:
    client = _client(_json_handler(500, {}))

    with pytest.raises(ProviderError):
        _run(geocode(client, "Tokyo"))


def test_transport_failure_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = _client(handler)

    with pytest.raises(ProviderError):
        _run(geocode(client, "Tokyo"))


def test_request_sends_name_and_count_as_query_params() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"results": []})

    client = _client(handler)

    _run(geocode(client, "Springfield"))

    assert len(captured) == 1
    request = captured[0]
    assert request.url.params["name"] == "Springfield"
    assert request.url.params["count"] == "5"
