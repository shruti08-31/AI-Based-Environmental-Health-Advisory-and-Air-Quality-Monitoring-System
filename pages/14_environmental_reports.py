from datetime import date
import html
import streamlit as st

from src.analytics.environmental_reports import (
    generate_environmental_report,
    report_to_csv_bytes,
    report_to_pdf_bytes,
)
from src.database import list_stations
from src.utils import render_warning_banner


def _inject_env_reports_theme() -> None:
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

        /* Green labels & light-green selectbox / date inputs with dark-green text */
        [data-testid="stSelectbox"] label,
        [data-testid="stSelectbox"] label p,
        [data-testid="stDateInput"] label,
        [data-testid="stDateInput"] label p {
            color: #1B5E3F !important;
            font-weight: 600 !important;
            font-size: 0.86rem !important;
        }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stDateInput"] input,
        [data-testid="stDateInput"] > div > div {
            background-color: #EAF4EC !important;
            border-color: #B4D6BE !important;
            border-radius: 10px !important;
            color: #133A2A !important;
            -webkit-text-fill-color: #133A2A !important;
            font-weight: 600 !important;
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
        div[data-testid="stSelectbox"] div[data-baseweb="select"] svg,
        [data-testid="stDateInput"] svg {
            color: #133A2A !important;
            fill: #133A2A !important;
        }

        /* Forest-green download buttons */
        div.stDownloadButton > button {
            background-color: #133A2A;
            color: #FFFFFF;
            border: 1px solid #133A2A;
            border-radius: 10px;
            font-weight: 600;
            transition: background-color 0.15s ease;
        }
        div.stDownloadButton > button:hover {
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

        /* KPI Cards */
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
            font-size: 1.62rem;
            font-weight: 700;
            color: #133A2A;
            line-height: 1.15;
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
            margin-top: 0.75rem;
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
            font-size: 0.85rem;
            color: #2D4238;
            line-height: 1.55;
        }
        .eco-panel-row {
            margin-bottom: 5px;
        }
        .eco-panel-list {
            margin: 4px 0 0 0;
            padding-left: 18px;
            color: #2D4238;
            font-size: 0.85rem;
            line-height: 1.6;
        }
        .eco-table-wrap {
            margin-top: 0.85rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    _inject_env_reports_theme()

    st.markdown(
        """
        <div class="eco-topbar">
            <div>
                <div class="eco-breadcrumb">EcoHealth &nbsp;/&nbsp; <strong>Environmental Reports</strong></div>
                <div class="eco-sub">Generate Daily, Weekly, and Monthly summaries with ReportLab PDF and Pandas CSV export.</div>
            </div>
            <div class="eco-pill">
                <span class="eco-dot"></span>PDF &amp; CSV Export
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    stations = list_stations()
    loc_options = ["All Locations"] + [str(s["station_name"]) for s in stations]

    c1, c2, c3 = st.columns([1.4, 2.0, 1.2])
    with c1:
        rtype = st.selectbox(
            "Report Period",
            options=["Daily", "Weekly", "Monthly"],
            index=0,
            key="env_report_type",
        )
    with c2:
        selected_loc = st.selectbox(
            "Location / Station",
            options=loc_options,
            index=0,
            key="env_report_location",
        )
    with c3:
        ref_dt = st.date_input(
            "Reference Date",
            value=date.today(),
            key="env_report_ref_date",
        )

    report = generate_environmental_report(
        report_type=rtype,
        location=selected_loc,
        reference_date=ref_dt,
    )

    if not report.sufficient_data:
        render_warning_banner(
            report.reason_if_insufficient or "Insufficient observations for this period.",
            is_placeholder=False,
        )
        return

    avg_aqi_str = f"{report.average_aqi:g}" if report.average_aqi is not None else "N/A"
    chg_sub = f"Change: {report.historical_change:+d}" if report.historical_change is not None else "Single point"
    hi_lo_str = (
        f"{report.highest_aqi} / {report.lowest_aqi}"
        if report.highest_aqi is not None and report.lowest_aqi is not None
        else "N/A"
    )
    anom_accent = "#DC2626" if int(report.anomalies_detected or 0) > 0 else "#1F7A5A"

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #133A2A;">
                <div class="eco-card-label">Observations</div>
                <div class="eco-card-value">{report.observation_count}</div>
                <div class="eco-card-sub">{html.escape(str(report.period_label))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #1F7A5A;">
                <div class="eco-card-label">Average AQI</div>
                <div class="eco-card-value">{html.escape(avg_aqi_str)}</div>
                <div class="eco-card-sub">{html.escape(chg_sub)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid #D97706;">
                <div class="eco-card-label">Highest / Lowest AQI</div>
                <div class="eco-card-value" style="font-size:1.38rem;">{html.escape(hi_lo_str)}</div>
                <div class="eco-card-sub">Observed range in window</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f"""
            <div class="eco-card" style="border-top:4px solid {anom_accent};">
                <div class="eco-card-label">Anomalies Detected</div>
                <div class="eco-card-value" style="color:{anom_accent};">{report.anomalies_detected}</div>
                <div class="eco-card-sub">Statistical flags in window</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    dl1, dl2 = st.columns(2)
    with dl1:
        pdf_bytes = report_to_pdf_bytes(report)
        st.download_button(
            label=f"Download {report.report_type} Report (PDF)",
            data=pdf_bytes,
            file_name=f"environmental_report_{report.report_type.lower()}_{ref_dt.isoformat()}.pdf",
            mime="application/pdf",
            width="stretch",
            key="btn_download_report_pdf",
        )
    with dl2:
        csv_bytes = report_to_csv_bytes(report)
        st.download_button(
            label=f"Download {report.report_type} Dataset (CSV)",
            data=csv_bytes,
            file_name=f"environmental_report_{report.report_type.lower()}_{ref_dt.isoformat()}.csv",
            mime="text/csv",
            width="stretch",
            key="btn_download_report_csv",
        )

    st.markdown(
        f"""
        <div class="eco-panel" style="border-left-color:#133A2A;">
            <div class="eco-panel-title">Health Advisory &amp; Data Quality Summary</div>
            <div class="eco-panel-body">
                <div class="eco-panel-row"><strong>Health Advisory:</strong> {html.escape(str(report.health_advisory_summary))}</div>
                <div class="eco-panel-row"><strong>Data Quality:</strong> {html.escape(str(report.data_quality_summary))}</div>
                <div class="eco-panel-row"><strong>Location Comparison:</strong> {html.escape(str(report.location_comparison_summary))}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if report.key_observations:
        obs_items = "".join(f"<li>{html.escape(str(k))}</li>" for k in report.key_observations)
        st.markdown(
            f"""
            <div class="eco-panel" style="border-left-color:#1F7A5A;">
                <div class="eco-panel-title">Important Environmental Observations</div>
                <ul class="eco-panel-list">{obs_items}</ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not report.export_df.empty:
        st.markdown('<div class="eco-table-wrap"></div>', unsafe_allow_html=True)
        st.dataframe(report.export_df, width="stretch", hide_index=True)


main()