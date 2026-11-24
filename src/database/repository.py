from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from src.api.waqi_client import POLLUTANT_KEYS, AqiReading
from src.core.aqi_engine import AqiEngineResult, evaluate_aqi_from_reading
from src.core.health_engine import HealthAdvisoryResult, SensitivityGroup, generate_health_advisory
from src.database.connection import DatabaseError, get_connection
from src.database.json_sync import (
    hydrate_sqlite_from_json,
    reading_to_json_record,
    save_observation_to_json,
)
from src.database.models import initialize_database
from src.intelligence.pollutant_analysis import PollutantAnalysisResult, analyze_pollutants_from_reading
from src.intelligence.source_insights import SourceInsight, generate_source_insights
from src.validation.data_validation import ValidationResult, validate_aqi_reading

_HYDRATED_DB_KEYS: set[str] = set()


def _db_cache_key(db_path: Path | str | None) -> str:
    return str(Path(db_path).resolve()) if db_path is not None else "__default__"


def _ensure_hydrated_if_empty(db_path: Path | str | None = None) -> None:
    """
    If `aqi_observations` currently has 0 rows after initialization, hydrate SQLite
    from `data/observations_store.json` at most once per DB target per process.
    """
    key = _db_cache_key(db_path)
    if key in _HYDRATED_DB_KEYS:
        return

    with get_connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM aqi_observations").fetchone()
        row_count = int(row["cnt"]) if row is not None else 0

    _HYDRATED_DB_KEYS.add(key)
    if row_count == 0:
        hydrate_sqlite_from_json(db_path=db_path)


def _normalize_obs_date(observation_time: str | None) -> tuple[str, str]:
    if observation_time and observation_time.strip():
        cleaned = observation_time.strip()
        date_part = cleaned[:10] if len(cleaned) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return cleaned, date_part
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:00+00:00")
    return now_iso, now_iso[:10]


def _upsert_station(
    conn: sqlite3.Connection,
    station_name: str,
    query_city: str,
    latitude: float | None,
    longitude: float | None,
) -> int:
    conn.execute(
        """
        INSERT INTO stations (station_name, query_city, latitude, longitude)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(station_name, query_city) DO UPDATE SET
            latitude = COALESCE(excluded.latitude, stations.latitude),
            longitude = COALESCE(excluded.longitude, stations.longitude),
            updated_at_utc = datetime('now')
        """,
        (station_name, query_city, latitude, longitude),
    )
    row = conn.execute(
        "SELECT station_id FROM stations WHERE station_name = ? AND query_city = ?",
        (station_name, query_city),
    ).fetchone()
    if row is None:
        raise DatabaseError("Failed to retrieve station_id after upsert.")
    return int(row["station_id"])


def save_observation_bundle(
    reading: AqiReading,
    validation: ValidationResult | None = None,
    aqi_result: AqiEngineResult | None = None,
    analysis: PollutantAnalysisResult | None = None,
    source_insights: list[SourceInsight] | None = None,
    advisory: HealthAdvisoryResult | None = None,
    db_path: Path | str | None = None,
    _sync_json: bool = True,
) -> tuple[int, bool]:
    """
    Persist an AQI observation along with pollutant measurements, analysis, advisory, and alerts.
    Returns (observation_id, inserted_new) where inserted_new is False if (station, observation_time) already existed.
    """
    initialize_database(db_path)

    val = validation or validate_aqi_reading(reading)
    aqi_res = aqi_result or evaluate_aqi_from_reading(reading)
    pol_analysis = analysis or analyze_pollutants_from_reading(reading)
    insights = source_insights if source_insights is not None else generate_source_insights(pol_analysis)
    adv = advisory or generate_health_advisory(
        category=aqi_res.category,
        sensitivity_group=SensitivityGroup.GENERAL,
        dominant_pollutant=aqi_res.dominant_pollutant,
    )

    station_label = (reading.station_name or reading.query or "Unknown Station").strip()
    query_label = (reading.query or station_label).strip()
    obs_time, obs_date = _normalize_obs_date(reading.observation_time)

    with get_connection(db_path) as conn:
        station_id = _upsert_station(
            conn=conn,
            station_name=station_label,
            query_city=query_label,
            latitude=reading.latitude,
            longitude=reading.longitude,
        )

        existing = conn.execute(
            "SELECT observation_id FROM aqi_observations WHERE station_id = ? AND observation_time = ?",
            (station_id, obs_time),
        ).fetchone()
        if existing is not None:
            return int(existing["observation_id"]), False

        cursor = conn.execute(
            """
            INSERT INTO aqi_observations (
                station_id,
                observation_time,
                observation_date,
                waqi_reported_aqi,
                calculated_aqi,
                aqi_category,
                dominant_pollutant,
                highest_measured_pollutant,
                completeness_ratio,
                is_valid,
                is_stale
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                station_id,
                obs_time,
                obs_date,
                float(reading.aqi) if reading.aqi is not None else None,
                aqi_res.calculated_aqi,
                aqi_res.category,
                aqi_res.dominant_pollutant,
                pol_analysis.highest_measured_pollutant,
                val.completeness_ratio,
                1 if val.is_valid else 0,
                1 if val.is_stale else 0,
            ),
        )
        observation_id = int(cursor.lastrowid)

        for key in POLLUTANT_KEYS:
            summ = pol_analysis.pollutant_summaries.get(key)
            raw_v = summ.raw_value if summ else reading.pollutants.get(key)
            sub_v = summ.sub_index if summ else None
            sev = summ.severity if summ else "Unavailable"
            stat = summ.status if summ else ("available" if raw_v is not None else "missing")
            conn.execute(
                """
                INSERT INTO pollutant_measurements (
                    observation_id, pollutant, raw_value, sub_index, severity, status
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (observation_id, key, raw_v, sub_v, sev, stat),
            )

        store_analysis_results(
            conn=conn,
            observation_id=observation_id,
            analysis=pol_analysis,
            source_insights=insights,
            advisory=adv,
        )

        _persist_triggered_alerts(
            conn=conn,
            station_id=station_id,
            observation_id=observation_id,
            aqi_res=aqi_res,
            analysis=pol_analysis,
        )

    if _sync_json:
        json_rec = reading_to_json_record(
            reading=reading,
            validation=val,
            aqi_result=aqi_res,
            analysis=pol_analysis,
            source_insights=insights,
            advisory=adv,
        )
        save_observation_to_json(json_rec)

    return observation_id, True


def store_analysis_results(
    conn: sqlite3.Connection,
    observation_id: int,
    analysis: PollutantAnalysisResult,
    source_insights: list[SourceInsight],
    advisory: HealthAdvisoryResult,
) -> None:
    combos_payload = [asdict(c) for c in analysis.combinations]
    insights_payload = [asdict(s) for s in source_insights]

    conn.execute(
        """
        INSERT INTO pollutant_analyses (
            observation_id, raw_vs_subindex_differs, combinations_json, source_insights_json
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(observation_id) DO UPDATE SET
            raw_vs_subindex_differs = excluded.raw_vs_subindex_differs,
            combinations_json = excluded.combinations_json,
            source_insights_json = excluded.source_insights_json
        """,
        (
            observation_id,
            1 if analysis.raw_vs_subindex_differs else 0,
            json.dumps(combos_payload),
            json.dumps(insights_payload),
        ),
    )

    conn.execute(
        """
        INSERT INTO health_advisories (
            observation_id,
            sensitivity_group,
            urgency_level,
            general_precautions_json,
            sensitive_precautions_json,
            exposure_suggestions_json,
            outdoor_precautions_json,
            rules_applied_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(observation_id, sensitivity_group) DO UPDATE SET
            urgency_level = excluded.urgency_level,
            general_precautions_json = excluded.general_precautions_json,
            sensitive_precautions_json = excluded.sensitive_precautions_json,
            exposure_suggestions_json = excluded.exposure_suggestions_json,
            outdoor_precautions_json = excluded.outdoor_precautions_json,
            rules_applied_json = excluded.rules_applied_json
        """,
        (
            observation_id,
            advisory.sensitivity_group,
            advisory.urgency_level,
            json.dumps(advisory.general_precautions),
            json.dumps(advisory.sensitive_group_precautions),
            json.dumps(advisory.exposure_reduction_suggestions),
            json.dumps(advisory.outdoor_activity_precautions),
            json.dumps(advisory.rules_applied),
        ),
    )


def _persist_triggered_alerts(
    conn: sqlite3.Connection,
    station_id: int,
    observation_id: int,
    aqi_res: AqiEngineResult,
    analysis: PollutantAnalysisResult,
) -> None:
    if aqi_res.calculated_aqi is not None and aqi_res.category in ("Poor", "Very Poor", "Severe"):
        conn.execute(
            """
            INSERT OR IGNORE INTO alerts (
                station_id, observation_id, alert_type, severity, title, message
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                station_id,
                observation_id,
                "AQI_THRESHOLD",
                aqi_res.category,
                f"{aqi_res.category} Air Quality Alert (AQI {aqi_res.calculated_aqi})",
                aqi_res.category_explanation,
            ),
        )

    for combo in analysis.combinations:
        conn.execute(
            """
            INSERT OR IGNORE INTO alerts (
                station_id, observation_id, alert_type, severity, title, message
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                station_id,
                observation_id,
                "POLLUTANT_PATTERN",
                combo.severity,
                combo.title,
                combo.summary,
            ),
        )


def list_stations(db_path: Path | str | None = None) -> list[dict[str, Any]]:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                s.station_id,
                s.station_name,
                s.query_city,
                s.latitude,
                s.longitude,
                COUNT(o.observation_id) AS observation_count,
                MAX(o.observation_time) AS latest_observation_time
            FROM stations s
            LEFT JOIN aqi_observations o ON o.station_id = s.station_id
            GROUP BY s.station_id
            ORDER BY latest_observation_time DESC, s.station_name ASC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def _hydrate_observations(conn: sqlite3.Connection, obs_rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    if not obs_rows:
        return []
    obs_ids = [int(r["observation_id"]) for r in obs_rows]
    placeholders = ",".join("?" for _ in obs_ids)
    meas_rows = conn.execute(
        f"""
        SELECT observation_id, pollutant, raw_value, sub_index, severity, status
        FROM pollutant_measurements
        WHERE observation_id IN ({placeholders})
        """,
        obs_ids,
    ).fetchall()

    meas_by_obs: dict[int, dict[str, dict[str, Any]]] = {}
    for m in meas_rows:
        oid = int(m["observation_id"])
        meas_by_obs.setdefault(oid, {})[str(m["pollutant"])] = {
            "raw_value": m["raw_value"],
            "sub_index": m["sub_index"],
            "severity": m["severity"],
            "status": m["status"],
        }

    results: list[dict[str, Any]] = []
    for r in obs_rows:
        item = dict(r)
        oid = int(item["observation_id"])
        p_map = meas_by_obs.get(oid, {})
        item["pollutants"] = p_map
        for key in POLLUTANT_KEYS:
            item[key] = p_map.get(key, {}).get("raw_value")
            item[f"{key}_sub_index"] = p_map.get(key, {}).get("sub_index")
        results.append(item)
    return results


def get_observations(
    location: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 500,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    initialize_database(db_path)
    _ensure_hydrated_if_empty(db_path)

    clauses: list[str] = []
    params: list[Any] = []

    if location and location.strip() and location.strip().lower() != "all locations":
        clauses.append("(s.station_name = ? OR s.query_city = ?)")
        loc_clean = location.strip()
        params.extend([loc_clean, loc_clean])

    if start_date and start_date.strip():
        clauses.append("o.observation_date >= ?")
        params.append(start_date.strip()[:10])

    if end_date and end_date.strip():
        clauses.append("o.observation_date <= ?")
        params.append(end_date.strip()[:10])

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(int(limit))

    with get_connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                o.observation_id,
                o.station_id,
                s.station_name,
                s.query_city,
                s.latitude,
                s.longitude,
                o.observation_time,
                o.observation_date,
                o.waqi_reported_aqi,
                o.calculated_aqi,
                o.aqi_category,
                o.dominant_pollutant,
                o.highest_measured_pollutant,
                o.completeness_ratio,
                o.is_valid,
                o.is_stale,
                o.recorded_at_utc
            FROM aqi_observations o
            JOIN stations s ON s.station_id = o.station_id
            {where_sql}
            ORDER BY o.observation_time ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return _hydrate_observations(conn, rows)


def get_observations_by_location(
    location: str,
    limit: int = 500,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    return get_observations(location=location, limit=limit, db_path=db_path)


def get_observations_by_date_range(
    start_date: str,
    end_date: str,
    location: str | None = None,
    limit: int = 500,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    return get_observations(
        location=location,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        db_path=db_path,
    )


def get_latest_observations_per_station(db_path: Path | str | None = None) -> list[dict[str, Any]]:
    initialize_database(db_path)
    _ensure_hydrated_if_empty(db_path)

    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                o.observation_id,
                o.station_id,
                s.station_name,
                s.query_city,
                s.latitude,
                s.longitude,
                o.observation_time,
                o.observation_date,
                o.waqi_reported_aqi,
                o.calculated_aqi,
                o.aqi_category,
                o.dominant_pollutant,
                o.highest_measured_pollutant,
                o.completeness_ratio,
                o.is_valid,
                o.is_stale,
                o.recorded_at_utc
            FROM aqi_observations o
            JOIN stations s ON s.station_id = o.station_id
            WHERE o.observation_id IN (
                SELECT MAX(o2.observation_id)
                FROM aqi_observations o2
                GROUP BY o2.station_id
            )
            ORDER BY s.station_name ASC
            """
        ).fetchall()
        return _hydrate_observations(conn, rows)


def get_active_alerts(limit: int = 50, db_path: Path | str | None = None) -> list[dict[str, Any]]:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                a.alert_id,
                s.station_name,
                s.query_city,
                o.observation_time,
                a.alert_type,
                a.severity,
                a.title,
                a.message,
                a.created_at_utc
            FROM alerts a
            JOIN stations s ON s.station_id = a.station_id
            LEFT JOIN aqi_observations o ON o.observation_id = a.observation_id
            WHERE a.is_active = 1
            ORDER BY a.alert_id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [dict(r) for r in rows]