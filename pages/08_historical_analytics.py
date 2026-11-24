from datetime import date, timedelta
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analytics import compute_historical_analytics
from src.api import POLLUTANT_KEYS
from src.database import get_observations, list_stations
from src.utils import (
    render_info_panel,
    render_metric_card,
    render_page_header,
    render_warning_banner,
)


def main() -> None:
    render_page_header(
        title="Historical Analytics",
        subtitle="Persistent SQLite time-series analysis, pollutant trends, severity distribution, and daily/weekly rollups.",
        is_placeholder=False,
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

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_metric_card(
            label="Average AQI",
            value=f"{summary.average_aqi:g}" if summary.average_aqi is not None else "N/A",
            meta=f"Across {summary.observation_count} observation(s)",
            is_placeholder=False,
        )
    with m2:
        render_metric_card(
            label="Maximum AQI",
            value=str(summary.max_aqi) if summary.max_aqi is not None else "N/A",
            meta="Peak calculated CPCB AQI",
            is_placeholder=False,
        )
    with m3:
        render_metric_card(
            label="Minimum AQI",
            value=str(summary.min_aqi) if summary.min_aqi is not None else "N/A",
            meta="Lowest calculated CPCB AQI",
            is_placeholder=False,
        )
    with m4:
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
        render_metric_card(
            label="Historical AQI Change",
            value=change_str,
            meta=pct_meta,
            is_placeholder=False,
        )

    st.markdown("### Pollutant-Wise Averages (Unimputed)")
    p_cols = st.columns(6)
    for col, key in zip(p_cols, POLLUTANT_KEYS):
        avg_val = summary.pollutant_averages.get(key)
        with col:
            render_metric_card(
                label=key.upper(),
                value=f"{avg_val:g}" if avg_val is not None else "N/A",
                meta="Mean reported value",
                is_placeholder=False,
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
            labels={
                "observation_time": "Observation Time",
                "effective_aqi": "Calculated AQI (CPCB)",
                "station_name": "Station",
            },
        )
        fig_ts.update_layout(height=320, margin={"l": 40, "r": 20, "t": 20, "b": 40})
        st.plotly_chart(fig_ts, width="stretch", key="hist_aqi_timeseries_chart")

    # 2. Pollutant Trends & 3. Severity Distribution
    c_left, c_right = st.columns([1.6, 1])
    with c_left:
        with st.container(border=True):
            st.markdown("**Pollutant Trends**")
            fig_pol = go.Figure()
            for key in POLLUTANT_KEYS:
                if key in summary.timeseries_df.columns and summary.timeseries_df[key].notna().any():
                    fig_pol.add_trace(
                        go.Scatter(
                            x=summary.timeseries_df["observation_time"],
                            y=summary.timeseries_df[key],
                            mode="lines+markers",
                            name=key.upper(),
                        )
                    )
            fig_pol.update_layout(
                height=310,
                margin={"l": 40, "r": 20, "t": 20, "b": 40},
                xaxis={"title": "Observation Time"},
                yaxis={"title": "Measured Value"},
            )
            st.plotly_chart(fig_pol, width="stretch", key="hist_pollutant_trends_chart")

    with c_right:
        with st.container(border=True):
            st.markdown("**Severity Distribution**")
            if summary.severity_distribution:
                sev_labels = list(summary.severity_distribution.keys())
                sev_counts = list(summary.severity_distribution.values())
                fig_sev = go.Figure(
                    go.Bar(x=sev_labels, y=sev_counts, marker_color="#0284C7")
                )
                fig_sev.update_layout(
                    height=310,
                    margin={"l": 40, "r": 20, "t": 20, "b": 40},
                    xaxis={"title": "Category"},
                    yaxis={"title": "Observation Count"},
                )
                st.plotly_chart(fig_sev, width="stretch", key="hist_severity_dist_chart")
            else:
                st.caption("No severity categories available.")

    # 4. Daily & 5. Weekly Comparisons
    d_col, w_col = st.columns(2)
    with d_col:
        with st.container(border=True):
            st.markdown("**Daily Comparison (Average vs. Max AQI)**")
            if not summary.daily_df.empty:
                fig_daily = go.Figure()
                fig_daily.add_trace(
                    go.Bar(x=summary.daily_df["Date"], y=summary.daily_df["Average AQI"], name="Avg AQI")
                )
                fig_daily.add_trace(
                    go.Bar(x=summary.daily_df["Date"], y=summary.daily_df["Max AQI"], name="Max AQI")
                )
                fig_daily.update_layout(
                    barmode="group",
                    height=290,
                    margin={"l": 40, "r": 20, "t": 20, "b": 40},
                    xaxis={"title": "Date"},
                    yaxis={"title": "AQI"},
                )
                st.plotly_chart(fig_daily, width="stretch", key="hist_daily_comparison_chart")
                st.dataframe(summary.daily_df, width="stretch", hide_index=True)

    with w_col:
        with st.container(border=True):
            st.markdown("**Weekly Comparison (Average vs. Max AQI)**")
            if not summary.weekly_df.empty:
                fig_weekly = go.Figure()
                fig_weekly.add_trace(
                    go.Bar(x=summary.weekly_df["Week"], y=summary.weekly_df["Average AQI"], name="Avg AQI")
                )
                fig_weekly.add_trace(
                    go.Bar(x=summary.weekly_df["Week"], y=summary.weekly_df["Max AQI"], name="Max AQI")
                )
                fig_weekly.update_layout(
                    barmode="group",
                    height=290,
                    margin={"l": 40, "r": 20, "t": 20, "b": 40},
                    xaxis={"title": "ISO Week"},
                    yaxis={"title": "AQI"},
                )
                st.plotly_chart(fig_weekly, width="stretch", key="hist_weekly_comparison_chart")
                st.dataframe(summary.weekly_df, width="stretch", hide_index=True)

    render_info_panel(
        title="Stored Observations Log",
        body=f"Showing {summary.observation_count} deduplicated observation(s) from SQLite.",
        is_placeholder=False,
    )


main()