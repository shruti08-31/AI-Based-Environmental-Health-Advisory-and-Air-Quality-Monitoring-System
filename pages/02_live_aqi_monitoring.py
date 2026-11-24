from datetime import datetime, timezone
import html
import time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import config
from src.alerts import evaluate_alert_candidates, persist_alerts
from src.api import POLLUTANT_KEYS, AqiReading, StationSearchResult, WaqiClient, WaqiClientError
from src.database import get_observations, save_observation_bundle
from src.utils import render_warning_banner
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


def _inject_live_page_theme() -> None:
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

        /* Green labels for text input & selectbox */
        [data-testid="stTextInput"] label,
        [data-testid="stTextInput"] label p,
        [data-testid="stSelectbox"] label,
        [data-testid="stSelectbox"] label p {
            color: #1B5E3F !important;
            font-weight: 600 !important;
            font-size: 0.88rem !important;
        }

        /* Light green input & selectbox containers + dark green text */
        [data-testid="stTextInput"] input,
        [data-testid="stTextInput"] > div > div {
            background-color: #EAF4EC !important;
            color: #133A2A !important;
            -webkit-text-fill-color: #133A2A !important;
            font-weight: 600 !important;
            border-color: #B4D6BE !important;
            border-radius: 10px !important;
        }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            background-color: #EAF4EC !important;
            border-color: #B4D6BE !important;
            border-radius: 10px !important;
        }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div > div,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] span,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] input {
            color: #133A2A !important;
            -webkit-text-fill-color: #133A2A !important;
            opacity: 1 !important;
            font-weight: 600 !important;
        }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] svg {
            color: #133A2A !important;
            fill: #133A2A !important;
        }

        /* Action Buttons */
        div.stButton > button {
            background-color: #133A2A;
            color: #FFFFFF;
            border: 1px solid #133A2A;
            border-radius: 10px;
            font-weight: 600;
            transition: background-color 0.15s ease;
        }
        div.stButton > button:hover {
            background-color: #1F5740;
            border-color: #1F5740;
            color: #FFFFFF;
        }

        /* Breadcrumb & Hero Header */
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
        .eco-live-pill {
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

        /* Validation Banner matching soft amber/rose tone */
        .eco-val-banner {
            background-color: #FDF2F2;
            border: 1px solid #F5C6C6;
            border-left: 4px solid #C83E3E;
            color: #8A1F1F;
            border-radius: 10px;
            padding: 11px 16px;
            font-size: 0.85rem;
            font-weight: 500;
            margin: 0.65rem 0 0.95rem 0;
        }

        /* KPI Cards */
        .eco-card {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-radius: 16px;
            padding: 18px 20px;
            box-shadow: 0 2px 8px rgba(19, 58, 42, 0.03);
            height: 100%;
            position: relative;
            overflow: hidden;
        }
        .eco-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .eco-card-label {
            font-size: 0.83rem;
            font-weight: 500;
            color: #5E7167;
        }
        .eco-badge {
            font-size: 0.73rem;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 999px;
        }
        .eco-card-value {
            font-size: 1.85rem;
            font-weight: 700;
            color: #16261E;
            line-height: 1.15;
            margin-bottom: 6px;
        }
        .eco-card-sub {
            font-size: 0.79rem;
            color: #6B7E74;
        }

        /* Color-coded Pollutant Cards */
        .eco-pol-card {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-radius: 14px;
            padding: 14px 16px;
            margin-bottom: 0.75rem;
            box-shadow: 0 1px 5px rgba(19, 58, 42, 0.025);
        }
        .eco-pol-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }
        .eco-pol-name {
            font-size: 0.84rem;
            font-weight: 700;
            color: #24382E;
        }
        .eco-pol-tag {
            font-size: 0.68rem;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 999px;
        }
        .eco-pol-val {
            font-size: 1.38rem;
            font-weight: 700;
            margin-bottom: 4px;
        }
        .eco-pol-ref {
            font-size: 0.75rem;
            color: #6B7E74;
        }

        /* Seamless chart & section styling */
        [data-testid="stPlotlyChart"],
        [data-testid="stPlotlyChart"] > div {
            background: transparent !important;
        }

        .eco-section-title {
            font-size: 1.02rem;
            font-weight: 700;
            color: #16261E;
            margin: 1rem 0 0.65rem 0;
        }
        .eco-ready-box {
            background: linear-gradient(125deg, #F1F7F2 0%, #E3EFE6 100%);
            border: 1px solid #D6E6DA;
            border-radius: 16px;
            padding: 22px 24px;
            margin-top: 0.75rem;
            color: #1F3B2D;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def _severity_palette(severity: str) -> tuple[str, str, str]:
    """Returns (badge_bg, badge_fg, accent_hex) for a severity label."""
    s = severity.strip().lower()
    if s == "good":
        return ("#E4F5EC", "#166534", "#1F7A5A")
    if s == "moderate":
        return ("#FEF6E6", "#9A5B13", "#D97706")
    if s == "sensitive":
        return ("#FDECE4", "#9A3412", "#EA580C")
    if s == "unhealthy":
        return ("#FBE7E7", "#991B1B", "#DC2626")
    if s == "severe":
        return ("#F3E8FF", "#6B21A8", "#7E22CE")
    return ("#EEF3F0", "#4A6055", "#5E7167")


def _pollutant_level_style(p_key: str, val: float | None) -> tuple[str, str, str, str]:
    """Returns (border_accent, pill_bg, pill_fg, level_text) based on pollutant value."""
    if val is None:
        return ("#CBD5E1", "#F1F5F9", "#64748B", "Missing")
    thresholds: dict[str, tuple[float, float, float]] = {
        "pm25": (30.0, 60.0, 120.0),
        "pm10": (50.0, 100.0, 250.0),
        "no2": (40.0, 80.0, 180.0),
        "so2": (40.0, 80.0, 380.0),
        "co": (1.0, 2.0, 10.0),
        "o3": (50.0, 100.0, 168.0),
    }
    low, mod, high = thresholds.get(p_key, (50.0, 100.0, 200.0))
    if val <= low:
        return ("#22A06B", "#E4F5EC", "#166534", "Low")
    if val <= mod:
        return ("#D97706", "#FEF6E6", "#9A5B13", "Moderate")
    if val <= high:
        return ("#EA580C", "#FDECE4", "#9A3412", "Elevated")
    return ("#DC2626", "#FBE7E7", "#991B1B", "High")


@st.cache_data(ttl=300, show_spinner=False)
def _cached_search_cities(keyword: str, token_fingerprint: str) -> list[StationSearchResult]:
    client = WaqiClient(app_config=config)
    return client.search_cities(keyword)


def _build_unavailable_reading(
    target_query: str,
    chosen_station: StationSearchResult | None = None,
) -> AqiReading:
    """Creates a clean empty AqiReading when live fetch fails or returns no AQI."""
    return AqiReading(
        query=target_query,
        station_name=chosen_station.station_name if chosen_station else target_query,
        aqi=None,
        dominant_pollutant=None,
        pollutants={k: None for k in POLLUTANT_KEYS},
        observation_time=None,
        latitude=chosen_station.latitude if chosen_station else None,
        longitude=chosen_station.longitude if chosen_station else None,
    )


def _render_pollutant_chart(pollutants: dict[str, float | None], station_label: str) -> None:
    rows = [
        {"Pollutant": key.upper(), "Value": pollutants.get(key)}
        for key in POLLUTANT_KEYS
        if pollutants.get(key) is not None
    ]
    with st.container(border=True):
        st.markdown(f"**Reported Pollutant Measurements — {station_label}**")
        if not rows:
            st.caption("No numeric pollutant measurements were returned in this payload.")
        else:
            df = pd.DataFrame(rows)
            fig = go.Figure(
                go.Bar(
                    x=df["Pollutant"],
                    y=df["Value"],
                    marker_color="#133A2A",
                    marker_line_color="#0E2C20",
                    marker_line_width=1,
                    text=df["Value"].map(lambda v: f"{v:g}"),
                    textposition="outside",
                    textfont={"color": "#133A2A", "size": 12, "family": "sans-serif"},
                )
            )
            fig.update_layout(
                height=295,
                margin={"l": 44, "r": 20, "t": 28, "b": 42},
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"color": "#133A2A"},
                xaxis={
                    "title": {"text": "Pollutant", "font": {"color": "#133A2A", "size": 12}},
                    "tickfont": {"color": "#133A2A", "size": 11},
                    "showgrid": False,
                    "linecolor": "#B8CFC1",
                },
                yaxis={
                    "title": {"text": "Reported Value (IAQI / Raw)", "font": {"color": "#133A2A", "size": 12}},
                    "tickfont": {"color": "#133A2A", "size": 11},
                    "gridcolor": "#DFEAE3",
                    "linecolor": "#B8CFC1",
                    "zerolinecolor": "#9BBAA6",
                },
            )
            st.plotly_chart(fig, width="stretch", key="live_pollutant_bar_chart")


def _render_reading_view(
    reading: AqiReading,
    validation: ValidationResult,
    fetched_utc: str,
    from_cache: bool,
) -> None:
    severity = _classify_severity_label(reading.aqi)
    badge_bg, badge_fg, accent_hex = _severity_palette(severity)

    aqi_display = html.escape(str(reading.aqi) if reading.aqi is not None else "Unavailable")
    station_display = reading.station_name or "Station Name Unavailable"
    safe_station = html.escape(station_display)
    coord_display = (
        f"{reading.latitude:.4f}, {reading.longitude:.4f}"
        if reading.latitude is not None and reading.longitude is not None
        else "Coordinates Missing"
    )
    safe_coords = html.escape(coord_display)
    obs_display = reading.observation_time or "Timestamp Missing"
    dom_display = html.escape((reading.dominant_pollutant or "Not Reported").upper())
    completeness_pct = int(validation.completeness_ratio * 100)

    for err in validation.errors:
        st.markdown(
            f'<div class="eco-val-banner">Validation Error: {html.escape(err)}</div>',
            unsafe_allow_html=True,
        )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid {accent_hex};">
                <div class="eco-card-header">
                    <span class="eco-card-label">Reported AQI</span>
                    <span class="eco-badge" style="background:{badge_bg};color:{badge_fg};">{html.escape(severity)}</span>
                </div>
                <div class="eco-card-value" style="color:{accent_hex};">{aqi_display}</div>
                <div class="eco-card-sub">Severity Band: {html.escape(severity)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #133A2A;">
                <div class="eco-card-header">
                    <span class="eco-card-label">Dominant Pollutant</span>
                    <span class="eco-badge" style="background:#EAF3EC;color:#166534;">{completeness_pct}% Feed</span>
                </div>
                <div class="eco-card-value">{dom_display}</div>
                <div class="eco-card-sub">Completeness: {completeness_pct}% of 6 pollutants</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #1F7A5A;">
                <div class="eco-card-header">
                    <span class="eco-card-label">Station Coordinates</span>
                </div>
                <div class="eco-card-value" style="font-size:1.45rem;">{safe_coords}</div>
                <div class="eco-card-sub">{safe_station}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="eco-section-title">Pollutant Breakdown (Unimputed)</div>', unsafe_allow_html=True)
    for idx in range(0, len(POLLUTANT_KEYS), 3):
        cols = st.columns(3)
        for col, p_key in zip(cols, POLLUTANT_KEYS[idx : idx + 3]):
            val = reading.pollutants.get(p_key)
            border_c, tag_bg, tag_fg, level_txt = _pollutant_level_style(p_key, val)
            val_label = f"{val:g}" if val is not None else "Missing (Not Available)"
            std_ref = "WAQI iaqi feed value" if val is not None else "Absent in API response"
            val_font = "1.45rem" if val is not None else "1.02rem"
            val_color = "#16261E" if val is not None else "#6B7E74"
            with col:
                st.markdown(
                    f"""
                    <div class="eco-pol-card" style="border-left:4px solid {border_c};">
                        <div class="eco-pol-top">
                            <span class="eco-pol-name">{html.escape(p_key.upper())}</span>
                            <span class="eco-pol-tag" style="background:{tag_bg};color:{tag_fg};">{level_txt}</span>
                        </div>
                        <div class="eco-pol-val" style="font-size:{val_font};color:{val_color};">{html.escape(val_label)}</div>
                        <div class="eco-pol-ref">{html.escape(std_ref)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
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
    _inject_live_page_theme()

    default_city = st.session_state.get("selected_location", config.default_location)

    st.markdown(
        """
        <div class="eco-topbar">
            <div>
                <div class="eco-breadcrumb">EcoHealth &nbsp;/&nbsp; <strong>Live AQI Monitoring</strong></div>
                <div class="eco-sub">Select a monitoring station in Delhi or search any city, fetch live WAQI telemetry, and inspect data quality.</div>
            </div>
            <div class="eco-live-pill">
                <span class="eco-dot"></span>WAQI Live Feed
            </div>
        </div>
        """,
        unsafe_allow_html=True,
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
    chosen_station: StationSearchResult | None = None

    if matches:
        option_labels = [m.station_name for m in matches]
        chosen_idx = st.selectbox(
            "Select Place / Monitoring Station in Delhi (or Search Results)",
            options=list(range(len(option_labels))),
            format_func=lambda i: option_labels[i],
            key="waqi_station_choice",
        )
        chosen_station = matches[chosen_idx]
        if chosen_station.uid is not None:
            selected_feed_target = f"@{chosen_station.uid}"
        elif "City-Wide" in chosen_station.station_name:
            selected_feed_target = "Delhi"
        else:
            selected_feed_target = chosen_station.station_name

    auto_live = st.toggle("Enable Live Auto-Refresh (every 2 hours)", value=False, key="live_auto_refresh_toggle")

    explicit_refresh = fetch_clicked or refresh_clicked or auto_live
    initial_load = "waqi_last_reading" not in st.session_state and config.has_api_token

    if explicit_refresh or initial_load:
        with st.spinner(f"Fetching current live telemetry for {selected_feed_target} from WAQI..."):
            fetched_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            try:
                client = WaqiClient(app_config=config)
                reading = client.get_city_aqi(selected_feed_target)

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
                except Exception as db_exc:
                    st.session_state["last_persisted_status"] = (
                        f"Live telemetry displayed; SQLite persistence skipped ({db_exc})."
                    )

                if explicit_refresh:
                    st.toast(f"Updated live AQI for {reading.station_name or selected_feed_target}")
            except WaqiClientError as exc:
                fallback_reading = _build_unavailable_reading(selected_feed_target, chosen_station)
                st.session_state["waqi_last_reading"] = fallback_reading
                st.session_state["waqi_last_fetched_utc"] = fetched_utc
                st.session_state["waqi_last_fetched_at"] = fetched_utc
                st.session_state["waqi_last_was_cached"] = False
                st.session_state["last_persisted_status"] = (
                    f"WAQI fetch unavailable ({exc.kind.value}: {exc.message})."
                )

    last_reading: AqiReading | None = st.session_state.get("waqi_last_reading")
    last_fetched_utc: str | None = st.session_state.get("waqi_last_fetched_utc")

    if last_reading is not None and last_fetched_utc is not None:
        validation = validate_aqi_reading(last_reading)
        was_cached = bool(st.session_state.get("waqi_last_was_cached", False))
        _render_reading_view(last_reading, validation, last_fetched_utc, from_cache=was_cached)
        st.session_state["waqi_last_was_cached"] = True
    else:
        st.markdown(
            """
            <div class="eco-ready-box">
                <strong>Ready to Query WAQI</strong><br>
                Select a monitoring station above and click 'Fetch Live AQI' or search any city keyword.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if auto_live:
        time.sleep(7200)
        st.rerun()


main()