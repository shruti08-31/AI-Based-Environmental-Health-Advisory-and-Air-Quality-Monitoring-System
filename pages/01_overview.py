import html
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import config
from src.analytics import compute_historical_analytics
from src.api import AqiReading
from src.core import evaluate_aqi_from_reading, generate_health_advisory
from src.database import get_observations
from src.intelligence import analyze_pollutants_from_reading
from src.utils import render_warning_banner


def _inject_ecohealth_theme() -> None:
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

        /* Deep forest-green sidebar matching EcoHealth screenshot */
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

        /* Breadcrumb header bar */
        .eco-topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 0.65rem;
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
        .eco-loc-pill {
            background: #FFFFFF;
            border: 1px solid #DCE6E0;
            border-radius: 10px;
            padding: 7px 14px;
            font-size: 0.84rem;
            color: #24382E;
            box-shadow: 0 1px 2px rgba(19, 58, 42, 0.04);
        }
        .eco-dot {
            display: inline-block;
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: #22A06B;
            margin-right: 6px;
        }

        /* Sage gradient hero banner */
        .eco-hero {
            background: linear-gradient(125deg, #F1F7F2 0%, #E3EFE6 100%);
            border: 1px solid #D6E6DA;
            border-radius: 18px;
            padding: 28px 32px;
            margin-bottom: 1.25rem;
            position: relative;
            overflow: hidden;
        }
        .eco-hero-kicker {
            font-size: 0.70rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #4D6B5C;
            margin-bottom: 6px;
        }
        .eco-hero-title {
            font-size: 1.85rem;
            font-weight: 700;
            color: #16261E;
            margin: 0 0 6px 0;
            line-height: 1.2;
        }
        .eco-hero-desc {
            font-size: 0.93rem;
            color: #4A6055;
            margin: 0;
        }
        .eco-hero-emblem {
            position: absolute;
            right: 36px;
            top: 50%;
            transform: translateY(-50%);
            width: 68px;
            height: 68px;
            border-radius: 50%;
            background: rgba(163, 201, 174, 0.35);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #2C5E46;
            font-size: 1.5rem;
            box-shadow: 0 0 0 16px rgba(163, 201, 174, 0.14);
        }

        /* Clean white metric cards */
        .eco-card {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-radius: 16px;
            padding: 20px 22px;
            box-shadow: 0 2px 8px rgba(19, 58, 42, 0.03);
            height: 100%;
            position: relative;
            overflow: hidden;
        }
        .eco-card::after {
            content: "";
            position: absolute;
            right: -18px;
            bottom: -18px;
            width: 72px;
            height: 72px;
            border-radius: 50%;
            background: #F2F6F3;
            pointer-events: none;
        }
        .eco-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        .eco-card-label {
            font-size: 0.84rem;
            font-weight: 500;
            color: #5E7167;
        }
        .eco-badge {
            font-size: 0.73rem;
            font-weight: 600;
            padding: 3px 10px;
            border-radius: 999px;
        }
        .eco-card-value {
            font-size: 1.95rem;
            font-weight: 700;
            color: #16261E;
            line-height: 1.15;
            margin-bottom: 8px;
        }
        .eco-card-unit {
            font-size: 0.84rem;
            font-weight: 500;
            color: #6B7E74;
            margin-left: 4px;
        }
        .eco-card-sub {
            font-size: 0.80rem;
            color: #6B7E74;
            position: relative;
            z-index: 1;
        }

        /* Section cards (Pollutant strip, Chart, Advisory) */
        .eco-section {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-radius: 16px;
            padding: 20px 22px;
            box-shadow: 0 2px 8px rgba(19, 58, 42, 0.03);
            margin-top: 1rem;
        }
        .eco-section-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
        }
        .eco-section-title {
            font-size: 0.98rem;
            font-weight: 650;
            color: #16261E;
        }
        .eco-section-meta {
            font-size: 0.78rem;
            color: #6B7E74;
        }
        .eco-mini-tile {
            background: #F8FAF9;
            border: 1px solid #E7EFEA;
            border-radius: 12px;
            padding: 12px 14px;
        }
        .eco-mini-label {
            font-size: 0.76rem;
            font-weight: 600;
            color: #5E7167;
            margin-bottom: 4px;
        }
        .eco-mini-val {
            font-size: 1.25rem;
            font-weight: 700;
            color: #16261E;
        }
        .eco-advisory-list {
            margin: 8px 0 0 0;
            padding-left: 18px;
            color: #364B40;
            font-size: 0.88rem;
            line-height: 1.6;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _category_badge_colors(category: str) -> tuple[str, str]:
    c = category.strip().lower()
    if "good" in c:
        return ("#E4F5EC", "#166534")
    if "satisfactory" in c:
        return ("#ECF7E8", "#3F6212")
    if "moderate" in c:
        return ("#FEF6E6", "#9A5B13")
    if "poor" in c and "very" not in c:
        return ("#FDECE4", "#9A3412")
    if "very poor" in c or "unhealthy" in c or "severe" in c:
        return ("#FBE7E7", "#991B1B")
    return ("#EEF3F0", "#4A6055")


def _filter_last_24h(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Return rows from the last 24 hours based on fetched observation timestamps."""
    if df.empty or "observation_time" not in df.columns:
        return df, "Fetched readings"

    parsed = pd.to_datetime(df["observation_time"], errors="coerce", utc=True)
    valid_mask = parsed.notna()
    if not valid_mask.any():
        return df, "Fetched readings"

    work_df = df.loc[valid_mask].copy()
    work_ts = parsed.loc[valid_mask]
    cutoff = work_ts.max() - pd.Timedelta(hours=24)
    last_24h_df = work_df.loc[work_ts >= cutoff].copy()
    last_24h_df["_ts"] = work_ts.loc[work_ts >= cutoff]
    last_24h_df = last_24h_df.sort_values("_ts")

    if last_24h_df.empty:
        return df, "Latest fetched readings (none within last 24h)"
    return last_24h_df, f"Last 24 hrs ({len(last_24h_df)} fetched reading{'s' if len(last_24h_df) != 1 else ''})"


def main() -> None:
    _inject_ecohealth_theme()

    selected_location = (
        (st.session_state.get("selected_location") or config.default_location).strip()
        or config.default_location
    )
    reading: AqiReading | None = st.session_state.get("waqi_last_reading")

    try:
        stored_obs = get_observations(limit=500)
        db_available = True
    except Exception as db_err:
        stored_obs = []
        db_available = False
        render_warning_banner(
            f"SQLite persistence temporarily unavailable ({db_err}); live session telemetry remains operational.",
            is_placeholder=False,
        )

    safe_loc = html.escape(selected_location)
    st.markdown(
        f"""
        <div class="eco-topbar">
            <div>
                <div class="eco-breadcrumb">EcoHealth &nbsp;/&nbsp; <strong>Overview</strong></div>
                <div class="eco-sub">Integrated air quality status, health guidance, and last-24h fetched pollution trend.</div>
            </div>
            <div class="eco-loc-pill">
                <span class="eco-dot"></span>Location: <strong>{safe_loc}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if reading is None and not stored_obs:
        st.markdown(
            f"""
            <div class="eco-hero">
                <div class="eco-hero-kicker">YOUR ENVIRONMENT, AT A GLANCE</div>
                <div class="eco-hero-title">Air quality overview</div>
                <p class="eco-hero-desc">Stay informed about the air around <strong>{safe_loc}</strong> and make confident choices for your day.</p>
                <div class="eco-hero-emblem">&#10035;</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_warning_banner(
            "No live or historical WAQI observations available yet. Open 'Live AQI Monitoring' to fetch station telemetry.",
            is_placeholder=True,
        )
        r1c1, r1c2, r1c3 = st.columns(3)
        with r1c1:
            st.markdown(
                """
                <div class="eco-card">
                    <div class="eco-card-header">
                        <span class="eco-card-label">Calculated CPCB AQI</span>
                        <span class="eco-badge" style="background:#EEF3F0;color:#4A6055;">Pending</span>
                    </div>
                    <div class="eco-card-value">Unavailable</div>
                    <div class="eco-card-sub">No reading fetched yet</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with r1c2:
            st.markdown(
                f"""
                <div class="eco-card">
                    <div class="eco-card-header">
                        <span class="eco-card-label">Selected Location</span>
                    </div>
                    <div class="eco-card-value">{safe_loc}</div>
                    <div class="eco-card-sub">Configured default location</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with r1c3:
            st.markdown(
                """
                <div class="eco-card">
                    <div class="eco-card-header">
                        <span class="eco-card-label">Dominant Pollutant</span>
                    </div>
                    <div class="eco-card-value">Unavailable</div>
                    <div class="eco-card-sub">No sub-index data</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return

    pollutants_map: dict[str, float | None] = {}
    if reading is not None:
        aqi_res = evaluate_aqi_from_reading(reading)
        analyze_pollutants_from_reading(reading)
        advisory = generate_health_advisory(
            category=aqi_res.category,
            dominant_pollutant=aqi_res.dominant_pollutant,
        )
        calc_aqi_str = str(aqi_res.calculated_aqi) if aqi_res.calculated_aqi is not None else "Unavailable"
        waqi_str = str(reading.aqi) if reading.aqi is not None else "N/A"
        category_str = aqi_res.category
        explanation_str = aqi_res.category_explanation
        station_str = reading.station_name or selected_location
        dom_str = (aqi_res.dominant_pollutant or "None").upper()
        obs_str = reading.observation_time or "Timestamp Missing"
        urgency_str = advisory.urgency_level
        general_precautions = advisory.general_precautions
        pollutants_map = dict(reading.pollutants or {})
    else:
        latest = stored_obs[-1]
        calc_aqi_str = str(latest["calculated_aqi"]) if latest.get("calculated_aqi") is not None else "Unavailable"
        waqi_str = str(latest["waqi_reported_aqi"]) if latest.get("waqi_reported_aqi") is not None else "N/A"
        category_str = str(latest.get("aqi_category") or "Unavailable")
        explanation_str = f"Persisted reading from SQLite ({latest.get('observation_time')})."
        station_str = str(latest.get("station_name") or selected_location)
        dom_str = str(latest.get("dominant_pollutant") or "None").upper()
        obs_str = str(latest.get("observation_time") or "Timestamp Missing")
        advisory = generate_health_advisory(category=category_str, dominant_pollutant=dom_str)
        urgency_str = advisory.urgency_level
        general_precautions = advisory.general_precautions
        for key in ("pm25", "pm10", "no2", "so2", "co", "o3"):
            if latest.get(key) is not None:
                pollutants_map[key] = latest.get(key)

    badge_bg, badge_fg = _category_badge_colors(category_str)
    safe_station = html.escape(station_str)
    safe_category = html.escape(category_str)
    safe_explanation = html.escape(explanation_str)
    safe_dom = html.escape(dom_str)
    safe_urgency = html.escape(urgency_str)
    safe_obs = html.escape(obs_str)
    safe_calc = html.escape(calc_aqi_str)
    safe_waqi = html.escape(waqi_str)

    st.markdown(
        f"""
        <div class="eco-hero">
            <div class="eco-hero-kicker">YOUR ENVIRONMENT, AT A GLANCE</div>
            <div class="eco-hero-title">Air quality overview</div>
            <p class="eco-hero-desc">Stay informed about the air around <strong>{safe_station}</strong> and make confident choices for your day.</p>
            <div class="eco-hero-emblem">&#10035;</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        st.markdown(
            f"""
            <div class="eco-card">
                <div class="eco-card-header">
                    <span class="eco-card-label">Calculated AQI (CPCB)</span>
                    <span class="eco-badge" style="background:{badge_bg};color:{badge_fg};">{safe_category}</span>
                </div>
                <div class="eco-card-value">{safe_calc}<span class="eco-card-unit">CPCB AQI</span></div>
                <div class="eco-card-sub">WAQI Reported: {safe_waqi} &bull; {safe_obs}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r1c2:
        st.markdown(
            f"""
            <div class="eco-card">
                <div class="eco-card-header">
                    <span class="eco-card-label">Station / Location</span>
                </div>
                <div class="eco-card-value" style="font-size:1.45rem;">{safe_station}</div>
                <div class="eco-card-sub">Selected: {safe_loc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r1c3:
        st.markdown(
            f"""
            <div class="eco-card">
                <div class="eco-card-header">
                    <span class="eco-card-label">Dominant Pollutant</span>
                    <span class="eco-badge" style="background:#EAF3EC;color:#1D5E41;">{safe_urgency}</span>
                </div>
                <div class="eco-card-value">{safe_dom}</div>
                <div class="eco-card-sub">{safe_explanation}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if pollutants_map:
        ordered_keys = [
            ("pm25", "PM2.5"),
            ("pm10", "PM10"),
            ("no2", "NO2"),
            ("so2", "SO2"),
            ("co", "CO"),
            ("o3", "O3"),
        ]
        tiles_html = []
        for raw_k, label in ordered_keys:
            val = pollutants_map.get(raw_k)
            val_display = f"{val}" if val is not None else "—"
            tiles_html.append(
                f'<div class="eco-mini-tile">'
                f'<div class="eco-mini-label">{label}</div>'
                f'<div class="eco-mini-val">{html.escape(val_display)}</div>'
                f"</div>"
            )
        st.markdown(
            f"""
            <div class="eco-section">
                <div class="eco-section-head">
                    <span class="eco-section-title">Pollutant Concentrations</span>
                    <span class="eco-section-meta">Updated {safe_obs}</span>
                </div>
                <div style="display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;">
                    {''.join(tiles_html)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    station_obs = [o for o in stored_obs if o.get("station_name") == station_str] or stored_obs
    hist = compute_historical_analytics(station_obs)
    df_24h, window_label = _filter_last_24h(hist.timeseries_df)

    left_col, right_col = st.columns([1.45, 1.0])
    with left_col:
        with st.container(border=True):
            st.markdown(f"**Last 24 Hours Fetched Trend — {station_str}**")
            if df_24h.empty:
                st.info(
                    "No fetched observations yet for this station."
                    if db_available
                    else "Trend chart unavailable while SQLite storage is offline."
                )
            else:
                x_vals = df_24h["_ts"].dt.tz_convert("Asia/Kolkata").dt.strftime("%b %d, %H:%M") if "_ts" in df_24h.columns else df_24h["observation_time"]
                fig = go.Figure(
                    go.Scatter(
                        x=x_vals,
                        y=df_24h["effective_aqi"],
                        mode="lines+markers",
                        name="Calculated CPCB AQI",
                        line={"color": "#1F7A5A", "width": 2.5},
                        marker={"color": "#133A2A", "size": 7},
                        fill="tozeroy",
                        fillcolor="rgba(31, 122, 90, 0.10)",
                        hovertemplate="<b>%{x}</b><br>CPCB AQI: %{y}<extra></extra>",
                    )
                )
                fig.update_layout(
                    height=265,
                    margin={"l": 36, "r": 16, "t": 12, "b": 36},
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis={"title": window_label, "showgrid": False},
                    yaxis={"title": "CPCB AQI", "gridcolor": "#EDF2EF"},
                )
                st.plotly_chart(fig, width="stretch", key="overview_last_24h_trend_chart")

    with right_col:
        precautions_li = "".join(f"<li>{html.escape(p)}</li>" for p in general_precautions)
        st.markdown(
            f"""
            <div class="eco-section" style="margin-top:0;height:100%;">
                <div class="eco-section-head">
                    <span class="eco-section-title">Health Advisory ({safe_category} — {safe_urgency})</span>
                </div>
                <ul class="eco-advisory-list">{precautions_li}</ul>
            </div>
            """,
            unsafe_allow_html=True,
        )


main()