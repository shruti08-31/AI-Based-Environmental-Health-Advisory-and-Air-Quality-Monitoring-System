import html
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
from src.utils import render_warning_banner


def _inject_smart_alerts_theme() -> None:
    st.markdown(
        """
        <style>
        /* Remove Streamlit's default top dark header bar */
        [data-testid="stHeader"],
        header[data-testid="stHeader"],
        [data-testid="stDecoration"],
        [data-testid="stToolbar"] {
            display: none !important;
        }

        /* Main canvas & typography */
        .stApp {
            background-color: #F7F9F8;
            color: #16261E;
        }
        .block-container {
            padding-top: 1.25rem !important;
            padding-bottom: 2.5rem;
            max-width: 1280px;
        }

        /* Deep forest-green sidebar */
        [data-testid="stSidebar"] {
            background-color: #133A2A !important;
            border-right: 1px solid #0E2C20;
        }
        [data-testid="stSidebar"] * {
            color: #E2ECE6 !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {
            border-radius: 10px;
            margin: 2px 8px;
            padding: 6px 12px;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {
            background-color: rgba(255, 255, 255, 0.08) !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {
            background-color: #315B48 !important;
            font-weight: 600;
        }

        /* Green labels & light-green controls with crisp dark-green text */
        [data-testid="stNumberInput"] label,
        [data-testid="stNumberInput"] label p,
        [data-testid="stSelectbox"] label,
        [data-testid="stSelectbox"] label p,
        [data-testid="stCheckbox"] label,
        [data-testid="stCheckbox"] label p {
            color: #1B5E3F !important;
            font-weight: 600 !important;
            font-size: 0.86rem !important;
        }
        [data-testid="stNumberInput"] input,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            background-color: #EAF4EC !important;
            border-color: #B4D6BE !important;
            border-radius: 10px !important;
            color: #133A2A !important;
            -webkit-text-fill-color: #133A2A !important;
            font-weight: 600 !important;
        }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] *,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] div,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] span,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] input {
            color: #133A2A !important;
            -webkit-text-fill-color: #133A2A !important;
            opacity: 1 !important;
            font-weight: 600 !important;
        }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] svg {
            color: #133A2A !important;
            fill: #133A2A !important;
        }

        /* Forest-green action buttons */
        div.stButton > button {
            background-color: #133A2A;
            color: #FFFFFF;
            border: 1px solid #133A2A;
            border-radius: 10px;
            font-weight: 600;
            transition: background-color 0.15s ease;
        }
        div.stButton > button:hover {
            background-color: #1F5740;
            border-color: #1F5740;
            color: #FFFFFF;
        }

        /* Breadcrumb & Top Bar */
        .eco-topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.9rem;
            padding-bottom: 0.6rem;
            border-bottom: 1px solid #E4ECE7;
        }
        .eco-breadcrumb {
            font-size: 0.92rem;
            color: #5E7167;
        }
        .eco-breadcrumb strong {
            color: #16261E;
            font-weight: 600;
        }
        .eco-sub {
            font-size: 0.78rem;
            color: #74877D;
            margin-top: 2px;
        }
        .eco-pill {
            background: #EAF3EC;
            border: 1px solid #CBE0D1;
            border-radius: 999px;
            padding: 5px 13px;
            font-size: 0.78rem;
            font-weight: 600;
            color: #1A4D38;
        }
        .eco-dot {
            display: inline-block;
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: #22A06B;
            margin-right: 6px;
        }

        /* Metric Cards */
        .eco-card {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-radius: 16px;
            padding: 16px 18px;
            box-shadow: 0 2px 8px rgba(19, 58, 42, 0.03);
            height: 100%;
            margin-bottom: 0.65rem;
        }
        .eco-card-label {
            font-size: 0.80rem;
            font-weight: 500;
            color: #5E7167;
            margin-bottom: 6px;
        }
        .eco-card-value {
            font-size: 1.65rem;
            font-weight: 700;
            color: #133A2A;
            line-height: 1.15;
            margin-bottom: 5px;
        }
        .eco-card-sub {
            font-size: 0.76rem;
            color: #6B7E74;
        }

        /* Compact Rule Breakdown Strip */
        .eco-rule-strip {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-radius: 12px;
            padding: 10px 16px;
            margin: 0.5rem 0 0.85rem 0;
            font-size: 0.82rem;
            color: #24382E;
        }

        /* Info Panel */
        .eco-panel {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-left: 4px solid #133A2A;
            border-radius: 14px;
            padding: 15px 18px;
            margin-top: 0.85rem;
            box-shadow: 0 2px 6px rgba(19, 58, 42, 0.025);
        }
        .eco-panel-title {
            font-size: 0.92rem;
            font-weight: 700;
            color: #133A2A;
            margin-bottom: 4px;
        }
        .eco-panel-body {
            font-size: 0.85rem;
            color: #2D4238;
            line-height: 1.5;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    _inject_smart_alerts_theme()

    st.markdown(
        """
        <div class="eco-topbar">
            <div>
                <div class="eco-breadcrumb">EcoHealth &nbsp;/&nbsp; <strong>Smart Alerts</strong></div>
                <div class="eco-sub">In-app threshold, deterioration, pollutant limit, and statistical anomaly alerts stored in SQLite.</div>
            </div>
            <div class="eco-pill">
                <span class="eco-dot"></span>Rule Engine
            </div>
        </div>
        """,
        unsafe_allow_html=True,
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
        st.write("")
        show_ack = st.checkbox("Include Acknowledged Alerts", value=True, key="alert_show_ack")

    base_alerts = list_stored_alerts(include_acknowledged=show_ack, location=selected_loc, limit=500)

    t_col1, t_col2, t_col3 = st.columns([1.4, 1.4, 1.2])
    with t_col1:
        status_filter = st.selectbox(
            "Status Filter",
            options=["All", "Unacknowledged Only", "Acknowledged Only"],
            index=0,
            key="alert_status_filter",
        )
    with t_col2:
        type_options = ["All Types"] + sorted(
            {str(a.get("alert_type") or "") for a in base_alerts if a.get("alert_type")}
        )
        selected_type = st.selectbox(
            "Alert Rule Type",
            options=type_options,
            index=0,
            key="alert_type_filter",
        )
    with t_col3:
        st.write("")
        ack_all_clicked = st.button("Acknowledge Filtered", width="stretch", key="btn_ack_filtered")

    filtered_alerts = [
        a
        for a in base_alerts
        if (selected_type == "All Types" or str(a.get("alert_type")) == selected_type)
        and (
            status_filter == "All"
            or (status_filter == "Unacknowledged Only" and int(a.get("acknowledged", 0)) == 0)
            or (status_filter == "Acknowledged Only" and int(a.get("acknowledged", 0)) == 1)
        )
    ]

    if ack_all_clicked:
        batch_ids = [int(a["alert_id"]) for a in filtered_alerts if int(a.get("acknowledged", 0)) == 0]
        for aid in batch_ids:
            acknowledge_alert(aid)
        st.rerun()

    unack_count = sum(1 for a in filtered_alerts if int(a.get("acknowledged", 0)) == 0)
    unack_accent = "#DC2626" if unack_count > 0 else "#1F7A5A"

    m1, m2 = st.columns(2)
    with m1:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #133A2A;">
                <div class="eco-card-label">Displayed Alerts</div>
                <div class="eco-card-value">{len(filtered_alerts)}</div>
                <div class="eco-card-sub">Matching active filters in SQLite</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid {unack_accent};">
                <div class="eco-card-label">Unacknowledged Alerts</div>
                <div class="eco-card-value" style="color:{unack_accent};">{unack_count}</div>
                <div class="eco-card-sub">Awaiting review in current view</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not filtered_alerts:
        render_warning_banner("No matching alerts found for the current filter.", is_placeholder=False)
        return

    type_counts: dict[str, int] = {}
    for a in filtered_alerts:
        k = str(a.get("alert_type") or "UNKNOWN")
        type_counts[k] = type_counts.get(k, 0) + 1
    breakdown_str = " &nbsp;&bull;&nbsp; ".join(
        f"<strong>{html.escape(k)}</strong>: {v}" for k, v in sorted(type_counts.items())
    )
    st.markdown(
        f'<div class="eco-rule-strip">Rule breakdown: {breakdown_str}</div>',
        unsafe_allow_html=True,
    )

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
            for a in filtered_alerts
        ]
    )
    st.dataframe(df_alerts, width="stretch", hide_index=True)

    unack_ids = [int(a["alert_id"]) for a in filtered_alerts if int(a.get("acknowledged", 0)) == 0]
    if unack_ids:
        a_col1, a_col2 = st.columns([2, 1])
        with a_col1:
            chosen_id = st.selectbox("Select Alert ID to Acknowledge", options=unack_ids, key="ack_alert_id_select")
        with a_col2:
            st.write("")
            if st.button("Acknowledge Alert", width="stretch", key="btn_ack_alert"):
                acknowledge_alert(int(chosen_id))
                st.rerun()

    st.markdown(
        """
        <div class="eco-panel" style="border-left-color:#133A2A;">
            <div class="eco-panel-title">Deduplication &amp; Acknowledgement</div>
            <div class="eco-panel-body">
                Alerts with the same station, observation timestamp, type, and title are deduplicated in SQLite.
                Acknowledged alerts stay in history for auditability.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


main()