import html
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.database import get_latest_observations_per_station
from src.utils import render_warning_banner


def _inject_geographic_theme() -> None:
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

        /* Green labels & controls */
        [data-testid="stSlider"] label,
        [data-testid="stSlider"] label p,
        [data-testid="stRadio"] label,
        [data-testid="stRadio"] label p,
        [data-testid="stCheckbox"] label,
        [data-testid="stCheckbox"] label p {
            color: #1B5E3F !important;
            font-weight: 600 !important;
            font-size: 0.86rem !important;
        }
        [data-testid="stSlider"] [data-testid="stThumbValue"] {
            color: #133A2A !important;
            font-weight: 700 !important;
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

        /* Legend Strip & Info Panel */
        .geo-legend-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 0.35rem 0 0.75rem 0;
        }
        .geo-legend-pill {
            background: #FFFFFF;
            border: 1px solid #DCE8E0;
            border-radius: 999px;
            padding: 3px 11px;
            font-size: 0.75rem;
            font-weight: 600;
            color: #16261E;
        }
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


def _aqi_marker_color(aqi_val: float | int | None) -> str:
    if aqi_val is None or pd.isna(aqi_val):
        return "#64748B"
    v = float(aqi_val)
    if v <= 50:
        return "#22A06B"
    if v <= 100:
        return "#65A30D"
    if v <= 200:
        return "#D97706"
    if v <= 300:
        return "#EA580C"
    if v <= 400:
        return "#DC2626"
    return "#7E22CE"


def main() -> None:
    _inject_geographic_theme()

    st.markdown(
        """
        <div class="eco-topbar">
            <div>
                <div class="eco-breadcrumb">EcoHealth &nbsp;/&nbsp; <strong>Geographic Monitoring</strong></div>
                <div class="eco-sub">Spatial station view using actual coordinates, AQI markers, station comparison, and hotspot screening.</div>
            </div>
            <div class="eco-pill">
                <span class="eco-dot"></span>Spatial Network
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    latest_obs = get_latest_observations_per_station()
    if not latest_obs:
        render_warning_banner(
            "No stored station observations found. Fetch readings on 'Live AQI Monitoring' to populate geographic markers.",
            is_placeholder=False,
        )
        return

    geo_rows: list[dict[str, object]] = []
    missing_coords: list[str] = []

    for obs in latest_obs:
        st_name = str(obs.get("station_name") or obs.get("query_city") or "Unknown")
        lat = obs.get("latitude")
        lon = obs.get("longitude")
        aqi_calc = obs.get("calculated_aqi")
        aqi_waqi = obs.get("waqi_reported_aqi")
        eff_aqi = aqi_calc if aqi_calc is not None else aqi_waqi

        if lat is None or lon is None:
            missing_coords.append(st_name)
            continue

        geo_rows.append(
            {
                "Station": st_name,
                "City Query": str(obs.get("query_city") or ""),
                "Latitude": float(lat),
                "Longitude": float(lon),
                "Calculated AQI": eff_aqi,
                "WAQI AQI": aqi_waqi,
                "Severity": str(obs.get("aqi_category") or "Unavailable"),
                "Observation Time": str(obs.get("observation_time") or "Missing"),
            }
        )

    if missing_coords:
        render_warning_banner(
            "Stations excluded from map due to missing coordinates (not invented): "
            + ", ".join(missing_coords),
            is_placeholder=False,
        )

    if not geo_rows:
        render_warning_banner("None of the stored stations have valid latitude/longitude coordinates.", is_placeholder=False)
        return

    df_geo = pd.DataFrame(geo_rows)
    valid_aqi_df = df_geo.dropna(subset=["Calculated AQI"]).copy()

    ctrl_l, ctrl_r = st.columns([2.2, 1.2])
    with ctrl_l:
        hotspot_threshold = st.slider(
            "Potential Hotspot AQI Threshold",
            min_value=50,
            max_value=400,
            value=150,
            step=10,
            key="geo_hotspot_threshold",
        )
    with ctrl_r:
        view_filter = st.radio(
            "Map & Table Scope",
            options=["All Mapped Stations", "Hotspots Only"],
            index=0,
            horizontal=True,
            key="geo_scope_filter",
        )

    df_geo["Is Hotspot"] = df_geo["Calculated AQI"].apply(
        lambda v: "Yes" if (v is not None and pd.notna(v) and float(v) >= hotspot_threshold) else "No"
    )
    hotspots = df_geo[df_geo["Is Hotspot"] == "Yes"]["Station"].tolist()

    display_df = df_geo[df_geo["Is Hotspot"] == "Yes"].copy() if view_filter == "Hotspots Only" else df_geo.copy()

    peak_val = int(pd.to_numeric(valid_aqi_df["Calculated AQI"]).max()) if not valid_aqi_df.empty else None
    peak_st = (
        str(valid_aqi_df.loc[pd.to_numeric(valid_aqi_df["Calculated AQI"]).idxmax(), "Station"])
        if not valid_aqi_df.empty
        else "N/A"
    )
    hotspot_sub = (
        f"AQI >= {hotspot_threshold}: {', '.join(hotspots[:2])}" + (f" (+{len(hotspots) - 2} more)" if len(hotspots) > 2 else "")
        if hotspots
        else f"No stations >= {hotspot_threshold}"
    )

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #133A2A;">
                <div class="eco-card-label">Mapped Stations</div>
                <div class="eco-card-value">{len(df_geo)}</div>
                <div class="eco-card-sub">Stations with valid coordinates</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #DC2626;">
                <div class="eco-card-label">Highest Station AQI</div>
                <div class="eco-card-value" style="color:#DC2626;">{html.escape(str(peak_val) if peak_val is not None else "N/A")}</div>
                <div class="eco-card-sub">{html.escape(peak_st)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #EA580C;">
                <div class="eco-card-label">Potential Hotspots</div>
                <div class="eco-card-value" style="color:#EA580C;">{len(hotspots)}</div>
                <div class="eco-card-sub">{html.escape(hotspot_sub)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        map_head_l, map_head_r = st.columns([2.2, 1.0])
        with map_head_l:
            st.markdown("**Station Coordinates & AQI Markers**")
        with map_head_r:
            show_labels = st.checkbox("Show station labels on map", value=False, key="geo_show_labels")

        st.markdown(
            """
            <div class="geo-legend-strip">
                <span class="geo-legend-pill"><span style="color:#22A06B;">&#9679;</span> Good (&le;50)</span>
                <span class="geo-legend-pill"><span style="color:#65A30D;">&#9679;</span> Satisfactory (51&ndash;100)</span>
                <span class="geo-legend-pill"><span style="color:#D97706;">&#9679;</span> Moderate (101&ndash;200)</span>
                <span class="geo-legend-pill"><span style="color:#EA580C;">&#9679;</span> Poor (201&ndash;300)</span>
                <span class="geo-legend-pill"><span style="color:#DC2626;">&#9679;</span> Very Poor (301&ndash;400)</span>
                <span class="geo-legend-pill"><span style="color:#7E22CE;">&#9679;</span> Severe (&gt;400)</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if display_df.empty:
            st.info(f"No stations currently exceed the hotspot threshold of {hotspot_threshold} AQI.")
        else:
            sizes = [
                max(13.0, min(28.0, float(v) / 14.0)) if v is not None and pd.notna(v) else 12.0
                for v in display_df["Calculated AQI"]
            ]
            marker_colors = [_aqi_marker_color(v) for v in display_df["Calculated AQI"]]
            short_labels = [str(s).split(",")[0] for s in display_df["Station"]]

            fig_map = go.Figure()

            # Subtle outer halo ring for stations meeting or exceeding the hotspot threshold
            hotspot_subset = display_df[display_df["Is Hotspot"] == "Yes"]
            if not hotspot_subset.empty:
                halo_sizes = [
                    max(22.0, min(38.0, float(v) / 14.0 + 10.0)) if v is not None and pd.notna(v) else 22.0
                    for v in hotspot_subset["Calculated AQI"]
                ]
                fig_map.add_trace(
                    go.Scattermap(
                        lat=hotspot_subset["Latitude"],
                        lon=hotspot_subset["Longitude"],
                        mode="markers",
                        hoverinfo="skip",
                        showlegend=False,
                        marker={
                            "size": halo_sizes,
                            "color": "rgba(220, 38, 38, 0.22)",
                        },
                    )
                )

            fig_map.add_trace(
                go.Scattermap(
                    lat=display_df["Latitude"],
                    lon=display_df["Longitude"],
                    mode="markers+text" if show_labels else "markers",
                    text=short_labels,
                    textposition="top center",
                    textfont={"size": 11, "color": "#133A2A"},
                    customdata=display_df[
                        ["Station", "Calculated AQI", "WAQI AQI", "Severity", "Observation Time", "Is Hotspot"]
                    ],
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Calculated AQI: %{customdata[1]} (%{customdata[3]})<br>"
                        "WAQI API AQI: %{customdata[2]}<br>"
                        "Hotspot: %{customdata[5]}<br>"
                        "Observed: %{customdata[4]}<extra></extra>"
                    ),
                    showlegend=False,
                    marker={
                        "size": sizes,
                        "color": marker_colors,
                    },
                )
            )

            fig_map.update_layout(
                height=420,
                margin={"l": 0, "r": 0, "t": 0, "b": 0},
                paper_bgcolor="rgba(0,0,0,0)",
                map={
                    "style": "carto-positron",
                    "center": {
                        "lat": float(display_df["Latitude"].mean()),
                        "lon": float(display_df["Longitude"].mean()),
                    },
                    "zoom": 9.8 if len(display_df) > 1 else 11.0,
                },
            )
            st.plotly_chart(fig_map, width="stretch", key="geo_station_map")

    st.markdown('<div class="eco-section-title">Station Coordinates & Comparison Table</div>', unsafe_allow_html=True)
    st.dataframe(display_df, width="stretch", hide_index=True)

    st.markdown(
        f"""
        <div class="eco-panel" style="border-left-color:#133A2A;">
            <div class="eco-panel-title">Hotspot Screening Note</div>
            <div class="eco-panel-body">
                Stations with AQI &ge; {hotspot_threshold} are highlighted as potential hotspots for closer review;
                high AQI at a single station reflects local/regional conditions at its reported observation time and does not prove wider area boundaries.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


main()