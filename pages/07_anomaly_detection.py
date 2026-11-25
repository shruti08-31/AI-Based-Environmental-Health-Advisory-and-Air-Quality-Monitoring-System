from datetime import datetime, timedelta, timezone
import html
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.database import get_observations, hydrate_sqlite_from_json, initialize_database, list_stations
from src.intelligence import detect_anomalies
from src.utils import render_warning_banner

AQI_MIN_VALID = 0.0
AQI_MAX_VALID = 500.0


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
        div[data-baseweb="select"] > div,
        [data-testid="stNumberInput"] input {
            background-color: #EAF4EC !important;
            border-color: #B4D6BE !important;
            border-radius: 10px !important;
            color: #133A2A !important;
            -webkit-text-fill-color: #133A2A !important;
            font-weight: 600 !important;
        }
        div[data-baseweb="select"] *,
        div[data-baseweb="select"] div,
        div[data-baseweb="select"] span,
        div[data-baseweb="select"] input {
            color: #133A2A !important;
            -webkit-text-fill-color: #133A2A !important;
            opacity: 1 !important;
            font-weight: 600 !important;
        }
        div[data-baseweb="select"] svg {
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


def _extract_numeric_aqi(row: dict) -> float | None:
    for key in ("aqi", "AQI", "aqi_value", "value"):
        if key in row and row[key] is not None:
            val = pd.to_numeric(row[key], errors="coerce")
            if pd.notna(val):
                return float(val)
    return None


def _sanitize_station_rows(st_rows_sorted: list[dict], cap_outliers: bool = True) -> tuple[list[dict], int]:
    """Validate AQI values against standard 0-500 bounds; cap or flag extreme sensor spikes."""
    sanitized_rows: list[dict] = []
    outlier_count = 0

    for row in st_rows_sorted:
        raw_aqi = _extract_numeric_aqi(row)
        is_extreme = raw_aqi is not None and (raw_aqi < AQI_MIN_VALID or raw_aqi > AQI_MAX_VALID)
        if is_extreme:
            outlier_count += 1

        row_copy = dict(row)
        if raw_aqi is not None and is_extreme and cap_outliers:
            capped_aqi = max(AQI_MIN_VALID, min(AQI_MAX_VALID, raw_aqi))
            for key in ("aqi", "AQI", "aqi_value", "value"):
                if key in row_copy and row_copy[key] is not None:
                    row_copy[key] = capped_aqi
            existing_note = str(row_copy.get("data_quality_note") or "").strip()
            spike_note = f"Extreme AQI ({raw_aqi:g}) capped to {capped_aqi:g} [0-500 range]"
            row_copy["data_quality_note"] = f"{existing_note} | {spike_note}" if existing_note else spike_note
        elif raw_aqi is not None and is_extreme:
            existing_note = str(row_copy.get("data_quality_note") or "").strip()
            spike_note = f"Extreme AQI ({raw_aqi:g}) outside standard 0-500 range"
            row_copy["data_quality_note"] = f"{existing_note} | {spike_note}" if existing_note else spike_note

        sanitized_rows.append(row_copy)

    return sanitized_rows, outlier_count


def _evaluate_findings_by_station(
    obs_rows: list[dict],
    jump_thresh: float,
    cap_outliers: bool = True,
) -> list:
    """Evaluate anomalies per station first so cross-station transitions are not treated as jumps."""
    by_station: dict[str, list[dict]] = {}
    for row in obs_rows:
        st_name = str(row.get("station_name") or row.get("query_city") or "Unknown Station")
        by_station.setdefault(st_name, []).append(row)

    all_findings = []
    for st_rows in by_station.values():
        st_rows_sorted = sorted(st_rows, key=lambda r: _to_utc_dt(r.get("observation_time")))
        st_rows_clean, _ = _sanitize_station_rows(st_rows_sorted, cap_outliers=cap_outliers)

        aqi_series = pd.Series([_extract_numeric_aqi(r) for r in st_rows_clean], dtype="float64")
        step_diffs = aqi_series.diff()

        station_findings = detect_anomalies(st_rows_clean, aqi_jump_threshold=jump_thresh)
        for idx, finding in enumerate(station_findings):
            diff_val = step_diffs.iloc[idx] if idx < len(step_diffs) else None
            if diff_val is not None and pd.notna(diff_val):
                step_val = float(diff_val)
                finding.aqi_delta = step_val
                if abs(step_val) > float(jump_thresh):
                    finding.is_anomaly = True
            all_findings.append(finding)

    all_findings.sort(key=lambda f: (_to_utc_dt(f.observation_time), str(f.station_name or "")))
    return all_findings


def _is_step_flagged(finding: object, jump_thresh: float) -> bool:
    delta = getattr(finding, "aqi_delta", None)
    if delta is not None:
        val = pd.to_numeric(delta, errors="coerce")
        if pd.notna(val):
            return bool(abs(float(val)) > float(jump_thresh))
    return bool(getattr(finding, "is_anomaly", False))


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


def _build_station_summary_df(findings: list, jump_thresh: float) -> pd.DataFrame:
    records = []
    for f in findings:
        delta_val = pd.to_numeric(getattr(f, "aqi_delta", 0.0), errors="coerce")
        delta_num = float(delta_val) if pd.notna(delta_val) else 0.0
        records.append({
            "Station": str(getattr(f, "station_name", None) or "Unknown Station"),
            "Flagged": _is_step_flagged(f, jump_thresh),
            "Delta": delta_num,
        })
    if not records:
        return pd.DataFrame(columns=["Station", "Evaluated", "Flagged", "Normal", "Peak |ΔAQI|"])

    df_rec = pd.DataFrame(records)
    summary = df_rec.groupby("Station", as_index=False).agg(
        Evaluated=("Delta", "count"),
        Flagged=("Flagged", "sum"),
        Peak_Abs_Delta=("Delta", lambda s: float(s.abs().max())),
    )
    summary["Normal"] = summary["Evaluated"] - summary["Flagged"]
    summary = summary.sort_values(["Flagged", "Evaluated"], ascending=[False, False]).reset_index(drop=True)
    return summary[["Station", "Evaluated", "Flagged", "Normal", "Peak_Abs_Delta"]]


def _style_station_column(df: pd.DataFrame, station_color: str) -> "pd.io.formats.style.Styler":
    if df.empty or "Station" not in df.columns:
        return df.style
    return df.style.map(
        lambda _: f"color: {station_color}; font-weight: 700;",
        subset=["Station"],
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

    f1, f2, f3, f4 = st.columns([2, 1, 1.1, 1.0])
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
    with f3:
        cap_extreme_aqi = st.checkbox(
            "Cap AQI outside 0–500",
            value=True,
            key="anomaly_cap_extreme_aqi",
        )
    with f4:
        station_label_mode = st.selectbox(
            "Station Label Color",
            options=["Green", "Blue"],
            index=0,
            key="anomaly_station_label_color",
        )

    station_color = "#1B5E3F" if station_label_mode == "Green" else "#1D4ED8"

    obs_rows = get_observations(location=selected_loc, limit=1000)
    if not obs_rows:
        render_warning_banner(
            "No valid observations stored yet. Fetch live readings on 'Live AQI Monitoring' to run anomaly analysis.",
            is_placeholder=False,
        )
        return

    findings = _evaluate_findings_by_station(
        obs_rows,
        jump_thresh=float(jump_thresh),
        cap_outliers=bool(cap_extreme_aqi),
    )
    if not findings:
        render_warning_banner(
            "Stored observations for this selection do not contain valid numeric AQI values for anomaly scoring.",
            is_placeholder=False,
        )
        return

    flagged = [f for f in findings if _is_step_flagged(f, float(jump_thresh))]
    step_magnitudes = [
        abs(float(f.aqi_delta))
        for f in findings
        if getattr(f, "aqi_delta", None) is not None and pd.notna(pd.to_numeric(f.aqi_delta, errors="coerce"))
    ]
    peak_step = max(step_magnitudes) if step_magnitudes else 0.0
    flagged_pct = (len(flagged) / len(findings) * 100.0) if findings else 0.0

    latest_f = findings[-1]
    latest_flagged = _is_step_flagged(latest_f, float(jump_thresh))
    latest_status_txt = "Anomaly Flagged" if latest_flagged else "Normal Baseline"
    latest_accent = "#DC2626" if latest_flagged else "#1F7A5A"

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #133A2A;">
                <div class="eco-card-label">Evaluated Observations</div>
                <div class="eco-card-value">{len(findings)}</div>
                <div class="eco-card-sub">Grouped per station &amp; chronological</div>
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
                <div class="eco-card-sub">|ΔAQI| &gt; {jump_thresh:g} ({flagged_pct:.1f}%)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #2563EB;">
                <div class="eco-card-label">Peak Step Change (|ΔAQI|)</div>
                <div class="eco-card-value">{peak_step:.1f}</div>
                <div class="eco-card-sub">Largest station step jump</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid {latest_accent};">
                <div class="eco-card-label">Latest Observation Status</div>
                <div class="eco-card-value" style="font-size:1.45rem;color:{latest_accent};">{html.escape(latest_status_txt)}</div>
                <div class="eco-card-sub">{html.escape(str(latest_f.evidence_strength or "Baseline"))}</div>
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

    # Presentation-friendly visual charts & station summary with colored station labels
    with st.container(border=True):
        c_left, c_right = st.columns([1.4, 1])
        with c_left:
            st.markdown("**Station Step Anomalies vs. Normal Readings**")
        with c_right:
            window_choice = st.radio(
                "Window Filter",
                options=["7 Days", "15 Days", "30 Days"],
                index=2,
                horizontal=True,
                key="anomaly_chart_window_days",
            )

        days_map = {"7 Days": 7, "15 Days": 15, "30 Days": 30}
        selected_days = days_map.get(window_choice, 30)
        window_findings, used_all_fallback = _filter_findings_by_days(findings, selected_days)
        if used_all_fallback and len(findings) > 0:
            st.caption(
                f"Showing all {len(window_findings)} available observations (stored data spans fewer than {selected_days} days)."
            )

        station_df = _build_station_summary_df(window_findings, float(jump_thresh)).head(10)
        if not station_df.empty:
            colored_y_labels = [
                f"<span style='color:{station_color};font-weight:700;'>{html.escape(str(st))}</span>"
                for st in station_df["Station"]
            ]
            fig_st = go.Figure()
            fig_st.add_trace(
                go.Bar(
                    y=colored_y_labels,
                    x=station_df["Normal"],
                    customdata=station_df["Station"],
                    name="Normal (|ΔAQI| ≤ Threshold)",
                    orientation="h",
                    marker_color="#64748B",
                    hovertemplate=(
                        f"<b style='color:{station_color};'>%{{customdata}}</b><br>"
                        "Normal Readings: %{x}<extra></extra>"
                    ),
                )
            )
            fig_st.add_trace(
                go.Bar(
                    y=colored_y_labels,
                    x=station_df["Flagged"],
                    customdata=station_df["Station"],
                    name="Flagged (|ΔAQI| > Threshold)",
                    orientation="h",
                    marker_color="#DC2626",
                    hovertemplate=(
                        f"<b style='color:{station_color};'>%{{customdata}}</b><br>"
                        "Flagged Anomalies: %{x}<extra></extra>"
                    ),
                )
            )
            fig_st.update_layout(
                barmode="stack",
                height=310,
                margin={"l": 10, "r": 16, "t": 18, "b": 36},
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"color": "#133A2A"},
                legend={"orientation": "h", "y": 1.14, "x": 0},
                yaxis={"autorange": "reversed", "tickfont": {"size": 11, "color": station_color}},
                xaxis={"title": {"text": "Evaluated Observations", "font": {"size": 12}}, "gridcolor": "#E2ECE6"},
            )
            st.plotly_chart(fig_st, width="stretch", key="anomaly_station_stack_chart")

    st.markdown("**Station-by-Station Overview**")
    st.dataframe(
        _style_station_column(_build_station_summary_df(findings, float(jump_thresh)), station_color),
        width="stretch",
        hide_index=True,
    )

    h_col1, h_col2 = st.columns([3, 1])
    with h_col1:
        st.markdown("### Anomaly History & Pollutant Deviations")
    with h_col2:
        only_flagged = st.checkbox("Show flagged only", value=False, key="anomaly_only_flagged")

    display_findings = [
        f for f in reversed(findings)
        if (_is_step_flagged(f, float(jump_thresh)) or not only_flagged)
    ]
    if not display_findings:
        _render_panel(
            title="No Flagged Anomalies",
            body=f"All {len(findings)} evaluated observations remained within the ±{jump_thresh:g} AQI step threshold and baseline bounds.",
            accent="#1F7A5A",
        )
    else:
        history_rows = [
            {
                "Timestamp": _format_display_time(f.observation_time),
                "Station": f.station_name,
                "Anomaly": "Yes" if _is_step_flagged(f, float(jump_thresh)) else "No",
                "Step Delta": f"{f.aqi_delta:+.1f}" if getattr(f, "aqi_delta", None) is not None else "0.0",
                "Evidence": f.evidence_strength or "Baseline",
                "Observed Change": f.observed_change,
                "Reference Baseline": f.reference_baseline,
                "Explanation": f.explanation,
                "Data Quality / Interval Note": f.data_quality_note,
            }
            for f in display_findings
        ]
        st.dataframe(
            _style_station_column(pd.DataFrame(history_rows), station_color),
            width="stretch",
            hide_index=True,
        )

    _render_panel(
        title="Interpretation Note",
        body="Statistical anomalies highlight unusual shifts or baselines in valid readings; invalid API measurements are excluded and never treated as confirmed pollution events.",
        accent="#315B48",
    )


main()