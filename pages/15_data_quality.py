from pathlib import Path
import streamlit as st

from config import config
from src.api import POLLUTANT_KEYS, AqiReading, WaqiClient
from src.database import DEFAULT_DB_PATH, get_connection, get_observations, list_stations
from src.prediction import DEFAULT_MODEL_ARTIFACT_PATH
from src.rag import DEFAULT_INDEX_DIR
from src.utils import (
    render_info_panel,
    render_metric_card,
    render_page_header,
    render_warning_banner,
)
from src.validation import validate_aqi_reading


def _check_sqlite_health(db_path: Path = DEFAULT_DB_PATH) -> tuple[bool, str]:
    try:
        with get_connection(db_path) as conn:
            conn.execute("SELECT 1").fetchone()
        obs_cnt = len(get_observations(limit=1000, db_path=db_path))
        st_cnt = len(list_stations(db_path=db_path))
        return True, f"Connected ({st_cnt} station(s), {obs_cnt} stored observation(s))"
    except Exception as exc:
        return False, f"Database error: {exc}"


def main() -> None:
    render_page_header(
        title="Data Quality & System Health",
        subtitle="Telemetry completeness vs. measurement accuracy, retrieval status, and subsystem availability.",
        is_placeholder=False,
    )

    reading: AqiReading | None = st.session_state.get("waqi_last_reading")
    db_ok, db_detail = _check_sqlite_health()

    mlp_ready = DEFAULT_MODEL_ARTIFACT_PATH.exists()
    rag_ready = (DEFAULT_INDEX_DIR / "knowledge.faiss").exists() and (DEFAULT_INDEX_DIR / "knowledge_meta.joblib").exists()
    groq_ready = config.has_groq_api_key
    waqi_token_ready = config.has_api_token

    st.info(
        "**Completeness vs. Accuracy:** *Data completeness* measures whether expected fields/pollutants are present "
        "(non-null). *Measurement accuracy / validity* reflects sensor/API plausibility and timestamp freshness "
        "(e.g., rejecting negative readings or flagging stale timestamps)—a reading can be 100% complete yet stale or inaccurate."
    )

    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    with r1c1:
        render_metric_card(
            "WAQI API Token",
            "Configured" if waqi_token_ready else "Missing",
            "Live endpoint token status",
            is_placeholder=False,
        )
    with r1c2:
        render_metric_card(
            "SQLite Database",
            "Online" if db_ok else "Error",
            db_detail,
            is_placeholder=False,
        )
    with r1c3:
        render_metric_card(
            "MLP Severity Model",
            "Available" if mlp_ready else "Not Trained Yet",
            "Artifact: mlp_aqi_severity_model.joblib",
            is_placeholder=False,
        )
    with r1c4:
        render_metric_card(
            "RAG & Groq LLM",
            f"RAG: {'Ready' if rag_ready else 'Init'} | LLM: {'Key Set' if groq_ready else 'Fallback'}",
            f"Groq model: {config.groq_model}",
            is_placeholder=False,
        )

    all_obs = get_observations(limit=1000)
    stale_total = sum(1 for o in all_obs if int(o.get("is_stale", 0)) == 1)
    invalid_total = sum(1 for o in all_obs if int(o.get("is_valid", 1)) == 0)

    if reading is None:
        render_warning_banner(
            "No live WAQI reading is currently active in session. Stored database quality counts are shown below.",
            is_placeholder=True,
        )
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            render_metric_card("Last Successful Retrieval", "None in Session", "Fetch on Live AQI Monitoring", is_placeholder=True)
        with m2:
            render_metric_card("Active Completeness", "N/A", "Awaiting active reading", is_placeholder=True)
        with m3:
            render_metric_card("Stored Stale Records", str(stale_total), "Flagged stale timestamps", is_placeholder=False)
        with m4:
            render_metric_card("Stored Invalid Records", str(invalid_total), "Flagged invalid observations", is_placeholder=False)
        return

    val = validate_aqi_reading(reading)
    missing_pols = [k.upper() for k in POLLUTANT_KEYS if reading.pollutants.get(k) is None]

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_metric_card(
            "Last Successful Retrieval",
            reading.observation_time or "Timestamp Missing",
            f"Station: {reading.station_name or reading.query}",
            is_placeholder=False,
        )
    with m2:
        render_metric_card(
            "Pollutant Completeness",
            f"{int(val.completeness_ratio * 100)}%",
            f"{6 - len(missing_pols)} of 6 pollutants present",
            is_placeholder=False,
        )
    with m3:
        render_metric_card(
            "Reading Validity (Accuracy Gate)",
            "Valid" if val.is_valid else "Invalid / Flagged",
            "Stale" if val.is_stale else "Fresh",
            is_placeholder=False,
        )
    with m4:
        render_metric_card(
            "Missing Pollutants",
            str(len(missing_pols)),
            ", ".join(missing_pols) if missing_pols else "All 6 pollutants present",
            is_placeholder=False,
        )

    render_info_panel(
        title="Validation Warnings & Notes",
        body="<br>".join(f"• {w}" for w in val.warnings) if val.warnings else "No validation warnings on active reading.",
        is_placeholder=False,
    )


main()