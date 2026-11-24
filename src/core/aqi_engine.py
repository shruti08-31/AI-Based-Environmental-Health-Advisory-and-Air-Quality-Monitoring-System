from dataclasses import dataclass, field
from typing import Any

from src.api.waqi_client import POLLUTANT_KEYS, AqiReading

AQI_STANDARD_NAME = "CPCB National Air Quality Index (IND-AQI) Breakpoint Standard"
AQI_STANDARD_NOTES = (
    "Sub-indices are computed deterministically via piecewise linear interpolation using "
    "CPCB breakpoint bands across six categories (Good, Satisfactory, Moderate, Poor, "
    "Very Poor, Severe). Reference averaging basis: PM2.5, PM10, NO2, SO2 (24-hr basis in "
    "ug/m3); CO (8-hr basis in mg/m3); O3 (8-hr basis in ug/m3). WAQI API 'aqi' is "
    "preserved separately and never overwritten or determined by an LLM."
)

# Each tuple entry: (bp_low, bp_high, index_low, index_high, category_name)
# Bands cover 0..500 across Good (0-50), Satisfactory (51-100), Moderate (101-200),
# Poor (201-300), Very Poor (301-400), and Severe (401-500).
POLLUTANT_BREAKPOINTS: dict[str, list[tuple[float, float, float, float, str]]] = {
    "pm25": [
        (0.0, 30.0, 0.0, 50.0, "Good"),
        (30.001, 60.0, 51.0, 100.0, "Satisfactory"),
        (60.001, 90.0, 101.0, 200.0, "Moderate"),
        (90.001, 120.0, 201.0, 300.0, "Poor"),
        (120.001, 250.0, 301.0, 400.0, "Very Poor"),
        (250.001, 500.0, 401.0, 500.0, "Severe"),
    ],
    "pm10": [
        (0.0, 50.0, 0.0, 50.0, "Good"),
        (50.001, 100.0, 51.0, 100.0, "Satisfactory"),
        (100.001, 250.0, 101.0, 200.0, "Moderate"),
        (250.001, 350.0, 201.0, 300.0, "Poor"),
        (350.001, 430.0, 301.0, 400.0, "Very Poor"),
        (430.001, 800.0, 401.0, 500.0, "Severe"),
    ],
    "no2": [
        (0.0, 40.0, 0.0, 50.0, "Good"),
        (40.001, 80.0, 51.0, 100.0, "Satisfactory"),
        (80.001, 180.0, 101.0, 200.0, "Moderate"),
        (180.001, 280.0, 201.0, 300.0, "Poor"),
        (280.001, 400.0, 301.0, 400.0, "Very Poor"),
        (400.001, 800.0, 401.0, 500.0, "Severe"),
    ],
    "so2": [
        (0.0, 40.0, 0.0, 50.0, "Good"),
        (40.001, 80.0, 51.0, 100.0, "Satisfactory"),
        (80.001, 380.0, 101.0, 200.0, "Moderate"),
        (380.001, 800.0, 201.0, 300.0, "Poor"),
        (800.001, 1600.0, 301.0, 400.0, "Very Poor"),
        (1600.001, 2400.0, 401.0, 500.0, "Severe"),
    ],
    "co": [
        (0.0, 1.0, 0.0, 50.0, "Good"),
        (1.001, 2.0, 51.0, 100.0, "Satisfactory"),
        (2.001, 10.0, 101.0, 200.0, "Moderate"),
        (10.001, 17.0, 201.0, 300.0, "Poor"),
        (17.001, 34.0, 301.0, 400.0, "Very Poor"),
        (34.001, 60.0, 401.0, 500.0, "Severe"),
    ],
    "o3": [
        (0.0, 50.0, 0.0, 50.0, "Good"),
        (50.001, 100.0, 51.0, 100.0, "Satisfactory"),
        (100.001, 168.0, 101.0, 200.0, "Moderate"),
        (168.001, 208.0, 201.0, 300.0, "Poor"),
        (208.001, 748.0, 301.0, 400.0, "Very Poor"),
        (748.001, 1000.0, 401.0, 500.0, "Severe"),
    ],
}

CATEGORY_EXPLANATIONS: dict[str, str] = {
    "Good": (
        "Air quality is considered clean with minimal health impact across the general population."
    ),
    "Satisfactory": (
        "Air quality is acceptable; minor breathing discomfort may occur in unusually sensitive individuals."
    ),
    "Moderate": (
        "May cause breathing discomfort to individuals with lung conditions such as asthma, "
        "and discomfort to people with heart disease, children, and older adults."
    ),
    "Poor": (
        "May cause breathing discomfort to most people on prolonged exposure, and discomfort to "
        "individuals with heart or respiratory conditions."
    ),
    "Very Poor": (
        "May cause respiratory illness on prolonged exposure; effects are more pronounced in "
        "people with lung or heart diseases."
    ),
    "Severe": (
        "Severe air quality level that may cause respiratory effects even in healthy people and "
        "serious health impacts in individuals with lung or heart conditions."
    ),
    "Unavailable": (
        "Insufficient valid pollutant measurements are available to deterministically compute an AQI."
    ),
}


@dataclass(frozen=True)
class PollutantSubIndex:
    pollutant: str
    raw_value: float | None
    sub_index: float | None
    category: str
    is_valid_input: bool
    note: str


@dataclass(frozen=True)
class AqiEngineResult:
    standard_name: str
    standard_notes: str
    calculated_aqi: int | None
    category: str
    category_explanation: str
    dominant_pollutant: str | None
    waqi_reported_aqi: float | int | None
    sub_indices: dict[str, PollutantSubIndex] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def classify_aqi_category(aqi_value: float | int | None) -> str:
    if aqi_value is None or isinstance(aqi_value, bool):
        return "Unavailable"
    try:
        val = float(aqi_value)
    except (TypeError, ValueError):
        return "Unavailable"
    if val != val or val in (float("inf"), float("-inf")) or val < 0:
        return "Unavailable"
    if val <= 50.0:
        return "Good"
    if val <= 100.0:
        return "Satisfactory"
    if val <= 200.0:
        return "Moderate"
    if val <= 300.0:
        return "Poor"
    if val <= 400.0:
        return "Very Poor"
    return "Severe"


def calculate_pollutant_sub_index(pollutant: str, concentration: Any) -> PollutantSubIndex:
    key = (pollutant or "").strip().lower()
    if key not in POLLUTANT_BREAKPOINTS:
        return PollutantSubIndex(
            pollutant=key,
            raw_value=None,
            sub_index=None,
            category="Unavailable",
            is_valid_input=False,
            note=f"Unsupported pollutant '{pollutant}'.",
        )

    if concentration is None or isinstance(concentration, bool):
        return PollutantSubIndex(
            pollutant=key,
            raw_value=None,
            sub_index=None,
            category="Unavailable",
            is_valid_input=False,
            note="Measurement missing (not imputed).",
        )

    try:
        conc = float(concentration)
    except (TypeError, ValueError):
        return PollutantSubIndex(
            pollutant=key,
            raw_value=None,
            sub_index=None,
            category="Unavailable",
            is_valid_input=False,
            note="Non-numeric measurement excluded.",
        )

    if conc != conc or conc in (float("inf"), float("-inf")):
        return PollutantSubIndex(
            pollutant=key,
            raw_value=None,
            sub_index=None,
            category="Unavailable",
            is_valid_input=False,
            note="Non-finite measurement excluded.",
        )

    if conc < 0.0:
        return PollutantSubIndex(
            pollutant=key,
            raw_value=conc,
            sub_index=None,
            category="Unavailable",
            is_valid_input=False,
            note=f"Negative measurement ({conc}) excluded.",
        )

    bands = POLLUTANT_BREAKPOINTS[key]
    for bp_lo, bp_hi, idx_lo, idx_hi, band_category in bands:
        if bp_lo <= conc <= bp_hi:
            if bp_hi == bp_lo:
                sub_val = idx_hi
            else:
                ratio = (conc - bp_lo) / (bp_hi - bp_lo)
                sub_val = idx_lo + ratio * (idx_hi - idx_lo)
            clamped = max(0.0, min(500.0, sub_val))
            rounded_sub = round(clamped, 1)
            return PollutantSubIndex(
                pollutant=key,
                raw_value=conc,
                sub_index=rounded_sub,
                category=classify_aqi_category(rounded_sub),
                is_valid_input=True,
                note=f"CPCB band [{bp_lo:g}, {bp_hi:g}] -> index [{idx_lo:g}, {idx_hi:g}] ({band_category}).",
            )

    # Above highest configured breakpoint upper bound: cap at 500 (Severe)
    return PollutantSubIndex(
        pollutant=key,
        raw_value=conc,
        sub_index=500.0,
        category="Severe",
        is_valid_input=True,
        note="Above upper CPCB breakpoint band; capped at 500 (Severe).",
    )


def evaluate_aqi(
    pollutants: dict[str, Any],
    waqi_reported_aqi: float | int | None = None,
) -> AqiEngineResult:
    sub_indices: dict[str, PollutantSubIndex] = {}
    warnings: list[str] = []

    best_pollutant: str | None = None
    best_sub_index: float = -1.0

    for key in POLLUTANT_KEYS:
        raw_val = pollutants.get(key) if isinstance(pollutants, dict) else None
        sub = calculate_pollutant_sub_index(key, raw_val)
        sub_indices[key] = sub

        if raw_val is not None and not sub.is_valid_input:
            warnings.append(f"{key.upper()}: {sub.note}")

        if sub.is_valid_input and sub.sub_index is not None:
            if sub.sub_index > best_sub_index:
                best_sub_index = sub.sub_index
                best_pollutant = key

    if best_pollutant is None or best_sub_index < 0:
        return AqiEngineResult(
            standard_name=AQI_STANDARD_NAME,
            standard_notes=AQI_STANDARD_NOTES,
            calculated_aqi=None,
            category="Unavailable",
            category_explanation=CATEGORY_EXPLANATIONS["Unavailable"],
            dominant_pollutant=None,
            waqi_reported_aqi=waqi_reported_aqi,
            sub_indices=sub_indices,
            warnings=warnings or ["No valid pollutant concentrations available for AQI calculation."],
        )

    calculated_aqi = int(round(best_sub_index))
    category = classify_aqi_category(calculated_aqi)

    return AqiEngineResult(
        standard_name=AQI_STANDARD_NAME,
        standard_notes=AQI_STANDARD_NOTES,
        calculated_aqi=calculated_aqi,
        category=category,
        category_explanation=CATEGORY_EXPLANATIONS[category],
        dominant_pollutant=best_pollutant,
        waqi_reported_aqi=waqi_reported_aqi,
        sub_indices=sub_indices,
        warnings=warnings,
    )


def evaluate_aqi_from_reading(reading: AqiReading) -> AqiEngineResult:
    return evaluate_aqi(
        pollutants=reading.pollutants,
        waqi_reported_aqi=reading.aqi,
    )