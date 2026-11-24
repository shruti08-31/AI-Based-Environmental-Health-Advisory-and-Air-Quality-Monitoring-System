import streamlit as st

SEVERITY_PALETTE: dict[str, dict[str, str]] = {
    "Good": {
        "bg": "#ECFDF5",
        "border": "#10B981",
        "text": "#065F46",
        "chart": "#059669",
    },
    "Satisfactory": {
        "bg": "#F0FDF4",
        "border": "#22C55E",
        "text": "#166534",
        "chart": "#16A34A",
    },
    "Moderate": {
        "bg": "#FFFBEB",
        "border": "#F59E0B",
        "text": "#92400E",
        "chart": "#D97706",
    },
    "Poor": {
        "bg": "#FFF7ED",
        "border": "#F97316",
        "text": "#9A3412",
        "chart": "#EA580C",
    },
    "Very Poor": {
        "bg": "#FEF2F2",
        "border": "#EF4444",
        "text": "#991B1B",
        "chart": "#DC2626",
    },
    "Severe": {
        "bg": "#FAF5FF",
        "border": "#9333EA",
        "text": "#581C87",
        "chart": "#7E22CE",
    },
    "Sensitive": {
        "bg": "#FFF7ED",
        "border": "#F97316",
        "text": "#9A3412",
        "chart": "#EA580C",
    },
    "Unhealthy": {
        "bg": "#FEF2F2",
        "border": "#EF4444",
        "text": "#991B1B",
        "chart": "#DC2626",
    },
    "Pending": {
        "bg": "#F8FAFC",
        "border": "#94A3B8",
        "text": "#1E293B",
        "chart": "#64748B",
    },
    "Unavailable": {
        "bg": "#F8FAFC",
        "border": "#94A3B8",
        "text": "#1E293B",
        "chart": "#64748B",
    },
}


def get_severity_style(severity: str) -> dict[str, str]:
    return SEVERITY_PALETTE.get(severity, SEVERITY_PALETTE["Pending"])


def apply_base_theme() -> None:
    st.markdown(
        """<style>
        .block-container { padding-top: 1.5rem; padding-bottom: 2.5rem; max-width: 1320px; }
        .page-header { border-bottom: 1px solid rgba(148, 163, 184, 0.35); padding-bottom: 0.85rem; margin-bottom: 1.25rem; }
        .page-title { font-size: 1.65rem; font-weight: 700; margin: 0.25rem 0 0 0; line-height: 1.25; }
        .page-subtitle { font-size: 0.94rem; opacity: 0.82; margin: 0.35rem 0 0 0; }
        .demo-tag { display: inline-block; font-size: 0.68rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; color: #1E293B; background-color: #E2E8F0; border: 1px solid #CBD5E1; border-radius: 4px; padding: 0.1rem 0.45rem; margin-bottom: 0.45rem; }
        .ui-card { background-color: #FFFFFF; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 8px; padding: 1rem 1.05rem; margin-bottom: 0.9rem; overflow-wrap: break-word; word-break: normal; }
        .ui-card-title { font-size: 0.74rem; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 0.3rem; }
        .ui-card-value { font-size: 1.25rem; font-weight: 700; color: #0F172A; margin-bottom: 0.25rem; line-height: 1.25; }
        .ui-card-meta { font-size: 0.8rem; color: #475569; line-height: 1.35; }
        .info-panel { background-color: #FFFFFF; color: #0F172A; border: 1px solid #CBD5E1; border-left: 4px solid #0284C7; border-radius: 6px; padding: 1rem 1.15rem; margin-bottom: 1rem; line-height: 1.5; }
        .chart-container { background-color: #FFFFFF; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 8px; padding: 1rem 1.15rem 0.5rem 1.15rem; margin-bottom: 1rem; }
        </style>""",
        unsafe_allow_html=True,
    )