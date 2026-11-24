from dataclasses import dataclass, field
from enum import Enum


class SensitivityGroup(str, Enum):
    GENERAL = "General Public"
    SENSITIVE = "Sensitive Groups (Asthma, Heart/Lung Disease, Children, Older Adults)"


MEDICAL_DISCLAIMER = (
    "Informational public-health guidance only. This output is not a medical diagnosis "
    "or clinical treatment plan; consult a qualified healthcare provider for personal symptoms."
)


@dataclass(frozen=True)
class HealthAdvisoryResult:
    category: str
    sensitivity_group: str
    urgency_level: str
    general_precautions: list[str] = field(default_factory=list)
    sensitive_group_precautions: list[str] = field(default_factory=list)
    exposure_reduction_suggestions: list[str] = field(default_factory=list)
    outdoor_activity_precautions: list[str] = field(default_factory=list)
    rules_applied: list[str] = field(default_factory=list)
    disclaimer: str = MEDICAL_DISCLAIMER


_ADVISORY_RULES: dict[str, dict[str, object]] = {
    "Good": {
        "urgency": "Low",
        "general": [
            "Routine daily activities can proceed normally.",
            "Keep indoor spaces naturally ventilated when outdoor air is clear.",
        ],
        "sensitive": [
            "Normal outdoor activity is generally well tolerated.",
            "Continue routine prescribed maintenance plans if applicable.",
        ],
        "exposure": [
            "Maintain basic housekeeping to prevent indoor dust buildup.",
            "Use natural cross-ventilation during mild hours.",
        ],
        "outdoor": [
            "No AQI-driven restrictions on outdoor exercise or travel.",
        ],
        "rule_id": "RULE_AQI_GOOD (0-50)",
    },
    "Satisfactory": {
        "urgency": "Low-Moderate",
        "general": [
            "Most adults can carry out normal outdoor routines comfortably.",
            "Monitor local AQI updates if spending extended hours near busy roadways.",
        ],
        "sensitive": [
            "Individuals unusually sensitive to particulates or ozone should watch for mild throat or airway irritation.",
            "Keep quick-relief inhalers or routine medications accessible if advised by a clinician.",
        ],
        "exposure": [
            "Reduce prolonged idling or unnecessary exposure near heavy traffic corridors.",
            "Ventilate indoor rooms during cleaner periods of the day.",
        ],
        "outdoor": [
            "Routine outdoor activities are acceptable; sensitive individuals may prefer lighter exertion.",
        ],
        "rule_id": "RULE_AQI_SATISFACTORY (51-100)",
    },
    "Moderate": {
        "urgency": "Moderate",
        "general": [
            "Consider moderating prolonged or strenuous outdoor exertion.",
            "Pay attention to respiratory or cardiovascular symptoms during outdoor tasks.",
        ],
        "sensitive": [
            "Children, older adults, and people with asthma or heart/lung conditions should limit prolonged outdoor exertion.",
            "Monitor symptoms closely and move strenuous tasks indoors if discomfort appears.",
        ],
        "exposure": [
            "Keep windows closed during peak traffic or high-pollution hours.",
            "Use indoor air filtration if available and avoid indoor smoke or incense sources.",
        ],
        "outdoor": [
            "Shorten intense outdoor workouts; schedule outdoor errands outside peak congestion hours.",
        ],
        "rule_id": "RULE_AQI_MODERATE (101-200)",
    },
    "Poor": {
        "urgency": "High",
        "general": [
            "Reduce prolonged or heavy outdoor physical activity.",
            "Limit time spent near congested roads, construction sites, or open burning.",
        ],
        "sensitive": [
            "Avoid prolonged outdoor exposure; sensitive groups should prioritize indoor environments.",
            "Follow clinician guidance promptly if coughing, wheezing, chest tightness, or shortness of breath occurs.",
        ],
        "exposure": [
            "Keep doors and windows closed to limit outdoor infiltration.",
            "Run portable HEPA filtration or clean indoor air recirculation where available.",
            "Consider a well-fitted particulate respirator (such as N95/FFP2) if outdoor exposure is unavoidable.",
        ],
        "outdoor": [
            "Reschedule vigorous outdoor exercise indoors; keep outdoor trips brief.",
        ],
        "rule_id": "RULE_AQI_POOR (201-300)",
    },
    "Very Poor": {
        "urgency": "Very High",
        "general": [
            "Avoid prolonged outdoor exertion and minimize non-essential outdoor time.",
            "Watch for respiratory irritation, headaches, or unusual fatigue.",
        ],
        "sensitive": [
            "Remain indoors as much as possible and avoid outdoor physical activity.",
            "Seek medical evaluation promptly if symptoms worsen or do not resolve indoors.",
        ],
        "exposure": [
            "Keep indoor air sealed from outdoor drafts and operate air purifiers continuously if available.",
            "Wear a well-fitting N95/FFP2 respirator when stepping outside is necessary.",
            "Avoid adding indoor pollutants such as candles, spray cleaners, or indoor smoking.",
        ],
        "outdoor": [
            "Move all exercise and recreation indoors; keep outdoor errands brief and direct.",
        ],
        "rule_id": "RULE_AQI_VERY_POOR (301-400)",
    },
    "Severe": {
        "urgency": "Critical",
        "general": [
            "Avoid outdoor physical exertion and stay indoors as much as possible.",
            "Treat acute breathing difficulty or chest discomfort as urgent and seek medical care.",
        ],
        "sensitive": [
            "Stay strictly indoors in filtered or clean indoor spaces and avoid all outdoor exertion.",
            "Maintain close contact with caregivers or healthcare providers for individuals with chronic heart or lung disease.",
        ],
        "exposure": [
            "Keep windows and exterior gaps closed; run high-efficiency indoor filtration if available.",
            "Use a properly fitted N95/FFP2 respirator if essential outdoor travel cannot be deferred.",
        ],
        "outdoor": [
            "Cancel or postpone outdoor workouts and non-essential outdoor activities.",
        ],
        "rule_id": "RULE_AQI_SEVERE (401-500)",
    },
    "Unavailable": {
        "urgency": "Unknown",
        "general": [
            "Insufficient valid pollutant readings are available to determine an AQI health tier.",
            "Rely on verified local public-health advisories until valid measurements return.",
        ],
        "sensitive": [
            "Sensitive individuals should exercise caution and avoid unverified high-exposure areas while data is unavailable.",
        ],
        "exposure": [
            "Check sensor/feed status and avoid assuming clean air when data is missing.",
        ],
        "outdoor": [
            "Exercise caution with strenuous outdoor activity until valid air quality data is confirmed.",
        ],
        "rule_id": "RULE_AQI_UNAVAILABLE",
    },
}


def generate_health_advisory(
    category: str,
    sensitivity_group: SensitivityGroup | str = SensitivityGroup.GENERAL,
    dominant_pollutant: str | None = None,
) -> HealthAdvisoryResult:
    norm_category = category if category in _ADVISORY_RULES else "Unavailable"
    group_label = (
        sensitivity_group.value
        if isinstance(sensitivity_group, SensitivityGroup)
        else str(sensitivity_group or SensitivityGroup.GENERAL.value)
    )
    is_sensitive = "sensitive" in group_label.lower()

    spec = _ADVISORY_RULES[norm_category]
    general = list(spec["general"])  # type: ignore[arg-type]
    sensitive = list(spec["sensitive"])  # type: ignore[arg-type]
    exposure = list(spec["exposure"])  # type: ignore[arg-type]
    outdoor = list(spec["outdoor"])  # type: ignore[arg-type]
    rules_applied = [
        str(spec["rule_id"]),
        f"RULE_SENSITIVITY_PROFILE ({group_label})",
    ]

    if dominant_pollutant:
        dom = dominant_pollutant.strip().upper()
        rules_applied.append(f"RULE_DOMINANT_POLLUTANT_CONTEXT ({dom})")
        if dom in ("PM25", "PM10") and norm_category in ("Moderate", "Poor", "Very Poor", "Severe"):
            exposure.append(
                f"Particulate matter ({dom}) is the leading sub-index contributor; fine/coarse particles penetrate indoors and deep airways."
            )
        elif dom == "O3" and norm_category in ("Moderate", "Poor", "Very Poor", "Severe"):
            outdoor.append(
                "Ground-level ozone (O3) often peaks in afternoon sunlight; avoid strenuous outdoor exertion during peak sun hours."
            )
        elif dom in ("NO2", "SO2", "CO") and norm_category in ("Moderate", "Poor", "Very Poor", "Severe"):
            exposure.append(
                f"Gaseous pollutant ({dom}) is driving the index; avoid roadways, industrial zones, and enclosed combustion areas."
            )

    if is_sensitive and norm_category in ("Moderate", "Poor", "Very Poor", "Severe"):
        outdoor.insert(0, "Sensitive profile active: prioritize indoor activities and shorten outdoor exposure windows.")

    return HealthAdvisoryResult(
        category=norm_category,
        sensitivity_group=group_label,
        urgency_level=str(spec["urgency"]),
        general_precautions=general,
        sensitive_group_precautions=sensitive,
        exposure_reduction_suggestions=exposure,
        outdoor_activity_precautions=outdoor,
        rules_applied=rules_applied,
        disclaimer=MEDICAL_DISCLAIMER,
    )