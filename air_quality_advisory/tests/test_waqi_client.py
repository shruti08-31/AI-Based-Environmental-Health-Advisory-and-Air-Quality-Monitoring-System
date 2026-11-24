from pathlib import Path
from unittest.mock import MagicMock
import requests
import pytest

from config import AppConfig
from src.api.waqi_client import WaqiClient, WaqiClientError, WaqiErrorKind


def _make_config(token: str = "test_valid_token") -> AppConfig:
    base = Path(__file__).resolve().parent.parent
    return AppConfig(
        app_name="Test AQI App",
        app_env="test",
        waqi_api_token=token,
        request_timeout_seconds=5,
        default_location="Vadodara",
        base_dir=base,
        data_dir=base / "data",
        assets_dir=base / "assets",
    )


def _mock_response(status_code: int = 200, json_data: object = None, raw_text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = raw_text
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("Invalid JSON")
    return resp


def test_get_city_aqi_success_with_all_pollutants() -> None:
    session = MagicMock()
    session.get.return_value = _mock_response(
        200,
        {
            "status": "ok",
            "data": {
                "aqi": 84,
                "dominentpol": "pm25",
                "city": {"name": "Vadodara, India", "geo": [22.3072, 73.1812]},
                "time": {"iso": "2026-11-24T06:00:00+00:00"},
                "iaqi": {
                    "pm25": {"v": 84},
                    "pm10": {"v": 112},
                    "no2": {"v": 22.5},
                    "so2": {"v": 9.1},
                    "co": {"v": 6.4},
                    "o3": {"v": 31.0},
                },
            },
        },
    )
    client = WaqiClient(app_config=_make_config(), session=session)
    reading = client.get_city_aqi("Vadodara")

    assert reading.aqi == 84
    assert reading.station_name == "Vadodara, India"
    assert reading.latitude == 22.3072
    assert reading.longitude == 73.1812
    assert reading.observation_time == "2026-11-24T06:00:00+00:00"
    assert reading.pollutants["pm25"] == 84.0
    assert reading.pollutants["o3"] == 31.0
    assert reading.missing_pollutants == []


def test_get_city_aqi_missing_pollutants_kept_none() -> None:
    session = MagicMock()
    session.get.return_value = _mock_response(
        200,
        {
            "status": "ok",
            "data": {
                "aqi": 60,
                "city": {"name": "Station A", "geo": [22.3, 73.1]},
                "time": {"iso": "2026-11-24T06:00:00+00:00"},
                "iaqi": {"pm25": {"v": 60}},
            },
        },
    )
    client = WaqiClient(app_config=_make_config(), session=session)
    reading = client.get_city_aqi("Station A")

    assert reading.pollutants["pm25"] == 60.0
    assert reading.pollutants["so2"] is None
    assert "so2" in reading.missing_pollutants


def test_missing_token_raises_auth_error() -> None:
    session = MagicMock()
    client = WaqiClient(app_config=_make_config(token=""), session=session)
    with pytest.raises(WaqiClientError) as exc_info:
        client.get_city_aqi("Vadodara")
    assert exc_info.value.kind == WaqiErrorKind.AUTH_ERROR


def test_http_401_raises_auth_error() -> None:
    session = MagicMock()
    session.get.return_value = _mock_response(401, {"status": "error", "data": "Invalid key"})
    client = WaqiClient(app_config=_make_config(), session=session)
    with pytest.raises(WaqiClientError) as exc_info:
        client.get_city_aqi("Vadodara")
    assert exc_info.value.kind == WaqiErrorKind.AUTH_ERROR


def test_http_429_raises_rate_limit() -> None:
    session = MagicMock()
    session.get.return_value = _mock_response(429, {"status": "error", "data": "Quota exceeded"})
    client = WaqiClient(app_config=_make_config(), session=session)
    with pytest.raises(WaqiClientError) as exc_info:
        client.get_city_aqi("Vadodara")
    assert exc_info.value.kind == WaqiErrorKind.RATE_LIMIT


def test_timeout_and_network_errors() -> None:
    session = MagicMock()
    session.get.side_effect = requests.Timeout("timed out")
    client = WaqiClient(app_config=_make_config(), session=session)
    with pytest.raises(WaqiClientError) as t_exc:
        client.get_city_aqi("Vadodara")
    assert t_exc.value.kind == WaqiErrorKind.TIMEOUT

    session.get.side_effect = requests.ConnectionError("conn failed")
    with pytest.raises(WaqiClientError) as n_exc:
        client.get_city_aqi("Vadodara")
    assert n_exc.value.kind == WaqiErrorKind.NETWORK_ERROR


def test_invalid_city_and_search_cities() -> None:
    session = MagicMock()
    session.get.return_value = _mock_response(200, {"status": "error", "data": "Unknown station"})
    client = WaqiClient(app_config=_make_config(), session=session)
    with pytest.raises(WaqiClientError) as exc_info:
        client.get_city_aqi("NoSuchCityXYZ")
    assert exc_info.value.kind == WaqiErrorKind.NOT_FOUND

    session.get.return_value = _mock_response(
        200,
        {
            "status": "ok",
            "data": [
                {
                    "uid": 1001,
                    "aqi": "75",
                    "station": {"name": "Vadodara Station", "geo": [22.3, 73.1]},
                    "time": {"stime": "2026-11-24 11:00:00"},
                }
            ],
        },
    )
    matches = client.search_cities("Vadodara")
    assert len(matches) == 1
    assert matches[0].uid == 1001
    assert matches[0].station_name == "Vadodara Station"


def test_invalid_json_raises_invalid_response() -> None:
    session = MagicMock()
    session.get.return_value = _mock_response(200, json_data=None, raw_text="<html>bad</html>")
    client = WaqiClient(app_config=_make_config(), session=session)
    with pytest.raises(WaqiClientError) as exc_info:
        client.get_city_aqi("Vadodara")
    assert exc_info.value.kind == WaqiErrorKind.INVALID_RESPONSE