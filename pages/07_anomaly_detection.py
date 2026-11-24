import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.database import get_observations, list_stations
from src.intelligence import detect_anomalies
from src.utils import (
    render_info_panel,
    render_metric_card,
    render_page_header,
    render_warning_banner,
)


def main() -> None:
    render_page_header(
        title="Anomaly Detection",
        subtitle="Explainable statistical detection of sudden AQI jumps, pollutant shifts, and baseline deviations.",
        is_placeholder=False,
    )

    stations = list_stations()
    station_options = ["All Locations"] + [str(s["station_name"]) for s in stations]

    f1, f2 = st.columns([2, 1])
    with f1:
        selected_loc = st.selectbox(
            "Location / Station",
            options=station_options,
            index=0,
            key="anomaly_station_select",
        )
    with f2:
        jump_thresh = st.number_input(
            "Sudden AQI Jump Threshold",
            min_value=10.0,
            max_value=300.0,
            value=50.0,
            step=5.0,
            key="anomaly_jump_thresh",
        )

    obs_rows = get_observations(location=selected_loc, limit=1000)
    if not obs_rows:
        render_warning_banner(
            "No valid observations stored yet. Fetch live readings on 'Live AQI Monitoring' to run anomaly analysis.",
            is_placeholder=False,
        )
        return

    findings = detect_anomalies(obs_rows, aqi_jump_threshold=float(jump_thresh))
    flagged = [f for f in findings if f.is_anomaly]

    m1, m2, m3 = st.columns(3)
    with m1:
        render_metric_card("Evaluated Observations", str(len(findings)), "Valid chronological points", is_placeholder=False)
    with m2:
        render_metric_card("Flagged Statistical Anomalies", str(len(flagged)), f"Jump threshold: {jump_thresh:g}", is_placeholder=False)
    with m3:
        latest_f = findings[-1] if findings else None
        render_metric_card(
            "Latest Observation Status",
            "Anomaly Flagged" if (latest_f and latest_f.is_anomaly) else "Normal Baseline",
            latest_f.evidence_strength if latest_f else "N/A",
            is_placeholder=False,
        )

    delta_rows = [
        {
            "Observation Time": f.observation_time,
            "Station": f.station_name,
            "AQI Delta": f.aqi_delta if f.aqi_delta is not None else 0.0,
            "Flagged": "Yes" if f.is_anomaly else "No",
            "Evidence Strength": f.evidence_strength,
        }
        for f in findings
    ]
    df_deltas = pd.DataFrame(delta_rows)

    with st.container(border=True):
        st.markdown("**Observed AQI Step Changes Across Sequence**")
        fig_d = go.Figure(
            go.Bar(
                x=df_deltas["Observation Time"],
                y=df_deltas["AQI Delta"],
                marker_color=["#DC2626" if x == "Yes" else "#0284C7" for x in df_deltas["Flagged"]],
            )
        )
        fig_d.update_layout(
            height=290,
            margin={"l": 40, "r": 20, "t": 20, "b": 40},
            xaxis={"title": "Observation Time"},
            yaxis={"title": "AQI Change vs. Prior"},
        )
        st.plotly_chart(fig_d, width="stretch", key="anomaly_aqi_delta_chart")

    st.markdown("### Anomaly History & Pollutant Deviations")
    history_rows = [
        {
            "Timestamp": f.observation_time,
            "Station": f.station_name,
            "Anomaly": "Yes" if f.is_anomaly else "No",
            "Evidence": f.evidence_strength,
            "Observed Change": f.observed_change,
            "Reference Baseline": f.reference_baseline,
            "Explanation": f.explanation,
            "Data Quality / Interval Note": f.data_quality_note,
        }
        for f in reversed(findings)
    ]
    st.dataframe(pd.DataFrame(history_rows), width="stretch", hide_index=True)

    render_info_panel(
        title="Interpretation Note",
        body="Statistical anomalies highlight unusual shifts or baselines in valid readings; invalid API measurements are excluded and never treated as confirmed pollution events.",
        is_placeholder=False,
    )


main()