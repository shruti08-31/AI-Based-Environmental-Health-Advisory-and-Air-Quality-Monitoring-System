import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.database import get_latest_observations_per_station
from src.utils import (
    render_info_panel,
    render_metric_card,
    render_page_header,
    render_warning_banner,
)


def main() -> None:
    render_page_header(
        title="Geographic Monitoring",
        subtitle="Spatial station view using actual coordinates, AQI markers, station comparison, and hotspot screening.",
        is_placeholder=False,
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
    hotspot_threshold = st.slider(
        "Potential Hotspot AQI Threshold",
        min_value=50,
        max_value=400,
        value=150,
        step=10,
        key="geo_hotspot_threshold",
    )

    hotspots = (
        valid_aqi_df[pd.to_numeric(valid_aqi_df["Calculated AQI"]) >= hotspot_threshold]["Station"].tolist()
        if not valid_aqi_df.empty
        else []
    )

    m1, m2, m3 = st.columns(3)
    with m1:
        render_metric_card("Mapped Stations", str(len(df_geo)), "Stations with valid coordinates", is_placeholder=False)
    with m2:
        peak_val = int(pd.to_numeric(valid_aqi_df["Calculated AQI"]).max()) if not valid_aqi_df.empty else None
        peak_st = (
            str(valid_aqi_df.loc[pd.to_numeric(valid_aqi_df["Calculated AQI"]).idxmax(), "Station"])
            if not valid_aqi_df.empty
            else "N/A"
        )
        render_metric_card("Highest Station AQI", str(peak_val) if peak_val is not None else "N/A", peak_st, is_placeholder=False)
    with m3:
        render_metric_card(
            "Potential Hotspots",
            str(len(hotspots)),
            f"AQI >= {hotspot_threshold}" + (f": {', '.join(hotspots[:2])}" if hotspots else ""),
            is_placeholder=False,
        )

    with st.container(border=True):
        st.markdown("**Station Coordinates & AQI Markers**")
        sizes = [
            max(12.0, min(32.0, float(v) / 8.0)) if v is not None and pd.notna(v) else 12.0
            for v in df_geo["Calculated AQI"]
        ]
        fig_map = go.Figure(
            go.Scattergeo(
                lat=df_geo["Latitude"],
                lon=df_geo["Longitude"],
                text=[
                    f"{r['Station']}<br>AQI: {r['Calculated AQI']} ({r['Severity']})<br>Time: {r['Observation Time']}"
                    for _, r in df_geo.iterrows()
                ],
                mode="markers+text",
                textposition="top center",
                marker={
                    "size": sizes,
                    "color": pd.to_numeric(df_geo["Calculated AQI"], errors="coerce"),
                    "colorscale": "OrRd",
                    "colorbar": {"title": "AQI"},
                    "line": {"width": 1, "color": "#0F172A"},
                },
            )
        )
        fig_map.update_geos(
            scope="asia",
            center={"lat": float(df_geo["Latitude"].mean()), "lon": float(df_geo["Longitude"].mean())},
            projection_scale=6,
            showland=True,
            landcolor="#F1F5F9",
            showcountries=True,
            countrycolor="#94A3B8",
        )
        fig_map.update_layout(height=380, margin={"l": 10, "r": 10, "t": 15, "b": 10})
        st.plotly_chart(fig_map, width="stretch", key="geo_station_map")

    st.markdown("### Station Coordinates & Comparison Table")
    st.dataframe(df_geo, width="stretch", hide_index=True)

    render_info_panel(
        title="Hotspot Screening Note",
        body=(
            f"Stations with AQI >= {hotspot_threshold} are highlighted as potential hotspots for closer review; "
            "high AQI at a single station reflects local/regional conditions at its reported observation time and does not prove wider area boundaries."
        ),
        is_placeholder=False,
    )


main()