import html
import json
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.api import AqiReading
from src.database import DEFAULT_DB_PATH, get_observations, list_stations
from src.validation import validate_aqi_reading


def _inject_data_quality_theme() -> None:
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

        /* Section Title & Metric Cards */
        .eco-section-title {
            font-size: 1.02rem;
            font-weight: 700;
            color: #133A2A;
            margin: 1.05rem 0 0.65rem 0;
        }
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
            font-size: 1.55rem;
            font-weight: 700;
            color: #133A2A;
            line-height: 1.18;
            margin-bottom: 5px;
        }
        .eco-card-sub {
            font-size: 0.76rem;
            color: #6B7E74;
        }

        /* Info Panels */
        .eco-panel {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-left: 4px solid #133A2A;
            border-radius: 14px;
            padding: 16px 20px;
            margin-top: 0.85rem;
            box-shadow: 0 2px 6px rgba(19, 58, 42, 0.025);
        }
        .eco-panel-title {
            font-size: 0.93rem;
            font-weight: 700;
            color: #133A2A;
            margin-bottom: 6px;
        }
        .eco-panel-body {
            font-size: 0.85rem;
            color: #2D4238;
            line-height: 1.55;
        }
        .eco-panel-list {
            margin: 4px 0 0 0;
            padding-left: 18px;
            color: #2D4238;
            font-size: 0.85rem;
            line-height: 1.6;
        }
        .eco-rule-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px 18px;
            margin-top: 4px;
        }
        .eco-rule-item {
            font-size: 0.84rem;
            color: #2D4238;
            line-height: 1.45;
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


def _render_dq_card(
    label: str,
    value: str,
    sub: str,
    accent: str = "#133A2A",
    value_color: str = "#133A2A",
    value_size: str = "1.55rem",
) -> None:
    st.markdown(
        f"""
        <div class="eco-card" style="border-top:4px solid {accent};">
            <div class="eco-card-label">{html.escape(label)}</div>
            <div class="eco-card-value" style="color:{value_color};font-size:{value_size};">{html.escape(value)}</div>
            <div class="eco-card-sub">{html.escape(sub)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _summarize_sources(all_obs: list[dict], db_path: Path = DEFAULT_DB_PATH) -> dict[str, object]:
    json_path = Path("data/observations_store.json")
    json_obs_count = 0
    if json_path.exists():
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            rows = raw.get("observations", []) if isinstance(raw, dict) else raw
            if isinstance(rows, list):
                json_obs_count = len(rows)
        except Exception:
            json_obs_count = 0

    model_count = 0
    waqi_count = 0
    for o in all_obs:
        st_name = str(o.get("station_name") or "").lower()
        q_city = str(o.get("query_city") or "").lower()
        if "open-meteo" in st_name or "cams" in st_name or "model" in q_city:
            model_count += 1
        else:
            waqi_count += 1

    db_mtime = "N/A"
    if db_path.exists():
        try:
            db_mtime = pd.Timestamp(db_path.stat().st_mtime, unit="s", tz="Asia/Kolkata").strftime("%Y-%m-%d %H:%M IST")
        except Exception:
            db_mtime = "Available"

    return {
        "waqi_count": waqi_count,
        "model_count": model_count,
        "json_obs_count": json_obs_count,
        "json_exists": json_path.exists(),
        "db_mtime": db_mtime,
    }


def main() -> None:
    _inject_data_quality_theme()

    st.markdown(
        """
        <div class="eco-topbar">
            <div>
                <div class="eco-breadcrumb">EcoHealth &nbsp;/&nbsp; <strong>Data Quality &amp; System Health</strong></div>
                <div class="eco-sub">Source breakdown, freshness audit, plausibility rules, and LLM reference sources.</div>
            </div>
            <div class="eco-pill">
                <span class="eco-dot"></span>Quality Audit
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    stations = list_stations()
    all_obs = get_observations(limit=5000)
    total_obs = len(all_obs)
    valid_obs = sum(1 for o in all_obs if int(o.get("is_valid", 1)) == 1)
    invalid_obs = total_obs - valid_obs
    stale_obs = sum(1 for o in all_obs if int(o.get("is_stale", 0)) == 1)
    fresh_obs = total_obs - stale_obs

    avg_comp = (
        round(
            sum(float(o.get("completeness_ratio") or 0.0) for o in all_obs) / total_obs * 100,
            1,
        )
        if total_obs > 0
        else 0.0
    )

    # Top 4 KPI Cards
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        _render_dq_card(
            "Stored Observations",
            str(total_obs),
            f"Across {len(stations)} monitored station(s)",
            accent="#133A2A",
        )
    with m2:
        _render_dq_card(
            "Average Completeness",
            f"{avg_comp}%",
            "Mean pollutant coverage ratio",
            accent="#1F7A5A",
            value_color="#1F7A5A",
        )
    with m3:
        _render_dq_card(
            "Fresh vs. Stale Records",
            f"{fresh_obs} / {stale_obs}",
            "Fresh readings / Stale timestamps",
            accent="#D97706" if stale_obs > 0 else "#1F7A5A",
            value_color="#D97706" if stale_obs > 0 else "#133A2A",
        )
    with m4:
        _render_dq_card(
            "Valid vs. Invalid Records",
            f"{valid_obs} / {invalid_obs}",
            "Plausibility & range check status",
            accent="#DC2626" if invalid_obs > 0 else "#1F7A5A",
            value_color="#DC2626" if invalid_obs > 0 else "#133A2A",
        )

    # Source / Ingestion Mode Breakdown
    src_info = _summarize_sources(all_obs)
    st.markdown('<div class="eco-section-title">Source &amp; Ingestion Breakdown</div>', unsafe_allow_html=True)
    s1, s2, s3 = st.columns(3)
    with s1:
        _render_dq_card(
            "Station / WAQI Records",
            str(src_info["waqi_count"]),
            "Station observations in SQLite",
            accent="#133A2A",
            value_size="1.35rem",
        )
    with s2:
        _render_dq_card(
            "Model / CAMS Records",
            str(src_info["model_count"]),
            "Model-derived station series in SQLite",
            accent="#1F7A5A",
            value_size="1.35rem",
        )
    with s3:
        json_sub = (
            f"{src_info['json_obs_count']} records in observations_store.json • DB updated {src_info['db_mtime']}"
            if src_info["json_exists"]
            else f"observations_store.json not found • DB updated {src_info['db_mtime']}"
        )
        _render_dq_card(
            "JSON Store & DB Sync",
            "Synced" if src_info["json_exists"] else "DB Only",
            json_sub,
            accent="#315B48",
            value_size="1.35rem",
        )

    # Observation Freshness & Validity Breakdown + LLM Guidance Source Info
    c_left, c_right = st.columns(2)

    with c_left:
        with st.container(border=True):
            st.markdown("**Observation Freshness & Validity Breakdown**")
            fig_fv = go.Figure(
                go.Bar(
                    x=["Fresh", "Stale", "Valid", "Invalid"],
                    y=[fresh_obs, stale_obs, valid_obs, invalid_obs],
                    marker_color=["#1F7A5A", "#D97706", "#133A2A", "#DC2626"],
                    text=[fresh_obs, stale_obs, valid_obs, invalid_obs],
                    textposition="outside",
                )
            )
            fig_fv.update_layout(
                height=290,
                margin={"l": 36, "r": 16, "t": 22, "b": 34},
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"color": "#133A2A"},
                xaxis={"tickfont": {"color": "#133A2A"}, "showgrid": False, "linecolor": "#B8CFC1"},
                yaxis={"title": "Records", "tickfont": {"color": "#133A2A"}, "gridcolor": "#DFEAE3"},
            )
            st.plotly_chart(fig_fv, use_container_width=True, key="dq_fresh_valid_chart")

    with c_right:
        st.markdown(
            """
            <div class="eco-panel" style="border-left-color:#133A2A;margin-top:0;">
                <div class="eco-panel-title">LLM Guidance APIs &amp; Advisory Reference Sites</div>
                <div class="eco-panel-body">
                    <ul class="eco-panel-list">
                        <li><strong>Groq API (<code>api.groq.com</code>):</strong> Generates activity guidance text via <code>llama-3.3-70b-versatile</code> when <code>GROQ_API_KEY</code> is configured.</li>
                        <li><strong>Google Gemini API (<code>generativelanguage.googleapis.com</code>):</strong> Fallback LLM endpoint via <code>gemini-2.5-flash</code> when <code>GEMINI_API_KEY</code> / <code>GOOGLE_API_KEY</code> is set.</li>
                        <li><strong>Public Air-Quality Advisory References:</strong> Prompts align guidance wording with public health &amp; AQI practices from <strong>CPCB</strong> (India), <strong>AirNow</strong>, and <strong>WHO</strong> while keeping measured AQI and pollutant values unchanged.</li>
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Plausibility & Range Audit Rules Summary
    st.markdown(
        """
        <div class="eco-panel" style="border-left-color:#1F7A5A;">
            <div class="eco-panel-title">Plausibility &amp; Range Audit Rules</div>
            <div class="eco-panel-body">
                <div class="eco-rule-grid">
                    <div class="eco-rule-item"><strong>AQI Bounds (0&ndash;500):</strong> Flags out-of-range or missing AQI values across reported and calculated metrics.</div>
                    <div class="eco-rule-item"><strong>Pollutant Non-Negativity:</strong> Rejects negative concentrations and tracks null/missing values across PM2.5, PM10, NO2, SO2, CO, and O3.</div>
                    <div class="eco-rule-item"><strong>Timestamp &amp; Freshness Gate:</strong> Parses ISO timestamps and flags older or lagging observations as stale rather than dropping history.</div>
                    <div class="eco-rule-item"><strong>Completeness Ratio:</strong> Computes the share of expected pollutant fields populated per observation so partial records remain transparent.</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Per-Station Quality & Freshness Audit + Stale/Gap Watchlist Filter
    if all_obs:
        df_all = pd.DataFrame(all_obs)
        st_col = "station_name" if "station_name" in df_all.columns else "query_city"
        grouped_rows = []
        for st_name, grp in df_all.groupby(st_col, dropna=False):
            ts_series = grp["observation_time"].dropna().astype(str) if "observation_time" in grp.columns else pd.Series(dtype=str)
            latest_ts = max(ts_series) if not ts_series.empty else "N/A"
            st_stale = int(pd.to_numeric(grp.get("is_stale", 0), errors="coerce").fillna(0).sum())
            st_invalid = int((pd.to_numeric(grp.get("is_valid", 1), errors="coerce").fillna(1) == 0).sum())
            st_comp = round(
                float(pd.to_numeric(grp.get("completeness_ratio", 0.0), errors="coerce").fillna(0.0).mean()) * 100,
                1,
            )
            grouped_rows.append(
                {
                    "Station": str(st_name or "Unknown"),
                    "Observations": int(len(grp)),
                    "Avg Completeness (%)": st_comp,
                    "Stale Count": st_stale,
                    "Invalid Count": st_invalid,
                    "Latest Observation": latest_ts,
                }
            )
        df_audit = pd.DataFrame(grouped_rows).sort_values(
            ["Stale Count", "Invalid Count", "Observations"],
            ascending=[False, False, False],
        )

        st.markdown('<div class="eco-section-title">Per-Station Quality &amp; Freshness Audit</div>', unsafe_allow_html=True)
        watchlist_filter = st.selectbox(
            "Watchlist Filter",
            options=[
                "All Stations",
                "Has Stale Records",
                "Incomplete (<100%)",
                "Has Invalid Records",
            ],
            index=0,
            key="dq_station_watchlist_filter",
        )

        if watchlist_filter == "Has Stale Records":
            filtered_audit = df_audit[df_audit["Stale Count"] > 0]
        elif watchlist_filter == "Incomplete (<100%)":
            filtered_audit = df_audit[df_audit["Avg Completeness (%)"] < 100.0]
        elif watchlist_filter == "Has Invalid Records":
            filtered_audit = df_audit[df_audit["Invalid Count"] > 0]
        else:
            filtered_audit = df_audit

        if filtered_audit.empty:
            st.info(f"No stations match the '{watchlist_filter}' filter.")
        else:
            st.dataframe(filtered_audit, use_container_width=True, hide_index=True)

    active_reading: AqiReading | None = st.session_state.get("waqi_last_reading")
    notes: list[str] = []
    if active_reading is not None:
        val = validate_aqi_reading(active_reading)
        notes.extend(str(w) for w in (val.warnings or []))
    if stale_obs > 0:
        notes.append(f"{stale_obs} stored observation(s) are marked stale relative to current/latest timestamps.")
    if invalid_obs > 0:
        notes.append(f"{invalid_obs} stored observation(s) failed plausibility/validity checks.")

    body_html = (
        f'<ul class="eco-panel-list">{"".join(f"<li>{html.escape(n)}</li>" for n in notes)}</ul>'
        if notes
        else "All stored observations pass validity checks with no active quality flags."
    )
    st.markdown(
        f"""
        <div class="eco-panel" style="border-left-color:#133A2A;">
            <div class="eco-panel-title">Quality Findings &amp; Audit Notes</div>
            <div class="eco-panel-body">{body_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


main()