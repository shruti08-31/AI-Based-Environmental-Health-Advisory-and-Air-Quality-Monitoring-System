from src.core.aqi_engine import (
    calculate_pollutant_sub_index,
    classify_aqi_category,
    evaluate_aqi,
)
from src.core.health_engine import SensitivityGroup, generate_health_advisory
from src.intelligence.pollutant_analysis import analyze_pollutants
from src.intelligence.source_insights import SOURCE_DISCLAIMER, generate_source_insights


def test_aqi_category_boundaries_and_missing_invalid() -> None:
    assert classify_aqi_category(0) == "Good"
    assert classify_aqi_category(50) == "Good"
    assert classify_aqi_category(51) == "Satisfactory"
    assert classify_aqi_category(100) == "Satisfactory"
    assert classify_aqi_category(101) == "Moderate"
    assert classify_aqi_category(200) == "Moderate"
    assert classify_aqi_category(201) == "Poor"
    assert classify_aqi_category(300) == "Poor"
    assert classify_aqi_category(301) == "Very Poor"
    assert classify_aqi_category(400) == "Very Poor"
    assert classify_aqi_category(401) == "Severe"
    assert classify_aqi_category(500) == "Severe"
    assert classify_aqi_category(-10) == "Unavailable"
    assert classify_aqi_category(None) == "Unavailable"

    missing_sub = calculate_pollutant_sub_index("pm25", None)
    assert missing_sub.sub_index is None
    assert missing_sub.is_valid_input is False

    neg_sub = calculate_pollutant_sub_index("pm10", -12.0)
    assert neg_sub.sub_index is None
    assert neg_sub.is_valid_input is False


def test_dominant_pollutant_vs_highest_raw_concentration() -> None:
    # PM10 raw = 120 -> sub-index ~113.8 (Moderate)
    # PM2.5 raw = 75 -> sub-index ~150.5 (Moderate)
    # CO raw = 8.0 -> sub-index ~175.0 (Moderate) -> highest sub-index is CO even though PM10 raw is 120
    pollutants = {
        "pm25": 75.0,
        "pm10": 120.0,
        "no2": 30.0,
        "so2": 15.0,
        "co": 8.0,
        "o3": 40.0,
    }
    res = evaluate_aqi(pollutants, waqi_reported_aqi=999)
    assert res.waqi_reported_aqi == 999
    assert res.dominant_pollutant == "co"
    assert res.calculated_aqi is not None
    assert res.category == "Moderate"

    analysis = analyze_pollutants(pollutants, waqi_reported_aqi=999)
    assert analysis.highest_measured_pollutant == "pm10"
    assert analysis.dominant_aqi_pollutant == "co"
    assert analysis.raw_vs_subindex_differs is True


def test_pollutant_combinations_and_source_insights() -> None:
    pollutants = {
        "pm25": 150.0,  # Very Poor (~323)
        "pm10": 280.0,  # Poor (~230)
        "no2": 95.0,    # Moderate (~120)
        "so2": 90.0,    # Moderate (~103)
        "co": 3.0,      # Moderate (~113)
        "o3": 120.0,    # Moderate (~123)
    }
    analysis = analyze_pollutants(pollutants)
    pattern_ids = {c.pattern_id for c in analysis.combinations}
    assert "HIGH_PM25_PM10" in pattern_ids
    assert "ELEVATED_NO2_PARTICULATES" in pattern_ids
    assert "ELEVATED_SO2_PARTICULATES" in pattern_ids
    assert "ELEVATED_O3_WITH_CO_POLLUTANTS" in pattern_ids

    insights = generate_source_insights(analysis)
    categories = {item.source_category for item in insights}
    assert categories == {
        "Traffic-related emissions",
        "Construction and dust",
        "Industrial emissions",
        "Fuel combustion",
        "Biomass burning",
    }
    for item in insights:
        assert item.observed_pattern
        assert item.possible_associated_source
        assert item.supporting_evidence
        assert item.explanation
        assert item.evidence_strength
        assert item.limitations
        assert any(SOURCE_DISCLAIMER in lim for lim in item.limitations)


def test_health_advisory_rules() -> None:
    adv = generate_health_advisory(
        category="Poor",
        sensitivity_group=SensitivityGroup.SENSITIVE,
        dominant_pollutant="pm25",
    )
    assert adv.category == "Poor"
    assert adv.urgency_level == "High"
    assert len(adv.general_precautions) > 0
    assert len(adv.sensitive_group_precautions) > 0
    assert len(adv.exposure_reduction_suggestions) > 0
    assert len(adv.outdoor_activity_precautions) > 0
    assert any("RULE_AQI_POOR" in r for r in adv.rules_applied)
    assert "not a medical diagnosis" in adv.disclaimer.lower()