import plotly.graph_objects as go
import streamlit as st

from src.analytics import compare_station_observations
from src.api import POLLUTANT_KEYS
from src.database import get_latest_observations_per_station
from src.utils import (
    render_info_panel,
    render_metric_card,
    render_page_header,
    render_warning_banner,
)


def main() -> None:
    render_page_header(
        title="Location Comparison",
        subtitle="Compare AQI, pollutants, severity tiers, and observation timestamps across stored stations.",
        is_placeholder=False,
    )

    latest_per_station = get_latest_observations_per_station()
    if not latest_per_station:
        render_warning_banner(
            "No stored station observations found in SQLite. Fetch readings for one or more cities on 'Live AQI Monitoring' first.",
            is_placeholder=False,
        )
        return

    all_station_names = [str(item["station_name"]) for item in latest_per_station]
    selected_stations = st.multiselect(
        "Select Stations / Cities to Compare",
        options=all_station_names,
        default=all_station_names,
        key="location_comparison_multiselect",
    )

    if not selected_stations:
        render_warning_banner("Select at least one station above to view comparison metrics.", is_placeholder=False)
        return

    comp = compare_station_observations(
        latest_observations=latest_per_station,
        selected_stations=selected_stations,
    )

    if comp.stations_compared < 2:
        render_warning_banner(
            "Only 1 station is currently selected or stored. Fetch additional cities/stations in 'Live AQI Monitoring' for multi-location comparison.",
            is_placeholder=False,
        )

    if comp.timestamp_warnings:
        with st.expander(
            f"Timestamp & Freshness Notices ({len(comp.timestamp_warnings)})",
            expanded=False,
        ):
            for warn in comp.timestamp_warnings:
                st.warning(f"Timestamp & Freshness Notice: {warn}")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_metric_card(
            label="Stations Compared",
            value=str(comp.stations_compared),
            meta="Latest stored observation per station",
            is_placeholder=False,
        )
    with m2:
        render_metric_card(
            label="Highest Available AQI",
            value=str(comp.highest_aqi_value) if comp.highest_aqi_value is not None else "N/A",
            meta=comp.highest_aqi_station or "No valid AQI",
            is_placeholder=False,
        )
    with m3:
        render_metric_card(
            label="Lowest Available AQI",
            value=str(comp.lowest_aqi_value) if comp.lowest_aqi_value is not None else "N/A",
            meta=comp.lowest_aqi_station or "No valid AQI",
            is_placeholder=False,
        )
    with m4:
        render_metric_card(
            label="Severity Categories Present",
            value=str(len(comp.available_severities)),
            meta=", ".join(comp.available_severities) if comp.available_severities else "None",
            is_placeholder=False,
        )

    c_left, c_right = st.columns(2)
    with c_left:
        with st.container(border=True):
            st.markdown("**AQI Comparison Across Locations (CPCB vs. WAQI)**")
            fig_aqi = go.Figure()
            fig_aqi.add_trace(
                go.Bar(
                    x=comp.comparison_df["Station"],
                    y=comp.comparison_df["Calculated AQI (CPCB)"],
                    name="Calculated AQI (CPCB)",
                )
            )
            fig_aqi.add_trace(
                go.Bar(
                    x=comp.comparison_df["Station"],
                    y=comp.comparison_df["WAQI API AQI"],
                    name="WAQI API AQI",
                )
            )
            fig_aqi.update_layout(
                barmode="group",
                height=310,
                margin={"l": 40, "r": 20, "t": 20, "b": 40},
                xaxis={"title": "Station"},
                yaxis={"title": "AQI"},
            )
            st.plotly_chart(fig_aqi, width="stretch", key="loc_comp_aqi_bar")

    with c_right:
        with st.container(border=True):
            st.markdown("**Pollutant Comparison Across Locations**")
            fig_pol = go.Figure()
            for key in POLLUTANT_KEYS:
                col_name = key.upper()
                if col_name in comp.comparison_df.columns and comp.comparison_df[col_name].notna().any():
                    fig_pol.add_trace(
                        go.Bar(
                            x=comp.comparison_df["Station"],
                            y=comp.comparison_df[col_name],
                            name=col_name,
                        )
                    )
            fig_pol.update_layout(
                barmode="group",
                height=310,
                margin={"l": 40, "r": 20, "t": 20, "b": 40},
                xaxis={"title": "Station"},
                yaxis={"title": "Reported Value"},
            )
            st.plotly_chart(fig_pol, width="stretch", key="loc_comp_pollutant_bar")

    st.markdown("### Station Comparison Table (With Observation Timestamps)")
    st.dataframe(comp.comparison_df, width="stretch", hide_index=True)

    render_info_panel(
        title="Comparison Integrity Note",
        body=(
            "Every compared station displays its exact observation timestamp and freshness status. "
            "Do not treat readings with different observation timestamps as simultaneous snapshots."
        ),
        is_placeholder=False,
    )


main()