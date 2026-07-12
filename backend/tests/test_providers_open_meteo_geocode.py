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
                # Deliberately non-null: a null population here alongside
                # Tokyo's would trigger _drop_unpopulated_noise (#91),
                # which isn't what this test is about -- see the dedicated
                # populated/unpopulated-mix tests below for that behavior.
                "population": 8000000,
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
            population=8000000,
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


def test_populated_and_unpopulated_mix_drops_unpopulated() -> None:
    # Mirrors Open-Meteo's real response for "NYC": one legitimate,
    # heavily-populated match alongside obscure population-less villages
    # that happen to share a letter-for-letter prefix (Issue #91).
    body = {
        "results": [
            {
                "id": 5128581,
                "name": "New York",
                "latitude": 40.71427,
                "longitude": -74.00597,
                "country": "United States",
                "population": 8804190,
            },
            {
                "id": 2687834,
                "name": "Nyckleby",
                "latitude": 58.16667,
                "longitude": 12.28333,
                "country": "Sweden",
                "population": None,
            },
            {
                "id": 2687847,
                "name": "Nyckelby",
                "latitude": 60.47369,
                "longitude": 15.48597,
                "country": "Sweden",
                "population": None,
            },
        ]
    }
    client = _client(_json_handler(200, body))

    result = _run(geocode(client, "NYC"))

    assert [loc.name for loc in result] == ["New York"]


def test_all_unpopulated_results_are_kept_unfiltered() -> None:
    # Mirrors Open-Meteo's real response for "LA": every candidate is
    # population-less, so there's no populated entry to prefer -- nothing
    # gets dropped (this fix deliberately does not touch this case).
    body = {
        "results": [
            {"id": 1, "name": "La", "latitude": 11.7, "longitude": 104.5, "population": None},
            {"id": 2, "name": "Lâ", "latitude": 14.8, "longitude": -16.0, "population": None},
            {"id": 3, "name": "La", "latitude": 7.0, "longitude": -11.3, "population": None},
        ]
    }
    client = _client(_json_handler(200, body))

    result = _run(geocode(client, "LA"))

    assert len(result) == 3


def test_all_populated_results_are_kept_unfiltered() -> None:
    body = {
        "results": [
            {"id": 1, "name": "Springfield", "latitude": 39.78, "longitude": -89.65, "population": 170188},
            {"id": 2, "name": "Springfield", "latitude": 37.21, "longitude": -93.30, "population": 114394},
        ]
    }
    client = _client(_json_handler(200, body))

    result = _run(geocode(client, "Springfield"))

    assert len(result) == 2


def test_single_unpopulated_result_is_kept() -> None:
    body = {
        "results": [
            {"id": 1, "name": "Nowhere", "latitude": 0.0, "longitude": 0.0, "population": None},
        ]
    }
    client = _client(_json_handler(200, body))

    result = _run(geocode(client, "Nowhere"))

    assert len(result) == 1


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
