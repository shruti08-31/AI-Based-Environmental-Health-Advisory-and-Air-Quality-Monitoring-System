from datetime import datetime, timedelta, timezone
import html
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.database import get_observations, hydrate_sqlite_from_json, initialize_database, list_stations
from src.intelligence import detect_anomalies
from src.utils import render_warning_banner


def _inject_anomaly_theme() -> None:
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

        /* Green labels & light-green inputs with dark-green text */
        [data-testid="stSelectbox"] label,
        [data-testid="stSelectbox"] label p,
        [data-testid="stNumberInput"] label,
        [data-testid="stNumberInput"] label p,
        [data-testid="stRadio"] label,
        [data-testid="stRadio"] label p,
        [data-testid="stCheckbox"] label,
        [data-testid="stCheckbox"] label p {
            color: #1B5E3F !important;
            font-weight: 600 !important;
            font-size: 0.86rem !important;
        }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stNumberInput"] input {
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

        /* KPI Cards */
        .eco-card {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-radius: 16px;
            padding: 18px 20px;
            box-shadow: 0 2px 8px rgba(19, 58, 42, 0.03);
            height: 100%;
        }
        .eco-card-label {
            font-size: 0.82rem;
            font-weight: 500;
            color: #5E7167;
            margin-bottom: 8px;
        }
        .eco-card-value {
            font-size: 1.75rem;
            font-weight: 700;
            color: #133A2A;
            line-height: 1.15;
            margin-bottom: 6px;
        }
        .eco-card-sub {
            font-size: 0.79rem;
            color: #6B7E74;
        }

        /* Info / Note Panels */
        .eco-panel {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-left: 4px solid #133A2A;
            border-radius: 14px;
            padding: 15px 18px;
            margin: 0.75rem 0;
            box-shadow: 0 2px 6px rgba(19, 58, 42, 0.025);
        }
        .eco-panel-title {
            font-size: 0.92rem;
            font-weight: 700;
            color: #133A2A;
            margin-bottom: 5px;
        }
        .eco-panel-body {
            font-size: 0.85rem;
            color: #2D4238;
            line-height: 1.55;
        }

        /* Seamless chart containers */
        [data-testid="stPlotlyChart"],
        [data-testid="stPlotlyChart"] > div {
            background: transparent !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _to_utc_dt(val: object) -> datetime:
    if not val:
        return datetime.min.replace(tzinfo=timezone.utc)
    ts = pd.to_datetime(str(val), errors="coerce", utc=True)
    if pd.isna(ts):
        return datetime.min.replace(tzinfo=timezone.utc)
    return ts.to_pydatetime()


def _format_display_time(raw_val: object) -> str:
    s = str(raw_val or "").strip()
    if not s:
        return "Unknown Time"
    ts = pd.to_datetime(s, errors="coerce", utc=True)
    if pd.isna(ts):
        return s
    return ts.tz_convert("Asia/Kolkata").strftime("%b %d, %Y %H:%M")


def _evaluate_findings_by_station(obs_rows: list[dict], jump_thresh: float) -> list:
    """Evaluate anomalies per station so cross-station transitions are not treated as jumps."""
    by_station: dict[str, list[dict]] = {}
    for row in obs_rows:
        st_name = str(row.get("station_name") or row.get("query_city") or "Unknown Station")
        by_station.setdefault(st_name, []).append(row)

    all_findings = []
    for st_rows in by_station.values():
        st_rows_sorted = sorted(st_rows, key=lambda r: _to_utc_dt(r.get("observation_time")))
        all_findings.extend(detect_anomalies(st_rows_sorted, aqi_jump_threshold=jump_thresh))

    all_findings.sort(key=lambda f: (_to_utc_dt(f.observation_time), str(f.station_name or "")))
    return all_findings


def _filter_findings_by_days(findings: list, days: int) -> tuple[list, bool]:
    """Filters findings to the last `days` window; returns (filtered_list, used_fallback_all)."""
    if not findings:
        return [], False
    parsed_times: list[datetime | None] = []
    for f in findings:
        raw_ts = str(f.observation_time or "").strip()
        dt = pd.to_datetime(raw_ts, errors="coerce", utc=True) if raw_ts else pd.NaT
        parsed_times.append(None if pd.isna(dt) else dt.to_pydatetime())

    valid_dts = [d for d in parsed_times if d is not None]
    if not valid_dts:
        return findings, True

    anchor_dt = max(valid_dts)
    cutoff = anchor_dt - timedelta(days=days)
    filtered = [
        f for f, d in zip(findings, parsed_times)
        if d is not None and d >= cutoff
    ]
    if filtered:
        return filtered, False
    return findings, True


def _render_panel(title: str, body: str, accent: str = "#133A2A") -> None:
    st.markdown(
        f"""
        <div class="eco-panel" style="border-left-color:{accent};">
            <div class="eco-panel-title">{html.escape(title)}</div>
            <div class="eco-panel-body">{html.escape(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    _inject_anomaly_theme()

    st.markdown(
        """
        <div class="eco-topbar">
            <div>
                <div class="eco-breadcrumb">EcoHealth &nbsp;/&nbsp; <strong>Anomaly Detection</strong></div>
                <div class="eco-sub">Explainable statistical detection of sudden AQI jumps, pollutant shifts, and baseline deviations.</div>
            </div>
            <div class="eco-pill">
                <span class="eco-dot"></span>Statistical Monitor
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    initialize_database()
    if not list_stations():
        hydrate_sqlite_from_json()

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

    findings = _evaluate_findings_by_station(obs_rows, jump_thresh=float(jump_thresh))
    if not findings:
        render_warning_banner(
            "Stored observations for this selection do not contain valid numeric AQI values for anomaly scoring.",
            is_placeholder=False,
        )
        return

    flagged = [f for f in findings if f.is_anomaly]
    latest_f = findings[-1]
    latest_status_txt = "Anomaly Flagged" if latest_f.is_anomaly else "Normal Baseline"
    latest_accent = "#DC2626" if latest_f.is_anomaly else "#1F7A5A"

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #133A2A;">
                <div class="eco-card-label">Evaluated Observations</div>
                <div class="eco-card-value">{len(findings)}</div>
                <div class="eco-card-sub">Valid chronological points</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #D97706;">
                <div class="eco-card-label">Flagged Statistical Anomalies</div>
                <div class="eco-card-value">{len(flagged)}</div>
                <div class="eco-card-sub">Jump threshold: {jump_thresh:g}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid {latest_accent};">
                <div class="eco-card-label">Latest Observation Status</div>
                <div class="eco-card-value" style="font-size:1.45rem;color:{latest_accent};">{html.escape(latest_status_txt)}</div>
                <div class="eco-card-sub">{html.escape(latest_f.evidence_strength or "Baseline")}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if len(findings) < 2:
        _render_panel(
            title="Limited Time-Series Depth",
            body="Only one valid observation is available for this station. Fetch additional readings over time to measure step-to-step AQI jumps.",
            accent="#1F7A5A",
        )

    with st.container(border=True):
        ch_head_l, ch_head_r = st.columns([2.2, 1.3])
        with ch_head_l:
            st.markdown("**Observed AQI Step Changes Across Sequence**")
        with ch_head_r:
            window_choice = st.radio(
                "Chart Window",
                options=["7 Days", "15 Days", "30 Days"],
                index=2,
                horizontal=True,
                key="anomaly_chart_window_days",
            )

        days_map = {"7 Days": 7, "15 Days": 15, "30 Days": 30}
        selected_days = days_map.get(window_choice, 30)
        chart_findings, used_all_fallback = _filter_findings_by_days(findings, selected_days)

        if used_all_fallback and len(findings) > 0:
            st.caption(
                f"Showing all {len(chart_findings)} available observations (stored data spans fewer than {selected_days} days)."
            )

        delta_rows = [
            {
                "Display Time": _format_display_time(f.observation_time),
                "Raw Time": str(f.observation_time or ""),
                "Station": f.station_name,
                "AQI Delta": f.aqi_delta if f.aqi_delta is not None else 0.0,
                "Flagged": "Yes" if f.is_anomaly else "No",
                "Evidence Strength": f.evidence_strength,
            }
            for f in chart_findings
        ]
        df_deltas = pd.DataFrame(delta_rows)

        fig_d = go.Figure(
            go.Bar(
                x=df_deltas["Display Time"],
                y=df_deltas["AQI Delta"],
                customdata=df_deltas[["Station", "Flagged", "Evidence Strength", "Raw Time"]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Time: %{customdata[3]}<br>"
                    "AQI Delta: %{y:+.1f}<br>"
                    "Flagged: %{customdata[1]} (%{customdata[2]})<extra></extra>"
                ),
                marker_color=["#DC2626" if x == "Yes" else "#133A2A" for x in df_deltas["Flagged"]],
            )
        )
        fig_d.add_hline(
            y=float(jump_thresh),
            line_dash="dash",
            line_color="#DC2626",
            annotation_text=f"+{jump_thresh:g}",
            annotation_font_color="#133A2A",
        )
        fig_d.add_hline(
            y=-float(jump_thresh),
            line_dash="dash",
            line_color="#1F7A5A",
            annotation_text=f"-{jump_thresh:g}",
            annotation_font_color="#133A2A",
        )
        fig_d.update_layout(
            height=305,
            margin={"l": 44, "r": 20, "t": 22, "b": 42},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"color": "#133A2A"},
            xaxis={
                "title": {"text": f"Observation Time ({window_choice})", "font": {"color": "#133A2A", "size": 12}},
                "tickfont": {"color": "#133A2A", "size": 11},
                "showgrid": False,
                "linecolor": "#B8CFC1",
            },
            yaxis={
                "title": {"text": "AQI Change vs. Prior", "font": {"color": "#133A2A", "size": 12}},
                "tickfont": {"color": "#133A2A", "size": 11},
                "gridcolor": "#DFEAE3",
                "linecolor": "#B8CFC1",
                "zerolinecolor": "#9BBAA6",
            },
        )
        st.plotly_chart(fig_d, width="stretch", key="anomaly_aqi_delta_chart")

    h_col1, h_col2 = st.columns([3, 1])
    with h_col1:
        st.markdown("### Anomaly History & Pollutant Deviations")
    with h_col2:
        only_flagged = st.checkbox("Show flagged only", value=False, key="anomaly_only_flagged")

    display_findings = [f for f in reversed(findings) if (f.is_anomaly or not only_flagged)]
    if not display_findings:
        _render_panel(
            title="No Flagged Anomalies",
            body=f"All {len(findings)} evaluated observations remained within the ±{jump_thresh:g} AQI step threshold and baseline bounds.",
            accent="#1F7A5A",
        )
    else:
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
            for f in display_findings
        ]
        st.dataframe(pd.DataFrame(history_rows), width="stretch", hide_index=True)

    _render_panel(
        title="Interpretation Note",
        body="Statistical anomalies highlight unusual shifts or baselines in valid readings; invalid API measurements are excluded and never treated as confirmed pollution events.",
        accent="#315B48",
    )


main()