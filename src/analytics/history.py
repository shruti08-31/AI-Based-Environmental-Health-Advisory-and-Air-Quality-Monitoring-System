from dataclasses import dataclass, field
from typing import Any
import pandas as pd

from src.api.waqi_client import POLLUTANT_KEYS


@dataclass(frozen=True)
class HistoricalSummary:
    observation_count: int
    has_sufficient_trend_data: bool
    average_aqi: float | None
    max_aqi: int | None
    min_aqi: int | None
    latest_aqi: int | None
    earliest_aqi: int | None
    aqi_change: int | None
    aqi_change_pct: float | None
    pollutant_averages: dict[str, float | None] = field(default_factory=dict)
    severity_distribution: dict[str, int] = field(default_factory=dict)
    timeseries_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    daily_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    weekly_df: pd.DataFrame = field(default_factory=pd.DataFrame)


def compute_historical_analytics(observations: list[dict[str, Any]]) -> HistoricalSummary:
    if not observations:
        return HistoricalSummary(
            observation_count=0,
            has_sufficient_trend_data=False,
            average_aqi=None,
            max_aqi=None,
            min_aqi=None,
            latest_aqi=None,
            earliest_aqi=None,
            aqi_change=None,
            aqi_change_pct=None,
            pollutant_averages={k: None for k in POLLUTANT_KEYS},
            severity_distribution={},
            timeseries_df=pd.DataFrame(),
            daily_df=pd.DataFrame(),
            weekly_df=pd.DataFrame(),
        )

    df = pd.DataFrame(observations).copy()
    df["parsed_time"] = pd.to_datetime(df["observation_time"], errors="coerce", utc=True)
    df = df.sort_values(by=["parsed_time", "observation_time"], ascending=True).reset_index(drop=True)

    df["effective_aqi"] = pd.to_numeric(df["calculated_aqi"], errors="coerce")
    valid_aqi = df["effective_aqi"].dropna()

    avg_aqi = round(float(valid_aqi.mean()), 1) if not valid_aqi.empty else None
    max_aqi = int(valid_aqi.max()) if not valid_aqi.empty else None
    min_aqi = int(valid_aqi.min()) if not valid_aqi.empty else None

    earliest_aqi = int(valid_aqi.iloc[0]) if len(valid_aqi) >= 1 else None
    latest_aqi = int(valid_aqi.iloc[-1]) if len(valid_aqi) >= 1 else None
    aqi_change = (latest_aqi - earliest_aqi) if (len(valid_aqi) >= 2 and latest_aqi is not None and earliest_aqi is not None) else None
    aqi_change_pct = (
        round((aqi_change / earliest_aqi) * 100.0, 1)
        if (aqi_change is not None and earliest_aqi and earliest_aqi > 0)
        else None
    )

    pollutant_averages: dict[str, float | None] = {}
    for key in POLLUTANT_KEYS:
        if key in df.columns:
            series = pd.to_numeric(df[key], errors="coerce").dropna()
            pollutant_averages[key] = round(float(series.mean()), 2) if not series.empty else None
        else:
            pollutant_averages[key] = None

    severity_distribution: dict[str, int] = {}
    if "aqi_category" in df.columns:
        counts = df["aqi_category"].fillna("Unavailable").value_counts()
        severity_distribution = {str(k): int(v) for k, v in counts.items()}

    # Build daily aggregation
    df["day_bucket"] = df["observation_date"].fillna(df["observation_time"].astype(str).str.slice(0, 10))
    daily_rows: list[dict[str, Any]] = []
    for day_val, grp in df.groupby("day_bucket", sort=True):
        day_aqi = pd.to_numeric(grp["effective_aqi"], errors="coerce").dropna()
        row: dict[str, Any] = {
            "Date": str(day_val),
            "Observations": int(len(grp)),
            "Average AQI": round(float(day_aqi.mean()), 1) if not day_aqi.empty else None,
            "Max AQI": int(day_aqi.max()) if not day_aqi.empty else None,
            "Min AQI": int(day_aqi.min()) if not day_aqi.empty else None,
        }
        for key in POLLUTANT_KEYS:
            p_ser = pd.to_numeric(grp[key], errors="coerce").dropna() if key in grp.columns else pd.Series(dtype=float)
            row[key.upper()] = round(float(p_ser.mean()), 2) if not p_ser.empty else None
        daily_rows.append(row)
    daily_df = pd.DataFrame(daily_rows)

    # Build weekly aggregation (ISO year-week)
    valid_dates = pd.to_datetime(df["day_bucket"], errors="coerce")
    df["week_bucket"] = valid_dates.dt.strftime("%G-W%V").fillna("Unknown-Week")
    weekly_rows: list[dict[str, Any]] = []
    for week_val, grp in df.groupby("week_bucket", sort=True):
        wk_aqi = pd.to_numeric(grp["effective_aqi"], errors="coerce").dropna()
        w_row: dict[str, Any] = {
            "Week": str(week_val),
            "Observations": int(len(grp)),
            "Average AQI": round(float(wk_aqi.mean()), 1) if not wk_aqi.empty else None,
            "Max AQI": int(wk_aqi.max()) if not wk_aqi.empty else None,
            "Min AQI": int(wk_aqi.min()) if not wk_aqi.empty else None,
        }
        for key in POLLUTANT_KEYS:
            p_ser = pd.to_numeric(grp[key], errors="coerce").dropna() if key in grp.columns else pd.Series(dtype=float)
            w_row[key.upper()] = round(float(p_ser.mean()), 2) if not p_ser.empty else None
        weekly_rows.append(w_row)
    weekly_df = pd.DataFrame(weekly_rows)

    return HistoricalSummary(
        observation_count=int(len(df)),
        has_sufficient_trend_data=int(len(df)) >= 2,
        average_aqi=avg_aqi,
        max_aqi=max_aqi,
        min_aqi=min_aqi,
        latest_aqi=latest_aqi,
        earliest_aqi=earliest_aqi,
        aqi_change=aqi_change,
        aqi_change_pct=aqi_change_pct,
        pollutant_averages=pollutant_averages,
        severity_distribution=severity_distribution,
        timeseries_df=df,
        daily_df=daily_df,
        weekly_df=weekly_df,
    )