import streamlit as st

from config import config
from src.database import hydrate_sqlite_from_json, initialize_database
from src.utils import apply_base_theme


def build_navigation() -> st.navigation:
    overview = st.Page("pages/01_overview.py", title="Overview", default=True)
    live_aqi = st.Page("pages/02_live_aqi_monitoring.py", title="Live AQI Monitoring")
    pollutants = st.Page("pages/03_pollutant_intelligence.py", title="Pollutant Intelligence")
    health = st.Page("pages/04_health_advisory.py", title="Health Advisory")
    assistant = st.Page("pages/05_ai_environmental_assistant.py", title="AI Environmental Assistant")

    anomaly = st.Page("pages/07_anomaly_detection.py", title="Anomaly Detection")
    historical = st.Page("pages/08_historical_analytics.py", title="Historical Analytics")
    comparison = st.Page("pages/09_location_comparison.py", title="Location Comparison")
    geographic = st.Page("pages/10_geographic_monitoring.py", title="Geographic Monitoring")
    weather = st.Page("pages/11_weather_analysis.py", title="Weather Analysis")

    alerts = st.Page("pages/12_smart_alerts.py", title="Smart Alerts")
    activity = st.Page("pages/13_activity_advisor.py", title="Activity Advisor")
    reports = st.Page("pages/14_environmental_reports.py", title="Environmental Reports")
    data_quality = st.Page("pages/15_data_quality.py", title="Data Quality")

    return st.navigation(
        {
            "Core Monitoring": [
                overview,
                live_aqi,
                pollutants,
                health,
                assistant,
            ],
            "Analytics & Forecasting": [
                anomaly,
                historical,
                comparison,
                geographic,
                weather,
            ],
            "Advisories, Alerts & Governance": [
                alerts,
                activity,
                reports,
                data_quality,
            ],
        },
        position="sidebar",
    )


def main() -> None:
    st.set_page_config(
        page_title=config.app_name,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_base_theme()

    initialize_database()
    hydrate_sqlite_from_json()

    if "selected_location" not in st.session_state:
        st.session_state["selected_location"] = config.default_location

    with st.sidebar:
        st.markdown(f"### {config.app_name}")
        st.caption(f"Environment: `{config.app_env}`")
        location_input = st.text_input(
            "Target Location",
            value=st.session_state["selected_location"],
            key="sidebar_location_input",
        )
        st.session_state["selected_location"] = location_input.strip() or config.default_location
        st.divider()

    nav = build_navigation()
    nav.run()


if __name__ == "__main__":
    main()