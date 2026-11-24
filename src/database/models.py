from pathlib import Path
from src.database.connection import get_connection

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS stations (
    station_id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_name TEXT NOT NULL,
    query_city TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    created_at_utc TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at_utc TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(station_name, query_city)
);

CREATE TABLE IF NOT EXISTS aqi_observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL,
    observation_time TEXT NOT NULL,
    observation_date TEXT NOT NULL,
    waqi_reported_aqi REAL,
    calculated_aqi INTEGER,
    aqi_category TEXT NOT NULL,
    dominant_pollutant TEXT,
    highest_measured_pollutant TEXT,
    completeness_ratio REAL NOT NULL DEFAULT 0.0,
    is_valid INTEGER NOT NULL DEFAULT 1,
    is_stale INTEGER NOT NULL DEFAULT 0,
    recorded_at_utc TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (station_id) REFERENCES stations(station_id) ON DELETE CASCADE,
    UNIQUE(station_id, observation_time)
);

CREATE TABLE IF NOT EXISTS pollutant_measurements (
    measurement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL,
    pollutant TEXT NOT NULL,
    raw_value REAL,
    sub_index REAL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (observation_id) REFERENCES aqi_observations(observation_id) ON DELETE CASCADE,
    UNIQUE(observation_id, pollutant)
);

CREATE TABLE IF NOT EXISTS pollutant_analyses (
    analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL UNIQUE,
    raw_vs_subindex_differs INTEGER NOT NULL DEFAULT 0,
    combinations_json TEXT NOT NULL DEFAULT '[]',
    source_insights_json TEXT NOT NULL DEFAULT '[]',
    created_at_utc TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (observation_id) REFERENCES aqi_observations(observation_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS health_advisories (
    advisory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL,
    sensitivity_group TEXT NOT NULL,
    urgency_level TEXT NOT NULL,
    general_precautions_json TEXT NOT NULL,
    sensitive_precautions_json TEXT NOT NULL,
    exposure_suggestions_json TEXT NOT NULL,
    outdoor_precautions_json TEXT NOT NULL,
    rules_applied_json TEXT NOT NULL,
    created_at_utc TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (observation_id) REFERENCES aqi_observations(observation_id) ON DELETE CASCADE,
    UNIQUE(observation_id, sensitivity_group)
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL,
    observation_id INTEGER,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at_utc TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (station_id) REFERENCES stations(station_id) ON DELETE CASCADE,
    FOREIGN KEY (observation_id) REFERENCES aqi_observations(observation_id) ON DELETE SET NULL,
    UNIQUE(station_id, observation_id, alert_type, title)
);

CREATE INDEX IF NOT EXISTS idx_obs_station_time ON aqi_observations(station_id, observation_time);
CREATE INDEX IF NOT EXISTS idx_obs_date ON aqi_observations(observation_date);
CREATE INDEX IF NOT EXISTS idx_meas_obs ON pollutant_measurements(observation_id);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(is_active, created_at_utc);
"""


def initialize_database(db_path: Path | str | None = None) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)