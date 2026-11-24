import html
import streamlit as st

from src.alerts import (
    DEFAULT_AQI_ALERT_THRESHOLD,
    DEFAULT_DETERIORATION_DELTA,
    evaluate_alert_candidates,
    list_stored_alerts,
    persist_alerts,
)
from src.api import AqiReading
from src.database import get_observations
from src.utils import render_warning_banner


def _inject_smart_alerts_clean_theme() -> None:
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
            padding-top: 1.2rem !important;
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

        /* Input & select styling */
        [data-testid="stNumberInput"] label,
        [data-testid="stNumberInput"] label p,
        [data-testid="stSelectbox"] label,
        [data-testid="stSelectbox"] label p {
            color: #1B5E3F !important;
            font-weight: 600 !important;
            font-size: 0.84rem !important;
        }
        [data-testid="stNumberInput"] input,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            border-color: #D5E2DA !important;
            border-radius: 8px !important;
            color: #16261E !important;
            -webkit-text-fill-color: #16261E !important;
            font-weight: 600 !important;
        }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] *,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] div,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] span,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] input {
            color: #16261E !important;
            -webkit-text-fill-color: #16261E !important;
            opacity: 1 !important;
            font-weight: 500 !important;
        }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] svg {
            color: #16261E !important;
            fill: #16261E !important;
        }

        /* Primary emerald/forest button & secondary toggle button */
        div.stButton > button[kind="primary"] {
            background-color: #0F8A6E !important;
            color: #FFFFFF !important;
            border: 1px solid #0F8A6E !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: #0B7059 !important;
            border-color: #0B7059 !important;
        }
        div.stButton > button[kind="secondary"] {
            background-color: #FFFFFF !important;
            color: #16261E !important;
            border: 1px solid #D5E2DA !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
        }
        div.stButton > button[kind="secondary"]:hover {
            background-color: #F1F6F3 !important;
            border-color: #BFD1C6 !important;
        }

        /* Header bar */
        .sa-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1rem;
        }
        .sa-title {
            font-size: 1.55rem;
            font-weight: 700;
            color: #16261E;
            line-height: 1.2;
            margin: 0;
        }
        .sa-subtitle {
            font-size: 0.84rem;
            color: #6B7E74;
            margin-top: 3px;
        }
        .sa-loc-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #FFFFFF;
            border: 1px solid #DCE7E0;
            border-radius: 999px;
            padding: 5px 12px;
            font-size: 0.80rem;
            font-weight: 500;
            color: #16261E;
        }

        /* Section cards */
        .sa-section-card {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-radius: 14px;
            padding: 16px 20px;
            margin-bottom: 1rem;
            box-shadow: 0 1px 4px rgba(19, 58, 42, 0.025);
        }
        .sa-section-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        .sa-section-title {
            font-size: 0.98rem;
            font-weight: 700;
            color: #16261E;
            margin: 0;
        }
        .sa-status-meta {
            font-size: 0.78rem;
            color: #7A8C82;
        }

        /* Active alert items */
        .sa-alert-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 14px;
            border: 1px solid #E7EFEA;
            border-radius: 10px;
            padding: 12px 16px;
            margin-bottom: 10px;
            background: #FFFFFF;
        }
        .sa-alert-item:last-child {
            margin-bottom: 0;
        }
        .sa-alert-tag {
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: #B45309;
            margin-bottom: 3px;
        }
        .sa-alert-msg {
            font-size: 0.88rem;
            color: #16261E;
            line-height: 1.4;
        }
        .sa-alert-msg strong {
            font-weight: 700;
        }
        .sa-alert-time {
            font-size: 0.75rem;
            color: #82938A;
            margin-top: 3px;
        }
        .sa-sev-badge {
            font-size: 0.73rem;
            font-weight: 600;
            padding: 4px 11px;
            border-radius: 999px;
            white-space: nowrap;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _severity_badge_style(severity: str) -> tuple[str, str, str]:
    s = (severity or "").strip().lower()
    if any(k in s for k in ("severe", "very poor", "very unhealthy", "critical")):
        return ("#FEE2E2", "#B91C1C", "#DC2626")
    if any(k in s for k in ("poor", "high", "unhealthy")):
        return ("#FFEDD5", "#C2410C", "#EA580C")
    if "moderate" in s:
        return ("#FEF3C7", "#B45309", "#D97706")
    return ("#E6F4EC", "#166534", "#15803D")


def _format_alert_type_label(raw_type: str) -> str:
    t = (raw_type or "").strip().upper()
    mapping = {
        "AQI_THRESHOLD": "THRESHOLD EXCEEDED",
        "DETERIORATION": "RAPID AQI SPIKE",
        "POLLUTANT_LIMIT": "POLLUTANT LIMIT",
        "POLLUTANT_PATTERN": "POLLUTANT PATTERN",
        "ANOMALY_DETECTED": "ANOMALY DETECTED",
    }
    return mapping.get(t, t.replace("_", " "))


def main() -> None:
    _inject_smart_alerts_clean_theme()

    if "alerts_monitoring_enabled" not in st.session_state:
        st.session_state["alerts_monitoring_enabled"] = True

    reading: AqiReading | None = st.session_state.get("waqi_last_reading")
    active_loc_label = (
        str(reading.station_name or reading.query)
        if reading is not None
        else "All Stored Stations"
    )

    st.markdown(
        f"""
        <div class="sa-header">
            <div>
                <h1 class="sa-title">Smart Alerts</h1>
                <div class="sa-subtitle">Environmental Health Advisory &amp; Monitoring System</div>
            </div>
            <div class="sa-loc-pill">&#128205; {html.escape(active_loc_label)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Top threshold & toggle bar
    with st.container(border=True):
        t_left, t_mid, t_right = st.columns([1.4, 1.4, 2.2])
        with t_left:
            aqi_thresh = st.number_input(
                "AQI Alert Threshold",
                min_value=50,
                max_value=450,
                value=DEFAULT_AQI_ALERT_THRESHOLD,
                step=10,
                key="alert_aqi_thresh",
            )
        with t_mid:
            det_delta = st.number_input(
                "AQI Deterioration Delta (+)",
                min_value=10,
                max_value=250,
                value=DEFAULT_DETERIORATION_DELTA,
                step=5,
                key="alert_det_delta",
            )
        with t_right:
            st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
            b1, b2 = st.columns([1.3, 1.0])
            with b1:
                eval_clicked = st.button(
                    "Apply & Evaluate Alerts",
                    type="primary",
                    use_container_width=True,
                    key="btn_eval_alerts",
                )
            with b2:
                toggle_label = (
                    "Disable Alerts"
                    if st.session_state["alerts_monitoring_enabled"]
                    else "Enable Alerts"
                )
                if st.button(
                    toggle_label,
                    type="secondary",
                    use_container_width=True,
                    key="btn_toggle_alerts_enabled",
                ):
                    st.session_state["alerts_monitoring_enabled"] = not st.session_state["alerts_monitoring_enabled"]
                    st.rerun()

    if not st.session_state["alerts_monitoring_enabled"]:
        render_warning_banner(
            "Alert evaluation is currently paused. Click 'Enable Alerts' above to resume monitoring.",
            is_placeholder=False,
        )

    if eval_clicked and st.session_state["alerts_monitoring_enabled"]:
        if reading is not None:
            prev_obs = get_observations(location=reading.station_name or reading.query, limit=50)
            cands = evaluate_alert_candidates(
                reading=reading,
                previous_observations=prev_obs,
                aqi_threshold=int(aqi_thresh),
                deterioration_delta=int(det_delta),
            )
            added = persist_alerts(cands, query_city=reading.query)
            st.success(f"Evaluated {len(cands)} alert rule(s); {added} new alert(s) stored.")
        else:
            st.info("No active live reading in session; displaying stored alerts from SQLite.")

    all_stored = list_stored_alerts(include_acknowledged=True, location="All Locations", limit=500)
    unack_alerts = [a for a in all_stored if int(a.get("acknowledged", 0)) == 0]

    # Active Alerts card section
    status_text = (
        "Status: Monitoring Enabled"
        if st.session_state["alerts_monitoring_enabled"]
        else "Status: Monitoring Disabled"
    )
    st.markdown(
        f"""
        <div class="sa-section-card">
            <div class="sa-section-head">
                <h2 class="sa-section-title">Active Alerts ({len(unack_alerts)})</h2>
                <span class="sa-status-meta">{html.escape(status_text)}</span>
            </div>
        """,
        unsafe_allow_html=True,
    )

    if not unack_alerts:
        st.markdown(
            '<div class="sa-alert-msg" style="color:#6B7E74;">No unacknowledged active alerts right now.</div>',
            unsafe_allow_html=True,
        )
    else:
        for a in unack_alerts[:6]:
            sev_str = str(a.get("severity") or "Moderate")
            badge_bg, badge_fg, tag_color = _severity_badge_style(sev_str)
            tag_label = _format_alert_type_label(str(a.get("alert_type") or "ALERT"))
            loc_str = str(a.get("location") or "Unknown")
            title_str = str(a.get("title") or "")
            exp_str = str(a.get("explanation") or "")
            ts_str = str(a.get("observation_time") or "")
            msg_detail = exp_str if exp_str else title_str

            st.markdown(
                f"""
                <div class="sa-alert-item">
                    <div>
                        <div class="sa-alert-tag" style="color:{tag_color};">{html.escape(tag_label)}</div>
                        <div class="sa-alert-msg"><strong>{html.escape(loc_str)}</strong> &mdash; {html.escape(msg_detail)}</div>
                        <div class="sa-alert-time">{html.escape(ts_str)}</div>
                    </div>
                    <span class="sa-sev-badge" style="background:{badge_bg};color:{badge_fg};">{html.escape(sev_str)}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)


main()