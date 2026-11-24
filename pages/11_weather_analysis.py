import streamlit as st
from config import config
from src.api import AqiReading
from src.api.weather_client import WeatherClient, WeatherClientError, analyze_weather_pollution_context
from src.core import evaluate_aqi_from_reading
from src.utils import (
    render_info_panel,
    render_metric_card,
    render_page_header,
    render_warning_banner,
)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_weather_cached(lat: float, lon: float):
    client = WeatherClient(app_config=config)
    return client.get_current_weather(lat, lon)


def main() -> None:
    render_page_header(
        title="Weather Analysis",
        subtitle="Meteorological variables alongside AQI and non-causal dispersion/weather context.",
        is_placeholder=False,
    )

    reading: AqiReading | None = st.session_state.get("waqi_last_reading")

    c_lat, c_lon, c_btn = st.columns([1.5, 1.5, 1])
    with c_lat:
        lat_val = st.number_input(
            "Latitude",
            min_value=-90.0,
            max_value=90.0,
            value=float(reading.latitude) if reading and reading.latitude is not None else 28.6139,
            format="%.4f",
            key="weather_lat_input",
        )
    with c_lon:
        lon_val = st.number_input(
            "Longitude",
            min_value=-180.0,
            max_value=180.0,
            value=float(reading.longitude) if reading and reading.longitude is not None else 77.2090,
            format="%.4f",
            key="weather_lon_input",
        )
    with c_btn:
        st.write("")
        fetch_weather = st.button("Fetch Weather", width="stretch", key="btn_fetch_weather")

    if fetch_weather or "last_weather_obs" not in st.session_state:
        try:
            w_obs = _fetch_weather_cached(float(lat_val), float(lon_val))
            st.session_state["last_weather_obs"] = w_obs
            st.session_state.pop("last_weather_error", None)
        except WeatherClientError as w_exc:
            st.session_state["last_weather_error"] = f"Weather service error ({w_exc.kind.value}): {w_exc.message}"

    if "last_weather_error" in st.session_state:
        render_warning_banner(
            st.session_state["last_weather_error"] + " (WAQI telemetry state is unaffected.)",
            is_placeholder=False,
        )
        return

    w_obs = st.session_state.get("last_weather_obs")
    if w_obs is None:
        return

    if w_obs.missing_fields:
        render_warning_banner(
            "Some weather fields were missing or unavailable: " + ", ".join(w_obs.missing_fields),
            is_placeholder=False,
        )

    aqi_val: int | float | None = None
    aqi_label = "No AQI loaded"
    if reading is not None:
        eng = evaluate_aqi_from_reading(reading)
        aqi_val = eng.calculated_aqi if eng.calculated_aqi is not None else reading.aqi
        aqi_label = f"{reading.station_name or reading.query} • CPCB: {eng.calculated_aqi} ({eng.category}) / WAQI: {reading.aqi}"

    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        render_metric_card(
            "Temperature",
            f"{w_obs.temperature_c:g} °C" if w_obs.temperature_c is not None else "Missing",
            f"Weather time: {w_obs.observation_time or 'N/A'}",
            is_placeholder=False,
        )
    with r1c2:
        render_metric_card(
            "Relative Humidity",
            f"{w_obs.humidity_pct:g} %" if w_obs.humidity_pct is not None else "Missing",
            f"Fetched: {w_obs.fetched_at_utc}",
            is_placeholder=False,
        )
    with r1c3:
        render_metric_card(
            "Associated AQI Reference",
            str(aqi_val) if aqi_val is not None else "Pending",
            aqi_label,
            is_placeholder=reading is None,
        )

    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1:
        render_metric_card(
            "Wind Speed",
            f"{w_obs.wind_speed_kmh:g} km/h" if w_obs.wind_speed_kmh is not None else "Missing",
            "10m wind speed",
            is_placeholder=False,
        )
    with r2c2:
        render_metric_card(
            "Wind Direction",
            f"{w_obs.wind_direction_deg:g}°" if w_obs.wind_direction_deg is not None else "Missing",
            "10m wind direction",
            is_placeholder=False,
        )
    with r2c3:
        render_metric_card(
            "Rainfall & Pressure",
            f"{w_obs.rain_mm:g} mm | {w_obs.surface_pressure_hpa:g} hPa"
            if w_obs.rain_mm is not None and w_obs.surface_pressure_hpa is not None
            else f"Rain: {w_obs.rain_mm if w_obs.rain_mm is not None else 'N/A'} | Pressure: {w_obs.surface_pressure_hpa if w_obs.surface_pressure_hpa is not None else 'N/A'}",
            "Rain (mm) and Surface Pressure (hPa)",
            is_placeholder=False,
        )

    st.markdown("### Weather & Pollution Context (Non-Causal Notes)")
    notes = analyze_weather_pollution_context(w_obs, aqi_value=aqi_val)
    for n in notes:
        render_info_panel(
            title=f"{n.factor} — {n.observed_summary}",
            body=f"{n.possible_relationship}<br><i>Note: {n.caution}</i>",
            is_placeholder=False,
        )


main()