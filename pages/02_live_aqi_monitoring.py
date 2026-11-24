from datetime import datetime, timezone
import time
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
    StationSearchResult(uid=3715, station_name="ITO, Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.6289, longitude=77.2405),
    StationSearchResult(uid=7024, station_name="US Diplomatic Post: New Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.5981, longitude=77.1891),
    StationSearchResult(uid=2553, station_name="Anand Vihar, Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.6468, longitude=77.3160),
    StationSearchResult(uid=2554, station_name="Mandir Marg, Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.6364, longitude=77.2011),
    StationSearchResult(uid=2555, station_name="Punjabi Bagh, Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.6740, longitude=77.1310),
    StationSearchResult(uid=2556, station_name="R K Puram, Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.5633, longitude=77.1869),
    StationSearchResult(uid=10112, station_name="Dwarka-Sector 8, Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.5710, longitude=77.0719),
    StationSearchResult(uid=10118, station_name="Rohini, Delhi, India", aqi_raw="Live", timestamp_str=None, latitude=28.7325, longitude=77.1199),
    StationSearchResult(uid=None, station_name="Delhi (City-Wide Feed)", aqi_raw="Live", timestamp_str=None, latitude=28.6139, longitude=77.2090),
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

    for err in validation.errors:
        st.error(f"Validation Error: {err}")

    c1, c2, c3 = st.columns(3)
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

    with st.container(border=True):
        st.markdown("#### Station & Telemetry Metadata")
        validation_badge = "Passed" if validation.is_valid else "Issues Detected"
        st.markdown(
            f"""
| Field | Details |
| :--- | :--- |
| **Station** | {station_display} |
| **Query Target** | `{reading.query}` |
| **Coordinates** | {coord_display} |
| **Observation Time** | {obs_display} |
| **Validation Status** | {validation_badge} |
            """.strip()
        )

    persist_status = st.session_state.get("last_persisted_status")
    with st.expander("Persistence & Data Quality Diagnostics", expanded=False):
        if from_cache:
            st.caption(
                f"Displaying session WAQI response retrieved at {fetched_utc}. Click 'Fetch Live AQI' or 'Force Refresh' to query WAQI again."
            )
        if persist_status:
            st.info(persist_status)
        if validation.warnings:
            for warn in validation.warnings:
                st.warning(f"Data Quality Warning: {warn}")
        elif not persist_status and not from_cache:
            st.caption("No persistence or data quality warnings.")


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
            _cached_search_cities.clear()
            matches_found = _cached_search_cities(cleaned_city, token_fp)
            st.session_state["waqi_search_matches"] = matches_found
        except WaqiClientError as exc:
            st.error(f"Station search failed ({exc.kind.value}): {exc.message}")

    # Sort matches so active stations reporting a live numeric AQI appear first
    matches = sorted(
        st.session_state.get("waqi_search_matches", list(DELHI_PRESET_STATIONS)),
        key=lambda m: (0 if str(m.aqi_raw).isdigit() else 1, m.station_name),
    )
    selected_feed_target = cleaned_city

    if matches:
        option_labels = [m.station_name for m in matches]
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

    auto_live = st.toggle("Enable Live Auto-Refresh (every 2 hours)", value=False, key="live_auto_refresh_toggle")

    explicit_refresh = fetch_clicked or refresh_clicked or auto_live
    initial_load = "waqi_last_reading" not in st.session_state and config.has_api_token

    if explicit_refresh or initial_load:
        with st.spinner(f"Fetching current live telemetry for {selected_feed_target} from WAQI..."):
            try:
                client = WaqiClient(app_config=config)
                reading = client.get_city_aqi(selected_feed_target)
                fetched_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

                st.session_state["waqi_last_reading"] = reading
                st.session_state["waqi_last_fetched_utc"] = fetched_utc
                st.session_state["waqi_last_fetched_at"] = fetched_utc
                st.session_state["waqi_last_was_cached"] = False

                try:
                    obs_id, was_inserted = save_observation_bundle(reading)
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
                            f"Saved new live observation #{obs_id} to SQLite."
                        )
                    else:
                        st.session_state["last_persisted_status"] = (
                            f"Live API checked; station observation #{obs_id} is already up to date in SQLite."
                        )
                except DatabaseError as db_exc:
                    st.error(f"Database persistence error: {db_exc.message}")

                if explicit_refresh:
                    st.toast(f"Updated live AQI for {reading.station_name or selected_feed_target}")
            except WaqiClientError as exc:
                st.error(f"WAQI fetch failed ({exc.kind.value}): {exc.message}")

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

    if auto_live:
        time.sleep(7200)
        st.rerun()


main()