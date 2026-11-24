from datetime import date, timedelta
import html
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analytics import compute_historical_analytics
from src.api import POLLUTANT_KEYS
from src.database import get_observations, list_stations
from src.utils import render_warning_banner


_FOREST_SERIES_PALETTE: list[str] = [
    "#133A2A",
    "#1F7A5A",
    "#D97706",
    "#2B6CB0",
    "#9A3412",
    "#4D7C0F",
    "#6B21A8",
    "#0F766E",
]


def _inject_historical_theme() -> None:
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

        /* Green labels for filters */
        [data-testid="stSelectbox"] label,
        [data-testid="stSelectbox"] label p,
        [data-testid="stDateInput"] label,
        [data-testid="stDateInput"] label p {
            color: #1B5E3F !important;
            font-weight: 600 !important;
            font-size: 0.86rem !important;
        }

        /* Light-green selectbox & date inputs with crisp dark-green text */
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stDateInput"] input,
        [data-testid="stDateInput"] > div > div {
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
        div[data-testid="stSelectbox"] div[data-baseweb="select"] svg,
        [data-testid="stDateInput"] svg {
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

        /* KPI & Pollutant Cards */
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

        /* Section Title & Info Panel */
        .eco-section-title {
            font-size: 1.02rem;
            font-weight: 700;
            color: #133A2A;
            margin: 1.05rem 0 0.65rem 0;
        }
        .eco-panel {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-left: 4px solid #133A2A;
            border-radius: 14px;
            padding: 15px 18px;
            margin-top: 0.75rem;
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


def _severity_bar_color(label: str) -> str:
    s = (label or "").strip().lower()
    if "good" in s:
        return "#22A06B"
    if "satisfactory" in s:
        return "#4D7C0F"
    if "moderate" in s:
        return "#D97706"
    if "poor" in s and "very" not in s:
        return "#EA580C"
    if "very poor" in s or "unhealthy" in s:
        return "#DC2626"
    if "severe" in s:
        return "#7E22CE"
    return "#133A2A"


def _apply_eco_chart_layout(
    fig: go.Figure,
    height: int,
    x_title: str,
    y_title: str,
    barmode: str | None = None,
) -> None:
    layout_kwargs: dict[str, object] = {
        "height": height,
        "margin": {"l": 44, "r": 20, "t": 24, "b": 42},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#133A2A"},
        "legend": {
            "bgcolor": "rgba(255,255,255,0.75)",
            "bordercolor": "#DCE8E0",
            "borderwidth": 1,
            "font": {"color": "#133A2A", "size": 11},
        },
        "xaxis": {
            "title": {"text": x_title, "font": {"color": "#133A2A", "size": 12}},
            "tickfont": {"color": "#133A2A", "size": 11},
            "showgrid": False,
            "linecolor": "#B8CFC1",
        },
        "yaxis": {
            "title": {"text": y_title, "font": {"color": "#133A2A", "size": 12}},
            "tickfont": {"color": "#133A2A", "size": 11},
            "gridcolor": "#DFEAE3",
            "linecolor": "#B8CFC1",
            "zerolinecolor": "#9BBAA6",
        },
    }
    if barmode:
        layout_kwargs["barmode"] = barmode
    fig.update_layout(**layout_kwargs)


def _pick_rollup_columns(df, preferred_x: str, fallback_x: str) -> tuple[str | None, str | None, str | None]:
    if df is None or df.empty:
        return None, None, None
    x_col = (
        preferred_x if preferred_x in df.columns
        else (fallback_x if fallback_x in df.columns else str(df.columns[0]))
    )
    avg_col = next((c for c in ("Average AQI", "avg_aqi", "average_aqi") if c in df.columns), None)
    max_col = next((c for c in ("Max AQI", "max_aqi", "maximum_aqi") if c in df.columns), None)
    return x_col, avg_col, max_col


def main() -> None:
    _inject_historical_theme()

    st.markdown(
        """
        <div class="eco-topbar">
            <div>
                <div class="eco-breadcrumb">EcoHealth &nbsp;/&nbsp; <strong>Historical Analytics</strong></div>
                <div class="eco-sub">Persistent SQLite time-series analysis, pollutant trends, severity distribution, and daily/weekly rollups.</div>
            </div>
            <div class="eco-pill">
                <span class="eco-dot"></span>SQLite Archive
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    stations = list_stations()
    station_names = ["All Locations"] + [str(s["station_name"]) for s in stations]

    f_col1, f_col2, f_col3 = st.columns([2, 1, 1])
    with f_col1:
        selected_station = st.selectbox(
            "Filter by Location / Station",
            options=station_names,
            index=0,
            key="hist_station_filter",
        )
    with f_col2:
        start_dt = st.date_input(
            "Start Date",
            value=date.today() - timedelta(days=30),
            key="hist_start_date",
        )
    with f_col3:
        end_dt = st.date_input(
            "End Date",
            value=date.today(),
            key="hist_end_date",
        )

    if start_dt > end_dt:
        st.error("Start Date cannot be after End Date.")
        return

    observations = get_observations(
        location=selected_station,
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat(),
        limit=1000,
    )

    if not observations:
        render_warning_banner(
            "Insufficient historical data for the selected location and date range. "
            "Fetch live observations on 'Live AQI Monitoring' to populate SQLite storage.",
            is_placeholder=False,
        )
        return

    summary = compute_historical_analytics(observations)

    if not summary.has_sufficient_trend_data:
        render_warning_banner(
            "Only 1 historical record matches this filter. Summary metrics are shown below, "
            "but multi-point trend changes require at least 2 observations.",
            is_placeholder=False,
        )

    avg_aqi_str = f"{summary.average_aqi:g}" if summary.average_aqi is not None else "N/A"
    max_aqi_str = str(summary.max_aqi) if summary.max_aqi is not None else "N/A"
    min_aqi_str = str(summary.min_aqi) if summary.min_aqi is not None else "N/A"
    change_str = (
        f"{summary.aqi_change:+d}"
        if summary.aqi_change is not None
        else "Insufficient Data"
    )
    pct_meta = (
        f"{summary.aqi_change_pct:+.1f}% from first to latest"
        if summary.aqi_change_pct is not None
        else "Requires >= 2 observations"
    )
    change_color = (
        "#DC2626" if (summary.aqi_change is not None and summary.aqi_change > 0)
        else "#1F7A5A" if (summary.aqi_change is not None and summary.aqi_change < 0)
        else "#133A2A"
    )

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #133A2A;">
                <div class="eco-card-label">Average AQI</div>
                <div class="eco-card-value">{html.escape(avg_aqi_str)}</div>
                <div class="eco-card-sub">Across {summary.observation_count} observation(s)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #D97706;">
                <div class="eco-card-label">Maximum AQI</div>
                <div class="eco-card-value">{html.escape(max_aqi_str)}</div>
                <div class="eco-card-sub">Peak calculated CPCB AQI</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #1F7A5A;">
                <div class="eco-card-label">Minimum AQI</div>
                <div class="eco-card-value">{html.escape(min_aqi_str)}</div>
                <div class="eco-card-sub">Lowest calculated CPCB AQI</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid {change_color};">
                <div class="eco-card-label">Historical AQI Change</div>
                <div class="eco-card-value" style="font-size:1.45rem;color:{change_color};">{html.escape(change_str)}</div>
                <div class="eco-card-sub">{html.escape(pct_meta)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="eco-section-title">Pollutant-Wise Averages (Unimputed)</div>', unsafe_allow_html=True)
    p_cols = st.columns(6)
    for col, key in zip(p_cols, POLLUTANT_KEYS):
        avg_val = summary.pollutant_averages.get(key)
        val_txt = f"{avg_val:g}" if avg_val is not None else "N/A"
        with col:
            st.markdown(
                f"""
                <div class="eco-card" style="border-top:3px solid #2A6F4E;">
                    <div class="eco-card-label">{html.escape(key.upper())}</div>
                    <div class="eco-card-value" style="font-size:1.35rem;">{html.escape(val_txt)}</div>
                    <div class="eco-card-sub">Mean reported value</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # 1. AQI Time Series
    with st.container(border=True):
        st.markdown("**AQI Time Series**")
        fig_ts = px.line(
            summary.timeseries_df,
            x="observation_time",
            y="effective_aqi",
            color="station_name",
            markers=True,
            color_discrete_sequence=_FOREST_SERIES_PALETTE,
            labels={
                "observation_time": "Observation Time",
                "effective_aqi": "Calculated AQI (CPCB)",
                "station_name": "Station",
            },
        )
        _apply_eco_chart_layout(
            fig_ts,
            height=320,
            x_title="Observation Time",
            y_title="Calculated AQI (CPCB)",
        )
        st.plotly_chart(fig_ts, width="stretch", key="hist_aqi_timeseries_chart")

    # 2. Pollutant Trends & 3. Severity Distribution
    c_left, c_right = st.columns([1.6, 1])
    with c_left:
        with st.container(border=True):
            st.markdown("**Pollutant Trends**")
            fig_pol = go.Figure()
            for idx, key in enumerate(POLLUTANT_KEYS):
                if key in summary.timeseries_df.columns and summary.timeseries_df[key].notna().any():
                    series_col = _FOREST_SERIES_PALETTE[idx % len(_FOREST_SERIES_PALETTE)]
                    fig_pol.add_trace(
                        go.Scatter(
                            x=summary.timeseries_df["observation_time"],
                            y=summary.timeseries_df[key],
                            mode="lines+markers",
                            name=key.upper(),
                            line={"color": series_col, "width": 2},
                            marker={"color": series_col, "size": 6},
                        )
                    )
            _apply_eco_chart_layout(
                fig_pol,
                height=310,
                x_title="Observation Time",
                y_title="Measured Value",
            )
            st.plotly_chart(fig_pol, width="stretch", key="hist_pollutant_trends_chart")

    with c_right:
        with st.container(border=True):
            st.markdown("**Severity Distribution**")
            if summary.severity_distribution:
                sev_labels = list(summary.severity_distribution.keys())
                sev_counts = list(summary.severity_distribution.values())
                sev_colors = [_severity_bar_color(lbl) for lbl in sev_labels]
                fig_sev = go.Figure(
                    go.Bar(
                        x=sev_labels,
                        y=sev_counts,
                        marker_color=sev_colors,
                        text=sev_counts,
                        textposition="outside",
                        textfont={"color": "#133A2A", "size": 11},
                    )
                )
                _apply_eco_chart_layout(
                    fig_sev,
                    height=310,
                    x_title="Category",
                    y_title="Observation Count",
                )
                st.plotly_chart(fig_sev, width="stretch", key="hist_severity_dist_chart")
            else:
                st.caption("No severity categories available.")

    # 4. Daily & 5. Weekly Comparisons
    d_col, w_col = st.columns(2)
    with d_col:
        with st.container(border=True):
            st.markdown("**Daily Comparison (Average vs. Max AQI)**")
            dx_col, d_avg_col, d_max_col = _pick_rollup_columns(summary.daily_df, "Date", "date")
            if dx_col and d_avg_col and d_max_col:
                fig_daily = go.Figure()
                fig_daily.add_trace(
                    go.Bar(
                        x=summary.daily_df[dx_col],
                        y=summary.daily_df[d_avg_col],
                        name="Avg AQI",
                        marker_color="#133A2A",
                    )
                )
                fig_daily.add_trace(
                    go.Bar(
                        x=summary.daily_df[dx_col],
                        y=summary.daily_df[d_max_col],
                        name="Max AQI",
                        marker_color="#D97706",
                    )
                )
                _apply_eco_chart_layout(
                    fig_daily,
                    height=290,
                    x_title=str(dx_col),
                    y_title="AQI",
                    barmode="group",
                )
                st.plotly_chart(fig_daily, width="stretch", key="hist_daily_comparison_chart")
                st.dataframe(summary.daily_df, width="stretch", hide_index=True)
            else:
                st.caption("No daily summary data available for this selection.")

    with w_col:
        with st.container(border=True):
            st.markdown("**Weekly Comparison (Average vs. Max AQI)**")
            wx_col, w_avg_col, w_max_col = _pick_rollup_columns(summary.weekly_df, "Week", "week")
            if wx_col and w_avg_col and w_max_col:
                fig_weekly = go.Figure()
                fig_weekly.add_trace(
                    go.Bar(
                        x=summary.weekly_df[wx_col],
                        y=summary.weekly_df[w_avg_col],
                        name="Avg AQI",
                        marker_color="#1F7A5A",
                    )
                )
                fig_weekly.add_trace(
                    go.Bar(
                        x=summary.weekly_df[wx_col],
                        y=summary.weekly_df[w_max_col],
                        name="Max AQI",
                        marker_color="#EA580C",
                    )
                )
                _apply_eco_chart_layout(
                    fig_weekly,
                    height=290,
                    x_title=str(wx_col),
                    y_title="AQI",
                    barmode="group",
                )
                st.plotly_chart(fig_weekly, width="stretch", key="hist_weekly_comparison_chart")
                st.dataframe(summary.weekly_df, width="stretch", hide_index=True)
            else:
                st.caption("No weekly summary data available for this selection.")

    st.markdown(
        f"""
        <div class="eco-panel" style="border-left-color:#133A2A;">
            <div class="eco-panel-title">Stored Observations Log</div>
            <div class="eco-panel-body">Showing {summary.observation_count} deduplicated observation(s) from SQLite.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


main()