from datetime import datetime, timezone
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import config
from src.alerts import evaluate_alert_candidates, persist_alerts
from src.api import POLLUTANT_KEYS, AqiReading, StationSearchResult, WaqiClient, WaqiClientError
from src.database import DatabaseError, get_observations, save_observation_bundle
from src.utils import (
    render_info_panel,
    render_metric_card,
    render_page_header,
    render_pollutant_card,
    render_warning_banner,
)
from src.validation import ValidationResult, validate_aqi_reading

# Verified WAQI Delhi station presets (used if live station search has not populated yet)
DELHI_PRESET_STATIONS: list[StationSearchResult] = [
    StationSearchResult(uid=None, station_name="Delhi (City-Wide Feed)", aqi_raw="Live", timestamp_str=None, latitude=28.6139, longitude=77.2090),
    StationSearchResult(uid=3715, station_name="ITO, Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.6289, longitude=77.2405),
    StationSearchResult(uid=7024, station_name="US Diplomatic Post: New Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.5981, longitude=77.1891),
    StationSearchResult(uid=2553, station_name="Anand Vihar, Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.6468, longitude=77.3160),
    StationSearchResult(uid=2554, station_name="Mandir Marg, Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.6364, longitude=77.2011),
    StationSearchResult(uid=2555, station_name="Punjabi Bagh, Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.6740, longitude=77.1310),
    StationSearchResult(uid=2556, station_name="R K Puram, Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.5633, longitude=77.1869),
    StationSearchResult(uid=10112, station_name="Dwarka-Sector 8, Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.5710, longitude=77.0719),
    StationSearchResult(uid=10118, station_name="Rohini, Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.7325, longitude=77.1199),
]


def _classify_severity_label(aqi_val: float | int | None) -> str:
    if aqi_val is None:
        return "Pending"
    if aqi_val <= 50:
        return "Good"
    if aqi_val <= 100:
        return "Moderate"
    if aqi_val <= 150:
        return "Sensitive"
    if aqi_val <= 200:
        return "Unhealthy"
    return "Severe"


@st.cache_data(ttl=300, show_spinner=False)
def _cached_search_cities(keyword: str, token_fingerprint: str) -> list[StationSearchResult]:
    client = WaqiClient(app_config=config)
    return client.search_cities(keyword)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_fetch_city_aqi(target: str, token_fingerprint: str) -> tuple[AqiReading, str]:
    client = WaqiClient(app_config=config)
    reading = client.get_city_aqi(target)
    fetched_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return reading, fetched_utc


def _render_pollutant_chart(pollutants: dict[str, float | None], station_label: str) -> None:
    rows = [
        {"Pollutant": key.upper(), "Value": pollutants.get(key)}
        for key in POLLUTANT_KEYS
        if pollutants.get(key) is not None
    ]
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    st.markdown(f"**Reported Pollutant Measurements — {station_label}**")
    if not rows:
        st.caption("No numeric pollutant measurements were returned in this payload.")
    else:
        df = pd.DataFrame(rows)
        fig = go.Figure(
            go.Bar(
                x=df["Pollutant"],
                y=df["Value"],
                marker_color="#0284C7",
            )
        )
        fig.update_layout(
            height=280,
            margin={"l": 40, "r": 20, "t": 20, "b": 40},
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#F8FAFC",
            xaxis={"title": "Pollutant"},
            yaxis={"title": "Reported Value (IAQI / Raw)"},
        )
        st.plotly_chart(fig, width="stretch", key="live_pollutant_bar_chart")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_reading_view(
    reading: AqiReading,
    validation: ValidationResult,
    fetched_utc: str,
    from_cache: bool,
) -> None:
    severity = _classify_severity_label(reading.aqi)
    aqi_display = str(reading.aqi) if reading.aqi is not None else "Unavailable"
    station_display = reading.station_name or "Station Name Unavailable"
    coord_display = (
        f"{reading.latitude:.4f}, {reading.longitude:.4f}"
        if reading.latitude is not None and reading.longitude is not None
        else "Coordinates Missing"
    )
    obs_display = reading.observation_time or "Timestamp Missing"
    cache_note = (
        f"Cached response (TTL 300s) • Retrieved at {fetched_utc}"
        if from_cache
        else f"Freshly retrieved at {fetched_utc}"
    )

    if from_cache:
        render_warning_banner(
            f"Displaying cached WAQI response retrieved at {fetched_utc}. Click 'Force Refresh' to query WAQI again.",
            is_placeholder=False,
        )

    persist_status = st.session_state.get("last_persisted_status")
    if persist_status:
        st.caption(persist_status)

    for err in validation.errors:
        st.error(f"Validation Error: {err}")
    for warn in validation.warnings:
        st.warning(f"Data Quality Warning: {warn}")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card(
            label="Reported AQI",
            value=aqi_display,
            meta=f"Severity Band: {severity}",
            is_placeholder=False,
        )
    with c2:
        render_metric_card(
            label="Dominant Pollutant",
            value=(reading.dominant_pollutant or "Not Reported").upper(),
            meta=f"Completeness: {int(validation.completeness_ratio * 100)}% of 6 pollutants",
            is_placeholder=False,
        )
    with c3:
        render_metric_card(
            label="Observation Timestamp",
            value=obs_display,
            meta=cache_note,
            is_placeholder=False,
        )
    with c4:
        render_metric_card(
            label="Station Coordinates",
            value=coord_display,
            meta=station_display,
            is_placeholder=False,
        )

    st.markdown("### Pollutant Breakdown (Unimputed)")
    for idx in range(0, len(POLLUTANT_KEYS), 3):
        cols = st.columns(3)
        for col, p_key in zip(cols, POLLUTANT_KEYS[idx : idx + 3]):
            val = reading.pollutants.get(p_key)
            with col:
                render_pollutant_card(
                    pollutant_name=p_key.upper(),
                    concentration_label=f"{val:g}" if val is not None else "Missing (Not Available)",
                    standard_ref="WAQI iaqi feed value" if val is not None else "Absent in API response",
                    is_placeholder=False,
                )

    _render_pollutant_chart(reading.pollutants, station_display)

    render_info_panel(
        title="Station & Telemetry Metadata",
        body=(
            f"<b>Station:</b> {station_display}<br>"
            f"<b>Query Target:</b> {reading.query}<br>"
            f"<b>Coordinates:</b> {coord_display}<br>"
            f"<b>Observation Time:</b> {obs_display}<br>"
            f"<b>Validation Status:</b> {'Passed' if validation.is_valid else 'Issues Detected'}"
        ),
        is_placeholder=False,
    )


def main() -> None:
    default_city = st.session_state.get("selected_location", config.default_location)

    render_page_header(
        title="Live AQI Monitoring",
        subtitle="Select a monitoring station in Delhi or search any city, fetch live WAQI telemetry, and inspect data quality.",
        is_placeholder=False,
    )

    if not config.has_api_token:
        render_warning_banner(
            "WAQI_API_TOKEN is not configured in .env. Set a valid token to fetch live WAQI data.",
            is_placeholder=False,
        )

    token_fp = (config.waqi_api_token or "")[:6]

    # Auto-load live Delhi stations once per session so the dropdown is ready immediately
    if "waqi_search_matches" not in st.session_state and config.has_api_token:
        try:
            st.session_state["waqi_search_matches"] = _cached_search_cities("Delhi", token_fp)
        except WaqiClientError:
            st.session_state["waqi_search_matches"] = list(DELHI_PRESET_STATIONS)
    elif "waqi_search_matches" not in st.session_state:
        st.session_state["waqi_search_matches"] = list(DELHI_PRESET_STATIONS)

    input_col, search_btn_col, fetch_btn_col, refresh_btn_col = st.columns([2.5, 1.1, 1.1, 1.1])
    with input_col:
        city_input = st.text_input(
            "City or Station Search Keyword",
            value=default_city,
            key="live_aqi_city_input",
        )
    with search_btn_col:
        st.write("")
        search_clicked = st.button("Search Stations", width="stretch", key="btn_search_stations")
    with fetch_btn_col:
        st.write("")
        fetch_clicked = st.button("Fetch Live AQI", width="stretch", key="btn_fetch_live_aqi")
    with refresh_btn_col:
        st.write("")
        refresh_clicked = st.button("Force Refresh", width="stretch", key="btn_force_refresh_aqi")

    cleaned_city = (city_input or "").strip()
    if cleaned_city:
        st.session_state["selected_location"] = cleaned_city

    if search_clicked:
        try:
            matches = _cached_search_cities(cleaned_city, token_fp)
            st.session_state["waqi_search_matches"] = matches
        except WaqiClientError as exc:
            st.error(f"Station search failed ({exc.kind.value}): {exc.message}")

    matches: list[StationSearchResult] = st.session_state.get("waqi_search_matches", list(DELHI_PRESET_STATIONS))
    selected_feed_target = cleaned_city

    if matches:
        option_labels = [
            f"{m.station_name} (Reported AQI: {m.aqi_raw})"
            if m.uid is None
            else f"{m.station_name} — Station ID @{m.uid} (Reported AQI: {m.aqi_raw})"
            for m in matches
        ]
        chosen_idx = st.selectbox(
            "Select Place / Monitoring Station in Delhi (or Search Results)",
            options=list(range(len(option_labels))),
            format_func=lambda i: option_labels[i],
            key="waqi_station_choice",
        )
        chosen = matches[chosen_idx]
        if chosen.uid is not None:
            selected_feed_target = f"@{chosen.uid}"
        elif "City-Wide" in chosen.station_name:
            selected_feed_target = "Delhi"
        else:
            selected_feed_target = chosen.station_name

    if refresh_clicked:
        _cached_fetch_city_aqi.clear()
        fetch_clicked = True

    if fetch_clicked:
        try:
            reading, fetched_utc = _cached_fetch_city_aqi(selected_feed_target, token_fp)
            st.session_state["waqi_last_reading"] = reading
            st.session_state["waqi_last_fetched_utc"] = fetched_utc
            st.session_state["waqi_last_was_cached"] = False

            persist_key = f"{reading.station_name or reading.query}::{reading.observation_time}"
            persisted_keys: set[str] = st.session_state.setdefault("persisted_obs_keys", set())
            if persist_key not in persisted_keys:
                try:
                    obs_id, was_inserted = save_observation_bundle(reading)
                    persisted_keys.add(persist_key)
                    if was_inserted:
                        prior_obs = get_observations(
                            location=reading.station_name or reading.query,
                            limit=50,
                        )
                        alert_cands = evaluate_alert_candidates(
                            reading=reading,
                            previous_observations=prior_obs[:-1] if len(prior_obs) > 1 else [],
                        )
                        persist_alerts(alert_cands, query_city=reading.query)
                    st.session_state["last_persisted_status"] = (
                        f"Saved new observation #{obs_id} to SQLite."
                        if was_inserted
                        else f"Observation already stored in SQLite (record #{obs_id}); duplicate skipped."
                    )
                except DatabaseError as db_exc:
                    st.error(f"Database persistence error: {db_exc.message}")
        except WaqiClientError as exc:
            st.error(f"Live AQI fetch failed ({exc.kind.value}): {exc.message}")

    last_reading: AqiReading | None = st.session_state.get("waqi_last_reading")
    last_fetched_utc: str | None = st.session_state.get("waqi_last_fetched_utc")

    if last_reading is not None and last_fetched_utc is not None:
        validation = validate_aqi_reading(last_reading)
        was_cached = bool(st.session_state.get("waqi_last_was_cached", False))
        _render_reading_view(last_reading, validation, last_fetched_utc, from_cache=was_cached)
        st.session_state["waqi_last_was_cached"] = True
    else:
        render_info_panel(
            title="Ready to Query WAQI",
            body="Select a monitoring station above and click 'Fetch Live AQI' or search any city keyword.",
            is_placeholder=False,
        )


main()