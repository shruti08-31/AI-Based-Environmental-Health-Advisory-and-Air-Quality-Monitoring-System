from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors

from src.analytics.comparison import compare_station_observations
from src.analytics.history import compute_historical_analytics
from src.api.waqi_client import POLLUTANT_KEYS
from src.core.health_engine import SensitivityGroup, generate_health_advisory
from src.database.repository import get_latest_observations_per_station, get_observations
from src.intelligence.anomaly_detection import detect_anomalies


@dataclass
class PeriodReport:
    report_type: str  # "Daily" | "Weekly" | "Monthly"
    period_label: str
    sufficient_data: bool
    reason_if_insufficient: str | None
    observation_count: int
    average_aqi: float | None = None
    highest_aqi: int | None = None
    lowest_aqi: int | None = None
    dominant_pollutant_counts: dict[str, int] = field(default_factory=dict)
    pollutant_averages: dict[str, float | None] = field(default_factory=dict)
    severity_distribution: dict[str, int] = field(default_factory=dict)
    historical_change: int | None = None
    historical_change_pct: float | None = None
    anomalies_detected: int = 0
    anomaly_notes: list[str] = field(default_factory=list)
    health_advisory_summary: str = ""
    data_quality_summary: str = ""
    location_comparison_summary: str = ""
    key_observations: list[str] = field(default_factory=list)
    export_df: pd.DataFrame = field(default_factory=pd.DataFrame)


def _filter_by_window(
    observations: list[dict[str, Any]],
    days_back: int,
    reference_date: date | None = None,
) -> list[dict[str, Any]]:
    ref = reference_date or datetime.now(timezone.utc).date()
    start_str = (ref - timedelta(days=days_back)).isoformat()
    end_str = ref.isoformat()
    out: list[dict[str, Any]] = []
    for obs in observations:
        d_str = str(obs.get("observation_date") or obs.get("observation_time") or "")[:10]
        if d_str and start_str <= d_str <= end_str:
            out.append(obs)
    return out


def _build_period_report(
    report_type: str,
    period_label: str,
    window_obs: list[dict[str, Any]],
    min_required: int,
    all_obs: list[dict[str, Any]],
    latest_per_station: list[dict[str, Any]],
) -> PeriodReport:
    if len(window_obs) < min_required:
        return PeriodReport(
            report_type=report_type,
            period_label=period_label,
            sufficient_data=False,
            reason_if_insufficient=(
                f"Insufficient observations for {report_type} report ({len(window_obs)} found; "
                f"at least {min_required} required)."
            ),
            observation_count=len(window_obs),
        )

    hist = compute_historical_analytics(window_obs)
    anomalies = detect_anomalies(window_obs)
    flagged_anoms = [a for a in anomalies if a.is_anomaly]

    dom_counts: dict[str, int] = {}
    for row in window_obs:
        dom = str(row.get("dominant_pollutant") or "").strip().upper()
        if dom and dom != "NONE":
            dom_counts[dom] = dom_counts.get(dom, 0) + 1

    latest_cat = str(window_obs[-1].get("aqi_category") or "Unavailable")
    latest_dom = window_obs[-1].get("dominant_pollutant")
    adv = generate_health_advisory(
        category=latest_cat,
        sensitivity_group=SensitivityGroup.GENERAL,
        dominant_pollutant=latest_dom,
    )
    adv_summary = (
        f"Latest tier: {adv.category} (Urgency: {adv.urgency_level}). "
        + " ".join(adv.general_precautions[:2])
    )

    valid_rows = sum(1 for r in window_obs if int(r.get("is_valid", 1)) == 1)
    stale_rows = sum(1 for r in window_obs if int(r.get("is_stale", 0)) == 1)
    avg_comp = (
        round(
            sum(float(r.get("completeness_ratio") or 0.0) for r in window_obs) / len(window_obs) * 100.0,
            1,
        )
        if window_obs
        else 0.0
    )
    dq_summary = (
        f"Valid records: {valid_rows}/{len(window_obs)} | Stale flagged: {stale_rows} | "
        f"Mean pollutant completeness: {avg_comp}%."
    )

    comp = compare_station_observations(latest_per_station)
    if comp.stations_compared >= 2:
        loc_comp_summary = (
            f"Across {comp.stations_compared} stations, highest latest AQI is "
            f"{comp.highest_aqi_station} ({comp.highest_aqi_value}) and lowest is "
            f"{comp.lowest_aqi_station} ({comp.lowest_aqi_value})."
        )
    elif comp.stations_compared == 1:
        loc_comp_summary = (
            f"Only 1 station ({comp.highest_aqi_station}, AQI {comp.highest_aqi_value}) has stored observations; "
            "multi-location comparison requires >= 2 stations."
        )
    else:
        loc_comp_summary = "No multi-station comparison data available."

    key_obs: list[str] = []
    if hist.average_aqi is not None and hist.max_aqi is not None and hist.min_aqi is not None:
        key_obs.append(
            f"AQI averaged {hist.average_aqi:g} with range {hist.min_aqi}–{hist.max_aqi}."
        )
    if dom_counts:
        top_dom = max(dom_counts.items(), key=lambda x: x[1])
        key_obs.append(f"Most frequent dominant AQI pollutant: {top_dom[0]} ({top_dom[1]} readings).")
    if hist.aqi_change is not None:
        key_obs.append(f"Net AQI change across period: {hist.aqi_change:+d} points.")
    if flagged_anoms:
        key_obs.append(f"{len(flagged_anoms)} statistical anomaly event(s) flagged in period.")

    export_cols = [
        "observation_id",
        "station_name",
        "query_city",
        "observation_time",
        "observation_date",
        "calculated_aqi",
        "waqi_reported_aqi",
        "aqi_category",
        "dominant_pollutant",
        "completeness_ratio",
        "is_valid",
        "is_stale",
    ] + list(POLLUTANT_KEYS)
    df_export = pd.DataFrame(window_obs)
    present_cols = [c for c in export_cols if c in df_export.columns]
    df_export = df_export[present_cols] if present_cols else df_export

    return PeriodReport(
        report_type=report_type,
        period_label=period_label,
        sufficient_data=True,
        reason_if_insufficient=None,
        observation_count=len(window_obs),
        average_aqi=hist.average_aqi,
        highest_aqi=hist.max_aqi,
        lowest_aqi=hist.min_aqi,
        dominant_pollutant_counts=dom_counts,
        pollutant_averages=hist.pollutant_averages,
        severity_distribution=hist.severity_distribution,
        historical_change=hist.aqi_change,
        historical_change_pct=hist.aqi_change_pct,
        anomalies_detected=len(flagged_anoms),
        anomaly_notes=[f"{a.observation_time} ({a.evidence_strength}): {a.explanation}" for a in flagged_anoms],
        health_advisory_summary=adv_summary,
        data_quality_summary=dq_summary,
        location_comparison_summary=loc_comp_summary,
        key_observations=key_obs,
        export_df=df_export,
    )


def generate_environmental_report(
    report_type: str,
    location: str | None = None,
    reference_date: date | None = None,
    db_path: Path | str | None = None,
) -> PeriodReport:
    rtype = report_type.strip().capitalize()
    all_obs = get_observations(location=location, limit=2000, db_path=db_path)
    latest_stations = get_latest_observations_per_station(db_path=db_path)

    if rtype == "Daily":
        window_obs = _filter_by_window(all_obs, days_back=1, reference_date=reference_date)
        return _build_period_report(
            report_type="Daily",
            period_label="Last 24–48 Hours (Daily Window)",
            window_obs=window_obs,
            min_required=1,
            all_obs=all_obs,
            latest_per_station=latest_stations,
        )

    if rtype == "Weekly":
        window_obs = _filter_by_window(all_obs, days_back=7, reference_date=reference_date)
        return _build_period_report(
            report_type="Weekly",
            period_label="Last 7 Days (Weekly Window)",
            window_obs=window_obs,
            min_required=2,
            all_obs=all_obs,
            latest_per_station=latest_stations,
        )

    if rtype == "Monthly":
        window_obs = _filter_by_window(all_obs, days_back=30, reference_date=reference_date)
        return _build_period_report(
            report_type="Monthly",
            period_label="Last 30 Days (Monthly Window)",
            window_obs=window_obs,
            min_required=3,
            all_obs=all_obs,
            latest_per_station=latest_stations,
        )

    raise ValueError(f"Unsupported report type: '{report_type}'. Choose Daily, Weekly, or Monthly.")


def report_to_csv_bytes(report: PeriodReport) -> bytes:
    if report.export_df.empty:
        return b""
    return report.export_df.to_csv(index=False).encode("utf-8")


def report_to_pdf_bytes(report: PeriodReport) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=36, bottomMargin=36, leftMargin=36, rightMargin=36)
    styles = getSampleStyleSheet()
    story: list[Any] = []

    story.append(Paragraph(f"{report.report_type} Environmental Air Quality Report", styles["Title"]))
    story.append(Paragraph(f"Period: {report.period_label} | Observations: {report.observation_count}", styles["Normal"]))
    story.append(Spacer(1, 12))

    if not report.sufficient_data:
        story.append(
            Paragraph(
                report.reason_if_insufficient or "Insufficient observations to generate report statistics.",
                styles["Normal"],
            )
        )
        doc.build(story)
        return buffer.getvalue()

    summary_data = [
        ["Metric", "Value"],
        ["Average AQI", str(report.average_aqi) if report.average_aqi is not None else "N/A"],
        ["Highest AQI", str(report.highest_aqi) if report.highest_aqi is not None else "N/A"],
        ["Lowest AQI", str(report.lowest_aqi) if report.lowest_aqi is not None else "N/A"],
        [
            "Historical AQI Change",
            f"{report.historical_change:+d}" if report.historical_change is not None else "N/A",
        ],
        ["Anomalies Flagged", str(report.anomalies_detected)],
    ]
    tbl = Table(summary_data, colWidths=[200, 320])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(tbl)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Health Advisory Summary", styles["Heading2"]))
    story.append(Paragraph(report.health_advisory_summary or "N/A", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Data Quality & Location Comparison", styles["Heading2"]))
    story.append(Paragraph(report.data_quality_summary or "N/A", styles["Normal"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(report.location_comparison_summary or "N/A", styles["Normal"]))
    story.append(Spacer(1, 10))

    if report.key_observations:
        story.append(Paragraph("Key Environmental Observations", styles["Heading2"]))
        for item in report.key_observations:
            story.append(Paragraph(f"• {item}", styles["Normal"]))
            story.append(Spacer(1, 4))

    doc.build(story)
    return buffer.getvalue()