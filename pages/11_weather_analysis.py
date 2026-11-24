import html
import json
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import config
from src.database import get_observations, hydrate_sqlite_from_json, initialize_database, list_stations
from src.utils import render_warning_banner

DEFAULT_STATION_COORDS: dict[str, tuple[float, float]] = {
    "Delhi (CPCB City Composite)": (28.6139, 77.2090),
    "Anand Vihar, Delhi, Delhi, India": (28.6508, 77.3152),
    "Burari Crossing, Delhi, Delhi, India": (28.725646, 77.203384),
    "Delhi Institute of Tool Engineering, Wazirpur, Delhi, Delhi, India": (28.700505, 77.165603),
    "ITI Jahangirpuri, Delhi, Delhi, India": (28.733016, 77.171970),
    "ITI Shahdra, Jhilmil Industrial Area, Delhi, Delhi, India": (28.672114, 77.313832),
    "Jawaharlal Nehru Stadium, Delhi, Delhi, India": (28.582846, 77.234366),
    "Lodhi Road, Delhi, Delhi, India": (28.589701, 77.221917),
    "Major Dhyan Chand National Stadium, Delhi, Delhi, India": (28.612498, 77.237388),
    "Mandir Marg, Delhi, Delhi, India": (28.634100, 77.200500),
    "Mother Dairy Plant, Parparganj, Delhi, Delhi, India": (28.620171, 77.287705),
    "PGDAV College, Sriniwaspuri, Delhi, Delhi, India": (28.566827, 77.251418),
    "Pusa, Delhi, Delhi, India": (28.636997, 77.172248),
    "R.K. Puram, Delhi, Delhi, India": (28.564800, 77.174400),
    "Satyawati College, Delhi, Delhi, India": (28.695720, 77.181295),
    "Sector-1, Noida, India": (28.589800, 77.310100),
    "Sonia Vihar Water Treatment Plant DJB, Delhi, Delhi, India": (28.710066, 77.246220),
    "IHBAS, Delhi, Delhi, India": (28.682152, 77.302613),
    "ITO, Delhi, Delhi, India": (28.628577, 77.241036),
    "New Delhi US Embassy, India": (28.635760, 77.224450),
    "North Campus, Delhi": (28.687716, 77.210232),
    "Shadipur, Delhi, Delhi, India": (28.651553, 77.158042),
}


def _inject_weather_dashboard_theme() -> None:
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

        /* Green label & light-green selectbox with dark-green text */
        [data-testid="stSelectbox"] label,
        [data-testid="stSelectbox"] label p {
            color: #1B5E3F !important;
            font-weight: 600 !important;
            font-size: 0.88rem !important;
        }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            background-color: #EAF4EC !important;
            border-color: #B4D6BE !important;
            border-radius: 10px !important;
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
        div[data-testid="stSelectbox"] div[data-baseweb="select"] svg {
            color: #133A2A !important;
            fill: #133A2A !important;
        }

        /* Forest-green action button */
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

        /* Metric Cards */
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
            font-size: 1.62rem;
            font-weight: 700;
            color: #133A2A;
            line-height: 1.15;
            margin-bottom: 5px;
        }
        .eco-card-sub {
            font-size: 0.76rem;
            color: #6B7E74;
        }

        /* Section Titles & Context Cards */
        .eco-section-title {
            font-size: 1.02rem;
            font-weight: 700;
            color: #133A2A;
            margin: 1.05rem 0 0.65rem 0;
        }
        .eco-context-card {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-left: 4px solid #1F7A5A;
            border-radius: 14px;
            padding: 14px 18px;
            margin-bottom: 10px;
            box-shadow: 0 2px 6px rgba(19, 58, 42, 0.025);
        }
        .eco-context-title {
            font-weight: 700;
            color: #133A2A;
            font-size: 0.92rem;
            margin-bottom: 4px;
        }
        .eco-context-body {
            color: #2D4238;
            font-size: 0.85rem;
            line-height: 1.5;
        }
        .eco-context-note {
            color: #6B7E74;
            font-size: 0.76rem;
            font-style: italic;
            margin-top: 6px;
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


def _build_location_map() -> dict[str, tuple[float, float]]:
    loc_map = dict(DEFAULT_STATION_COORDS)
    try:
        for row in list_stations():
            name = str(row.get("station_name") or "").strip()
            lat = row.get("latitude")
            lon = row.get("longitude")
            if name and lat is not None and lon is not None:
                loc_map[name] = (float(lat), float(lon))
    except Exception:
        pass
    return loc_map


@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_30d_weather(lat: float, lon: float) -> pd.DataFrame:
    params = urlencode({
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,surface_pressure",
        "past_days": 30,
        "forecast_days": 1,
        "timezone": "Asia/Kolkata",
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    with urlopen(url, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return pd.DataFrame()

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(times, errors="coerce"),
        "temperature_c": pd.to_numeric(hourly.get("temperature_2m"), errors="coerce"),
        "humidity_pct": pd.to_numeric(hourly.get("relative_humidity_2m"), errors="coerce"),
        "wind_speed_kmh": pd.to_numeric(hourly.get("wind_speed_10m"), errors="coerce"),
        "wind_dir_deg": pd.to_numeric(hourly.get("wind_direction_10m"), errors="coerce"),
        "rainfall_mm": pd.to_numeric(hourly.get("precipitation"), errors="coerce"),
        "pressure_hpa": pd.to_numeric(hourly.get("surface_pressure"), errors="coerce"),
    })
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    if df.empty:
        return df

    cutoff = df["timestamp"].max() - pd.Timedelta(days=30)
    return df[df["timestamp"] >= cutoff].reset_index(drop=True)


def _render_metric_box(label: str, value: str, sub: str, accent: str = "#133A2A", value_size: str = "1.62rem") -> None:
    st.markdown(
        f"""
        <div class="eco-card" style="border-top:4px solid {accent};">
            <div class="eco-card-label">{html.escape(label)}</div>
            <div class="eco-card-value" style="font-size:{value_size};">{html.escape(value)}</div>
            <div class="eco-card-sub">{html.escape(sub)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_context_note(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="eco-context-card">
            <div class="eco-context-title">{html.escape(title)}</div>
            <div class="eco-context-body">{html.escape(body)}</div>
            <div class="eco-context-note">
                Note: Association only; meteorological co-occurrence does not prove causation.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    _inject_weather_dashboard_theme()

    st.markdown(
        """
        <div class="eco-topbar">
            <div>
                <div class="eco-breadcrumb">EcoHealth &nbsp;/&nbsp; <strong>Weather Analysis</strong></div>
                <div class="eco-sub">Location-based meteorological variables and a 30-day weather context dashboard.</div>
            </div>
            <div class="eco-pill">
                <span class="eco-dot"></span>30-Day Meteorology
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    initialize_database()
    if not list_stations():
        hydrate_sqlite_from_json()

    loc_map = _build_location_map()
    options = list(loc_map.keys())
    preferred = st.session_state.get("selected_location") or config.default_location
    default_idx = options.index(preferred) if preferred in options else 0

    col_loc, col_btn = st.columns([3, 1])
    with col_loc:
        selected_station = st.selectbox(
            "Select Monitoring Location",
            options=options,
            index=default_idx,
            key="weather_station_select",
        )
    with col_btn:
        st.write("")
        refresh_clicked = st.button("Refresh Weather", use_container_width=True)

    st.session_state["selected_location"] = selected_station
    lat, lon = loc_map[selected_station]

    if refresh_clicked:
        _fetch_30d_weather.clear()

    try:
        df_30d = _fetch_30d_weather(lat, lon)
    except Exception as exc:
        render_warning_banner(
            f"Unable to load 30-day weather data for {selected_station}: {exc}",
            is_placeholder=False,
        )
        return

    if df_30d.empty:
        render_warning_banner(
            f"No 30-day meteorological records returned for {selected_station}.",
            is_placeholder=False,
        )
        return

    latest = df_30d.iloc[-1]
    mean_temp = float(df_30d["temperature_c"].mean())
    max_temp = float(df_30d["temperature_c"].max())
    min_temp = float(df_30d["temperature_c"].min())
    avg_wind = float(df_30d["wind_speed_kmh"].mean())
    avg_rh = float(df_30d["humidity_pct"].mean())
    total_rain = float(df_30d["rainfall_mm"].sum())

    # Associated AQI context if available for this station
    aqi_note = "No stored AQI reading for this location"
    aqi_val_str = "Pending"
    try:
        obs_list = get_observations(location=selected_station, limit=1)
        if obs_list:
            latest_obs = obs_list[-1]
            aqi_num = latest_obs.get("calculated_aqi") or latest_obs.get("waqi_reported_aqi")
            if aqi_num is not None:
                aqi_val_str = f"{aqi_num} AQI"
                aqi_note = f"{latest_obs.get('aqi_category') or 'Recorded'} • {latest_obs.get('observation_time') or ''}"
    except Exception:
        pass

    st.markdown(f'<div class="eco-section-title">Current Conditions — {html.escape(selected_station)}</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        _render_metric_box(
            "Temperature",
            f"{latest['temperature_c']:.1f} °C",
            f"30d range: {min_temp:.1f}°–{max_temp:.1f}°C",
            accent="#D97706",
        )
    with c2:
        _render_metric_box(
            "Relative Humidity",
            f"{latest['humidity_pct']:.0f} %",
            f"30d avg: {avg_rh:.0f}%",
            accent="#2B6CB0",
        )
    with c3:
        _render_metric_box(
            "Associated AQI Reference",
            aqi_val_str,
            aqi_note,
            accent="#133A2A",
        )

    c4, c5, c6 = st.columns(3)
    with c4:
        _render_metric_box(
            "Wind Speed",
            f"{latest['wind_speed_kmh']:.1f} km/h",
            f"30d avg: {avg_wind:.1f} km/h",
            accent="#1F7A5A",
        )
    with c5:
        _render_metric_box(
            "Wind Direction",
            f"{latest['wind_dir_deg']:.0f}°",
            "10m wind bearing",
            accent="#4D7C0F",
        )
    with c6:
        _render_metric_box(
            "Rainfall & Pressure",
            f"{latest['rainfall_mm']:.1f} mm | {latest['pressure_hpa']:.1f} hPa",
            f"30d total rain: {total_rain:.1f} mm",
            accent="#315B48",
            value_size="1.22rem",
        )

    st.markdown(f'<div class="eco-section-title">Last 30 Days Weather Dashboard — {html.escape(selected_station)}</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        _render_metric_box("30-Day Mean Temp", f"{mean_temp:.1f} °C", "Hourly mean", accent="#133A2A", value_size="1.42rem")
    with m2:
        _render_metric_box("30-Day Max Temp", f"{max_temp:.1f} °C", "Peak recorded", accent="#D97706", value_size="1.42rem")
    with m3:
        _render_metric_box("30-Day Avg Wind", f"{avg_wind:.1f} km/h", "10m mean wind", accent="#1F7A5A", value_size="1.42rem")
    with m4:
        _render_metric_box("30-Day Rainfall", f"{total_rain:.1f} mm", "Cumulative total", accent="#2B6CB0", value_size="1.42rem")

    g1, g2 = st.columns(2)
    with g1:
        with st.container(border=True):
            st.markdown("**30-Day Temperature (°C) & Humidity (%)**")
            fig_th = go.Figure()
            fig_th.add_trace(
                go.Scatter(
                    x=df_30d["timestamp"],
                    y=df_30d["temperature_c"],
                    mode="lines",
                    name="Temperature (°C)",
                    line={"color": "#D97706", "width": 2},
                )
            )
            fig_th.add_trace(
                go.Scatter(
                    x=df_30d["timestamp"],
                    y=df_30d["humidity_pct"],
                    mode="lines",
                    name="Humidity (%)",
                    yaxis="y2",
                    line={"color": "#2B6CB0", "width": 1.6},
                )
            )
            fig_th.update_layout(
                height=290,
                margin={"l": 40, "r": 40, "t": 16, "b": 32},
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"color": "#133A2A"},
                xaxis={"tickfont": {"color": "#133A2A"}, "linecolor": "#B8CFC1", "showgrid": False},
                yaxis={"title": "°C", "tickfont": {"color": "#133A2A"}, "gridcolor": "#DFEAE3"},
                yaxis2={"title": "% RH", "tickfont": {"color": "#133A2A"}, "overlaying": "y", "side": "right", "showgrid": False},
                legend={"orientation": "h", "y": 1.14, "font": {"color": "#133A2A"}},
            )
            st.plotly_chart(fig_th, use_container_width=True, key="weather_30d_temp_rh")

    with g2:
        with st.container(border=True):
            st.markdown("**30-Day Wind Speed (km/h) & Daily Rainfall (mm)**")
            daily_rain = (
                df_30d.set_index("timestamp")["rainfall_mm"]
                .resample("1D")
                .sum()
                .reset_index()
            )
            fig_wr = go.Figure()
            fig_wr.add_trace(
                go.Scatter(
                    x=df_30d["timestamp"],
                    y=df_30d["wind_speed_kmh"],
                    mode="lines",
                    name="Wind Speed (km/h)",
                    line={"color": "#1F7A5A", "width": 2},
                )
            )
            fig_wr.add_trace(
                go.Bar(
                    x=daily_rain["timestamp"],
                    y=daily_rain["rainfall_mm"],
                    name="Daily Rain (mm)",
                    yaxis="y2",
                    marker_color="rgba(43, 108, 176, 0.45)",
                )
            )
            fig_wr.update_layout(
                height=290,
                margin={"l": 40, "r": 40, "t": 16, "b": 32},
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"color": "#133A2A"},
                xaxis={"tickfont": {"color": "#133A2A"}, "linecolor": "#B8CFC1", "showgrid": False},
                yaxis={"title": "km/h", "tickfont": {"color": "#133A2A"}, "gridcolor": "#DFEAE3"},
                yaxis2={"title": "Rain (mm)", "tickfont": {"color": "#133A2A"}, "overlaying": "y", "side": "right", "showgrid": False},
                legend={"orientation": "h", "y": 1.14, "font": {"color": "#133A2A"}},
            )
            st.plotly_chart(fig_wr, use_container_width=True, key="weather_30d_wind_rain")

    daily_summary = (
        df_30d.set_index("timestamp")
        .resample("1D")
        .agg(
            Avg_Temp_C=("temperature_c", "mean"),
            Max_Temp_C=("temperature_c", "max"),
            Min_Temp_C=("temperature_c", "min"),
            Avg_Humidity_Pct=("humidity_pct", "mean"),
            Avg_Wind_kmh=("wind_speed_kmh", "mean"),
            Total_Rain_mm=("rainfall_mm", "sum"),
        )
        .reset_index()
        .sort_values("timestamp", ascending=False)
    )
    daily_summary["Date"] = daily_summary["timestamp"].dt.strftime("%Y-%m-%d")
    daily_table = daily_summary[
        ["Date", "Avg_Temp_C", "Min_Temp_C", "Max_Temp_C", "Avg_Humidity_Pct", "Avg_Wind_kmh", "Total_Rain_mm"]
    ].round(1)

    with st.container(border=True):
        st.markdown("**30-Day Daily Weather Summary**")
        st.dataframe(daily_table, use_container_width=True, hide_index=True)

    st.markdown('<div class="eco-section-title">Weather &amp; Pollution Context (Non-Causal Notes)</div>', unsafe_allow_html=True)
    _render_context_note(
        "Wind Speed & Dispersion",
        f"Over the last 30 days at {selected_station}, average wind speed was {avg_wind:.1f} km/h. Calm or low-wind periods generally correspond with weaker horizontal air dispersion.",
    )
    _render_context_note(
        "Temperature & Humidity Cycle",
        f"Temperatures ranged from {min_temp:.1f} °C to {max_temp:.1f} °C with {avg_rh:.0f}% average relative humidity, reflecting diurnal boundary-layer shifts.",
    )
    _render_context_note(
        "Rainfall & Dry Surface Conditions",
        f"Cumulative 30-day rainfall was {total_rain:.1f} mm; dry spells leave surfaces unwashed while rain can temporarily clear airborne particulates.",
    )


main()