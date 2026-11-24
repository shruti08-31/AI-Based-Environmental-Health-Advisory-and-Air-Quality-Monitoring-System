from dataclasses import dataclass, field

from src.intelligence.pollutant_analysis import PollutantAnalysisResult

SOURCE_DISCLAIMER = (
    "Possible associations only. Pollutant patterns do not prove actual emission sources "
    "without dispersion modeling, chemical speciation, and local inspection."
)


@dataclass(frozen=True)
class SourceInsight:
    source_category: str
    observed_pattern: str
    possible_associated_source: str
    supporting_evidence: list[str] = field(default_factory=list)
    explanation: str = ""
    evidence_strength: str = "Low"
    limitations: list[str] = field(default_factory=list)


def generate_source_insights(analysis: PollutantAnalysisResult) -> list[SourceInsight]:
    subs = analysis.aqi_result.sub_indices if analysis.aqi_result else {}

    def _idx(key: str) -> float | None:
        item = subs.get(key)
        return item.sub_index if item and item.is_valid_input and item.sub_index is not None else None

    pm25 = _idx("pm25")
    pm10 = _idx("pm10")
    no2 = _idx("no2")
    so2 = _idx("so2")
    co = _idx("co")
    o3 = _idx("o3")

    common_limits = [
        SOURCE_DISCLAIMER,
        "Single-station readings cannot isolate local vs. transported air masses or meteorological mixing depth.",
    ]

    insights: list[SourceInsight] = []

    # 1. Traffic-related emissions
    no2_high = no2 is not None and no2 >= 51.0
    co_high = co is not None and co >= 51.0
    pm_present = (pm25 is not None and pm25 >= 51.0) or (pm10 is not None and pm10 >= 51.0)
    traffic_ev: list[str] = []
    if no2 is not None:
        traffic_ev.append(f"NO2 sub-index = {no2:g}")
    if co is not None:
        traffic_ev.append(f"CO sub-index = {co:g}")
    if pm_present:
        traffic_ev.append("Co-occurring particulate sub-index >= 51")

    if no2_high and (co_high or pm_present):
        strength = "Moderate"
        pattern = "Elevated NO2 paired with CO and/or particulate matter"
    elif no2_high or co_high:
        strength = "Low-Moderate"
        pattern = "Elevated NO2 or CO indicator without full multi-species confirmation"
    else:
        strength = "Low"
        pattern = "No prominent traffic-indicator spike in available measurements"

    insights.append(
        SourceInsight(
            source_category="Traffic-related emissions",
            observed_pattern=pattern,
            possible_associated_source="Road transport exhaust and vehicle activity",
            supporting_evidence=traffic_ev or ["Insufficient NO2/CO/PM sub-index data."],
            explanation=(
                "Combustion in motor vehicles commonly contributes to nitrogen oxides (NO2), "
                "carbon monoxide (CO), and fine/coarse particulates along roadways."
            ),
            evidence_strength=strength,
            limitations=common_limits + ["Traffic volume, fleet mix, and wind direction are not included."],
        )
    )

    # 2. Construction and dust
    coarse_ratio = (pm10 / pm25) if (pm10 is not None and pm25 is not None and pm25 > 0) else None
    dust_ev: list[str] = []
    if pm10 is not None:
        dust_ev.append(f"PM10 sub-index = {pm10:g}")
    if coarse_ratio is not None:
        dust_ev.append(f"PM10/PM2.5 sub-index ratio = {coarse_ratio:.2f}")

    if pm10 is not None and pm10 >= 101.0 and (coarse_ratio is None or coarse_ratio >= 1.1):
        strength = "Moderate"
        pattern = "Elevated PM10 sub-index with coarse-fraction contribution"
    elif pm10 is not None and pm10 >= 51.0:
        strength = "Low-Moderate"
        pattern = "Moderate-or-higher PM10 sub-index"
    else:
        strength = "Low"
        pattern = "PM10 sub-index below elevated threshold or missing"

    insights.append(
        SourceInsight(
            source_category="Construction and dust",
            observed_pattern=pattern,
            possible_associated_source="Construction activity, unpaved surfaces, or windblown dust",
            supporting_evidence=dust_ev or ["Insufficient PM10/PM2.5 data."],
            explanation=(
                "Mechanical disturbance, earthworks, and resuspended road or soil dust often raise "
                "coarse particulate matter (PM10) levels."
            ),
            evidence_strength=strength,
            limitations=common_limits + ["Soil moisture, surface wind speed, and nearby site activity are unverified."],
        )
    )

    # 3. Industrial emissions
    ind_ev: list[str] = []
    if so2 is not None:
        ind_ev.append(f"SO2 sub-index = {so2:g}")
    if no2 is not None:
        ind_ev.append(f"NO2 sub-index = {no2:g}")
    if pm25 is not None:
        ind_ev.append(f"PM2.5 sub-index = {pm25:g}")

    if so2 is not None and so2 >= 51.0 and (pm25 is not None and pm25 >= 51.0):
        strength = "Moderate"
        pattern = "Elevated SO2 co-occurring with particulate matter"
    elif so2 is not None and so2 >= 51.0:
        strength = "Low-Moderate"
        pattern = "Elevated SO2 sub-index"
    else:
        strength = "Low"
        pattern = "No elevated SO2 signature in current readings"

    insights.append(
        SourceInsight(
            source_category="Industrial emissions",
            observed_pattern=pattern,
            possible_associated_source="Industrial boilers, processing units, or sulfur-bearing emissions",
            supporting_evidence=ind_ev or ["Insufficient SO2/particulate data."],
            explanation=(
                "Sulfur dioxide (SO2) alongside particulates can coincide with industrial fuel use or "
                "process emissions, though non-industrial sources also exist."
            ),
            evidence_strength=strength,
            limitations=common_limits + ["Facility-level emissions and stack plume trajectories are not observed."],
        )
    )

    # 4. Fuel combustion
    comb_ev: list[str] = []
    for k, v in (("pm25", pm25), ("co", co), ("no2", no2), ("so2", so2)):
        if v is not None:
            comb_ev.append(f"{k.upper()} sub-index = {v:g}")

    active_comb_count = sum(1 for v in (pm25, co, no2, so2) if v is not None and v >= 51.0)
    if active_comb_count >= 2:
        strength = "Moderate"
        pattern = "Multiple combustion-related sub-indices above baseline"
    elif active_comb_count == 1:
        strength = "Low-Moderate"
        pattern = "Single combustion-related pollutant elevated"
    else:
        strength = "Low"
        pattern = "Combustion indicators low or unavailable"

    insights.append(
        SourceInsight(
            source_category="Fuel combustion",
            observed_pattern=pattern,
            possible_associated_source="Stationary or mobile fossil-fuel combustion",
            supporting_evidence=comb_ev or ["Insufficient combustion-related pollutant data."],
            explanation=(
                "Incomplete or high-temperature fuel burning can elevate PM2.5, CO, NO2, or SO2 "
                "depending on fuel type and operating conditions."
            ),
            evidence_strength=strength,
            limitations=common_limits + ["Fuel composition and combustion efficiency cannot be inferred from AQI alone."],
        )
    )

    # 5. Biomass burning
    bio_ev: list[str] = []
    if pm25 is not None:
        bio_ev.append(f"PM2.5 sub-index = {pm25:g}")
    if co is not None:
        bio_ev.append(f"CO sub-index = {co:g}")
    if o3 is not None:
        bio_ev.append(f"O3 sub-index = {o3:g}")

    if pm25 is not None and pm25 >= 101.0 and co is not None and co >= 51.0:
        strength = "Moderate"
        pattern = "Elevated fine particulates (PM2.5) accompanied by elevated CO"
    elif pm25 is not None and pm25 >= 51.0:
        strength = "Low-Moderate"
        pattern = "Elevated PM2.5 sub-index (possible smoke or regional aerosol contribution)"
    else:
        strength = "Low"
        pattern = "Low or missing PM2.5/CO smoke indicators"

    insights.append(
        SourceInsight(
            source_category="Biomass burning",
            observed_pattern=pattern,
            possible_associated_source="Agricultural residue burning, wood/biomass fires, or open burning",
            supporting_evidence=bio_ev or ["Insufficient PM2.5/CO/O3 data."],
            explanation=(
                "Biomass and open burning frequently release fine particulate matter (PM2.5) and "
                "carbon monoxide (CO), and can contribute to regional haze."
            ),
            evidence_strength=strength,
            limitations=common_limits + ["Satellite fire detections and chemical tracers (e.g., levoglucosan/potassium) are not included."],
        )
    )

    return insights


def generate_source_insights_from_analysis(analysis: PollutantAnalysisResult) -> list[SourceInsight]:
    return generate_source_insights(analysis)