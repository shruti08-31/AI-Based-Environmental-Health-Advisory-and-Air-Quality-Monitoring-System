from dataclasses import dataclass, field
from typing import Any

from src.api.waqi_client import AqiReading
from src.core.aqi_engine import AqiEngineResult, evaluate_aqi_from_reading
from src.core.health_engine import SensitivityGroup

SUPPORTED_ACTIVITIES: tuple[str, ...] = (
    "Walking",
    "Running",
    "Cycling",
    "Outdoor exercise",
    "Indoor exercise",
)

SAFETY_DISCLAIMER = (
    "Guidance only; air quality conditions change and this advisor does not guarantee "
    "that any activity is free from health risk."
)


@dataclass(frozen=True)
class ActivityGuidance:
    activity: str
    aqi_category: str
    calculated_aqi: int | None
    sensitivity_group: str
    recommendation: str
    precautions: list[str] = field(default_factory=list)
    alternative_activity: str = ""
    explanation: str = ""
    disclaimer: str = SAFETY_DISCLAIMER


def advise_activity(
    activity: str,
    aqi_category: str,
    calculated_aqi: int | None = None,
    pollutants: dict[str, Any] | None = None,
    sensitivity_group: SensitivityGroup | str = SensitivityGroup.GENERAL,
) -> ActivityGuidance:
    act_norm = activity if activity in SUPPORTED_ACTIVITIES else "Outdoor exercise"
    cat_norm = aqi_category if aqi_category in (
        "Good",
        "Satisfactory",
        "Moderate",
        "Poor",
        "Very Poor",
        "Severe",
    ) else "Unavailable"

    group_label = (
        sensitivity_group.value
        if isinstance(sensitivity_group, SensitivityGroup)
        else str(sensitivity_group or SensitivityGroup.GENERAL.value)
    )
    is_sensitive = "sensitive" in group_label.lower()
    is_high_exertion = act_norm in ("Running", "Cycling", "Outdoor exercise")
    is_indoor = act_norm == "Indoor exercise"

    available_pols = [
        k.upper()
        for k, v in (pollutants or {}).items()
        if v is not None and not isinstance(v, bool)
    ]
    pol_note = (
        f"Available pollutants considered: {', '.join(available_pols)}."
        if available_pols
        else "Limited or no individual pollutant measurements available."
    )

    if cat_norm == "Unavailable":
        recommendation = "Exercise Caution / Defer High Exertion"
        alternative = "Low-intensity Indoor exercise in a clean, well-ventilated space until valid AQI data is available."
        explanation = f"Severity category is unavailable due to missing or invalid AQI readings. {pol_note}"
        precautions = [
            "Avoid assuming outdoor air is clean when AQI readings are unavailable.",
            "Keep exertion moderate and monitor how you feel.",
        ]
    elif is_indoor:
        if cat_norm in ("Good", "Satisfactory", "Moderate"):
            recommendation = "Suitable for Indoor Exercise"
            alternative = "Brisk Walking or light outdoor activity if indoor air is comfortable."
            explanation = f"Indoor exercise avoids direct outdoor exposure during {cat_norm} conditions. {pol_note}"
            precautions = [
                "Maintain steady indoor airflow without drawing in polluted outdoor air.",
                "Stay hydrated and pace sessions appropriately.",
            ]
        else:
            recommendation = "Preferred Option During Elevated Outdoor AQI"
            alternative = "Gentle indoor mobility or stretching in filtered/clean indoor air."
            explanation = f"Outdoor AQI is {cat_norm}, making controlled indoor exercise preferable to outdoor exertion. {pol_note}"
            precautions = [
                "Keep windows and doors closed to limit outdoor pollutant infiltration.",
                "Avoid indoor smoke, incense, or unvented combustion sources during workouts.",
            ]
    elif cat_norm in ("Good", "Satisfactory"):
        recommendation = "Generally Favorable" if not is_sensitive else "Generally Favorable With Routine Care"
        alternative = "Indoor exercise if weather or personal comfort makes outdoors inconvenient."
        explanation = f"Calculated AQI category is {cat_norm} (AQI: {calculated_aqi if calculated_aqi is not None else 'N/A'}). {pol_note}"
        precautions = [
            "Choose routes away from heavy traffic or active construction dust where possible.",
            "Stop and rest if unusual shortness of breath or irritation occurs.",
        ]
    elif cat_norm == "Moderate":
        if is_high_exertion or is_sensitive:
            recommendation = "Moderate Intensity / Shorten Duration"
            alternative = "Indoor exercise or lighter Walking instead of vigorous Running or Cycling."
            explanation = f"Moderate AQI ({calculated_aqi if calculated_aqi is not None else 'N/A'}) increases respiratory ventilation during exertion. {pol_note}"
            precautions = [
                "Reduce workout intensity and duration, especially for sensitive individuals.",
                "Avoid peak traffic hours and busy arterial roads.",
            ]
        else:
            recommendation = "Acceptable With Pacing"
            alternative = "Indoor exercise if feeling mild throat or airway sensitivity."
            explanation = f"Moderate AQI allows paced walking with basic exposure awareness. {pol_note}"
            precautions = [
                "Keep walking pace comfortable and avoid dusty roadside corridors.",
            ]
    else:
        # Poor, Very Poor, or Severe
        recommendation = "Limit or Avoid Outdoor Exertion" if cat_norm == "Poor" else "Avoid Outdoor Activity; Move Indoors"
        alternative = "Indoor exercise in a clean, enclosed space rather than outdoor Running, Cycling, or Walking."
        explanation = f"Elevated AQI tier ({cat_norm}, AQI: {calculated_aqi if calculated_aqi is not None else 'N/A'}) poses higher respiratory/cardiovascular load. {pol_note}"
        precautions = [
            "Postpone strenuous outdoor exercise such as running or cycling.",
            "If brief outdoor travel is unavoidable, consider a well-fitted particulate respirator (e.g., N95/FFP2).",
            "Sensitive groups should stay indoors and follow clinician guidance if symptoms arise.",
        ]

    if is_sensitive and cat_norm in ("Moderate", "Poor", "Very Poor", "Severe"):
        precautions.insert(0, f"Sensitivity profile ({group_label}) is active: prioritize indoor options and watch for symptoms.")

    return ActivityGuidance(
        activity=act_norm,
        aqi_category=cat_norm,
        calculated_aqi=calculated_aqi,
        sensitivity_group=group_label,
        recommendation=recommendation,
        precautions=precautions,
        alternative_activity=alternative,
        explanation=explanation,
        disclaimer=SAFETY_DISCLAIMER,
    )


def advise_activity_from_reading(
    activity: str,
    reading: AqiReading,
    aqi_result: AqiEngineResult | None = None,
    sensitivity_group: SensitivityGroup | str = SensitivityGroup.GENERAL,
) -> ActivityGuidance:
    eng = aqi_result or evaluate_aqi_from_reading(reading)
    return advise_activity(
        activity=activity,
        aqi_category=eng.category,
        calculated_aqi=eng.calculated_aqi,
        pollutants=reading.pollutants,
        sensitivity_group=sensitivity_group,
    )