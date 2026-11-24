import streamlit as st

from src.activity import SUPPORTED_ACTIVITIES, advise_activity, advise_activity_from_reading
from src.api import AqiReading
from src.core import SensitivityGroup, evaluate_aqi_from_reading
from src.utils import (
    render_aqi_indicator,
    render_info_panel,
    render_metric_card,
    render_page_header,
    render_warning_banner,
)


def main() -> None:
    render_page_header(
        title="Activity Advisor",
        subtitle="Activity suitability guidance for walking, running, cycling, outdoor exercise, and indoor exercise.",
        is_placeholder=False,
    )

    c1, c2 = st.columns(2)
    with c1:
        activity_choice = st.selectbox(
            "Activity",
            options=list(SUPPORTED_ACTIVITIES),
            index=0,
            key="activity_advisor_activity_select",
        )
    with c2:
        sensitivity_choice = st.selectbox(
            "Sensitivity Category",
            options=[
                SensitivityGroup.GENERAL.value,
                SensitivityGroup.SENSITIVE.value,
            ],
            index=0,
            key="activity_advisor_sensitivity_select",
        )

    reading: AqiReading | None = st.session_state.get("waqi_last_reading")

    if reading is None:
        render_warning_banner(
            "No live WAQI reading is loaded yet. Showing general placeholder guidance until a station reading is fetched.",
            is_placeholder=True,
        )
        guidance = advise_activity(
            activity=activity_choice,
            aqi_category="Unavailable",
            calculated_aqi=None,
            pollutants=None,
            sensitivity_group=sensitivity_choice,
        )
    else:
        eng = evaluate_aqi_from_reading(reading)
        guidance = advise_activity_from_reading(
            activity=activity_choice,
            reading=reading,
            aqi_result=eng,
            sensitivity_group=sensitivity_choice,
        )

    st.info(guidance.disclaimer)

    left, right = st.columns([1, 2])
    with left:
        render_aqi_indicator(
            severity=guidance.aqi_category,
            status_text=f"Calculated AQI: {guidance.calculated_aqi if guidance.calculated_aqi is not None else 'N/A'}",
            is_placeholder=reading is None,
        )
        render_metric_card(
            label="Recommendation",
            value=guidance.recommendation,
            meta=f"Activity: {guidance.activity}",
            is_placeholder=reading is None,
        )
    with right:
        render_info_panel(
            title="Explanation",
            body=guidance.explanation,
            is_placeholder=reading is None,
        )
        render_info_panel(
            title="Precautions",
            body="<br>".join(f"• {p}" for p in guidance.precautions),
            is_placeholder=reading is None,
        )
        render_info_panel(
            title="Alternative Activity",
            body=guidance.alternative_activity,
            is_placeholder=reading is None,
        )


main()