from datetime import datetime, timedelta, timezone

from src.api.waqi_client import AqiReading
from src.validation.data_validation import validate_aqi_reading


def _base_reading(**overrides) -> AqiReading:
    ref_now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
    defaults = {
        "query": "Vadodara",
        "station_name": "Vadodara, India",
        "aqi": 72,
        "aqi_raw": 72,
        "dominant_pollutant": "pm25",
        "pollutants": {
            "pm25": 72.0,
            "pm10": 95.0,
            "no2": 18.0,
            "so2": 7.5,
            "co": 5.2,
            "o3": 28.0,
        },
        "latitude": 22.3072,
        "longitude": 73.1812,
        "observation_time": (ref_now - timedelta(minutes=15)).isoformat(),
        "missing_fields": [],
        "missing_pollutants": [],
    }
    defaults.update(overrides)
    return AqiReading(**defaults)


def test_valid_fresh_reading() -> None:
    ref_now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
    reading = _base_reading()
    result = validate_aqi_reading(reading, reference_time=ref_now)
    assert result.is_valid is True
    assert result.errors == []
    assert result.is_stale is False
    assert result.completeness_ratio == 1.0


def test_negative_measurement_and_missing_pollutants() -> None:
    ref_now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
    reading = _base_reading(
        aqi=-5,
        pollutants={
            "pm25": 50.0,
            "pm10": None,
            "no2": -2.0,
            "so2": None,
            "co": None,
            "o3": None,
        },
    )
    result = validate_aqi_reading(reading, reference_time=ref_now)
    assert result.is_valid is False
    assert any("Negative AQI" in err for err in result.errors)
    assert any("negative measurement" in err for err in result.errors)
    assert "pm10" in result.missing_pollutants
    assert result.completeness_ratio < 1.0


def test_missing_coordinates_and_stale_timestamp() -> None:
    ref_now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
    old_ts = (ref_now - timedelta(hours=5)).isoformat()
    reading = _base_reading(latitude=None, longitude=None, observation_time=old_ts)
    result = validate_aqi_reading(reading, reference_time=ref_now, stale_after_minutes=120)
    assert result.is_stale is True
    assert result.observation_age_minutes == 300.0
    assert any("coordinates" in w.lower() for w in result.warnings)
    assert any("stale" in w.lower() for w in result.warnings)


def test_invalid_timestamp_warning() -> None:
    ref_now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
    reading = _base_reading(observation_time="not-a-timestamp")
    result = validate_aqi_reading(reading, reference_time=ref_now)
    assert any("timestamp" in w.lower() for w in result.warnings)