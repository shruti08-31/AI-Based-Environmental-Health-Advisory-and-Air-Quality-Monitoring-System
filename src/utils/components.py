import html
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from src.utils.theme import get_severity_style


def render_page_header(title: str, subtitle: str, is_placeholder: bool = True) -> None:
    if is_placeholder:
        st.caption("DEMONSTRATION PLACEHOLDER")
    st.title(title)
    st.caption(subtitle)
    st.divider()


def render_metric_card(
    label: str,
    value: str,
    meta: str = "Demonstration Placeholder",
    is_placeholder: bool = True,
) -> None:
    with st.container(border=True):
        if is_placeholder:
            st.caption("Placeholder")
        st.metric(label=label, value=value)
        st.caption(meta)


def render_aqi_indicator(
    severity: str = "Pending",
    status_text: str = "Awaiting live or stored air quality feed",
    is_placeholder: bool = True,
) -> None:
    style = get_severity_style(severity)
    safe_sev = html.escape(severity)
    safe_status = html.escape(status_text)
    badge = '<div style="font-size:0.68rem;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;opacity:0.85;margin-bottom:0.25rem;">Demonstration Placeholder</div>' if is_placeholder else ""
    st.markdown(
        f'<div style="background-color:{style["bg"]};border:1px solid {style["border"]};border-left:5px solid {style["border"]};color:{style["text"]};border-radius:8px;padding:0.9rem 1rem;margin-bottom:0.9rem;">{badge}<div style="font-size:0.74rem;font-weight:700;text-transform:uppercase;">AQI Severity Indicator</div><div style="font-size:1.2rem;font-weight:700;margin:0.2rem 0;">{safe_sev}</div><div style="font-size:0.8rem;line-height:1.35;">{safe_status}</div></div>',
        unsafe_allow_html=True,
    )


def render_pollutant_card(
    pollutant_name: str,
    concentration_label: str = "Awaiting telemetry",
    standard_ref: str = "Reference threshold pending integration",
    is_placeholder: bool = True,
) -> None:
    with st.container(border=True):
        if is_placeholder:
            st.caption("Placeholder")
        st.metric(label=pollutant_name, value=concentration_label)
        st.caption(standard_ref)


def render_info_panel(title: str, body: str, is_placeholder: bool = True) -> None:
    clean_body = body.replace("<br>", "\n")
    with st.container(border=True):
        if is_placeholder:
            st.caption("Demonstration Placeholder")
        st.markdown(f"**{title}**")
        st.markdown(clean_body)


def render_warning_banner(message: str, is_placeholder: bool = True) -> None:
    prefix = "[Demonstration Placeholder] " if is_placeholder else ""
    st.warning(f"{prefix}{message}")


def render_placeholder_plotly_chart(
    title: str,
    x_label: str,
    y_label: str,
    chart_key: str,
    note: str = "Empty layout scaffold — populated in a later stage when data services are connected.",
) -> None:
    with st.container(border=True):
        st.caption("Demonstration Placeholder")
        st.markdown(f"**{title}**")

        empty_df = pd.DataFrame({x_label: [], y_label: []})
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=empty_df[x_label],
                y=empty_df[y_label],
                mode="lines+markers",
                name="Placeholder Series",
                line={"color": "#64748B", "width": 2},
            )
        )
        fig.update_layout(
            height=290,
            margin={"l": 40, "r": 20, "t": 20, "b": 40},
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#F8FAFC",
            xaxis={"title": x_label, "showgrid": True, "gridcolor": "#E2E8F0"},
            yaxis={"title": y_label, "showgrid": True, "gridcolor": "#E2E8F0"},
            annotations=[
                {
                    "text": note,
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                    "font": {"size": 12, "color": "#64748B"},
                }
            ],
        )
        st.plotly_chart(fig, width="stretch", key=chart_key)