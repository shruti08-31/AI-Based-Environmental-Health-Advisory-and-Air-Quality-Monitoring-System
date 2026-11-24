from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any

from src.api.waqi_client import POLLUTANT_KEYS, AqiReading
from src.core.aqi_engine import AqiEngineResult, evaluate_aqi_from_reading
from src.database.connection import get_connection
from src.database.models import initialize_database
from src.intelligence.anomaly_detection import AnomalyFinding, detect_anomalies
from src.intelligence.pollutant_analysis import PollutantAnalysisResult, analyze_pollutants

# Configurable pollutant concentration / sub-index alert limits
DEFAULT_POLLUTANT_ALERT_LIMITS: dict[str, float] = {
    "pm25": 60.0,
    "pm10": 100.0,
    "no2": 80.0,
    "so2": 80.0,
    "co": 2.0,
    "o3": 100.0,
}

# AQI threshold that triggers threshold alert if >= this value
DEFAULT_AQI_ALERT_THRESHOLD = 101

# Significant deterioration delta vs. prior observation
DEFAULT_DETERIORATION_DELTA = 35


@dataclass(frozen=True)
class AlertCandidate:
    alert_type: str
    location: str
    severity: str
    observation_time: str
    title: str
    explanation: str


def evaluate_alert_candidates(
    reading: AqiReading,
    previous_observations: list[dict[str, Any]] | None = None,
    aqi_result: AqiEngineResult | None = None,
    analysis: PollutantAnalysisResult | None = None,
    aqi_threshold: int = DEFAULT_AQI_ALERT_THRESHOLD,
    deterioration_delta: int = DEFAULT_DETERIORATION_DELTA,
    pollutant_limits: dict[str, float] | None = None,
) -> list[AlertCandidate]:
    """
    Deterministic in-app alert candidate evaluator (does not claim continuous background monitoring).
    """
    limits = {**DEFAULT_POLLUTANT_ALERT_LIMITS, **(pollutant_limits or {})}
    eng = aqi_result or evaluate_aqi_from_reading(reading)
    pol_res = analysis or analyze_pollutants(
        pollutants=reading.pollutants,
        waqi_reported_aqi=reading.aqi,
        aqi_result=eng,
    )

    location = (reading.station_name or reading.query or "Unknown Location").strip()
    obs_time = (reading.observation_time or "Timestamp Missing").strip()
    candidates: list[AlertCandidate] = []

    # 1. AQI crosses configured threshold
    if eng.calculated_aqi is not None and eng.calculated_aqi >= aqi_threshold:
        candidates.append(
            AlertCandidate(
                alert_type="AQI_THRESHOLD",
                location=location,
                severity=eng.category,
                observation_time=obs_time,
                title=f"AQI Threshold Exceeded ({eng.calculated_aqi} >= {aqi_threshold})",
                explanation=(
                    f"Calculated CPCB AQI ({eng.calculated_aqi}, {eng.category}) reached or exceeded "
                    f"the configured threshold of {aqi_threshold}. {eng.category_explanation}"
                ),
            )
        )

    # 2. Significant AQI deterioration compared to prior observation
    if eng.calculated_aqi is not None and previous_observations:
        prior_valid = [
            o.get("calculated_aqi")
            for o in previous_observations
            if o.get("calculated_aqi") is not None
        ]
        if prior_valid:
            prev_aqi = int(prior_valid[-1])
            delta = eng.calculated_aqi - prev_aqi
            if delta >= deterioration_delta:
                candidates.append(
                    AlertCandidate(
                        alert_type="AQI_DETERIORATION",
                        location=location,
                        severity=eng.category,
                        observation_time=obs_time,
                        title=f"Significant AQI Deterioration (+{delta} vs. Prior)",
                        explanation=(
                            f"Calculated AQI rose by +{delta} points from prior reading ({prev_aqi}) "
                            f"to {eng.calculated_aqi} at {obs_time}, meeting the >={deterioration_delta} deterioration rule."
                        ),
                    )
                )

    # 3. Pollutant conditions cross configured limits
    exceeded_pols: list[str] = []
    for key in POLLUTANT_KEYS:
        val = reading.pollutants.get(key)
        limit = limits.get(key)
        if val is not None and isinstance(val, (int, float)) and not isinstance(val, bool) and limit is not None:
            if float(val) > limit:
                exceeded_pols.append(f"{key.upper()}={float(val):g} (>{limit:g})")

    if exceeded_pols:
        candidates.append(
            AlertCandidate(
                alert_type="POLLUTANT_LIMIT",
                location=location,
                severity=eng.category if eng.category != "Unavailable" else "Moderate",
                observation_time=obs_time,
                title="Configured Pollutant Limit Exceeded",
                explanation="Pollutants above configured reference limits: " + ", ".join(exceeded_pols) + ".",
            )
        )

    # 4. Statistical anomaly detected across sequence
    combined_seq: list[dict[str, Any]] = list(previous_observations or [])
    current_row: dict[str, Any] = {
        "station_name": location,
        "query_city": reading.query,
        "observation_time": obs_time,
        "calculated_aqi": eng.calculated_aqi,
        "waqi_reported_aqi": reading.aqi,
        "is_valid": 1,
    }
    for key in POLLUTANT_KEYS:
        current_row[key] = reading.pollutants.get(key)
    combined_seq.append(current_row)

    anomaly_findings: list[AnomalyFinding] = detect_anomalies(combined_seq)
    if anomaly_findings and anomaly_findings[-1].is_anomaly:
        latest_anom = anomaly_findings[-1]
        candidates.append(
            AlertCandidate(
                alert_type="ANOMALY_DETECTED",
                location=location,
                severity=latest_anom.evidence_strength,
                observation_time=obs_time,
                title=f"Statistical Anomaly Flagged ({latest_anom.evidence_strength} Evidence)",
                explanation=f"{latest_anom.explanation} ({latest_anom.observed_change}; {latest_anom.reference_baseline}).",
            )
        )

    return candidates


def _ensure_alert_acknowledgement_column(conn: sqlite3.Connection) -> None:
    cols = {str(r["name"]) for r in conn.execute("PRAGMA table_info(alerts)").fetchall()}
    if "acknowledged" not in cols:
        conn.execute("ALTER TABLE alerts ADD COLUMN acknowledged INTEGER NOT NULL DEFAULT 0;")


def persist_alerts(
    candidates: list[AlertCandidate],
    query_city: str = "",
    db_path: Path | str | None = None,
) -> int:
    """
    Store alert candidates in SQLite while preventing duplicate alerts for the same
    station, observation_time, alert_type, and title. Returns count of newly inserted alerts.
    """
    initialize_database(db_path)
    if not candidates:
        return 0

    inserted_count = 0
    with get_connection(db_path) as conn:
        _ensure_alert_acknowledgement_column(conn)

        for cand in candidates:
            st_row = conn.execute(
                "SELECT station_id FROM stations WHERE station_name = ? LIMIT 1",
                (cand.location,),
            ).fetchone()
            if st_row is not None:
                station_id = int(st_row["station_id"])
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO stations (station_name, query_city) VALUES (?, ?)",
                    (cand.location, query_city or cand.location),
                )
                st_row = conn.execute(
                    "SELECT station_id FROM stations WHERE station_name = ? LIMIT 1",
                    (cand.location,),
                ).fetchone()
                station_id = int(st_row["station_id"])

            obs_row = conn.execute(
                "SELECT observation_id FROM aqi_observations WHERE station_id = ? AND observation_time = ? LIMIT 1",
                (station_id, cand.observation_time),
            ).fetchone()
            obs_id = int(obs_row["observation_id"]) if obs_row is not None else None

            dup = conn.execute(
                """
                SELECT alert_id FROM alerts
                WHERE station_id = ?
                  AND COALESCE(observation_id, -1) = COALESCE(?, -1)
                  AND alert_type = ?
                  AND title = ?
                LIMIT 1
                """,
                (station_id, obs_id, cand.alert_type, cand.title),
            ).fetchone()
            if dup is not None:
                continue

            conn.execute(
                """
                INSERT INTO alerts (
                    station_id, observation_id, alert_type, severity, title, message, is_active, acknowledged
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, 0)
                """,
                (
                    station_id,
                    obs_id,
                    cand.alert_type,
                    cand.severity,
                    cand.title,
                    f"[{cand.observation_time}] {cand.explanation}",
                ),
            )
            inserted_count += 1

    return inserted_count


def list_stored_alerts(
    include_acknowledged: bool = True,
    location: str | None = None,
    limit: int = 200,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    initialize_database(db_path)
    clauses: list[str] = []
    params: list[Any] = []

    with get_connection(db_path) as conn:
        _ensure_alert_acknowledgement_column(conn)

        if not include_acknowledged:
            clauses.append("COALESCE(a.acknowledged, 0) = 0")
        if location and location.strip() and location.strip().lower() != "all locations":
            clauses.append("s.station_name = ?")
            params.append(location.strip())

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))

        rows = conn.execute(
            f"""
            SELECT
                a.alert_id,
                a.alert_type,
                s.station_name AS location,
                COALESCE(o.observation_time, 'N/A') AS observation_time,
                a.severity,
                a.title,
                a.message AS explanation,
                COALESCE(a.acknowledged, 0) AS acknowledged,
                a.created_at_utc
            FROM alerts a
            JOIN stations s ON s.station_id = a.station_id
            LEFT JOIN aqi_observations o ON o.observation_id = a.observation_id
            {where_sql}
            ORDER BY a.alert_id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def acknowledge_alert(alert_id: int, db_path: Path | str | None = None) -> None:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        _ensure_alert_acknowledgement_column(conn)
        conn.execute(
            "UPDATE alerts SET acknowledged = 1 WHERE alert_id = ?",
            (int(alert_id),),
        )