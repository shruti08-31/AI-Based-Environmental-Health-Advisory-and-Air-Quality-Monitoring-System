import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.api import POLLUTANT_KEYS, AqiReading
from src.core import evaluate_aqi_from_reading
from src.intelligence import analyze_pollutants_from_reading, generate_source_insights
from src.utils import (
    render_info_panel,
    render_metric_card,
    render_page_header,
    render_pollutant_card,
    render_warning_banner,
)


def _render_comparison_and_subindex_charts(
    raw_rows: list[dict[str, object]],
    sub_rows: list[dict[str, object]],
) -> None:
    c_left, c_right = st.columns(2)

    with c_left:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown("**Pollutant Raw Measurement Comparison**")
        if not raw_rows:
            st.caption("No numeric pollutant measurements available to plot.")
        else:
            df_raw = pd.DataFrame(raw_rows)
            fig_raw = go.Figure(
                go.Bar(
                    x=df_raw["Pollutant"],
                    y=df_raw["Raw Value"],
                    marker_color="#0284C7",
                )
            )
            fig_raw.update_layout(
                height=300,
                margin={"l": 40, "r": 20, "t": 20, "b": 40},
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#F8FAFC",
                xaxis={"title": "Pollutant"},
                yaxis={"title": "Measured Value"},
            )
            st.plotly_chart(fig_raw, width="stretch", key="pollutant_raw_comparison_chart")
        st.markdown("</div>", unsafe_allow_html=True)

    with c_right:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown("**CPCB Sub-Index Analysis**")
        if not sub_rows:
            st.caption("No valid pollutant sub-indices calculated.")
        else:
            df_sub = pd.DataFrame(sub_rows)
            fig_sub = go.Figure(
                go.Bar(
                    x=df_sub["Pollutant"],
                    y=df_sub["Sub-Index"],
                    marker_color="#D97706",
                )
            )
            fig_sub.update_layout(
                height=300,
                margin={"l": 40, "r": 20, "t": 20, "b": 40},
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#F8FAFC",
                xaxis={"title": "Pollutant"},
                yaxis={"title": "Calculated Sub-Index (0-500)"},
            )
            st.plotly_chart(fig_sub, width="stretch", key="pollutant_subindex_chart")
        st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    reading: AqiReading | None = st.session_state.get("waqi_last_reading")

    render_page_header(
        title="Pollutant Intelligence",
        subtitle="Pollutant diagnostics, sub-index vs. raw value comparison, combinations, and possible source insights.",
        is_placeholder=reading is None,
    )

    if reading is None:
        render_warning_banner(
            "No live WAQI reading is loaded. Fetch a station in 'Live AQI Monitoring' first; cards below are placeholders.",
            is_placeholder=True,
        )
        for idx in range(0, len(POLLUTANT_KEYS), 3):
            cols = st.columns(3)
            for col, name in zip(cols, POLLUTANT_KEYS[idx : idx + 3]):
                with col:
                    render_pollutant_card(pollutant_name=name.upper(), is_placeholder=True)
        return

    aqi_res = evaluate_aqi_from_reading(reading)
    analysis = analyze_pollutants_from_reading(reading)
    insights = generate_source_insights(analysis)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_metric_card(
            label="Highest Measured Pollutant",
            value=(analysis.highest_measured_pollutant or "None").upper(),
            meta=(
                f"Raw value: {analysis.highest_measured_value:g}"
                if analysis.highest_measured_value is not None
                else "No valid raw value"
            ),
            is_placeholder=False,
        )
    with m2:
        render_metric_card(
            label="Dominant AQI Pollutant",
            value=(analysis.dominant_aqi_pollutant or "None").upper(),
            meta=(
                f"Sub-index: {analysis.highest_sub_index:g}"
                if analysis.highest_sub_index is not None
                else "No sub-index"
            ),
            is_placeholder=False,
        )
    with m3:
        render_metric_card(
            label="Raw vs. Sub-Index Lead",
            value="Different" if analysis.raw_vs_subindex_differs else "Same / N/A",
            meta="Highest raw reading vs. highest sub-index",
            is_placeholder=False,
        )
    with m4:
        render_metric_card(
            label="Near/Over Threshold",
            value=str(len(analysis.approaching_threshold_pollutants)),
            meta=(
                ", ".join(p.upper() for p in analysis.approaching_threshold_pollutants)
                if analysis.approaching_threshold_pollutants
                else "None flagged"
            ),
            is_placeholder=False,
        )

    if analysis.missing_pollutants:
        render_warning_banner(
            "Missing or unmeasured pollutants (not imputed): "
            + ", ".join(p.upper() for p in analysis.missing_pollutants),
            is_placeholder=False,
        )

    st.markdown("### Pollutant-Wise Breakdown")
    raw_chart_rows: list[dict[str, object]] = []
    sub_chart_rows: list[dict[str, object]] = []

    for idx in range(0, len(POLLUTANT_KEYS), 3):
        cols = st.columns(3)
        for col, key in zip(cols, POLLUTANT_KEYS[idx : idx + 3]):
            summ = analysis.pollutant_summaries[key]
            sub_obj = aqi_res.sub_indices[key]
            with col:
                val_str = f"{summ.raw_value:g}" if summ.raw_value is not None else "Missing"
                sub_str = f"{sub_obj.sub_index:g}" if sub_obj.sub_index is not None else "N/A"
                render_pollutant_card(
                    pollutant_name=f"{key.upper()} ({summ.severity})",
                    concentration_label=f"Raw: {val_str} | Sub-Index: {sub_str}",
                    standard_ref=summ.threshold_note,
                    is_placeholder=False,
                )
            if summ.status == "available" and summ.raw_value is not None:
                raw_chart_rows.append({"Pollutant": key.upper(), "Raw Value": summ.raw_value})
            if sub_obj.is_valid_input and sub_obj.sub_index is not None:
                sub_chart_rows.append({"Pollutant": key.upper(), "Sub-Index": sub_obj.sub_index})

    _render_comparison_and_subindex_charts(raw_chart_rows, sub_chart_rows)

    st.markdown("### Detected Pollutant Combinations")
    if not analysis.combinations:
        render_info_panel(
            title="No Configured Multi-Pollutant Combination Triggered",
            body="Current sub-indices did not meet any configured co-occurrence pattern threshold.",
            is_placeholder=False,
        )
    else:
        for combo in analysis.combinations:
            render_info_panel(
                title=f"{combo.title} [Severity: {combo.severity}]",
                body=f"{combo.summary} (Pollutants: {', '.join(p.upper() for p in combo.matched_pollutants)})",
                is_placeholder=False,
            )

    st.markdown("### Possible Pollution Source Insights (Non-Causal Associations)")
    for item in insights:
        ev_text = "; ".join(item.supporting_evidence)
        lim_text = " ".join(item.limitations)
        render_info_panel(
            title=f"{item.source_category} — Evidence Strength: {item.evidence_strength}",
            body=(
                f"<b>Observed Pattern:</b> {item.observed_pattern}<br>"
                f"<b>Possible Associated Source:</b> {item.possible_associated_source}<br>"
                f"<b>Supporting Evidence:</b> {ev_text}<br>"
                f"<b>Explanation:</b> {item.explanation}<br>"
                f"<b>Limitations:</b> {lim_text}"
            ),
            is_placeholder=False,
        )


main()