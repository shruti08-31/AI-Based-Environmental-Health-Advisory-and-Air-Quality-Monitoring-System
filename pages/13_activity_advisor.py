import html
import streamlit as st

from config import config
from src.activity import (
    SUPPORTED_ACTIVITIES,
    advise_activity,
    advise_activity_from_reading,
    enrich_guidance_with_llm,
)
from src.api import AqiReading
from src.core import SensitivityGroup, evaluate_aqi_from_reading
from src.database import get_observations, hydrate_sqlite_from_json, initialize_database, list_stations
from src.utils import render_warning_banner


def _inject_activity_advisor_theme() -> None:
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

        /* Green labels & light-green selectboxes with crisp dark-green text */
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

        /* Disclaimer Note Banner */
        .eco-disclaimer {
            background: #EAF3EC;
            border: 1px solid #CBE0D1;
            border-left: 4px solid #133A2A;
            border-radius: 12px;
            padding: 11px 16px;
            font-size: 0.84rem;
            color: #1A4D38;
            margin: 0.65rem 0 1rem 0;
        }

        /* Left Status & Recommendation Cards */
        .eco-card {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-radius: 16px;
            padding: 18px 20px;
            box-shadow: 0 2px 8px rgba(19, 58, 42, 0.03);
            margin-bottom: 0.85rem;
        }
        .eco-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .eco-card-label {
            font-size: 0.81rem;
            font-weight: 500;
            color: #5E7167;
        }
        .eco-badge {
            font-size: 0.72rem;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 999px;
        }
        .eco-card-value {
            font-size: 1.55rem;
            font-weight: 700;
            color: #133A2A;
            line-height: 1.2;
            margin-bottom: 6px;
        }
        .eco-card-sub {
            font-size: 0.78rem;
            color: #6B7E74;
        }

        /* Right Guidance Panels */
        .eco-panel {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-left: 4px solid #133A2A;
            border-radius: 14px;
            padding: 16px 20px;
            margin-bottom: 0.85rem;
            box-shadow: 0 2px 6px rgba(19, 58, 42, 0.025);
        }
        .eco-panel-title {
            font-size: 0.93rem;
            font-weight: 700;
            color: #133A2A;
            margin-bottom: 6px;
        }
        .eco-panel-body {
            font-size: 0.86rem;
            color: #2D4238;
            line-height: 1.55;
        }
        .eco-panel-list {
            margin: 4px 0 0 0;
            padding-left: 18px;
            color: #2D4238;
            font-size: 0.86rem;
            line-height: 1.6;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _severity_palette(category: str) -> tuple[str, str, str]:
    s = (category or "").strip().lower()
    if "good" in s:
        return ("#E4F5EC", "#166534", "#1F7A5A")
    if "satisfactory" in s:
        return ("#ECFCCB", "#3F6212", "#4D7C0F")
    if "moderate" in s:
        return ("#FEF6E6", "#9A5B13", "#D97706")
    if "poor" in s and "very" not in s:
        return ("#FDECE4", "#9A3412", "#EA580C")
    if "very poor" in s or "unhealthy" in s:
        return ("#FBE7E7", "#991B1B", "#DC2626")
    if "severe" in s:
        return ("#F3E8FF", "#6B21A8", "#7E22CE")
    return ("#EEF3F0", "#4A6055", "#5E7167")


def _recommendation_accent(rec: str) -> str:
    r = (rec or "").strip().lower()
    if any(k in r for k in ("avoid", "not recommended", "indoor only", "cancel")):
        return "#DC2626"
    if any(k in r for k in ("caution", "reduce", "limit", "shorten", "modify")):
        return "#D97706"
    if any(k in r for k in ("suitable", "safe", "proceed", "recommended", "favorable")):
        return "#1F7A5A"
    return "#133A2A"


def _matches_area(reading: AqiReading, target_area: str) -> bool:
    t = target_area.strip().lower()
    if not t:
        return False
    st = (reading.station_name or "").strip().lower()
    q = (reading.query or "").strip().lower()
    return t == st or t == q or t in st or (q and q in t)


def _available_areas() -> list[str]:
    names: list[str] = []
    try:
        initialize_database()
        rows = list_stations()
        if not rows:
            hydrate_sqlite_from_json()
            rows = list_stations()
        for r in rows:
            st_name = str(r.get("station_name") or "").strip()
            if st_name and st_name not in names:
                names.append(st_name)
    except Exception:
        pass

    last_reading: AqiReading | None = st.session_state.get("waqi_last_reading")
    if last_reading and last_reading.station_name and last_reading.station_name not in names:
        names.insert(0, last_reading.station_name)

    selected = (st.session_state.get("selected_location") or "").strip()
    if selected and selected not in names:
        names.insert(0, selected)

    if config.default_location and config.default_location not in names:
        names.append(config.default_location)

    return names or ["Delhi (CPCB City Composite)"]


def _reading_for_area(target_area: str) -> AqiReading | None:
    last_reading: AqiReading | None = st.session_state.get("waqi_last_reading")
    if last_reading is not None and _matches_area(last_reading, target_area):
        return last_reading

    try:
        initialize_database()
        rows = get_observations(location=target_area, limit=50)
        if not rows:
            hydrate_sqlite_from_json()
            rows = get_observations(location=target_area, limit=50)
    except Exception:
        rows = []

    if not rows:
        return None

    latest = rows[-1]
    return AqiReading(
        query=str(latest.get("query_city") or target_area),
        station_name=str(latest.get("station_name") or target_area),
        aqi=latest.get("waqi_reported_aqi"),
        aqi_raw=latest.get("waqi_aqi_raw", latest.get("waqi_reported_aqi")),
        dominant_pollutant=latest.get("dominant_pollutant"),
        pollutants={
            k: latest.get(k)
            for k in ("pm25", "pm10", "no2", "so2", "co", "o3")
        },
        latitude=latest.get("latitude"),
        longitude=latest.get("longitude"),
        observation_time=latest.get("observation_time"),
    )


@st.cache_data(ttl=600, show_spinner=False)
def _cached_llm_guidance(
    cache_key: tuple[str, str, str, str, str, str, str],
    guidance_obj: object,
    station_label: str,
    pollutants: dict[str, object] | None,
    use_llm: bool = True,
) -> tuple[str, list[str], str, str]:
    return enrich_guidance_with_llm(
        guidance=guidance_obj,
        station_label=station_label,
        pollutants=pollutants,
        use_llm=use_llm,
    )


def main() -> None:
    _inject_activity_advisor_theme()

    area_options = _available_areas()
    last_reading: AqiReading | None = st.session_state.get("waqi_last_reading")
    preferred_area = (
        (st.session_state.get("selected_location") or "").strip()
        or (last_reading.station_name if last_reading and last_reading.station_name else "")
        or area_options[0]
    )
    if preferred_area not in area_options:
        area_options.insert(0, preferred_area)
    default_idx = area_options.index(preferred_area)

    st.markdown(
        f"""
        <div class="eco-topbar">
            <div>
                <div class="eco-breadcrumb">EcoHealth &nbsp;/&nbsp; <strong>Activity Advisor</strong></div>
                <div class="eco-sub">Area-specific activity guidance for <strong>{html.escape(preferred_area)}</strong>.</div>
            </div>
            <div class="eco-pill">
                <span class="eco-dot"></span>{html.escape(preferred_area)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    f_area, f_act, f_sens, f_btn = st.columns([2.2, 1.5, 1.5, 1.0])
    with f_area:
        active_area = st.selectbox(
            "Area / Monitoring Station",
            options=area_options,
            index=default_idx,
            key="activity_advisor_area_select",
        )
    with f_act:
        activity_choice = st.selectbox(
            "Activity",
            options=list(SUPPORTED_ACTIVITIES),
            index=0,
            key="activity_advisor_activity_select",
        )
    with f_sens:
        sensitivity_choice = st.selectbox(
            "Sensitivity Category",
            options=[
                SensitivityGroup.GENERAL.value,
                SensitivityGroup.SENSITIVE.value,
            ],
            index=0,
            key="activity_advisor_sensitivity_select",
        )
    with f_btn:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("Refresh Guidance", width="stretch", key="btn_refresh_activity_guidance"):
            _cached_llm_guidance.clear()

    st.session_state["selected_location"] = active_area
    area_reading = _reading_for_area(active_area)

    if area_reading is None:
        render_warning_banner(
            f"No observation stored or fetched yet for '{active_area}'. Fetch or select a reading for this area first.",
            is_placeholder=True,
        )
        guidance = advise_activity(
            activity=activity_choice,
            aqi_category="Unavailable",
            calculated_aqi=None,
            pollutants=None,
            sensitivity_group=sensitivity_choice,
        )
        station_ref = active_area
        pollutants_data = None
    else:
        eng = evaluate_aqi_from_reading(area_reading)
        guidance = advise_activity_from_reading(
            activity=activity_choice,
            reading=area_reading,
            aqi_result=eng,
            sensitivity_group=sensitivity_choice,
        )
        station_ref = area_reading.station_name or active_area
        pollutants_data = area_reading.pollutants

    pol_sig = ",".join(
        f"{k}:{v}"
        for k, v in sorted((pollutants_data or {}).items())
        if v is not None
    )
    cache_key = (
        str(station_ref),
        str(guidance.activity),
        str(guidance.sensitivity_group),
        str(guidance.calculated_aqi),
        str(guidance.aqi_category),
        str(guidance.recommendation),
        pol_sig,
    )
    exp_text, precs_list, alt_text, guidance_source = _cached_llm_guidance(
        cache_key=cache_key,
        guidance_obj=guidance,
        station_label=str(station_ref),
        pollutants=pollutants_data,
        use_llm=True,
    )

    st.markdown(
        f'<div class="eco-disclaimer">{html.escape(str(guidance.disclaimer))} &bull; <strong>Area:</strong> {html.escape(str(station_ref))} &bull; <strong>Guidance Source:</strong> {html.escape(guidance_source)}</div>',
        unsafe_allow_html=True,
    )

    badge_bg, badge_fg, sev_accent = _severity_palette(guidance.aqi_category)
    rec_accent = _recommendation_accent(guidance.recommendation)
    aqi_val_txt = str(guidance.calculated_aqi) if guidance.calculated_aqi is not None else "N/A"
    precautions_items = "".join(f"<li>{html.escape(str(p))}</li>" for p in precs_list)

    left, right = st.columns([1, 2])
    with left:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid {sev_accent};">
                <div class="eco-card-header">
                    <span class="eco-card-label">Air Quality Status</span>
                    <span class="eco-badge" style="background:{badge_bg};color:{badge_fg};">{html.escape(str(guidance.aqi_category))}</span>
                </div>
                <div class="eco-card-value" style="color:{sev_accent};">AQI {html.escape(aqi_val_txt)}</div>
                <div class="eco-card-sub">{html.escape(str(station_ref))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid {rec_accent};">
                <div class="eco-card-label">Recommendation</div>
                <div class="eco-card-value" style="font-size:1.38rem;color:{rec_accent};">{html.escape(str(guidance.recommendation))}</div>
                <div class="eco-card-sub">Activity: {html.escape(str(guidance.activity))} &bull; {html.escape(str(sensitivity_choice))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            f"""
            <div class="eco-panel" style="border-left-color:#133A2A;">
                <div class="eco-panel-title">Explanation</div>
                <div class="eco-panel-body">{html.escape(exp_text)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="eco-panel" style="border-left-color:#D97706;">
                <div class="eco-panel-title">Precautions</div>
                <ul class="eco-panel-list">{precautions_items}</ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="eco-panel" style="border-left-color:#1F7A5A;">
                <div class="eco-panel-title">Alternative Activity</div>
                <div class="eco-panel-body">{html.escape(alt_text)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


main()