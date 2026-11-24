from datetime import date
import streamlit as st

from src.analytics.environmental_reports import (
    generate_environmental_report,
    report_to_csv_bytes,
    report_to_pdf_bytes,
)
from src.database import list_stations
from src.utils import (
    render_info_panel,
    render_metric_card,
    render_page_header,
    render_warning_banner,
)


def main() -> None:
    render_page_header(
        title="Environmental Reports",
        subtitle="Generate Daily, Weekly, and Monthly summaries with ReportLab PDF and Pandas CSV export.",
        is_placeholder=False,
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

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_metric_card("Observations", str(report.observation_count), report.period_label, is_placeholder=False)
    with m2:
        render_metric_card(
            "Average AQI",
            f"{report.average_aqi:g}" if report.average_aqi is not None else "N/A",
            f"Change: {report.historical_change:+d}" if report.historical_change is not None else "Single point",
            is_placeholder=False,
        )
    with m3:
        render_metric_card(
            "Highest / Lowest AQI",
            f"{report.highest_aqi} / {report.lowest_aqi}"
            if report.highest_aqi is not None and report.lowest_aqi is not None
            else "N/A",
            "Observed range in window",
            is_placeholder=False,
        )
    with m4:
        render_metric_card(
            "Anomalies Detected",
            str(report.anomalies_detected),
            "Statistical flags in window",
            is_placeholder=False,
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

    render_info_panel(
        title="Health Advisory & Data Quality Summary",
        body=(
            f"<b>Health Advisory:</b> {report.health_advisory_summary}<br>"
            f"<b>Data Quality:</b> {report.data_quality_summary}<br>"
            f"<b>Location Comparison:</b> {report.location_comparison_summary}"
        ),
        is_placeholder=False,
    )

    if report.key_observations:
        render_info_panel(
            title="Important Environmental Observations",
            body="<br>".join(f"• {k}" for k in report.key_observations),
            is_placeholder=False,
        )

    if not report.export_df.empty:
        st.dataframe(report.export_df, width="stretch", hide_index=True)


main()