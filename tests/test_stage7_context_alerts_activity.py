from pathlib import Path
from unittest.mock import MagicMock
import requests

from src.activity.activity_advisor import SUPPORTED_ACTIVITIES, advise_activity
from src.alerts.alert_engine import (
    acknowledge_alert,
    evaluate_alert_candidates,
    list_stored_alerts,
    persist_alerts,
)
from src.api.waqi_client import AqiReading
from src.api.weather_client import WeatherClient, WeatherClientError, WeatherErrorKind
from config import AppConfig


def _test_cfg() -> AppConfig:
    base = Path(__file__).resolve().parent.parent
    return AppConfig(
        app_name="Test App",
        app_env="test",
        waqi_api_token="tok",
        request_timeout_seconds=5,
        default_location="Delhi",
        base_dir=base,
        data_dir=base / "data",
        assets_dir=base / "assets",
    )


def test_weather_client_success_and_independent_failure() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "current": {
            "time": "2026-11-24T13:00",
            "temperature_2m": 27.5,
            "relative_humidity_2m": 48.0,
            "wind_speed_10m": 6.2,
            "wind_direction_10m": 290.0,
            "rain": 0.0,
            "surface_pressure": 1008.4,
        }
    }
    session = MagicMock()
    session.get.return_value = mock_resp

    client = WeatherClient(app_config=_test_cfg(), session=session)
    w = client.get_current_weather(28.6139, 77.2090)
    assert w.temperature_c == 27.5
    assert w.wind_speed_kmh == 6.2
    assert w.surface_pressure_hpa == 1008.4
    assert w.missing_fields == []

    # Missing coordinates rejected cleanly
    try:
        client.get_current_weather(None, 77.2090)
        assert False, "Expected WeatherClientError for missing coordinate"
    except WeatherClientError as exc:
        assert exc.kind == WeatherErrorKind.INVALID_COORDINATES

    # Weather timeout does not touch WAQI
    session.get.side_effect = requests.Timeout("weather down")
    try:
        client.get_current_weather(28.6139, 77.2090)
        assert False, "Expected WeatherClientError on timeout"
    except WeatherClientError as exc:
        assert exc.kind == WeatherErrorKind.TIMEOUT


def test_smart_alerts_deduplication_and_acknowledgement(tmp_path: Path) -> None:
    db_file = tmp_path / "alerts_test.db"
    reading = AqiReading(
        query="Delhi",
        station_name="ITO, Delhi",
        aqi=240,
        aqi_raw=240,
        dominant_pollutant="pm25",
        pollutants={"pm25": 165.0, "pm10": 260.0, "no2": 90.0, "so2": 15.0, "co": 2.5, "o3": 40.0},
        latitude=28.6289,
        longitude=77.2405,
        observation_time="2026-11-24T07:00:00+00:00",
    )
    prev_obs = [
        {
            "station_name": "ITO, Delhi",
            "observation_time": "2026-11-24T06:00:00+00:00",
            "calculated_aqi": 90,
            "pm25": 55.0,
            "pm10": 85.0,
            "no2": 30.0,
            "so2": 10.0,
            "co": 1.0,
            "o3": 25.0,
            "is_valid": 1,
        }
    ]

    cands = evaluate_alert_candidates(reading, previous_observations=prev_obs)
    assert len(cands) >= 2

    first_added = persist_alerts(cands, query_city="Delhi", db_path=db_file)
    assert first_added == len(cands)

    # Duplicate persist must insert 0 new rows
    second_added = persist_alerts(cands, query_city="Delhi", db_path=db_file)
    assert second_added == 0

    stored = list_stored_alerts(include_acknowledged=True, db_path=db_file)
    assert len(stored) == len(cands)

    target_id = int(stored[0]["alert_id"])
    acknowledge_alert(target_id, db_path=db_file)
    unack_after = list_stored_alerts(include_acknowledged=False, db_path=db_file)
    assert len(unack_after) == len(stored) - 1


def test_activity_advisor_all_activities() -> None:
    for act in SUPPORTED_ACTIVITIES:
        g_good = advise_activity(act, "Good", calculated_aqi=35, pollutants={"pm25": 18.0})
        assert g_good.recommendation
        assert g_good.precautions
        assert g_good.alternative_activity
        assert g_good.explanation
        assert "guarantee" not in g_good.disclaimer.lower() or "does not guarantee" in g_good.disclaimer.lower()

        g_severe = advise_activity(act, "Severe", calculated_aqi=430, pollutants={"pm25": 320.0})
        assert g_severe.recommendation