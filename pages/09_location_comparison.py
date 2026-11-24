import html
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics import compare_station_observations
from src.api import POLLUTANT_KEYS
from src.database import get_latest_observations_per_station
from src.utils import render_warning_banner


_POLLUTANT_BAR_COLORS: dict[str, str] = {
    "PM25": "#133A2A",
    "PM10": "#1F7A5A",
    "NO2": "#D97706",
    "SO2": "#2B6CB0",
    "CO": "#DC2626",
    "O3": "#4D7C0F",
}


def _severity_badge_style(severity: str | None) -> tuple[str, str, str]:
    sev = (severity or "").strip().lower()
    if "good" in sev:
        return "#DCFCE7", "#166534", "#86EFAC"
    if "moderate" in sev:
        return "#FEF9C3", "#854D0E", "#FDE047"
    if "sensitive" in sev or "poor" in sev:
        return "#FFEDD5", "#9A3412", "#FDBA74"
    if "unhealthy" in sev or "very" in sev or "severe" in sev or "hazardous" in sev:
        return "#FEE2E2", "#991B1B", "#FCA5A5"
    return "#EDF2F7", "#334155", "#CBD5E1"


def _clean_location_label(raw_name: str) -> str:
    """Remove duplicate consecutive segments such as 'Delhi, Delhi'."""
    parts = [part.strip() for part in str(raw_name).split(",") if part.strip()]
    cleaned: list[str] = []
    for part in parts:
        if not cleaned or cleaned[-1].lower() != part.lower():
            cleaned.append(part)
    return ", ".join(cleaned) if cleaned else str(raw_name).strip()


def _inject_location_comp_theme() -> None:
    st.markdown(
        """
        <style>
        /* Hide default Streamlit chrome */
        [data-testid="stHeader"],
        header[data-testid="stHeader"],
        [data-testid="stDecoration"],
        [data-testid="stToolbar"] {
            display: none !important;
        }

        /* Main canvas & typography */
        .stApp {
            background-color: #F4F7F5;
            color: #16261E;
        }
        .block-container {
            padding-top: 1.15rem !important;
            padding-bottom: 2.5rem;
            max-width: 1280px;
        }

        /* Deep forest-green sidebar */
        [data-testid="stSidebar"] {
            background-color: #0E3B2E !important;
            border-right: 1px solid #092920;
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
            background-color: #275A49 !important;
            font-weight: 600;
        }

        /* Top header row */
        .eco-header-title {
            font-size: 1.45rem;
            font-weight: 700;
            color: #132A20;
            line-height: 1.2;
            margin: 0;
        }
        .eco-header-sub {
            font-size: 0.82rem;
            color: #6B7E74;
            margin-top: 2px;
        }

        /* Selectbox & multiselect dropdown styling */
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            border-color: #CFE0D6 !important;
            border-radius: 10px !important;
            min-height: 40px !important;
        }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] * {
            color: #16261E !important;
            font-size: 0.84rem !important;
        }
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] span[data-baseweb="tag"] {
            background-color: #E3F1E8 !important;
            color: #0E3B2E !important;
            border: 1px solid #B5D5C1 !important;
            border-radius: 999px !important;
            padding: 2px 10px !important;
        }
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] span[data-baseweb="tag"] * {
            color: #0E3B2E !important;
            -webkit-text-fill-color: #0E3B2E !important;
            opacity: 1 !important;
            font-size: 0.78rem !important;
            font-weight: 600 !important;
        }
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] input {
            color: #16261E !important;
            -webkit-text-fill-color: #16261E !important;
        }
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] span[data-baseweb="tag"] svg {
            color: #0E3B2E !important;
            fill: #0E3B2E !important;
        }

        /* Surface cards matching screenshot */
        .eco-surface-card {
            background: #FFFFFF;
            border: 1px solid #E2EAE5;
            border-radius: 12px;
            padding: 16px 20px;
            box-shadow: 0 1px 3px rgba(15, 59, 46, 0.03);
            margin-bottom: 14px;
        }
        .eco-selector-title {
            font-size: 0.90rem;
            font-weight: 700;
            color: #16261E;
            margin-bottom: 8px;
        }

        /* Top highlight cards (Highest / Lowest AQI Location) */
        .eco-highlight-card {
            background: #FFFFFF;
            border: 1px solid #E2EAE5;
            border-radius: 12px;
            padding: 16px 20px;
            box-shadow: 0 1px 3px rgba(15, 59, 46, 0.03);
            height: 100%;
        }
        .eco-highlight-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .eco-highlight-label {
            font-size: 0.80rem;
            color: #6B7E74;
            font-weight: 500;
        }
        .eco-highlight-value {
            font-size: 1.35rem;
            font-weight: 700;
            color: #132A20;
            line-height: 1.25;
        }

        /* Severity pill badge */
        .eco-badge {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 600;
            border: 1px solid transparent;
            white-space: nowrap;
        }

        /* Summary card */
        .eco-summary-title {
            font-size: 0.88rem;
            font-weight: 700;
            color: #16261E;
            margin-bottom: 4px;
        }
        .eco-summary-text {
            font-size: 0.84rem;
            color: #4A5D53;
            line-height: 1.45;
        }

        /* Per-city mini cards */
        .eco-city-card {
            background: #FFFFFF;
            border: 1px solid #E2EAE5;
            border-radius: 12px;
            padding: 15px 18px;
            box-shadow: 0 1px 3px rgba(15, 59, 46, 0.03);
            height: 100%;
        }
        .eco-city-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 8px;
            margin-bottom: 14px;
        }
        .eco-city-name {
            font-size: 0.86rem;
            font-weight: 600;
            color: #4A5D53;
        }
        .eco-city-aqi-row {
            display: flex;
            align-items: baseline;
            gap: 6px;
            margin-bottom: 6px;
        }
        .eco-city-aqi-num {
            font-size: 1.65rem;
            font-weight: 700;
            color: #132A20;
            line-height: 1.1;
        }
        .eco-city-aqi-unit {
            font-size: 0.74rem;
            font-weight: 600;
            color: #7A8D83;
            text-transform: uppercase;
        }
        .eco-city-sub {
            font-size: 0.76rem;
            color: #7A8D83;
        }

        /* Section headers & chart cards */
        .eco-section-title {
            font-size: 1.0rem;
            font-weight: 700;
            color: #133A2A;
            margin: 1.1rem 0 0.6rem 0;
        }
        .eco-panel {
            background: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-left: 4px solid #0E3B2E;
            border-radius: 12px;
            padding: 14px 18px;
            margin-top: 0.85rem;
            box-shadow: 0 1px 3px rgba(15, 59, 46, 0.025);
        }
        .eco-panel-title {
            font-size: 0.90rem;
            font-weight: 700;
            color: #133A2A;
            margin-bottom: 4px;
        }
        .eco-panel-body {
            font-size: 0.84rem;
            color: #2D4238;
            line-height: 1.5;
        }

        [data-testid="stPlotlyChart"],
        [data-testid="stPlotlyChart"] > div {
            background: transparent !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _apply_eco_chart_layout(
    fig: go.Figure,
    height: int,
    x_title: str,
    y_title: str,
    barmode: str | None = None,
) -> None:
    layout_kwargs: dict[str, object] = {
        "height": height,
        "margin": {"l": 44, "r": 20, "t": 20, "b": 42},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#133A2A"},
        "legend": {
            "bgcolor": "rgba(255,255,255,0.85)",
            "bordercolor": "#DCE8E0",
            "borderwidth": 1,
            "font": {"color": "#133A2A", "size": 11},
        },
        "xaxis": {
            "title": {"text": x_title, "font": {"color": "#133A2A", "size": 12}},
            "tickfont": {"color": "#133A2A", "size": 11},
            "showgrid": False,
            "linecolor": "#C8D8CE",
        },
        "yaxis": {
            "title": {"text": y_title, "font": {"color": "#133A2A", "size": 12}},
            "tickfont": {"color": "#133A2A", "size": 11},
            "gridcolor": "#E6EFE9",
            "linecolor": "#C8D8CE",
            "zerolinecolor": "#B2C8BA",
        },
    }
    if barmode:
        layout_kwargs["barmode"] = barmode
    fig.update_layout(**layout_kwargs)


def _render_badge(label: str) -> str:
    bg, fg, border = _severity_badge_style(label)
    return (
        f'<span class="eco-badge" style="background:{bg};color:{fg};border-color:{border};">'
        f"{html.escape(label)}</span>"
    )


def _prepare_observations(
    latest_per_station: list[dict],
) -> tuple[list[dict], list[str], dict[str, str]]:
    """
    Clean duplicate city/region segments (e.g., 'Delhi, Delhi' -> 'Delhi')
    without adding station numbers, while preserving all rows from SQLite.
    """
    prepared: list[dict] = []
    display_to_raw: dict[str, str] = {}
    unique_labels: list[str] = []

    for item in latest_per_station:
        raw_name = str(item.get("station_name", "Unknown Station"))
        cleaned_label = _clean_location_label(raw_name)

        cloned = dict(item)
        cloned["station_name"] = cleaned_label
        prepared.append(cloned)

        if cleaned_label not in display_to_raw:
            display_to_raw[cleaned_label] = raw_name
            unique_labels.append(cleaned_label)

    return prepared, unique_labels, display_to_raw


def _extract_severity_for_station(
    comparison_df: pd.DataFrame,
    station_name: str | None,
    fallback_list: list[str],
) -> str:
    if not station_name:
        return fallback_list[0] if fallback_list else "Unknown"
    if "Station" in comparison_df.columns:
        matched = comparison_df[comparison_df["Station"] == station_name]
        for col in ("Severity", "Category", "AQI Category", "Severity Tier"):
            if col in matched.columns and not matched[col].dropna().empty:
                return str(matched[col].dropna().iloc[0])
    return fallback_list[0] if fallback_list else "N/A"


def _build_comparison_summary(comp, highest_sev: str, lowest_sev: str) -> str:
    if (
        comp.highest_aqi_station
        and comp.lowest_aqi_station
        and comp.highest_aqi_value is not None
        and comp.lowest_aqi_value is not None
    ):
        try:
            diff = round(float(comp.highest_aqi_value) - float(comp.lowest_aqi_value), 1)
            diff_str = f"{int(diff)}" if diff.is_integer() else f"{diff}"
            return (
                f"{comp.highest_aqi_station} currently has the highest pollution burden "
                f"(AQI {comp.highest_aqi_value}, {highest_sev}), which is {diff_str} AQI points "
                f"higher than {comp.lowest_aqi_station} (AQI {comp.lowest_aqi_value}, {lowest_sev})."
            )
        except (TypeError, ValueError):
            pass
    sev_meta = ", ".join(comp.available_severities) if comp.available_severities else "None"
    return (
        f"Comparing {comp.stations_compared} selected station(s) using latest stored observations. "
        f"Present severity categories: {sev_meta}."
    )


def main() -> None:
    _inject_location_comp_theme()

    raw_latest = get_latest_observations_per_station()
    prepared_obs, all_station_names, display_to_raw = _prepare_observations(
        raw_latest if raw_latest else []
    )

    hdr_left, hdr_right = st.columns([4.5, 1.8], vertical_alignment="center")
    with hdr_left:
        st.markdown(
            """
            <div>
                <div class="eco-header-title">Location Comparison</div>
                <div class="eco-header-sub">Environmental Health Advisory &amp; Monitoring System</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hdr_right:
        if all_station_names:
            st.selectbox(
                "Focus Station",
                options=all_station_names,
                key="location_comparison_focus_station",
                label_visibility="collapsed",
            )

    if not prepared_obs:
        render_warning_banner(
            "No stored station observations found in SQLite. Fetch readings for one or more cities on 'Live AQI Monitoring' first.",
            is_placeholder=False,
        )
        return

    default_two = all_station_names[:2]

    st.markdown(
        """
        <div class="eco-surface-card" style="margin-bottom: 6px;">
            <div class="eco-selector-title">Select Locations to Compare (Min 2)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    selected_stations = st.multiselect(
        "Select Locations to Compare (Min 2)",
        options=all_station_names,
        default=default_two,
        placeholder="Choose locations from dropdown...",
        key="location_comparison_multiselect",
        label_visibility="collapsed",
    )

    if not selected_stations:
        render_warning_banner("Select at least one station above to view comparison metrics.", is_placeholder=False)
        return

    comp = compare_station_observations(
        latest_observations=prepared_obs,
        selected_stations=selected_stations,
    )

    if comp.stations_compared < 2:
        render_warning_banner(
            "Only 1 station is currently selected or stored. Fetch additional cities/stations in 'Live AQI Monitoring' for multi-location comparison.",
            is_placeholder=False,
        )

    if comp.timestamp_warnings:
        with st.expander(
            f"Timestamp & Freshness Notices ({len(comp.timestamp_warnings)})",
            expanded=False,
        ):
            for warn in comp.timestamp_warnings:
                st.warning(f"Timestamp & Freshness Notice: {warn}")

    highest_val_str = str(comp.highest_aqi_value) if comp.highest_aqi_value is not None else "N/A"
    lowest_val_str = str(comp.lowest_aqi_value) if comp.lowest_aqi_value is not None else "N/A"
    highest_station_str = comp.highest_aqi_station or "No valid AQI"
    lowest_station_str = comp.lowest_aqi_station or "No valid AQI"

    highest_sev = _extract_severity_for_station(
        comp.comparison_df, comp.highest_aqi_station, comp.available_severities
    )
    lowest_sev = _extract_severity_for_station(
        comp.comparison_df, comp.lowest_aqi_station, comp.available_severities
    )

    hi_col, lo_col = st.columns(2)
    with hi_col:
        st.markdown(
            f"""
            <div class="eco-highlight-card">
                <div class="eco-highlight-top">
                    <span class="eco-highlight-label">Highest AQI Location</span>
                    {_render_badge(highest_sev)}
                </div>
                <div class="eco-highlight-value">
                    {html.escape(highest_station_str)} ({html.escape(highest_val_str)})
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with lo_col:
        st.markdown(
            f"""
            <div class="eco-highlight-card">
                <div class="eco-highlight-top">
                    <span class="eco-highlight-label">Lowest AQI Location</span>
                    {_render_badge(lowest_sev)}
                </div>
                <div class="eco-highlight-value">
                    {html.escape(lowest_station_str)} ({html.escape(lowest_val_str)})
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    summary_text = _build_comparison_summary(comp, highest_sev, lowest_sev)
    st.markdown(
        f"""
        <div class="eco-surface-card" style="margin-top: 12px;">
            <div class="eco-summary-title">Comparison Summary</div>
            <div class="eco-summary-text">{html.escape(summary_text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Per-station cards row (3 per row)
    df = comp.comparison_df
    if not df.empty and "Station" in df.columns:
        rows_data = df.to_dict(orient="records")
        for row_start in range(0, len(rows_data), 3):
            chunk = rows_data[row_start : row_start + 3]
            card_cols = st.columns(3)
            for idx, rec in enumerate(chunk):
                st_name = _clean_location_label(str(rec.get("Station", "Station")))
                aqi_val = rec.get("Calculated AQI (CPCB)")
                if pd.isna(aqi_val):
                    aqi_val = rec.get("WAQI API AQI")
                aqi_display = "N/A" if aqi_val is None or pd.isna(aqi_val) else str(aqi_val)

                sev_val = None
                for k in ("Severity", "Category", "AQI Category", "Severity Tier"):
                    if k in rec and rec[k] is not None and not pd.isna(rec[k]):
                        sev_val = str(rec[k])
                        break
                sev_label = sev_val or (
                    comp.available_severities[0] if comp.available_severities else "Observed"
                )

                pm25_val = rec.get("PM25")
                if pm25_val is not None and not pd.isna(pm25_val):
                    sub_line = f"PM2.5: {pm25_val} µg/m³"
                else:
                    ts_val = rec.get("Observation Timestamp") or rec.get("Timestamp") or ""
                    sub_line = f"Stations compared: {comp.stations_compared}" + (
                        f" • {ts_val}" if ts_val else ""
                    )

                with card_cols[idx]:
                    st.markdown(
                        f"""
                        <div class="eco-city-card">
                            <div class="eco-city-header">
                                <span class="eco-city-name">{html.escape(st_name)}</span>
                                {_render_badge(sev_label)}
                            </div>
                            <div class="eco-city-aqi-row">
                                <span class="eco-city-aqi-num">{html.escape(aqi_display)}</span>
                                <span class="eco-city-aqi-unit">AQI</span>
                            </div>
                            <div class="eco-city-sub">{html.escape(sub_line)}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    c_left, c_right = st.columns(2)
    with c_left:
        with st.container(border=True):
            st.markdown("**AQI Comparison Across Locations (CPCB vs. WAQI)**")
            fig_aqi = go.Figure()
            fig_aqi.add_trace(
                go.Bar(
                    x=comp.comparison_df["Station"],
                    y=comp.comparison_df["Calculated AQI (CPCB)"],
                    name="Calculated AQI (CPCB)",
                    marker_color="#0E3B2E",
                )
            )
            fig_aqi.add_trace(
                go.Bar(
                    x=comp.comparison_df["Station"],
                    y=comp.comparison_df["WAQI API AQI"],
                    name="WAQI API AQI",
                    marker_color="#D97706",
                )
            )
            _apply_eco_chart_layout(
                fig_aqi,
                height=310,
                x_title="Station",
                y_title="AQI",
                barmode="group",
            )
            st.plotly_chart(fig_aqi, width="stretch", key="loc_comp_aqi_bar")

    with c_right:
        with st.container(border=True):
            st.markdown("**Pollutant & AQI Comparison Chart**")
            fig_pol = go.Figure()
            for key in POLLUTANT_KEYS:
                col_name = key.upper()
                if col_name in comp.comparison_df.columns and comp.comparison_df[col_name].notna().any():
                    fig_pol.add_trace(
                        go.Bar(
                            x=comp.comparison_df["Station"],
                            y=comp.comparison_df[col_name],
                            name=col_name,
                            marker_color=_POLLUTANT_BAR_COLORS.get(col_name, "#1F7A5A"),
                        )
                    )
            _apply_eco_chart_layout(
                fig_pol,
                height=310,
                x_title="Station",
                y_title="Reported Value",
                barmode="group",
            )
            st.plotly_chart(fig_pol, width="stretch", key="loc_comp_pollutant_bar")

    st.markdown(
        '<div class="eco-section-title">Station Comparison Table (With Observation Timestamps)</div>',
        unsafe_allow_html=True,
    )
    table_df = comp.comparison_df.copy()
    if "Station" in table_df.columns and display_to_raw:
        table_df["Raw Station Name"] = table_df["Station"].map(
            lambda s: display_to_raw.get(str(s), str(s))
        )
    st.dataframe(table_df, width="stretch", hide_index=True)

    st.markdown(
        """
        <div class="eco-panel" style="border-left-color:#0E3B2E;">
            <div class="eco-panel-title">Comparison Integrity Note</div>
            <div class="eco-panel-body">
                Every compared station displays its exact observation timestamp and freshness status.
                Do not treat readings with different observation timestamps as simultaneous snapshots.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


main()