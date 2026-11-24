from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.api.waqi_client import POLLUTANT_KEYS, AqiReading

DEFAULT_STALE_THRESHOLD_MINUTES = 120


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_pollutants: list[str] = field(default_factory=list)
    is_stale: bool = False
    observation_age_minutes: float | None = None
    completeness_ratio: float = 0.0


def _is_finite_number(val: Any) -> bool:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    return val == val and val not in (float("inf"), float("-inf"))


def _parse_timestamp_utc(ts_str: str | None) -> datetime | None:
    if not ts_str or not isinstance(ts_str, str):
        return None
    cleaned = ts_str.strip()
    if not cleaned:
        return None
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                dt = datetime.strptime(cleaned, fmt)
                break
            except ValueError:
                continue
        else:
            return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_aqi_reading(
    reading: AqiReading,
    reference_time: datetime | None = None,
    stale_after_minutes: int = DEFAULT_STALE_THRESHOLD_MINUTES,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    missing_pollutants: list[str] = []

    now_utc = (
        reference_time.astimezone(timezone.utc)
        if reference_time and reference_time.tzinfo
        else (reference_time or datetime.now(timezone.utc)).replace(tzinfo=timezone.utc)
        if reference_time is None
        else reference_time.astimezone(timezone.utc)
    )

    if not reading.station_name or not reading.station_name.strip():
        errors.append("Missing required station name.")

    if reading.aqi is None:
        errors.append("Missing or non-numeric AQI value.")
    elif not _is_finite_number(reading.aqi):
        errors.append("AQI value is not a finite number.")
    elif reading.aqi < 0:
        errors.append(f"Negative AQI measurement detected ({reading.aqi}).")

    if reading.latitude is None or reading.longitude is None:
        warnings.append("Missing station latitude or longitude coordinates.")
    else:
        if not (-90.0 <= reading.latitude <= 90.0):
            errors.append(f"Latitude out of valid range [-90, 90]: {reading.latitude}.")
        if not (-180.0 <= reading.longitude <= 180.0):
            errors.append(f"Longitude out of valid range [-180, 180]: {reading.longitude}.")

    obs_dt = _parse_timestamp_utc(reading.observation_time)
    obs_age_minutes: float | None = None
    is_stale = False

    if obs_dt is None:
        warnings.append("Missing or unparseable observation timestamp.")
    else:
        age_seconds = (now_utc - obs_dt).total_seconds()
        if age_seconds < -300:
            warnings.append("Observation timestamp is in the future relative to current clock.")
        else:
            obs_age_minutes = round(max(age_seconds, 0.0) / 60.0, 1)
            if obs_age_minutes > stale_after_minutes:
                is_stale = True
                warnings.append(
                    f"Observation is stale ({obs_age_minutes:.0f} min old; threshold is {stale_after_minutes} min)."
                )

    present_pollutants = 0
    for key in POLLUTANT_KEYS:
        val = reading.pollutants.get(key)
        if val is None:
            missing_pollutants.append(key)
        elif not _is_finite_number(val):
            errors.append(f"Pollutant '{key}' has a non-numeric value.")
            missing_pollutants.append(key)
        elif val < 0:
            errors.append(f"Pollutant '{key}' has a negative measurement ({val}).")
        else:
            present_pollutants += 1

    if missing_pollutants:
        warnings.append(
            "Missing pollutant measurements (not imputed): "
            + ", ".join(p.upper() for p in missing_pollutants)
            + "."
        )

    completeness_ratio = round(present_pollutants / len(POLLUTANT_KEYS), 2) if POLLUTANT_KEYS else 0.0
    is_valid = len(errors) == 0

    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        missing_pollutants=missing_pollutants,
        is_stale=is_stale,
        observation_age_minutes=obs_age_minutes,
        completeness_ratio=completeness_ratio,
    )