import plotly.graph_objects as go
import streamlit as st

from config import config
from src.alerts import list_stored_alerts
from src.analytics import compute_historical_analytics
from src.api import AqiReading
from src.core import evaluate_aqi_from_reading, generate_health_advisory
from src.database import get_observations
from src.intelligence import analyze_pollutants_from_reading
from src.prediction import DEFAULT_MODEL_ARTIFACT_PATH, load_mlp_artifact, predict_next_severity
from src.utils import (
    render_aqi_indicator,
    render_info_panel,
    render_metric_card,
    render_page_header,
    render_warning_banner,
)
from src.validation import validate_aqi_reading


def main() -> None:
    selected_location = (
        (st.session_state.get("selected_location") or config.default_location).strip()
        or config.default_location
    )
    reading: AqiReading | None = st.session_state.get("waqi_last_reading")

    render_page_header(
        title="Overview Dashboard",
        subtitle="Integrated air quality status, health guidance, recent trend, next-step prediction, alerts, and data quality.",
        is_placeholder=reading is None,
    )

    try:
        stored_obs = get_observations(limit=200)
        unack_alerts = list_stored_alerts(include_acknowledged=False, limit=100)
        db_available = True
    except Exception as db_err:
        stored_obs = []
        unack_alerts = []
        db_available = False
        render_warning_banner(
            f"SQLite persistence temporarily unavailable ({db_err}); live session telemetry remains operational.",
            is_placeholder=False,
        )

    if reading is None and not stored_obs:
        render_warning_banner(
            "No live or historical WAQI observations available yet. Open 'Live AQI Monitoring' to fetch station telemetry.",
            is_placeholder=True,
        )
        r1c1, r1c2, r1c3 = st.columns(3)
        with r1c1:
            render_metric_card("Calculated CPCB AQI", "Unavailable", "No reading fetched yet", is_placeholder=True)
        with r1c2:
            render_aqi_indicator("Pending", "Awaiting telemetry ingestion", is_placeholder=True)
        with r1c3:
            render_metric_card("Selected Location", selected_location, "Configured default location", is_placeholder=False)

        r2c1, r2c2, r2c3, r2c4 = st.columns(4)
        with r2c1:
            render_metric_card("Dominant Pollutant", "Unavailable", "No sub-index data", is_placeholder=True)
        with r2c2:
            render_metric_card("Next-Step MLP Prediction", "Not Trained", "Train on AQI Prediction page", is_placeholder=True)
        with r2c3:
            alerts_meta = "0 alerts currently stored" if db_available else "SQLite offline"
            render_metric_card("Active Unacknowledged Alerts", str(len(unack_alerts)), alerts_meta, is_placeholder=not db_available)
        with r2c4:
            render_metric_card("Data Quality Status", "Awaiting Data", "Completeness & validity pending", is_placeholder=True)
        return

    if reading is not None:
        validation = validate_aqi_reading(reading)
        aqi_res = evaluate_aqi_from_reading(reading)
        analysis = analyze_pollutants_from_reading(reading)
        advisory = generate_health_advisory(
            category=aqi_res.category,
            dominant_pollutant=aqi_res.dominant_pollutant,
        )
        calc_aqi_str = str(aqi_res.calculated_aqi) if aqi_res.calculated_aqi is not None else "Unavailable"
        waqi_str = str(reading.aqi) if reading.aqi is not None else "N/A"
        category_str = aqi_res.category
        explanation_str = aqi_res.category_explanation
        station_str = reading.station_name or selected_location
        dom_str = (aqi_res.dominant_pollutant or "None").upper()
        obs_str = reading.observation_time or "Timestamp Missing"
        urgency_str = advisory.urgency_level
        dq_val = f"{int(validation.completeness_ratio * 100)}% Complete"
        dq_meta = "Valid & Fresh" if (validation.is_valid and not validation.is_stale) else ("Stale" if validation.is_stale else "Check Warnings")
        general_precautions = advisory.general_precautions
    else:
        latest = stored_obs[-1]
        calc_aqi_str = str(latest["calculated_aqi"]) if latest.get("calculated_aqi") is not None else "Unavailable"
        waqi_str = str(latest["waqi_reported_aqi"]) if latest.get("waqi_reported_aqi") is not None else "N/A"
        category_str = str(latest.get("aqi_category") or "Unavailable")
        explanation_str = f"Persisted reading from SQLite ({latest.get('observation_time')})."
        station_str = str(latest.get("station_name") or selected_location)
        dom_str = str(latest.get("dominant_pollutant") or "None").upper()
        obs_str = str(latest.get("observation_time") or "Timestamp Missing")
        advisory = generate_health_advisory(category=category_str, dominant_pollutant=dom_str)
        urgency_str = advisory.urgency_level
        dq_val = f"{int(float(latest.get('completeness_ratio') or 0.0) * 100)}% Complete"
        dq_meta = "Stored SQLite observation"
        general_precautions = advisory.general_precautions

    # Optional next-observation prediction when trained model artifact exists
    pred_value = "Model Not Trained"
    pred_meta = "Train MLP on AQI Prediction page"
    if DEFAULT_MODEL_ARTIFACT_PATH.exists() and stored_obs:
        try:
            art = load_mlp_artifact(DEFAULT_MODEL_ARTIFACT_PATH)
            p_res = predict_next_severity(
                art,
                latest_observation=stored_obs[-1],
                previous_observation=stored_obs[-2] if len(stored_obs) >= 2 else None,
            )
            pred_value = p_res.predicted_next_severity
            pred_meta = f"Next-step conf: {p_res.confidence * 100:.1f}% ({p_res.confidence_label})"
        except Exception:
            pred_value = "Unavailable"
            pred_meta = "Artifact load error"

    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        render_metric_card("Calculated AQI (CPCB)", calc_aqi_str, f"WAQI Reported: {waqi_str} • {obs_str}", is_placeholder=False)
    with r1c2:
        render_aqi_indicator(severity=category_str, status_text=explanation_str, is_placeholder=False)
    with r1c3:
        render_metric_card("Station / Location", station_str, f"Selected: {selected_location}", is_placeholder=False)

    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    with r2c1:
        render_metric_card("Dominant Pollutant", dom_str, f"Advisory Urgency: {urgency_str}", is_placeholder=False)
    with r2c2:
        render_metric_card("Next-Step Severity", pred_value, pred_meta, is_placeholder=(pred_value in ("Model Not Trained", "Unavailable")))
    with r2c3:
        alerts_meta = "In-app SQLite alerts" if db_available else "SQLite offline"
        render_metric_card("Active Unacknowledged Alerts", str(len(unack_alerts)), alerts_meta, is_placeholder=not db_available)
    with r2c4:
        render_metric_card("Data Quality", dq_val, dq_meta, is_placeholder=False)

    station_obs = [o for o in stored_obs if o.get("station_name") == station_str] or stored_obs
    hist = compute_historical_analytics(station_obs)

    with st.container(border=True):
        st.markdown(f"**Recent Pollution Trend — {station_str}**")
        if hist.timeseries_df.empty:
            st.info(
                "No stored observations yet for trend visualization."
                if db_available
                else "Trend chart unavailable while SQLite storage is offline."
            )
        else:
            fig = go.Figure(
                go.Scatter(
                    x=hist.timeseries_df["observation_time"],
                    y=hist.timeseries_df["effective_aqi"],
                    mode="lines+markers",
                    name="Calculated CPCB AQI",
                    line={"color": "#0284C7", "width": 2},
                )
            )
            fig.update_layout(height=280, margin={"l": 40, "r": 20, "t": 15, "b": 35})
            st.plotly_chart(fig, width="stretch", key="overview_recent_trend_chart")

    render_info_panel(
        title=f"Health Advisory ({category_str} — {urgency_str})",
        body="<br>".join(f"• {p}" for p in general_precautions),
        is_placeholder=False,
    )


main()