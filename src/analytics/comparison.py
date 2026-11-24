from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import pandas as pd

from src.api.waqi_client import POLLUTANT_KEYS


@dataclass(frozen=True)
class LocationComparisonResult:
    stations_compared: int
    comparison_df: pd.DataFrame
    highest_aqi_station: str | None
    highest_aqi_value: int | None
    lowest_aqi_station: str | None
    lowest_aqi_value: int | None
    available_severities: list[str] = field(default_factory=list)
    has_timestamp_skew_or_stale: bool = False
    timestamp_warnings: list[str] = field(default_factory=list)


def _parse_utc(ts: str | None) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    try:
        dt = datetime.fromisoformat(ts.strip())
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compare_station_observations(
    latest_observations: list[dict[str, Any]],
    selected_stations: list[str] | None = None,
    stale_after_minutes: int = 120,
    reference_time: datetime | None = None,
) -> LocationComparisonResult:
    now_utc = (
        reference_time.astimezone(timezone.utc)
        if reference_time and reference_time.tzinfo
        else (reference_time or datetime.now(timezone.utc)).replace(tzinfo=timezone.utc)
        if reference_time is None
        else reference_time.astimezone(timezone.utc)
    )

    filtered = latest_observations
    if selected_stations:
        wanted = {s.strip() for s in selected_stations if s and s.strip()}
        filtered = [
            obs
            for obs in latest_observations
            if str(obs.get("station_name", "")).strip() in wanted
            or str(obs.get("query_city", "")).strip() in wanted
        ]

    if not filtered:
        return LocationComparisonResult(
            stations_compared=0,
            comparison_df=pd.DataFrame(),
            highest_aqi_station=None,
            highest_aqi_value=None,
            lowest_aqi_station=None,
            lowest_aqi_value=None,
            available_severities=[],
            has_timestamp_skew_or_stale=False,
            timestamp_warnings=[],
        )

    rows: list[dict[str, Any]] = []
    parsed_times: list[tuple[str, datetime]] = []
    timestamp_warnings: list[str] = []

    for obs in filtered:
        st_name = str(obs.get("station_name") or obs.get("query_city") or "Unknown")
        obs_ts = str(obs.get("observation_time") or "Missing")
        dt = _parse_utc(obs.get("observation_time"))

        freshness_label = "Timestamp Unknown"
        age_min: float | None = None
        if dt is not None:
            parsed_times.append((st_name, dt))
            age_min = round(max((now_utc - dt).total_seconds(), 0.0) / 60.0, 1)
            is_stale_flag = bool(obs.get("is_stale")) or age_min > stale_after_minutes
            if is_stale_flag:
                freshness_label = f"Stale ({int(age_min)} min old)"
                timestamp_warnings.append(
                    f"{st_name}: observation timestamp ({obs_ts}) is {int(age_min)} min old (stale)."
                )
            else:
                freshness_label = f"Fresh ({int(age_min)} min old)"
        else:
            timestamp_warnings.append(f"{st_name}: missing or unparseable observation timestamp.")

        row: dict[str, Any] = {
            "Station": st_name,
            "Query City": str(obs.get("query_city") or ""),
            "Calculated AQI (CPCB)": obs.get("calculated_aqi"),
            "WAQI API AQI": obs.get("waqi_reported_aqi"),
            "Severity Category": str(obs.get("aqi_category") or "Unavailable"),
            "Dominant Pollutant": str(obs.get("dominant_pollutant") or "N/A").upper(),
            "Observation Timestamp": obs_ts,
            "Freshness Status": freshness_label,
        }
        for key in POLLUTANT_KEYS:
            row[key.upper()] = obs.get(key)
        rows.append(row)

    if len(parsed_times) >= 2:
        min_station, min_dt = min(parsed_times, key=lambda x: x[1])
        max_station, max_dt = max(parsed_times, key=lambda x: x[1])
        spread_minutes = (max_dt - min_dt).total_seconds() / 60.0
        if spread_minutes > 60:
            timestamp_warnings.append(
                f"Observation time skew of {int(spread_minutes)} minutes between "
                f"'{min_station}' ({min_dt.isoformat()}) and '{max_station}' ({max_dt.isoformat()})."
            )

    comp_df = pd.DataFrame(rows)
    valid_aqi_df = comp_df.dropna(subset=["Calculated AQI (CPCB)"]).copy()

    highest_station: str | None = None
    highest_val: int | None = None
    lowest_station: str | None = None
    lowest_val: int | None = None

    if not valid_aqi_df.empty:
        valid_aqi_df["Calculated AQI (CPCB)"] = pd.to_numeric(valid_aqi_df["Calculated AQI (CPCB)"])
        max_idx = valid_aqi_df["Calculated AQI (CPCB)"].idxmax()
        min_idx = valid_aqi_df["Calculated AQI (CPCB)"].idxmin()
        highest_station = str(valid_aqi_df.loc[max_idx, "Station"])
        highest_val = int(valid_aqi_df.loc[max_idx, "Calculated AQI (CPCB)"])
        lowest_station = str(valid_aqi_df.loc[min_idx, "Station"])
        lowest_val = int(valid_aqi_df.loc[min_idx, "Calculated AQI (CPCB)"])

    severities = sorted(
        {str(s) for s in comp_df["Severity Category"].dropna().tolist() if str(s).strip()}
    )

    return LocationComparisonResult(
        stations_compared=int(len(comp_df)),
        comparison_df=comp_df,
        highest_aqi_station=highest_station,
        highest_aqi_value=highest_val,
        lowest_aqi_station=lowest_station,
        lowest_aqi_value=lowest_val,
        available_severities=severities,
        has_timestamp_skew_or_stale=len(timestamp_warnings) > 0,
        timestamp_warnings=timestamp_warnings,
    )