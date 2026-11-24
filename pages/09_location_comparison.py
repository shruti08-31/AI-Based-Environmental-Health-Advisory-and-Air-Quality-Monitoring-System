import html
import plotly.graph_objects as go
import streamlit as st

from src.analytics import compare_station_observations
from src.api import POLLUTANT_KEYS
from src.database import get_latest_observations_per_station
from src.utils import render_warning_banner


_POLLUTANT_BAR_COLORS: dict[str, str] = {
    "PM25": "#133A2A",
    "PM10": "#1F7A5A",
    "NO2": "#D97706",
    "SO2": "#2B6CB0",
    "CO": "#DC2626",
    "O3": "#4D7C0F",
}


def _inject_location_comp_theme() -> None:
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

        /* Green label & light-green multiselect box with crisp dark-green text */
        [data-testid="stMultiSelect"] label,
        [data-testid="stMultiSelect"] label p {
            color: #1B5E3F !important;
            font-weight: 600 !important;
            font-size: 0.88rem !important;
        }
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
            background-color: #EAF4EC !important;
            border-color: #B4D6BE !important;
            border-radius: 10px !important;
        }
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] span[data-baseweb="tag"] {
            background-color: #D4E9DA !important;
            color: #133A2A !important;
            border: 1px solid #A7CEB4 !important;
        }
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] span[data-baseweb="tag"] *,
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] input {
            color: #133A2A !important;
            -webkit-text-fill-color: #133A2A !important;
            opacity: 1 !important;
            font-weight: 600 !important;
        }
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] svg {
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
            padding: 16px 18px;
            box-shadow: 0 2px 8px rgba(19, 58, 42, 0.03);
            height: 100%;
        }
        .eco-card-label {
            font-size: 0.80rem;
            font-weight: 500;
            color: #5E7167;
            margin-bottom: 8px;
        }
        .eco-card-value {
            font-size: 1.7rem;
            font-weight: 700;
            color: #133A2A;
            line-height: 1.15;
            margin-bottom: 6px;
        }
        .eco-card-sub {
            font-size: 0.77rem;
            color: #6B7E74;
        }

        /* Section Title & Note Panel */
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
            line-height: 1.5;
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


def main() -> None:
    _inject_location_comp_theme()

    st.markdown(
        """
        <div class="eco-topbar">
            <div>
                <div class="eco-breadcrumb">EcoHealth &nbsp;/&nbsp; <strong>Location Comparison</strong></div>
                <div class="eco-sub">Compare AQI, pollutants, severity tiers, and observation timestamps across stored stations.</div>
            </div>
            <div class="eco-pill">
                <span class="eco-dot"></span>Multi-Station View
            </div>
        </div>
        """,
        unsafe_allow_html=True,
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

    highest_val_str = str(comp.highest_aqi_value) if comp.highest_aqi_value is not None else "N/A"
    lowest_val_str = str(comp.lowest_aqi_value) if comp.lowest_aqi_value is not None else "N/A"
    sev_meta = ", ".join(comp.available_severities) if comp.available_severities else "None"

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #133A2A;">
                <div class="eco-card-label">Stations Compared</div>
                <div class="eco-card-value">{comp.stations_compared}</div>
                <div class="eco-card-sub">Latest stored observation per station</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #DC2626;">
                <div class="eco-card-label">Highest Available AQI</div>
                <div class="eco-card-value" style="color:#DC2626;">{html.escape(highest_val_str)}</div>
                <div class="eco-card-sub">{html.escape(comp.highest_aqi_station or "No valid AQI")}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #1F7A5A;">
                <div class="eco-card-label">Lowest Available AQI</div>
                <div class="eco-card-value" style="color:#1F7A5A;">{html.escape(lowest_val_str)}</div>
                <div class="eco-card-sub">{html.escape(comp.lowest_aqi_station or "No valid AQI")}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #D97706;">
                <div class="eco-card-label">Severity Categories Present</div>
                <div class="eco-card-value">{len(comp.available_severities)}</div>
                <div class="eco-card-sub">{html.escape(sev_meta)}</div>
            </div>
            """,
            unsafe_allow_html=True,
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
                    marker_color="#133A2A",
                )
            )
            fig_aqi.add_trace(
                go.Bar(
                    x=comp.comparison_df["Station"],
                    y=comp.comparison_df["WAQI API AQI"],
                    name="WAQI API AQI",
                    marker_color="#D97706",
                )
            )
            _apply_eco_chart_layout(
                fig_aqi,
                height=310,
                x_title="Station",
                y_title="AQI",
                barmode="group",
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
                            marker_color=_POLLUTANT_BAR_COLORS.get(col_name, "#1F7A5A"),
                        )
                    )
            _apply_eco_chart_layout(
                fig_pol,
                height=310,
                x_title="Station",
                y_title="Reported Value",
                barmode="group",
            )
            st.plotly_chart(fig_pol, width="stretch", key="loc_comp_pollutant_bar")

    st.markdown('<div class="eco-section-title">Station Comparison Table (With Observation Timestamps)</div>', unsafe_allow_html=True)
    st.dataframe(comp.comparison_df, width="stretch", hide_index=True)

    st.markdown(
        """
        <div class="eco-panel" style="border-left-color:#133A2A;">
            <div class="eco-panel-title">Comparison Integrity Note</div>
            <div class="eco-panel-body">
                Every compared station displays its exact observation timestamp and freshness status.
                Do not treat readings with different observation timestamps as simultaneous snapshots.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


main()