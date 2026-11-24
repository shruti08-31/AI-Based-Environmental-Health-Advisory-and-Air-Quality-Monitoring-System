import streamlit as st

from src.api import AqiReading
from src.core import SensitivityGroup, evaluate_aqi_from_reading, generate_health_advisory
from src.utils import (
    render_aqi_indicator,
    render_info_panel,
    render_metric_card,
    render_page_header,
    render_warning_banner,
)


def _format_bullets(items: list[str]) -> str:
    return "<br>".join(f"• {line}" for line in items)


def main() -> None:
    reading: AqiReading | None = st.session_state.get("waqi_last_reading")

    render_page_header(
        title="Health Advisory",
        subtitle="Deterministic public-health guidance by AQI tier and sensitivity profile.",
        is_placeholder=reading is None,
    )

    group_choice = st.selectbox(
        "Sensitivity Profile",
        options=[
            SensitivityGroup.GENERAL.value,
            SensitivityGroup.SENSITIVE.value,
        ],
        index=0,
        key="health_advisory_sensitivity_select",
    )

    if reading is None:
        render_warning_banner(
            "No live WAQI reading is available yet. Displaying baseline placeholder guidance until data is fetched.",
            is_placeholder=True,
        )
        advisory = generate_health_advisory("Unavailable", sensitivity_group=group_choice)
        left, right = st.columns([1, 2])
        with left:
            render_aqi_indicator("Pending", "Awaiting live AQI evaluation", is_placeholder=True)
            render_metric_card("Urgency Level", advisory.urgency_level, "No active telemetry", is_placeholder=True)
        with right:
            render_info_panel("General Precautions", _format_bullets(advisory.general_precautions), is_placeholder=True)
            render_info_panel("Outdoor Activity Precautions", _format_bullets(advisory.outdoor_activity_precautions), is_placeholder=True)
        st.caption(advisory.disclaimer)
        return

    aqi_res = evaluate_aqi_from_reading(reading)
    advisory = generate_health_advisory(
        category=aqi_res.category,
        sensitivity_group=group_choice,
        dominant_pollutant=aqi_res.dominant_pollutant,
    )

    st.info(advisory.disclaimer)

    left, right = st.columns([1, 2])
    with left:
        render_aqi_indicator(
            severity=advisory.category,
            status_text=aqi_res.category_explanation,
            is_placeholder=False,
        )
        render_metric_card(
            label="Urgency Level",
            value=advisory.urgency_level,
            meta=f"Calculated CPCB AQI: {aqi_res.calculated_aqi if aqi_res.calculated_aqi is not None else 'N/A'}",
            is_placeholder=False,
        )
        render_metric_card(
            label="Dominant Pollutant",
            value=(aqi_res.dominant_pollutant or "None").upper(),
            meta=f"WAQI API AQI: {reading.aqi if reading.aqi is not None else 'N/A'}",
            is_placeholder=False,
        )

    with right:
        render_info_panel(
            title="General Precautions",
            body=_format_bullets(advisory.general_precautions),
            is_placeholder=False,
        )
        render_info_panel(
            title="Sensitive-Group Precautions",
            body=_format_bullets(advisory.sensitive_group_precautions),
            is_placeholder=False,
        )
        render_info_panel(
            title="Exposure Reduction Suggestions",
            body=_format_bullets(advisory.exposure_reduction_suggestions),
            is_placeholder=False,
        )
        render_info_panel(
            title="Outdoor Activity Precautions",
            body=_format_bullets(advisory.outdoor_activity_precautions),
            is_placeholder=False,
        )
        render_info_panel(
            title="Deterministic Rules Applied",
            body=_format_bullets(advisory.rules_applied),
            is_placeholder=False,
        )


main()