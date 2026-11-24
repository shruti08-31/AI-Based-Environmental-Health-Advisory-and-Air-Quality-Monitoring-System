from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from src.activity import SUPPORTED_ACTIVITIES, advise_activity_from_reading
from src.analytics import compare_station_observations, compute_historical_analytics
from src.api import AqiReading
from src.api.weather_client import WeatherClient, WeatherClientError, analyze_weather_pollution_context
from src.core import evaluate_aqi_from_reading, generate_health_advisory
from src.database import get_latest_observations_per_station, get_observations
from src.intelligence import analyze_pollutants_from_reading, detect_anomalies, generate_source_insights
from src.prediction import DEFAULT_MODEL_ARTIFACT_PATH, load_mlp_artifact, predict_next_severity
from src.rag import RetrievedContext, retrieve_relevant_knowledge
from src.rag.web_search import WebSourceSnippet, search_trusted_environmental_websites


class QueryIntent(str, Enum):
    CURRENT_AQI = "Current AQI"
    POLLUTANT_ANALYSIS = "Pollutant analysis"
    HEALTH_PRECAUTIONS = "Health precautions"
    ENVIRONMENTAL_KNOWLEDGE = "Environmental knowledge"
    HISTORICAL_ANALYSIS = "Historical analysis"
    LOCATION_COMPARISON = "Location comparison"
    PREDICTION = "Prediction"
    ANOMALY_EXPLANATION = "Anomaly explanation"
    WEATHER_CONTEXT = "Weather context"
    ACTIVITY_RECOMMENDATIONS = "Activity recommendations"


@dataclass
class RoutedContext:
    intent: QueryIntent
    structured_facts: dict[str, Any] = field(default_factory=dict)
    deterministic_summary: str = ""
    retrieved_docs: list[RetrievedContext] = field(default_factory=list)
    web_sources: list[WebSourceSnippet] = field(default_factory=list)
    has_sufficient_evidence: bool = True


_INTENT_KEYWORDS: list[tuple[QueryIntent, tuple[str, ...]]] = [
    (QueryIntent.ACTIVITY_RECOMMENDATIONS, ("walk", "walking", "run", "running", "cycl", "exercise", "workout", "jog", "outdoor sport")),
    (QueryIntent.PREDICTION, ("predict", "forecast", "next observation", "tomorrow", "upcoming", "mlp", "future aqi")),
    (QueryIntent.ANOMALY_EXPLANATION, ("anomal", "spike", "sudden jump", "unusual", "irregular", "outlier")),
    (QueryIntent.LOCATION_COMPARISON, ("compare", "comparison", "versus", "vs ", "which city", "which station", "cleanest", "most polluted")),
    (QueryIntent.HISTORICAL_ANALYSIS, ("history", "historical", "trend", "over time", "daily", "weekly", "past", "average aqi")),
    (QueryIntent.WEATHER_CONTEXT, ("weather", "wind", "humidity", "rain", "rainfall", "temperature", "pressure", "dispersion")),
    (QueryIntent.HEALTH_PRECAUTIONS, ("health", "precaution", "asthma", "sensitive", "mask", "n95", "breathe", "children", "elderly", "safe")),
    (QueryIntent.POLLUTANT_ANALYSIS, ("pollutant", "pm2.5", "pm25", "pm10", "no2", "so2", "co ", "o3", "ozone", "dominant", "sub-index", "source")),
    (QueryIntent.CURRENT_AQI, ("current aqi", "aqi now", "today", "status", "air quality right now", "what is the aqi", "level")),
]


def classify_intent(user_query: str) -> QueryIntent:
    q = f" {(user_query or '').strip().lower()} "
    if not q.strip():
        return QueryIntent.ENVIRONMENTAL_KNOWLEDGE

    is_definitional = any(
        q.lstrip().startswith(prefix)
        for prefix in ("what is ", "what are ", "how does ", "why does ", "define ", "explain what ")
    )
    has_live_or_data_cue = any(
        cue in q
        for cue in ("current", "today", "station", "history", "historical", "trend", "average", "predict", "forecast")
    )
    if is_definitional and not has_live_or_data_cue:
        return QueryIntent.ENVIRONMENTAL_KNOWLEDGE

    for intent, keywords in _INTENT_KEYWORDS:
        if any(kw in q for kw in keywords):
            return intent

    return QueryIntent.ENVIRONMENTAL_KNOWLEDGE


def _attach_live_baseline(facts: dict[str, Any], current_reading: AqiReading | None) -> None:
    if current_reading is None:
        return
    eng = evaluate_aqi_from_reading(current_reading)
    adv = generate_health_advisory(category=eng.category, dominant_pollutant=eng.dominant_pollutant)
    facts["active_station_baseline"] = {
        "station_name": current_reading.station_name or current_reading.query,
        "observation_time": current_reading.observation_time,
        "calculated_cpcb_aqi": eng.calculated_aqi,
        "cpcb_category": eng.category,
        "dominant_pollutant": eng.dominant_pollutant,
        "waqi_reported_aqi": current_reading.aqi,
        "pollutant_concentrations": current_reading.pollutants,
        "advisory_urgency": adv.urgency_level,
    }


def route_query_to_services(
    user_query: str,
    current_reading: AqiReading | None = None,
    db_path: Path | str | None = None,
    model_path: Path | str | None = None,
    kb_dir: Path | str | None = None,
    index_dir: Path | str | None = None,
    use_web_search: bool = True,
) -> RoutedContext:
    intent = classify_intent(user_query)
    retrieved = retrieve_relevant_knowledge(
        user_query,
        top_k=3,
        kb_dir=kb_dir,
        index_dir=index_dir,
    )

    web_hits: list[WebSourceSnippet] = []
    if use_web_search:
        topic_parts = [user_query]
        if current_reading is not None and current_reading.dominant_pollutant:
            topic_parts.append(current_reading.dominant_pollutant.upper())
        web_hits = search_trusted_environmental_websites(" ".join(topic_parts), max_sources=4)

    facts: dict[str, Any] = {"intent": intent.value}
    _attach_live_baseline(facts, current_reading)

    if intent == QueryIntent.CURRENT_AQI:
        if current_reading is None:
            return RoutedContext(
                intent=intent,
                structured_facts=facts,
                deterministic_summary="No live AQI observation is currently loaded in session. Fetch a station on 'Live AQI Monitoring' first.",
                retrieved_docs=retrieved,
                web_sources=web_hits,
                has_sufficient_evidence=False,
            )
        eng = evaluate_aqi_from_reading(current_reading)
        facts.update(
            {
                "station_name": current_reading.station_name,
                "observation_time": current_reading.observation_time,
                "calculated_cpcb_aqi": eng.calculated_aqi,
                "category": eng.category,
                "dominant_pollutant": eng.dominant_pollutant,
                "waqi_reported_aqi": current_reading.aqi,
                "standard": eng.standard_name,
            }
        )
        summary = (
            f"Station: {current_reading.station_name or current_reading.query} | "
            f"Observation Time: {current_reading.observation_time or 'Unknown'} | "
            f"Calculated CPCB AQI: {eng.calculated_aqi} ({eng.category}) | "
            f"Dominant Pollutant: {(eng.dominant_pollutant or 'None').upper()} | "
            f"WAQI API Reported AQI: {current_reading.aqi}. {eng.category_explanation}"
        )
        return RoutedContext(
            intent=intent,
            structured_facts=facts,
            deterministic_summary=summary,
            retrieved_docs=retrieved,
            web_sources=web_hits,
        )

    if intent == QueryIntent.POLLUTANT_ANALYSIS:
        if current_reading is None:
            return RoutedContext(
                intent=intent,
                structured_facts=facts,
                deterministic_summary="No live pollutant reading is loaded to analyze.",
                retrieved_docs=retrieved,
                web_sources=web_hits,
                has_sufficient_evidence=False,
            )
        analysis = analyze_pollutants_from_reading(current_reading)
        sources = generate_source_insights(analysis)
        top_sources = [
            f"{s.source_category} (Evidence: {s.evidence_strength} — {s.observed_pattern})"
            for s in sources
            if s.evidence_strength != "Low"
        ]
        facts.update(
            {
                "station_name": current_reading.station_name,
                "dominant_aqi_pollutant": analysis.dominant_aqi_pollutant,
                "highest_sub_index": analysis.highest_sub_index,
                "highest_measured_pollutant": analysis.highest_measured_pollutant,
                "highest_measured_value": analysis.highest_measured_value,
                "missing_pollutants": analysis.missing_pollutants,
                "combinations": [c.title for c in analysis.combinations],
                "possible_sources_non_causal": top_sources,
            }
        )
        summary = (
            f"Dominant AQI-contributing pollutant: {(analysis.dominant_aqi_pollutant or 'None').upper()} "
            f"(sub-index {analysis.highest_sub_index}). "
            f"Highest raw concentration: {(analysis.highest_measured_pollutant or 'None').upper()} "
            f"({analysis.highest_measured_value}). "
            f"Missing pollutants (not imputed): {', '.join(p.upper() for p in analysis.missing_pollutants) or 'None'}. "
            f"Possible associated sources (non-causal): {', '.join(top_sources) or 'No elevated multi-pollutant source signature'}."
        )
        return RoutedContext(
            intent=intent,
            structured_facts=facts,
            deterministic_summary=summary,
            retrieved_docs=retrieved,
            web_sources=web_hits,
        )

    if intent == QueryIntent.HEALTH_PRECAUTIONS:
        if current_reading is None:
            return RoutedContext(
                intent=intent,
                structured_facts=facts,
                deterministic_summary="No live AQI observation is loaded; fetch a station reading to evaluate category-specific health precautions.",
                retrieved_docs=retrieved,
                web_sources=web_hits,
                has_sufficient_evidence=False,
            )
        eng = evaluate_aqi_from_reading(current_reading)
        adv = generate_health_advisory(category=eng.category, dominant_pollutant=eng.dominant_pollutant)
        facts.update(
            {
                "category": adv.category,
                "urgency": adv.urgency_level,
                "general_precautions": adv.general_precautions,
                "sensitive_precautions": adv.sensitive_group_precautions,
                "exposure_reduction": adv.exposure_reduction_suggestions,
                "disclaimer": adv.disclaimer,
            }
        )
        summary = (
            f"Category: {adv.category} (Urgency: {adv.urgency_level}). "
            f"General precautions: {' '.join(adv.general_precautions)} "
            f"Sensitive groups: {' '.join(adv.sensitive_group_precautions)} "
            f"Note: {adv.disclaimer}"
        )
        return RoutedContext(
            intent=intent,
            structured_facts=facts,
            deterministic_summary=summary,
            retrieved_docs=retrieved,
            web_sources=web_hits,
        )

    if intent == QueryIntent.ACTIVITY_RECOMMENDATIONS:
        if current_reading is None:
            return RoutedContext(
                intent=intent,
                structured_facts=facts,
                deterministic_summary="No live AQI reading is loaded to evaluate outdoor/indoor activity suitability.",
                retrieved_docs=retrieved,
                web_sources=web_hits,
                has_sufficient_evidence=False,
            )
        q_low = user_query.lower()
        chosen_act = "Outdoor exercise"
        for act in SUPPORTED_ACTIVITIES:
            if act.lower().split()[0] in q_low:
                chosen_act = act
                break
        guidance = advise_activity_from_reading(chosen_act, current_reading)
        facts.update(
            {
                "activity": guidance.activity,
                "aqi_category": guidance.aqi_category,
                "recommendation": guidance.recommendation,
                "precautions": guidance.precautions,
                "alternative_activity": guidance.alternative_activity,
                "disclaimer": guidance.disclaimer,
            }
        )
        summary = (
            f"Activity: {guidance.activity} | AQI Category: {guidance.aqi_category} | "
            f"Recommendation: {guidance.recommendation}. "
            f"Alternative: {guidance.alternative_activity} ({guidance.disclaimer})"
        )
        return RoutedContext(
            intent=intent,
            structured_facts=facts,
            deterministic_summary=summary,
            retrieved_docs=retrieved,
            web_sources=web_hits,
        )

    if intent == QueryIntent.HISTORICAL_ANALYSIS:
        obs = get_observations(limit=500, db_path=db_path)
        if not obs:
            return RoutedContext(
                intent=intent,
                structured_facts=facts,
                deterministic_summary=(
                    "There are no stored historical observations in the database yet to compute a trend. "
                    "Fetch readings across different times or stations on Live AQI Monitoring to build up history."
                ),
                retrieved_docs=retrieved,
                web_sources=web_hits,
                has_sufficient_evidence=False,
            )
        hist = compute_historical_analytics(obs)
        facts.update(
            {
                "observation_count": hist.observation_count,
                "average_aqi": hist.average_aqi,
                "min_aqi": hist.min_aqi,
                "max_aqi": hist.max_aqi,
                "aqi_change": hist.aqi_change,
                "severity_distribution": hist.severity_distribution,
            }
        )
        summary = (
            f"Stored observations: {hist.observation_count} | Average AQI: {hist.average_aqi} | "
            f"Min/Max AQI: {hist.min_aqi} / {hist.max_aqi} | "
            f"Historical Change: {hist.aqi_change if hist.aqi_change is not None else 'Insufficient multi-point series'}."
        )
        return RoutedContext(
            intent=intent,
            structured_facts=facts,
            deterministic_summary=summary,
            retrieved_docs=retrieved,
            web_sources=web_hits,
            has_sufficient_evidence=hist.observation_count >= 1,
        )

    if intent == QueryIntent.LOCATION_COMPARISON:
        latest = get_latest_observations_per_station(db_path=db_path)
        if not latest:
            return RoutedContext(
                intent=intent,
                structured_facts=facts,
                deterministic_summary="No stored station observations available in SQLite for location comparison.",
                retrieved_docs=retrieved,
                web_sources=web_hits,
                has_sufficient_evidence=False,
            )
        comp = compare_station_observations(latest)
        facts.update(
            {
                "stations_compared": comp.stations_compared,
                "highest_aqi_station": comp.highest_aqi_station,
                "highest_aqi_value": comp.highest_aqi_value,
                "lowest_aqi_station": comp.lowest_aqi_station,
                "lowest_aqi_value": comp.lowest_aqi_value,
                "timestamp_warnings": comp.timestamp_warnings,
            }
        )
        summary = (
            f"Stations compared: {comp.stations_compared} | "
            f"Highest AQI: {comp.highest_aqi_station} ({comp.highest_aqi_value}) | "
            f"Lowest AQI: {comp.lowest_aqi_station} ({comp.lowest_aqi_value}). "
            + (" ".join(comp.timestamp_warnings) if comp.timestamp_warnings else "")
        )
        return RoutedContext(
            intent=intent,
            structured_facts=facts,
            deterministic_summary=summary,
            retrieved_docs=retrieved,
            web_sources=web_hits,
        )

    if intent == QueryIntent.PREDICTION:
        obs = get_observations(limit=500, db_path=db_path)
        m_path = Path(model_path) if model_path is not None else DEFAULT_MODEL_ARTIFACT_PATH
        if not m_path.exists() or not obs:
            return RoutedContext(
                intent=intent,
                structured_facts=facts,
                deterministic_summary="No trained MLP severity model or historical observations available yet. Train the MLP on 'AQI Prediction' after collecting >= 4 observations.",
                retrieved_docs=retrieved,
                web_sources=web_hits,
                has_sufficient_evidence=False,
            )
        artifact = load_mlp_artifact(m_path)
        pred = predict_next_severity(
            artifact,
            latest_observation=obs[-1],
            previous_observation=obs[-2] if len(obs) >= 2 else None,
        )
        facts.update(
            {
                "predicted_next_severity": pred.predicted_next_severity,
                "confidence": pred.confidence,
                "confidence_label": pred.confidence_label,
                "class_probabilities": pred.class_probabilities,
                "test_accuracy": artifact.evaluation.accuracy,
            }
        )
        summary = (
            f"MLP Next-Observation Severity Prediction: {pred.predicted_next_severity} "
            f"(Confidence: {pred.confidence * 100:.1f}% — {pred.confidence_label}; "
            f"Held-out Test Accuracy: {artifact.evaluation.accuracy * 100:.1f}%)."
        )
        return RoutedContext(
            intent=intent,
            structured_facts=facts,
            deterministic_summary=summary,
            retrieved_docs=retrieved,
            web_sources=web_hits,
        )

    if intent == QueryIntent.ANOMALY_EXPLANATION:
        obs = get_observations(limit=500, db_path=db_path)
        if not obs:
            return RoutedContext(
                intent=intent,
                structured_facts=facts,
                deterministic_summary="No stored valid observations available to evaluate statistical anomalies.",
                retrieved_docs=retrieved,
                web_sources=web_hits,
                has_sufficient_evidence=False,
            )
        findings = detect_anomalies(obs)
        flagged = [f for f in findings if f.is_anomaly]
        latest_f = findings[-1] if findings else None
        facts.update(
            {
                "evaluated_count": len(findings),
                "flagged_count": len(flagged),
                "latest_is_anomaly": latest_f.is_anomaly if latest_f else False,
                "latest_explanation": latest_f.explanation if latest_f else "",
                "latest_evidence": latest_f.evidence_strength if latest_f else "None",
            }
        )
        summary = (
            f"Evaluated {len(findings)} valid observations; {len(flagged)} statistical anomalies flagged. "
            + (f"Latest status ({latest_f.evidence_strength}): {latest_f.explanation}" if latest_f else "")
        )
        return RoutedContext(
            intent=intent,
            structured_facts=facts,
            deterministic_summary=summary,
            retrieved_docs=retrieved,
            web_sources=web_hits,
        )

    if intent == QueryIntent.WEATHER_CONTEXT:
        if current_reading is None or current_reading.latitude is None or current_reading.longitude is None:
            return RoutedContext(
                intent=intent,
                structured_facts=facts,
                deterministic_summary="Station coordinates are unavailable; fetch a station with valid latitude/longitude first.",
                retrieved_docs=retrieved,
                web_sources=web_hits,
                has_sufficient_evidence=False,
            )
        try:
            w_obs = WeatherClient().get_current_weather(current_reading.latitude, current_reading.longitude)
            notes = analyze_weather_pollution_context(w_obs, aqi_value=current_reading.aqi)
            facts.update(
                {
                    "temperature_c": w_obs.temperature_c,
                    "humidity_pct": w_obs.humidity_pct,
                    "wind_speed_kmh": w_obs.wind_speed_kmh,
                    "wind_direction_deg": w_obs.wind_direction_deg,
                    "rain_mm": w_obs.rain_mm,
                    "surface_pressure_hpa": w_obs.surface_pressure_hpa,
                }
            )
            summary = (
                f"Weather at ({w_obs.latitude}, {w_obs.longitude}): Temp {w_obs.temperature_c}°C, "
                f"Humidity {w_obs.humidity_pct}%, Wind {w_obs.wind_speed_kmh} km/h ({w_obs.wind_direction_deg}°), "
                f"Rain {w_obs.rain_mm} mm, Pressure {w_obs.surface_pressure_hpa} hPa. "
                + " ".join(n.possible_relationship for n in notes[:2])
            )
            return RoutedContext(
                intent=intent,
                structured_facts=facts,
                deterministic_summary=summary,
                retrieved_docs=retrieved,
                web_sources=web_hits,
            )
        except WeatherClientError as exc:
            return RoutedContext(
                intent=intent,
                structured_facts=facts,
                deterministic_summary=f"Weather service unavailable ({exc.message}); AQI data remains unaffected.",
                retrieved_docs=retrieved,
                web_sources=web_hits,
                has_sufficient_evidence=False,
            )

    # Default: Environmental knowledge (RAG-grounded)
    if not retrieved and not web_hits:
        return RoutedContext(
            intent=QueryIntent.ENVIRONMENTAL_KNOWLEDGE,
            structured_facts=facts,
            deterministic_summary="No matching reference passages were retrieved from the curated environmental knowledge base or trusted web sources.",
            retrieved_docs=[],
            web_sources=[],
            has_sufficient_evidence=False,
        )

    kb_summary = " ".join(f"[{r.title}] {r.text}" for r in retrieved)
    return RoutedContext(
        intent=QueryIntent.ENVIRONMENTAL_KNOWLEDGE,
        structured_facts=facts,
        deterministic_summary=kb_summary,
        retrieved_docs=retrieved,
        web_sources=web_hits,
        has_sufficient_evidence=True,
    )