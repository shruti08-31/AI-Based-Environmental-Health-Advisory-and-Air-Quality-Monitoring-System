from dataclasses import dataclass, field
from typing import Any

from src.api.waqi_client import POLLUTANT_KEYS, AqiReading
from src.core.aqi_engine import AqiEngineResult, evaluate_aqi

# Near-threshold warning ratio (e.g., >= 80% of Good upper bound when below Good)
NEAR_THRESHOLD_RATIO = 0.80

# Good-band upper thresholds used for baseline threshold proximity checks
GOOD_UPPER_THRESHOLDS: dict[str, float] = {
    "pm25": 30.0,
    "pm10": 50.0,
    "no2": 40.0,
    "so2": 40.0,
    "co": 1.0,
    "o3": 50.0,
}

# Configurable multi-pollutant combination rules
COMBINATION_THRESHOLDS: dict[str, float] = {
    "high_pm25_sub_index": 101.0,
    "high_pm10_sub_index": 101.0,
    "elevated_no2_sub_index": 51.0,
    "elevated_so2_sub_index": 51.0,
    "elevated_o3_sub_index": 51.0,
    "particulate_sub_index": 51.0,
}


@dataclass(frozen=True)
class PollutantMetricSummary:
    pollutant: str
    raw_value: float | None
    sub_index: float | None
    severity: str
    status: str  # "available" | "missing" | "invalid"
    approaching_threshold: bool
    threshold_note: str


@dataclass(frozen=True)
class PollutantCombinationFinding:
    pattern_id: str
    title: str
    matched_pollutants: list[str]
    severity: str
    summary: str


@dataclass(frozen=True)
class PollutantAnalysisResult:
    highest_measured_pollutant: str | None
    highest_measured_value: float | None
    dominant_aqi_pollutant: str | None
    highest_sub_index: float | None
    raw_vs_subindex_differs: bool
    missing_pollutants: list[str] = field(default_factory=list)
    approaching_threshold_pollutants: list[str] = field(default_factory=list)
    pollutant_summaries: dict[str, PollutantMetricSummary] = field(default_factory=dict)
    combinations: list[PollutantCombinationFinding] = field(default_factory=list)
    aqi_result: AqiEngineResult | None = None


def analyze_pollutants(
    pollutants: dict[str, Any],
    waqi_reported_aqi: float | int | None = None,
    aqi_result: AqiEngineResult | None = None,
    thresholds: dict[str, float] | None = None,
) -> PollutantAnalysisResult:
    cfg = {**COMBINATION_THRESHOLDS, **(thresholds or {})}
    engine_res = aqi_result or evaluate_aqi(pollutants, waqi_reported_aqi=waqi_reported_aqi)

    summaries: dict[str, PollutantMetricSummary] = {}
    missing_pollutants: list[str] = []
    approaching_pollutants: list[str] = []

    highest_raw_pol: str | None = None
    highest_raw_val: float = -1.0

    for key in POLLUTANT_KEYS:
        sub = engine_res.sub_indices.get(key)
        raw_input = pollutants.get(key) if isinstance(pollutants, dict) else None

        if sub is None or raw_input is None:
            missing_pollutants.append(key)
            summaries[key] = PollutantMetricSummary(
                pollutant=key,
                raw_value=None,
                sub_index=None,
                severity="Unavailable",
                status="missing",
                approaching_threshold=False,
                threshold_note="No measurement available.",
            )
            continue

        if not sub.is_valid_input or sub.raw_value is None:
            missing_pollutants.append(key)
            summaries[key] = PollutantMetricSummary(
                pollutant=key,
                raw_value=sub.raw_value,
                sub_index=None,
                severity="Unavailable",
                status="invalid",
                approaching_threshold=False,
                threshold_note=sub.note,
            )
            continue

        val = sub.raw_value
        if val > highest_raw_val:
            highest_raw_val = val
            highest_raw_pol = key

        good_limit = GOOD_UPPER_THRESHOLDS[key]
        approaching = False
        threshold_note = f"Within Good reference (<= {good_limit:g})."

        if val > good_limit:
            approaching = True
            threshold_note = f"Exceeded Good threshold ({good_limit:g})."
        elif val >= good_limit * NEAR_THRESHOLD_RATIO:
            approaching = True
            threshold_note = f"Approaching Good threshold ({val:g} vs {good_limit:g} limit)."

        if approaching:
            approaching_pollutants.append(key)

        summaries[key] = PollutantMetricSummary(
            pollutant=key,
            raw_value=val,
            sub_index=sub.sub_index,
            severity=sub.category,
            status="available",
            approaching_threshold=approaching,
            threshold_note=threshold_note,
        )

    dom_pol = engine_res.dominant_pollutant
    highest_sub = (
        engine_res.sub_indices[dom_pol].sub_index
        if dom_pol and dom_pol in engine_res.sub_indices
        else None
    )
    raw_vs_sub_differs = (
        highest_raw_pol is not None
        and dom_pol is not None
        and highest_raw_pol != dom_pol
    )

    combinations = detect_pollutant_combinations(engine_res, cfg)

    return PollutantAnalysisResult(
        highest_measured_pollutant=highest_raw_pol,
        highest_measured_value=highest_raw_val if highest_raw_pol is not None else None,
        dominant_aqi_pollutant=dom_pol,
        highest_sub_index=highest_sub,
        raw_vs_subindex_differs=raw_vs_sub_differs,
        missing_pollutants=missing_pollutants,
        approaching_threshold_pollutants=approaching_pollutants,
        pollutant_summaries=summaries,
        combinations=combinations,
        aqi_result=engine_res,
    )


def detect_pollutant_combinations(
    aqi_result: AqiEngineResult,
    thresholds: dict[str, float] | None = None,
) -> list[PollutantCombinationFinding]:
    cfg = {**COMBINATION_THRESHOLDS, **(thresholds or {})}
    subs = aqi_result.sub_indices

    def _sub(k: str) -> float | None:
        item = subs.get(k)
        return item.sub_index if item and item.is_valid_input and item.sub_index is not None else None

    pm25_idx = _sub("pm25")
    pm10_idx = _sub("pm10")
    no2_idx = _sub("no2")
    so2_idx = _sub("so2")
    o3_idx = _sub("o3")

    findings: list[PollutantCombinationFinding] = []

    # 1. High PM2.5 + high PM10
    if (
        pm25_idx is not None
        and pm10_idx is not None
        and pm25_idx >= cfg["high_pm25_sub_index"]
        and pm10_idx >= cfg["high_pm10_sub_index"]
    ):
        findings.append(
            PollutantCombinationFinding(
                pattern_id="HIGH_PM25_PM10",
                title="High PM2.5 + High PM10 Co-Occurrence",
                matched_pollutants=["pm25", "pm10"],
                severity="High",
                summary=(
                    f"Both PM2.5 sub-index ({pm25_idx:g}) and PM10 sub-index ({pm10_idx:g}) "
                    f"meet or exceed configured high thresholds ({cfg['high_pm25_sub_index']:g} / {cfg['high_pm10_sub_index']:g})."
                ),
            )
        )

    # 2. Elevated NO2 + particulate matter (PM2.5 or PM10)
    pm_for_no2 = [
        (name, idx)
        for name, idx in (("pm25", pm25_idx), ("pm10", pm10_idx))
        if idx is not None and idx >= cfg["particulate_sub_index"]
    ]
    if no2_idx is not None and no2_idx >= cfg["elevated_no2_sub_index"] and pm_for_no2:
        matched = ["no2"] + [n for n, _ in pm_for_no2]
        findings.append(
            PollutantCombinationFinding(
                pattern_id="ELEVATED_NO2_PARTICULATES",
                title="Elevated NO2 Combined with Particulate Matter",
                matched_pollutants=matched,
                severity="Moderate-High",
                summary=(
                    f"NO2 sub-index ({no2_idx:g}) is elevated alongside particulate sub-index "
                    f"({', '.join(f'{n.upper()}={v:g}' for n, v in pm_for_no2)})."
                ),
            )
        )

    # 3. Elevated SO2 + particulate matter (PM2.5 or PM10)
    pm_for_so2 = [
        (name, idx)
        for name, idx in (("pm25", pm25_idx), ("pm10", pm10_idx))
        if idx is not None and idx >= cfg["particulate_sub_index"]
    ]
    if so2_idx is not None and so2_idx >= cfg["elevated_so2_sub_index"] and pm_for_so2:
        matched = ["so2"] + [n for n, _ in pm_for_so2]
        findings.append(
            PollutantCombinationFinding(
                pattern_id="ELEVATED_SO2_PARTICULATES",
                title="Elevated SO2 Combined with Particulate Matter",
                matched_pollutants=matched,
                severity="Moderate-High",
                summary=(
                    f"SO2 sub-index ({so2_idx:g}) is elevated alongside particulate sub-index "
                    f"({', '.join(f'{n.upper()}={v:g}' for n, v in pm_for_so2)})."
                ),
            )
        )

    # 4. Elevated O3 with other available measurements
    other_available = [
        k
        for k in POLLUTANT_KEYS
        if k != "o3" and _sub(k) is not None
    ]
    if o3_idx is not None and o3_idx >= cfg["elevated_o3_sub_index"] and other_available:
        findings.append(
            PollutantCombinationFinding(
                pattern_id="ELEVATED_O3_WITH_CO_POLLUTANTS",
                title="Elevated O3 Alongside Other Available Pollutant Readings",
                matched_pollutants=["o3"] + other_available,
                severity="Moderate",
                summary=(
                    f"O3 sub-index ({o3_idx:g}) is elevated with other available measurements "
                    f"({', '.join(k.upper() for k in other_available)})."
                ),
            )
        )

    return findings


def analyze_pollutants_from_reading(reading: AqiReading) -> PollutantAnalysisResult:
    return analyze_pollutants(
        pollutants=reading.pollutants,
        waqi_reported_aqi=reading.aqi,
    )