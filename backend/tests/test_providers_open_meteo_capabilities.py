from skycast.domain.provider import WeatherVariable
from skycast.providers.open_meteo.capabilities import capabilities


def test_max_forecast_days_is_16() -> None:
    assert capabilities().max_forecast_days == 16


def test_available_variables_is_every_weather_variable() -> None:
    assert capabilities().available_variables == set(WeatherVariable)


def test_supports_geocoding_is_true() -> None:
    assert capabilities().supports_geocoding is True


def test_rate_limit_per_minute_is_none() -> None:
    assert capabilities().rate_limit_per_minute is None
