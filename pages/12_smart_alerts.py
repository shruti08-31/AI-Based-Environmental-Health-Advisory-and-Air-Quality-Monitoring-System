import pandas as pd
import streamlit as st

from src.alerts import (
    DEFAULT_AQI_ALERT_THRESHOLD,
    DEFAULT_DETERIORATION_DELTA,
    acknowledge_alert,
    evaluate_alert_candidates,
    list_stored_alerts,
    persist_alerts,
)
from src.api import AqiReading
from src.database import get_observations, list_stations
from src.utils import (
    render_info_panel,
    render_metric_card,
    render_page_header,
    render_warning_banner,
)


def main() -> None:
    render_page_header(
        title="Smart Alerts",
        subtitle="In-app threshold, deterioration, pollutant limit, and statistical anomaly alerts stored in SQLite.",
        is_placeholder=False,
    )
    st.caption("Scope: Evaluates in-app on demand and upon live fetches (not a continuous background daemon).")

    c_thr, c_det, c_eval = st.columns([1.5, 1.5, 1.2])
    with c_thr:
        aqi_thresh = st.number_input(
            "AQI Alert Threshold",
            min_value=50,
            max_value=450,
            value=DEFAULT_AQI_ALERT_THRESHOLD,
            step=10,
            key="alert_aqi_thresh",
        )
    with c_det:
        det_delta = st.number_input(
            "AQI Deterioration Delta (+)",
            min_value=10,
            max_value=250,
            value=DEFAULT_DETERIORATION_DELTA,
            step=5,
            key="alert_det_delta",
        )
    with c_eval:
        st.write("")
        eval_clicked = st.button("Evaluate Current Reading", width="stretch", key="btn_eval_alerts")

    reading: AqiReading | None = st.session_state.get("waqi_last_reading")
    if eval_clicked and reading is not None:
        prev_obs = get_observations(location=reading.station_name or reading.query, limit=50)
        cands = evaluate_alert_candidates(
            reading=reading,
            previous_observations=prev_obs,
            aqi_threshold=int(aqi_thresh),
            deterioration_delta=int(det_delta),
        )
        added = persist_alerts(cands, query_city=reading.query)
        st.success(f"Evaluated {len(cands)} alert rule(s); {added} new deduplicated alert(s) stored.")
    elif eval_clicked and reading is None:
        st.info("No active live reading in session; showing persisted alerts from SQLite below.")

    stations = list_stations()
    loc_options = ["All Locations"] + [str(s["station_name"]) for s in stations]
    f1, f2 = st.columns([2, 1])
    with f1:
        selected_loc = st.selectbox("Filter Alerts by Location", options=loc_options, index=0, key="alert_loc_filter")
    with f2:
        show_ack = st.checkbox("Include Acknowledged Alerts", value=True, key="alert_show_ack")

    alerts = list_stored_alerts(include_acknowledged=show_ack, location=selected_loc, limit=200)
    unack_count = sum(1 for a in alerts if int(a.get("acknowledged", 0)) == 0)

    m1, m2 = st.columns(2)
    with m1:
        render_metric_card("Displayed Alerts", str(len(alerts)), "Stored in SQLite alerts table", is_placeholder=False)
    with m2:
        render_metric_card("Unacknowledged Alerts", str(unack_count), "Awaiting review", is_placeholder=False)

    if not alerts:
        render_warning_banner("No matching alerts found for the current filter.", is_placeholder=False)
        return

    df_alerts = pd.DataFrame(
        [
            {
                "ID": a["alert_id"],
                "Type": a["alert_type"],
                "Location": a["location"],
                "Severity": a["severity"],
                "Observation Time": a["observation_time"],
                "Status": "Acknowledged" if int(a.get("acknowledged", 0)) == 1 else "Unacknowledged",
                "Title": a["title"],
                "Explanation": a["explanation"],
            }
            for a in alerts
        ]
    )
    st.dataframe(df_alerts, width="stretch", hide_index=True)

    unack_ids = [int(a["alert_id"]) for a in alerts if int(a.get("acknowledged", 0)) == 0]
    if unack_ids:
        a_col1, a_col2 = st.columns([2, 1])
        with a_col1:
            chosen_id = st.selectbox("Select Alert ID to Acknowledge", options=unack_ids, key="ack_alert_id_select")
        with a_col2:
            st.write("")
            if st.button("Acknowledge Alert", width="stretch", key="btn_ack_alert"):
                acknowledge_alert(int(chosen_id))
                st.rerun()

    render_info_panel(
        title="Deduplication & Acknowledgement",
        body="Alerts with the same station, observation timestamp, type, and title are deduplicated in SQLite. Acknowledged alerts stay in history for auditability.",
        is_placeholder=False,
    )


main()