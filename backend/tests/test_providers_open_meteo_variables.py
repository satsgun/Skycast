from skycast.domain.provider import WeatherVariable
from skycast.providers.open_meteo.variables import daily_params, hourly_params


def test_hourly_params_includes_weather_code_and_requested_variable() -> None:
    assert hourly_params({WeatherVariable.TEMPERATURE}) == [
        "weather_code",
        "temperature_2m",
    ]


def test_hourly_params_always_includes_weather_code_even_with_nothing_requested() -> (
    None
):
    assert hourly_params(set()) == ["weather_code"]


def test_hourly_params_covers_every_variable_without_duplicating_weather_code() -> (
    None
):
    result = hourly_params(set(WeatherVariable))

    assert result == [
        "weather_code",
        "temperature_2m",
        "apparent_temperature",
        "precipitation_probability",
        "precipitation",
        "wind_speed_10m",
    ]


def test_daily_params_includes_always_block_and_temperature_max_min() -> None:
    assert daily_params({WeatherVariable.TEMPERATURE}) == [
        "weather_code",
        "sunrise",
        "sunset",
        "temperature_2m_max",
        "temperature_2m_min",
    ]


def test_daily_params_drops_feels_like_entirely() -> None:
    assert daily_params({WeatherVariable.FEELS_LIKE}) == [
        "weather_code",
        "sunrise",
        "sunset",
    ]


def test_daily_params_for_every_variable_has_no_apparent_temperature_entries() -> None:
    result = daily_params(set(WeatherVariable))

    assert "apparent_temperature_max" not in result
    assert "apparent_temperature_min" not in result
    assert result == [
        "weather_code",
        "sunrise",
        "sunset",
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_probability_max",
        "precipitation_sum",
        "wind_speed_10m_max",
    ]


def test_daily_params_with_nothing_requested_is_just_the_always_block() -> None:
    assert daily_params(set()) == ["weather_code", "sunrise", "sunset"]


def test_param_order_is_deterministic_regardless_of_set_insertion_order() -> None:
    a = hourly_params({WeatherVariable.WIND_SPEED, WeatherVariable.TEMPERATURE})
    b = hourly_params({WeatherVariable.TEMPERATURE, WeatherVariable.WIND_SPEED})

    assert a == b == ["weather_code", "temperature_2m", "wind_speed_10m"]
