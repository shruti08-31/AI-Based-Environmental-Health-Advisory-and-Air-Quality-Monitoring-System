from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import numpy as np
import pandas as pd

from src.api.waqi_client import POLLUTANT_KEYS
from src.intelligence.pollutant_analysis import detect_pollutant_combinations
from src.core.aqi_engine import evaluate_aqi


@dataclass
class AnomalyFinding:
    observation_time: str
    station_name: str
    is_anomaly: bool
    evidence_strength: str  # "None" | "Low" | "Moderate" | "High"
    observed_change: str
    reference_baseline: str
    explanation: str
    aqi_delta: float | None = None
    pollutant_deviations: dict[str, float] = field(default_factory=dict)
    interval_minutes: float | None = None
    data_quality_note: str = ""


def _parse_dt(val: Any) -> datetime | None:
    if not val or not isinstance(val, str):
        return None
    try:
        return datetime.fromisoformat(val.strip())
    except ValueError:
        return None


def _valid_float(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    try:
        f = float(val)
        return f if np.isfinite(f) and f >= 0.0 else None
    except (TypeError, ValueError):
        return None


def detect_anomalies(
    observations: list[dict[str, Any]],
    aqi_jump_threshold: float = 50.0,
    zscore_threshold: float = 2.0,
) -> list[AnomalyFinding]:
    """
    Explainable statistical anomaly detection across chronological observations.
    Invalid or missing readings are never labeled as confirmed pollution events.
    """
    if not observations:
        return []

    valid_obs: list[dict[str, Any]] = []
    for raw in observations:
        if raw.get("is_valid") is not None and int(raw.get("is_valid")) == 0:
            continue
        aqi_val = _valid_float(raw.get("calculated_aqi"))
        if aqi_val is None:
            aqi_val = _valid_float(raw.get("waqi_reported_aqi"))
        if aqi_val is None:
            row_pols = {k: _valid_float(raw.get(k)) for k in POLLUTANT_KEYS}
            calc_from_pols = evaluate_aqi(row_pols).calculated_aqi
            if calc_from_pols is not None:
                aqi_val = float(calc_from_pols)
        if aqi_val is None:
            continue
        item = dict(raw)
        item["_aqi"] = aqi_val
        item["_dt"] = _parse_dt(raw.get("observation_time"))
        valid_obs.append(item)

    if not valid_obs:
        return []

    df = pd.DataFrame(valid_obs)
    df = df.sort_values(by=["_dt", "observation_time"], ascending=True).reset_index(drop=True)

    aqi_series = df["_aqi"].astype(float)
    baseline_mean = float(aqi_series.mean())
    baseline_std = float(aqi_series.std(ddof=0))

    pol_baselines: dict[str, tuple[float, float]] = {}
    for key in POLLUTANT_KEYS:
        if key in df.columns:
            p_vals = pd.to_numeric(df[key], errors="coerce").dropna()
            if len(p_vals) >= 2:
                pol_baselines[key] = (float(p_vals.mean()), float(p_vals.std(ddof=0)))

    findings: list[AnomalyFinding] = []
    prev_aqi: float | None = None
    prev_dt: datetime | None = None

    for idx, row in df.iterrows():
        obs_time = str(row.get("observation_time") or "Missing Timestamp")
        st_name = str(row.get("station_name") or row.get("query_city") or "Unknown")
        cur_aqi = float(row["_aqi"])
        cur_dt: datetime | None = row["_dt"]

        interval_min: float | None = None
        interval_note = "Regular/initial interval"
        if prev_dt is not None and cur_dt is not None:
            dt_a = prev_dt if prev_dt.tzinfo else prev_dt
            dt_b = cur_dt if cur_dt.tzinfo else cur_dt
            if (dt_a.tzinfo is None) == (dt_b.tzinfo is None):
                delta_sec = (dt_b - dt_a).total_seconds()
                if delta_sec >= 0:
                    interval_min = round(delta_sec / 60.0, 1)
                    if interval_min > 180:
                        interval_note = f"Irregular gap ({interval_min:g} min since prior reading)"

        aqi_delta: float | None = None
        sudden_jump = False
        if prev_aqi is not None:
            aqi_delta = round(cur_aqi - prev_aqi, 1)
            if aqi_delta >= aqi_jump_threshold:
                sudden_jump = True

        z_score = ((cur_aqi - baseline_mean) / baseline_std) if baseline_std > 1e-6 else 0.0
        hist_deviation = abs(z_score) >= zscore_threshold

        pol_devs: dict[str, float] = {}
        unusual_pollutants: list[str] = []
        missing_pols: list[str] = []
        pol_dict: dict[str, float | None] = {}

        for key in POLLUTANT_KEYS:
            pval = _valid_float(row.get(key)) if key in df.columns else None
            pol_dict[key] = pval
            if pval is None:
                missing_pols.append(key.upper())
                continue
            if key in pol_baselines:
                p_mean, p_std = pol_baselines[key]
                if p_std > 1e-6:
                    pz = round((pval - p_mean) / p_std, 2)
                    pol_devs[key.upper()] = pz
                    if abs(pz) >= zscore_threshold:
                        unusual_pollutants.append(f"{key.upper()} (z={pz:+.2f})")

        eng = evaluate_aqi(pol_dict, waqi_reported_aqi=cur_aqi)
        combos = detect_pollutant_combinations(eng)
        combo_triggered = len(combos) > 0

        reasons: list[str] = []
        if sudden_jump and aqi_delta is not None:
            reasons.append(f"Sudden AQI rise of {aqi_delta:+.1f} points (>= {aqi_jump_threshold:g} threshold)")
        if hist_deviation:
            reasons.append(f"AQI deviates from historical mean by z={z_score:+.2f}")
        if unusual_pollutants:
            reasons.append("Unusual pollutant shifts: " + ", ".join(unusual_pollutants))
        if combo_triggered:
            reasons.append(
                "Multi-pollutant combination pattern: " + ", ".join(c.title for c in combos)
            )

        trigger_count = len(reasons)
        is_anomaly = trigger_count > 0
        if trigger_count == 0:
            strength = "None"
        elif trigger_count == 1 and not sudden_jump:
            strength = "Low"
        elif trigger_count <= 2:
            strength = "Moderate"
        else:
            strength = "High"

        obs_change_str = (
            f"AQI {aqi_delta:+.1f} vs prior reading"
            if aqi_delta is not None
            else f"Initial series AQI {cur_aqi:g}"
        )
        ref_base_str = f"Mean AQI {baseline_mean:.1f} (SD {baseline_std:.1f}, n={len(df)})"
        explanation_str = (
            "; ".join(reasons)
            if reasons
            else "Within statistical baseline across available AQI and pollutant readings."
        )
        dq_parts = [interval_note]
        if missing_pols:
            dq_parts.append(f"Missing pollutants: {', '.join(missing_pols)}")
        dq_parts.append("Statistical flag only; not a verified emission event without field confirmation.")

        findings.append(
            AnomalyFinding(
                observation_time=obs_time,
                station_name=st_name,
                is_anomaly=is_anomaly,
                evidence_strength=strength,
                observed_change=obs_change_str,
                reference_baseline=ref_base_str,
                explanation=explanation_str,
                aqi_delta=aqi_delta,
                pollutant_deviations=pol_devs,
                interval_minutes=interval_min,
                data_quality_note=" | ".join(dq_parts),
            )
        )

        prev_aqi = cur_aqi
        prev_dt = cur_dt

    return findings