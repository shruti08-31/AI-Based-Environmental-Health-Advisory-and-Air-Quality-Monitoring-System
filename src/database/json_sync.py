from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from config import config
from src.api.waqi_client import POLLUTANT_KEYS, AqiReading

DEFAULT_JSON_STORE_PATH = config.data_dir / "observations_store.json"


def _obs_unique_key(record: dict[str, Any]) -> tuple[str, str, str]:
    station = str(record.get("station_name") or "").strip().lower()
    city = str(record.get("query_city") or "").strip().lower()
    obs_time = str(record.get("observation_time") or "").strip()
    return (station, city, obs_time)


def reading_to_json_record(
    reading: AqiReading,
    query_city: str | None = None,
    calculated_aqi: int | None = None,
    aqi_category: str | None = None,
    dominant_pollutant: str | None = None,
    completeness_ratio: float = 0.0,
    is_valid: bool = True,
    is_stale: bool = False,
    validation: Any = None,
    aqi_result: Any = None,
    analysis: Any = None,
    source_insights: Any = None,
    advisory: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    _ = kwargs  # Ignore any extra optional bundle metadata safely
    pollutants_clean: dict[str, float | None] = {}
    for key in POLLUTANT_KEYS:
        val = reading.pollutants.get(key)
        if val is None or isinstance(val, bool):
            pollutants_clean[key] = None
        else:
            try:
                fval = float(val)
                pollutants_clean[key] = fval if fval == fval and abs(fval) != float("inf") else None
            except (TypeError, ValueError):
                pollutants_clean[key] = None

    calc_aqi = (
        calculated_aqi
        if calculated_aqi is not None
        else getattr(aqi_result, "calculated_aqi", kwargs.get("calculated_aqi"))
    )
    category = (
        aqi_category
        if aqi_category is not None
        else getattr(aqi_result, "category", kwargs.get("aqi_category"))
    )
    dom_pol = (
        dominant_pollutant
        if dominant_pollutant is not None
        else getattr(aqi_result, "dominant_pollutant", kwargs.get("dominant_pollutant"))
    )
    comp_ratio = getattr(validation, "completeness_ratio", completeness_ratio)
    valid_flag = getattr(validation, "is_valid", is_valid)
    stale_flag = getattr(validation, "is_stale", is_stale)

    return {
        "query_city": (query_city or reading.query or "").strip(),
        "station_name": (reading.station_name or reading.query or "Unknown Station").strip(),
        "latitude": reading.latitude,
        "longitude": reading.longitude,
        "observation_time": reading.observation_time,
        "waqi_reported_aqi": reading.aqi,
        "waqi_aqi_raw": reading.aqi_raw,
        "calculated_aqi": calc_aqi,
        "aqi_category": category,
        "dominant_pollutant": dom_pol,
        "completeness_ratio": comp_ratio,
        "is_valid": 1 if valid_flag else 0,
        "is_stale": 1 if stale_flag else 0,
        "advisory_urgency": getattr(advisory, "urgency_level", None),
        "pollutants": pollutants_clean,
    }


def load_json_records(json_path: Path | str | None = None) -> list[dict[str, Any]]:
    path = Path(json_path) if json_path is not None else DEFAULT_JSON_STORE_PATH
    if not path.exists():
        return []
    try:
        raw_text = path.read_text(encoding="utf-8").strip()
        if not raw_text:
            return []
        payload = json.loads(raw_text)
        if isinstance(payload, dict) and isinstance(payload.get("observations"), list):
            return [r for r in payload["observations"] if isinstance(r, dict)]
        if isinstance(payload, list):
            return [r for r in payload if isinstance(r, dict)]
        return []
    except Exception:
        return []


def save_observation_to_json(
    record: dict[str, Any],
    json_path: Path | str | None = None,
) -> bool:
    """
    Append a deduplicated observation record to the JSON store atomically.
    Returns True if newly added, False if already present.
    """
    path = Path(json_path) if json_path is not None else DEFAULT_JSON_STORE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = load_json_records(path)
    seen = {_obs_unique_key(r) for r in existing}
    key = _obs_unique_key(record)
    if key in seen:
        return False

    existing.append(record)
    payload = {
        "version": 1,
        "observations": existing,
    }

    fd, tmp_name = tempfile.mkstemp(prefix=".obs_store_", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            json.dump(payload, tmp_file, indent=2, ensure_ascii=False)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise
    return True


def hydrate_sqlite_from_json(
    db_path: Path | str | None = None,
    json_path: Path | str | None = None,
) -> int:
    """
    Load observation records from JSON into SQLite on startup or after DB reset.
    Deduplicates automatically via save_observation_bundle.
    Returns count of newly restored SQLite rows.
    """
    from src.database.repository import save_observation_bundle

    records = load_json_records(json_path)
    if not records:
        return 0

    restored = 0
    for rec in records:
        pols_raw = rec.get("pollutants") if isinstance(rec.get("pollutants"), dict) else {}
        pollutants = {k: pols_raw.get(k, rec.get(k)) for k in POLLUTANT_KEYS}

        reading = AqiReading(
            query=str(rec.get("query_city") or rec.get("station_name") or ""),
            station_name=str(rec.get("station_name") or rec.get("query_city") or "Unknown Station"),
            aqi=rec.get("waqi_reported_aqi"),
            aqi_raw=rec.get("waqi_aqi_raw", rec.get("waqi_reported_aqi")),
            dominant_pollutant=rec.get("dominant_pollutant"),
            pollutants=pollutants,
            latitude=rec.get("latitude"),
            longitude=rec.get("longitude"),
            observation_time=rec.get("observation_time"),
        )
        _, was_inserted = save_observation_bundle(
            reading,
            db_path=db_path,
            _sync_json=False,
        )
        if was_inserted:
            restored += 1

    return restored