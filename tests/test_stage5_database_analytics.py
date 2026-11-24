from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.analytics.comparison import compare_station_observations
from src.analytics.history import compute_historical_analytics
from src.api.waqi_client import AqiReading
from src.database.models import initialize_database
from src.database.repository import (
    get_active_alerts,
    get_latest_observations_per_station,
    get_observations,
    get_observations_by_date_range,
    get_observations_by_location,
    save_observation_bundle,
)


def _sample_reading(
    station: str = "Station Alpha",
    city: str = "CityA",
    obs_time: str = "2026-11-24T08:00:00+00:00",
    pm25: float = 95.0,
    pm10: float = 130.0,
) -> AqiReading:
    return AqiReading(
        query=city,
        station_name=station,
        aqi=150,
        aqi_raw=150,
        dominant_pollutant="pm25",
        pollutants={
            "pm25": pm25,
            "pm10": pm10,
            "no2": 45.0,
            "so2": 15.0,
            "co": 1.2,
            "o3": 40.0,
        },
        latitude=22.3,
        longitude=73.1,
        observation_time=obs_time,
    )


def test_database_insert_retrieve_and_duplicate_prevention(tmp_path: Path) -> None:
    db_file = tmp_path / "test_aqi.db"
    initialize_database(db_file)

    r1 = _sample_reading(obs_time="2026-11-23T10:00:00+00:00", pm25=95.0)
    obs_id_1, inserted_1 = save_observation_bundle(r1, db_path=db_file)
    assert inserted_1 is True
    assert obs_id_1 > 0

    # Re-inserting exact same station + observation_time (simulating Streamlit rerun) must not duplicate
    obs_id_dup, inserted_dup = save_observation_bundle(r1, db_path=db_file)
    assert inserted_dup is False
    assert obs_id_dup == obs_id_1

    # New timestamp for same station inserts cleanly
    r2 = _sample_reading(obs_time="2026-11-24T10:00:00+00:00", pm25=140.0, pm10=260.0)
    obs_id_2, inserted_2 = save_observation_bundle(r2, db_path=db_file)
    assert inserted_2 is True
    assert obs_id_2 != obs_id_1

    by_loc = get_observations_by_location("Station Alpha", db_path=db_file)
    assert len(by_loc) == 2

    by_date = get_observations_by_date_range("2026-11-24", "2026-11-24", db_path=db_file)
    assert len(by_date) == 1
    assert by_date[0]["observation_date"] == "2026-11-24"

    alerts = get_active_alerts(db_path=db_file)
    assert len(alerts) >= 1


def test_historical_analytics_and_location_comparison(tmp_path: Path) -> None:
    db_file = tmp_path / "test_analytics.db"
    ref_now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)

    r_a1 = _sample_reading("Station Alpha", "CityA", (ref_now - timedelta(days=1)).isoformat(), pm25=40.0, pm10=60.0)
    r_a2 = _sample_reading("Station Alpha", "CityA", (ref_now - timedelta(minutes=20)).isoformat(), pm25=80.0, pm10=110.0)
    r_b1 = _sample_reading("Station Beta", "CityB", (ref_now - timedelta(hours=6)).isoformat(), pm25=150.0, pm10=270.0)

    save_observation_bundle(r_a1, db_path=db_file)
    save_observation_bundle(r_a2, db_path=db_file)
    save_observation_bundle(r_b1, db_path=db_file)

    alpha_obs = get_observations(location="Station Alpha", db_path=db_file)
    hist = compute_historical_analytics(alpha_obs)
    assert hist.observation_count == 2
    assert hist.has_sufficient_trend_data is True
    assert hist.min_aqi is not None and hist.max_aqi is not None
    assert hist.max_aqi >= hist.min_aqi
    assert hist.aqi_change is not None and hist.aqi_change > 0
    assert hist.pollutant_averages["pm25"] == 60.0
    assert len(hist.daily_df) == 2
    assert len(hist.weekly_df) >= 1

    latest_all = get_latest_observations_per_station(db_path=db_file)
    comp = compare_station_observations(latest_all, reference_time=ref_now)
    assert comp.stations_compared == 2
    assert comp.highest_aqi_station == "Station Beta"
    assert comp.lowest_aqi_station == "Station Alpha"
    assert comp.has_timestamp_skew_or_stale is True
    assert any("stale" in w.lower() or "skew" in w.lower() for w in comp.timestamp_warnings)