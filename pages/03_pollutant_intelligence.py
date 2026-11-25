import html
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.api import POLLUTANT_KEYS, AqiReading
from src.core import evaluate_aqi_from_reading
from src.intelligence import analyze_pollutants_from_reading, generate_source_insights
from src.utils import render_warning_banner


def _inject_pollutant_intel_theme() -> None:
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

        /* Top KPI Cards */
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
            margin-bottom: 8px;
        }
        .eco-card-value {
            font-size: 1.65rem;
            font-weight: 700;
            color: #133A2A;
            line-height: 1.15;
            margin-bottom: 6px;
        }
        .eco-card-sub {
            font-size: 0.77rem;
            color: #6B7E74;
        }

        /* Pollutant Breakdown Cards */
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
            font-size: 0.85rem;
            font-weight: 700;
            color: #16261E;
        }
        .eco-pol-tag {
            font-size: 0.69rem;
            font-weight: 700;
            padding: 2px 9px;
            border-radius: 999px;
        }
        .eco-pol-val {
            font-size: 1.05rem;
            font-weight: 700;
            color: #133A2A;
            margin-bottom: 5px;
        }
        .eco-pol-ref {
            font-size: 0.75rem;
            color: #6B7E74;
        }

        /* Section Titles & Info Panels */
        .eco-section-title {
            font-size: 1.04rem;
            font-weight: 700;
            color: #133A2A;
            margin: 1.1rem 0 0.65rem 0;
        }
        .eco-insight-panel {
            background: #FFFFFF;
            border: 1px solid #DCE8E0;
            border-left: 4px solid #133A2A;
            border-radius: 14px;
            padding: 16px 20px;
            margin-bottom: 0.75rem;
            box-shadow: 0 2px 6px rgba(19, 58, 42, 0.025);
        }
        .eco-insight-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .eco-insight-title {
            font-size: 0.94rem;
            font-weight: 700;
            color: #133A2A;
        }
        .eco-insight-body {
            font-size: 0.85rem;
            color: #2E4238;
            line-height: 1.55;
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


def _severity_badge_style(severity: str) -> tuple[str, str, str]:
    """Returns (left_border_hex, pill_bg, pill_fg) for severity or evidence strength."""
    s = (severity or "").strip().lower()
    if any(k in s for k in ("good", "low", "minimal")):
        return ("#22A06B", "#E4F5EC", "#166534")
    if any(k in s for k in ("satisfactory", "moderate")):
        return ("#D97706", "#FEF6E6", "#9A5B13")
    if any(k in s for k in ("poor", "elevated", "high")) and "very" not in s:
        return ("#EA580C", "#FDECE4", "#9A3412")
    if any(k in s for k in ("very poor", "severe", "critical", "strong")):
        return ("#DC2626", "#FBE7E7", "#991B1B")
    return ("#94A3B8", "#F1F5F9", "#475569")


def _render_comparison_and_subindex_charts(
    raw_rows: list[dict[str, object]],
    sub_rows: list[dict[str, object]],
) -> None:
    c_left, c_right = st.columns(2)

    with c_left:
        with st.container(border=True):
            st.markdown("**Pollutant Raw Measurement Comparison**")
            if not raw_rows:
                st.caption("No numeric pollutant measurements available to plot.")
            else:
                df_raw = pd.DataFrame(raw_rows)
                fig_raw = go.Figure(
                    go.Bar(
                        x=df_raw["Pollutant"],
                        y=df_raw["Raw Value"],
                        marker_color="#133A2A",
                        marker_line_color="#0E2C20",
                        marker_line_width=1,
                        text=df_raw["Raw Value"].map(lambda v: f"{v:g}"),
                        textposition="outside",
                        textfont={"color": "#133A2A", "size": 11},
                    )
                )
                fig_raw.update_layout(
                    height=305,
                    margin={"l": 42, "r": 18, "t": 26, "b": 42},
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
                        "title": {"text": "Measured Value", "font": {"color": "#133A2A", "size": 12}},
                        "tickfont": {"color": "#133A2A", "size": 11},
                        "gridcolor": "#DFEAE3",
                        "linecolor": "#B8CFC1",
                        "zerolinecolor": "#9BBAA6",
                    },
                )
                st.plotly_chart(fig_raw, width="stretch", key="pollutant_raw_comparison_chart")

    with c_right:
        with st.container(border=True):
            st.markdown("**CPCB Sub-Index Analysis**")
            if not sub_rows:
                st.caption("No valid pollutant sub-indices calculated.")
            else:
                df_sub = pd.DataFrame(sub_rows)
                fig_sub = go.Figure(
                    go.Bar(
                        x=df_sub["Pollutant"],
                        y=df_sub["Sub-Index"],
                        marker_color="#2A6F4E",
                        marker_line_color="#133A2A",
                        marker_line_width=1,
                        text=df_sub["Sub-Index"].map(lambda v: f"{v:g}"),
                        textposition="outside",
                        textfont={"color": "#133A2A", "size": 11},
                    )
                )
                fig_sub.update_layout(
                    height=305,
                    margin={"l": 42, "r": 18, "t": 26, "b": 42},
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
                        "title": {"text": "Calculated Sub-Index (0-500)", "font": {"color": "#133A2A", "size": 12}},
                        "tickfont": {"color": "#133A2A", "size": 11},
                        "gridcolor": "#DFEAE3",
                        "linecolor": "#B8CFC1",
                        "zerolinecolor": "#9BBAA6",
                    },
                )
                st.plotly_chart(fig_sub, width="stretch", key="pollutant_subindex_chart")


def main() -> None:
    _inject_pollutant_intel_theme()

    reading: AqiReading | None = st.session_state.get("waqi_last_reading")

    station_badge = (
        html.escape(reading.station_name or reading.query)
        if reading is not None
        else "Awaiting Live Station"
    )
    st.markdown(
        f"""
        <div class="eco-topbar">
            <div>
                <div class="eco-breadcrumb">EcoHealth &nbsp;/&nbsp; <strong>Pollutant Intelligence</strong></div>
                <div class="eco-sub">Pollutant diagnostics, sub-index vs. raw value comparison, combinations, and possible source insights.</div>
            </div>
            <div class="eco-pill">
                <span class="eco-dot"></span>{station_badge}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
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
                    st.markdown(
                        f"""
                        <div class="eco-pol-card" style="border-left:4px solid #CBD5E1;">
                            <div class="eco-pol-top">
                                <span class="eco-pol-name">{html.escape(name.upper())}</span>
                                <span class="eco-pol-tag" style="background:#F1F5F9;color:#64748B;">Pending</span>
                            </div>
                            <div class="eco-pol-val" style="color:#6B7E74;">Awaiting Telemetry</div>
                            <div class="eco-pol-ref">Fetch a live station to inspect sub-index</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        return

    aqi_res = evaluate_aqi_from_reading(reading)
    analysis = analyze_pollutants_from_reading(reading)
    insights = generate_source_insights(analysis)

    highest_pol = html.escape((analysis.highest_measured_pollutant or "None").upper())
    highest_meta = (
        f"Raw value: {analysis.highest_measured_value:g}"
        if analysis.highest_measured_value is not None
        else "No valid raw value"
    )
    dom_pol = html.escape((analysis.dominant_aqi_pollutant or "None").upper())
    dom_meta = (
        f"Sub-index: {analysis.highest_sub_index:g}"
        if analysis.highest_sub_index is not None
        else "No sub-index"
    )
    near_count = str(len(analysis.approaching_threshold_pollutants))
    near_meta = (
        ", ".join(p.upper() for p in analysis.approaching_threshold_pollutants)
        if analysis.approaching_threshold_pollutants
        else "None flagged"
    )

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #133A2A;">
                <div class="eco-card-label">Highest Measured Pollutant</div>
                <div class="eco-card-value">{highest_pol}</div>
                <div class="eco-card-sub">{html.escape(highest_meta)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #1F7A5A;">
                <div class="eco-card-label">Dominant AQI Pollutant</div>
                <div class="eco-card-value">{dom_pol}</div>
                <div class="eco-card-sub">{html.escape(dom_meta)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #D97706;">
                <div class="eco-card-label">Near/Over Threshold</div>
                <div class="eco-card-value">{html.escape(near_count)}</div>
                <div class="eco-card-sub">{html.escape(near_meta)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if analysis.missing_pollutants:
        render_warning_banner(
            "Missing or unmeasured pollutants (not imputed): "
            + ", ".join(p.upper() for p in analysis.missing_pollutants),
            is_placeholder=False,
        )

    st.markdown('<div class="eco-section-title">Pollutant-Wise Breakdown</div>', unsafe_allow_html=True)
    raw_chart_rows: list[dict[str, object]] = []
    sub_chart_rows: list[dict[str, object]] = []

    for idx in range(0, len(POLLUTANT_KEYS), 3):
        cols = st.columns(3)
        for col, key in zip(cols, POLLUTANT_KEYS[idx : idx + 3]):
            summ = analysis.pollutant_summaries[key]
            sub_obj = aqi_res.sub_indices[key]
            border_c, tag_bg, tag_fg = _severity_badge_style(summ.severity)
            val_str = f"{summ.raw_value:g}" if summ.raw_value is not None else "Missing"
            sub_str = f"{sub_obj.sub_index:g}" if sub_obj.sub_index is not None else "N/A"
            with col:
                st.markdown(
                    f"""
                    <div class="eco-pol-card" style="border-left:4px solid {border_c};">
                        <div class="eco-pol-top">
                            <span class="eco-pol-name">{html.escape(key.upper())}</span>
                            <span class="eco-pol-tag" style="background:{tag_bg};color:{tag_fg};">{html.escape(summ.severity)}</span>
                        </div>
                        <div class="eco-pol-val">Raw: {html.escape(val_str)} &nbsp;|&nbsp; Sub-Index: {html.escape(sub_str)}</div>
                        <div class="eco-pol-ref">{html.escape(summ.threshold_note)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            if summ.status == "available" and summ.raw_value is not None:
                raw_chart_rows.append({"Pollutant": key.upper(), "Raw Value": summ.raw_value})
            if sub_obj.is_valid_input and sub_obj.sub_index is not None:
                sub_chart_rows.append({"Pollutant": key.upper(), "Sub-Index": sub_obj.sub_index})

    _render_comparison_and_subindex_charts(raw_chart_rows, sub_chart_rows)

    st.markdown('<div class="eco-section-title">Detected Pollutant Combinations</div>', unsafe_allow_html=True)
    if not analysis.combinations:
        st.markdown(
            """
            <div class="eco-insight-panel" style="border-left-color:#315B48;">
                <div class="eco-insight-head">
                    <span class="eco-insight-title">No Configured Multi-Pollutant Combination Triggered</span>
                </div>
                <div class="eco-insight-body">
                    Current sub-indices did not meet any configured co-occurrence pattern threshold.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        for combo in analysis.combinations:
            b_col, p_bg, p_fg = _severity_badge_style(combo.severity)
            matched_str = ", ".join(p.upper() for p in combo.matched_pollutants)
            st.markdown(
                f"""
                <div class="eco-insight-panel" style="border-left-color:{b_col};">
                    <div class="eco-insight-head">
                        <span class="eco-insight-title">{html.escape(combo.title)}</span>
                        <span class="eco-pol-tag" style="background:{p_bg};color:{p_fg};">Severity: {html.escape(combo.severity)}</span>
                    </div>
                    <div class="eco-insight-body">
                        {html.escape(combo.summary)} (Pollutants: <strong>{html.escape(matched_str)}</strong>)
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div class="eco-section-title">Possible Pollution Source Insights (Non-Causal Associations)</div>', unsafe_allow_html=True)
    for item in insights:
        b_col, p_bg, p_fg = _severity_badge_style(item.evidence_strength)
        ev_text = "; ".join(item.supporting_evidence)
        lim_text = " ".join(item.limitations)
        st.markdown(
            f"""
            <div class="eco-insight-panel" style="border-left-color:{b_col};">
                <div class="eco-insight-head">
                    <span class="eco-insight-title">{html.escape(item.source_category)}</span>
                    <span class="eco-pol-tag" style="background:{p_bg};color:{p_fg};">Evidence: {html.escape(item.evidence_strength)}</span>
                </div>
                <div class="eco-insight-body">
                    <b>Observed Pattern:</b> {html.escape(item.observed_pattern)}<br>
                    <b>Possible Associated Source:</b> {html.escape(item.possible_associated_source)}<br>
                    <b>Supporting Evidence:</b> {html.escape(ev_text)}<br>
                    <b>Explanation:</b> {html.escape(item.explanation)}<br>
                    <b>Limitations:</b> {html.escape(lim_text)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


main()