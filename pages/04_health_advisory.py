import html
import streamlit as st

from config import config
from src.api import AqiReading
from src.chatbot import generate_assistant_response, route_query_to_services
from src.core import SensitivityGroup, evaluate_aqi_from_reading, generate_health_advisory
from src.utils import render_warning_banner


def _inject_health_advisory_theme() -> None:
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

        /* Green Selectbox label & light-green input with crisp dark-green text */
        [data-testid="stSelectbox"] label,
        [data-testid="stSelectbox"] label p {
            color: #1B5E3F !important;
            font-weight: 600 !important;
            font-size: 0.88rem !important;
        }
        [data-testid="stSelectbox"] > div > div,
        [data-testid="stSelectbox"] [data-baseweb="select"] > div {
            background-color: #EAF4EC !important;
            border-color: #B4D6BE !important;
            border-radius: 10px !important;
        }
        [data-testid="stSelectbox"] [data-baseweb="select"] *,
        [data-testid="stSelectbox"] [data-baseweb="select"] div,
        [data-testid="stSelectbox"] [data-baseweb="select"] span,
        [data-testid="stSelectbox"] [data-baseweb="select"] input {
            color: #133A2A !important;
            -webkit-text-fill-color: #133A2A !important;
            opacity: 1 !important;
            font-weight: 600 !important;
        }
        [data-testid="stSelectbox"] [data-baseweb="select"] svg {
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

        /* Disclaimer banner */
        .eco-disclaimer {
            background: #EAF4EC;
            border: 1px solid #C6DFCE;
            border-left: 4px solid #1F7A5A;
            border-radius: 12px;
            padding: 12px 16px;
            font-size: 0.84rem;
            color: #183C2C;
            margin: 0.6rem 0 1rem 0;
        }

        /* Left Column KPI Cards */
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
            font-size: 0.82rem;
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
            font-size: 1.65rem;
            font-weight: 700;
            color: #133A2A;
            line-height: 1.2;
            margin-bottom: 6px;
        }
        .eco-card-sub {
            font-size: 0.80rem;
            color: #4F6359;
            line-height: 1.45;
        }

        /* Right Column Precaution Panels */
        .eco-panel {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-left: 4px solid #133A2A;
            border-radius: 14px;
            padding: 16px 20px;
            margin-bottom: 0.8rem;
            box-shadow: 0 2px 6px rgba(19, 58, 42, 0.025);
        }
        .eco-panel-title {
            font-size: 0.94rem;
            font-weight: 700;
            color: #133A2A;
            margin-bottom: 8px;
        }
        .eco-panel-list {
            margin: 0;
            padding-left: 18px;
            color: #2B3F35;
            font-size: 0.86rem;
            line-height: 1.6;
        }

        /* LLM + Trusted Website Advisory Card */
        .eco-web-box {
            background: linear-gradient(135deg, #F3F8F4 0%, #E7F2EA 100%);
            border: 1px solid #CBE0D1;
            border-radius: 16px;
            padding: 20px 22px;
            margin-top: 0.9rem;
            color: #16261E;
        }
        .eco-web-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .eco-web-title {
            font-size: 1.0rem;
            font-weight: 700;
            color: #133A2A;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _severity_palette(category: str) -> tuple[str, str, str]:
    """Returns (badge_bg, badge_fg, accent_hex) for AQI severity."""
    c = (category or "").strip().lower()
    if "good" in c:
        return ("#E4F5EC", "#166534", "#1F7A5A")
    if "satisfactory" in c:
        return ("#ECF7E8", "#3F6212", "#4D7C0F")
    if "moderate" in c:
        return ("#FEF6E6", "#9A5B13", "#D97706")
    if "poor" in c and "very" not in c:
        return ("#FDECE4", "#9A3412", "#EA580C")
    if "very poor" in c or "unhealthy" in c or "severe" in c:
        return ("#FBE7E7", "#991B1B", "#DC2626")
    return ("#EEF3F0", "#4A6055", "#5E7167")


def _render_list_panel(title: str, items: list[str], accent: str = "#133A2A") -> None:
    li_html = "".join(f"<li>{html.escape(line)}</li>" for line in items)
    st.markdown(
        f"""
        <div class="eco-panel" style="border-left-color:{accent};">
            <div class="eco-panel-title">{html.escape(title)}</div>
            <ul class="eco-panel-list">{li_html}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_grounded_web_advisory(
    station_name: str,
    category: str,
    dominant_pollutant: str,
    sensitivity_group: str,
    calculated_aqi: int | float | None,
    has_groq_key: bool,
) -> tuple[str, list[str], str]:
    """Fetches authoritative WHO/EPA/CPCB guidance and synthesizes a concise advisory via LLM."""
    reading_ctx: AqiReading | None = st.session_state.get("waqi_last_reading")
    prompt = (
        f"Provide actionable public-health precautions and exposure-reduction guidance from trusted "
        f"government and public-health websites (such as WHO, US EPA, CPCB India, CDC, AirNow) for "
        f"the '{sensitivity_group}' sensitivity group when air quality at {station_name} is "
        f"'{category}' (CPCB AQI: {calculated_aqi}) with dominant pollutant {dominant_pollutant}. "
        f"Cite each website name and clickable link clearly."
    )
    routed = route_query_to_services(
        user_query=prompt,
        current_reading=reading_ctx,
        use_web_search=True,
    )
    res = generate_assistant_response(
        user_query=prompt,
        routed=routed,
        app_config=config,
    )
    engine_label = (
        f"Groq ({res.model_name}) + Trusted Web Search"
        if res.used_llm
        else "Deterministic + Trusted Web Search"
    )
    return res.answer, res.sources_used, engine_label


def main() -> None:
    _inject_health_advisory_theme()

    reading: AqiReading | None = st.session_state.get("waqi_last_reading")

    station_badge = (
        html.escape(reading.station_name or reading.query)
        if reading is not None
        else "Baseline Profile"
    )
    st.markdown(
        f"""
        <div class="eco-topbar">
            <div>
                <div class="eco-breadcrumb">EcoHealth &nbsp;/&nbsp; <strong>Health Advisory</strong></div>
                <div class="eco-sub">Deterministic public-health guidance by AQI tier, sensitivity profile, and trusted health agencies.</div>
            </div>
            <div class="eco-pill">
                <span class="eco-dot"></span>{station_badge}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    ctrl_left, ctrl_right = st.columns([2.2, 1.2])
    with ctrl_left:
        group_choice = st.selectbox(
            "Sensitivity Profile",
            options=[
                SensitivityGroup.GENERAL.value,
                SensitivityGroup.SENSITIVE.value,
            ],
            index=0,
            key="health_advisory_sensitivity_select",
        )
    with ctrl_right:
        include_web_llm = st.toggle(
            "Include WHO / EPA / CPCB Web Guidance (LLM)",
            value=True,
            key="health_advisory_web_llm_toggle",
        )

    if reading is None:
        render_warning_banner(
            "No live WAQI reading is available yet. Displaying baseline placeholder guidance until data is fetched.",
            is_placeholder=True,
        )
        advisory = generate_health_advisory("Unavailable", sensitivity_group=group_choice)
        left, right = st.columns([1, 2])
        with left:
            st.markdown(
                """
                <div class="eco-card" style="border-top:4px solid #94A3B8;">
                    <div class="eco-card-header">
                        <span class="eco-card-label">AQI Status</span>
                        <span class="eco-badge" style="background:#EEF3F0;color:#4A6055;">Pending</span>
                    </div>
                    <div class="eco-card-value">Awaiting Data</div>
                    <div class="eco-card-sub">Fetch a live station to evaluate AQI health tier.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                f"""
                <div class="eco-card" style="border-top:4px solid #315B48;">
                    <div class="eco-card-header">
                        <span class="eco-card-label">Urgency Level</span>
                    </div>
                    <div class="eco-card-value">{html.escape(advisory.urgency_level)}</div>
                    <div class="eco-card-sub">No active telemetry</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with right:
            _render_list_panel("General Precautions", advisory.general_precautions, accent="#315B48")
            _render_list_panel("Outdoor Activity Precautions", advisory.outdoor_activity_precautions, accent="#1F7A5A")

        st.markdown(
            f'<div class="eco-disclaimer">{html.escape(advisory.disclaimer)}</div>',
            unsafe_allow_html=True,
        )
        return

    aqi_res = evaluate_aqi_from_reading(reading)
    advisory = generate_health_advisory(
        category=aqi_res.category,
        sensitivity_group=group_choice,
        dominant_pollutant=aqi_res.dominant_pollutant,
    )

    badge_bg, badge_fg, accent_hex = _severity_palette(advisory.category)
    calc_aqi_txt = str(aqi_res.calculated_aqi) if aqi_res.calculated_aqi is not None else "N/A"
    waqi_aqi_txt = str(reading.aqi) if reading.aqi is not None else "N/A"
    dom_pol_txt = (aqi_res.dominant_pollutant or "None").upper()

    st.markdown(
        f'<div class="eco-disclaimer"><strong>Medical Disclaimer:</strong> {html.escape(advisory.disclaimer)}</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1, 2])
    with left:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid {accent_hex};">
                <div class="eco-card-header">
                    <span class="eco-card-label">CPCB Health Tier</span>
                    <span class="eco-badge" style="background:{badge_bg};color:{badge_fg};">{html.escape(advisory.category)}</span>
                </div>
                <div class="eco-card-value" style="color:{accent_hex};">{html.escape(advisory.category)}</div>
                <div class="eco-card-sub">{html.escape(aqi_res.category_explanation)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #133A2A;">
                <div class="eco-card-header">
                    <span class="eco-card-label">Urgency Level</span>
                    <span class="eco-badge" style="background:#EAF3EC;color:#166534;">CPCB AQI {html.escape(calc_aqi_txt)}</span>
                </div>
                <div class="eco-card-value">{html.escape(advisory.urgency_level)}</div>
                <div class="eco-card-sub">Calculated CPCB AQI: {html.escape(calc_aqi_txt)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #1F7A5A;">
                <div class="eco-card-header">
                    <span class="eco-card-label">Dominant Pollutant</span>
                </div>
                <div class="eco-card-value">{html.escape(dom_pol_txt)}</div>
                <div class="eco-card-sub">WAQI API AQI: {html.escape(waqi_aqi_txt)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        _render_list_panel("General Precautions", advisory.general_precautions, accent=accent_hex)
        _render_list_panel("Sensitive-Group Precautions", advisory.sensitive_group_precautions, accent="#D97706")
        _render_list_panel("Exposure Reduction Suggestions", advisory.exposure_reduction_suggestions, accent="#1F7A5A")
        _render_list_panel("Outdoor Activity Precautions", advisory.outdoor_activity_precautions, accent="#133A2A")
        _render_list_panel("Deterministic Rules Applied", advisory.rules_applied, accent="#4D6B5C")

    if include_web_llm:
        with st.spinner("Fetching authoritative health guidance from WHO, EPA, CPCB & synthesizing advisory..."):
            web_answer, web_sources, engine_used = _fetch_grounded_web_advisory(
                station_name=reading.station_name or reading.query,
                category=advisory.category,
                dominant_pollutant=dom_pol_txt,
                sensitivity_group=group_choice,
                calculated_aqi=aqi_res.calculated_aqi,
                has_groq_key=config.has_groq_api_key,
            )

        with st.container(border=True):
            st.markdown(f"#### Authoritative Agency Guidance (WHO / EPA / CPCB) — `{engine_used}`")
            st.markdown(web_answer)
            if web_sources:
                with st.expander("Verified Websites & Knowledge Base Sources Cited", expanded=True):
                    for src in web_sources:
                        st.markdown(f"- {src}")


main()