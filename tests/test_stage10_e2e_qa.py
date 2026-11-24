from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock
import requests

from config import AppConfig, ENV_PATH
from src.activity import advise_activity_from_reading
from src.alerts import evaluate_alert_candidates, list_stored_alerts, persist_alerts
from src.analytics import compare_station_observations, compute_historical_analytics
from src.analytics.environmental_reports import generate_environmental_report, report_to_csv_bytes, report_to_pdf_bytes
from src.api.waqi_client import AqiReading, WaqiClient, WaqiClientError
from src.api.weather_client import WeatherClient, WeatherClientError
from src.chatbot import generate_assistant_response, route_query_to_services
from src.core import evaluate_aqi_from_reading, generate_health_advisory
from src.database import get_observations, save_observation_bundle
from src.intelligence import analyze_pollutants_from_reading, detect_anomalies, generate_source_insights
from src.prediction import load_mlp_artifact, predict_next_severity, train_and_save_mlp_model
from src.rag import get_or_build_vector_store
from src.validation import validate_aqi_reading


def _qa_cfg(waqi_tok: str = "tok_waqi", groq_key: str = "") -> AppConfig:
    base = Path(__file__).resolve().parent.parent
    return AppConfig(
        app_name="QA Environmental App",
        app_env="test",
        waqi_api_token=waqi_tok,
        groq_api_key=groq_key,
        groq_model="llama-3.3-70b-versatile",
        request_timeout_seconds=5,
        default_location="Delhi",
        base_dir=base,
        data_dir=base / "data",
        assets_dir=base / "assets",
    )


def test_end_to_end_13_step_pipeline(tmp_path: Path) -> None:
    db_file = tmp_path / "e2e.db"
    model_file = tmp_path / "e2e_mlp.joblib"
    kb_dir = tmp_path / "kb"
    idx_dir = tmp_path / "idx"

    # Seed 6 chronological readings for Delhi stations so analytics, MLP, anomalies, and reports run end-to-end
    base_dt = datetime(2026, 11, 24, 6, 0, 0, tzinfo=timezone.utc)
    pm25_seq = [45.0, 85.0, 140.0, 55.0, 160.0, 210.0]
    latest_reading: AqiReading | None = None

    for i, pm25_v in enumerate(pm25_seq):
        r = AqiReading(
            query="Delhi",
            station_name="ITO, Delhi, India",
            aqi=int(pm25_v * 1.4),
            aqi_raw=int(pm25_v * 1.4),
            dominant_pollutant="pm25",
            pollutants={
                "pm25": pm25_v,
                "pm10": pm25_v * 1.5,
                "no2": 38.0 + i * 4.0,
                "so2": 14.0,
                "co": 1.3,
                "o3": 32.0,
            },
            latitude=28.6289,
            longitude=77.2405,
            observation_time=(base_dt + timedelta(hours=i)).isoformat(),
        )
        val = validate_aqi_reading(r)
        assert val.is_valid is True
        aqi_res = evaluate_aqi_from_reading(r)
        pol_res = analyze_pollutants_from_reading(r)
        src_res = generate_source_insights(pol_res)
        adv_res = generate_health_advisory(aqi_res.category, dominant_pollutant=aqi_res.dominant_pollutant)

        obs_id, inserted = save_observation_bundle(
            r,
            validation=val,
            aqi_result=aqi_res,
            analysis=pol_res,
            source_insights=src_res,
            advisory=adv_res,
            db_path=db_file,
        )
        assert obs_id > 0 and inserted is True

        cands = evaluate_alert_candidates(r)
        persist_alerts(cands, query_city="Delhi", db_path=db_file)
        latest_reading = r

    assert latest_reading is not None
    stored = get_observations(location="ITO, Delhi, India", db_path=db_file)
    assert len(stored) == 6

    hist = compute_historical_analytics(stored)
    assert hist.observation_count == 6 and hist.has_sufficient_trend_data is True

    artifact = train_and_save_mlp_model(stored, artifact_path=model_file, max_iter=500)
    reloaded = load_mlp_artifact(model_file)
    pred = predict_next_severity(reloaded, latest_observation=stored[-1], previous_observation=stored[-2])
    assert pred.predicted_next_severity in reloaded.model.classes_

    anomalies = detect_anomalies(stored)
    assert len(anomalies) == 6

    get_or_build_vector_store(kb_dir=kb_dir, index_dir=idx_dir)
    routed = route_query_to_services(
        "What is the current AQI and dominant pollutant?",
        current_reading=latest_reading,
        db_path=db_file,
        model_path=model_file,
        kb_dir=kb_dir,
        index_dir=idx_dir,
    )
    chat_res = generate_assistant_response(
        "What is the current AQI and dominant pollutant?",
        routed=routed,
        app_config=_qa_cfg(groq_key=""),  # Verifies deterministic+RAG fallback when LLM unavailable
    )
    assert chat_res.used_llm is False
    assert "PM25" in chat_res.answer
    assert "PM10" in chat_res.answer

    routed_aqi = route_query_to_services(
        "What is the current AQI status right now?",
        current_reading=latest_reading,
        db_path=db_file,
        model_path=model_file,
        kb_dir=kb_dir,
        index_dir=idx_dir,
    )
    chat_aqi = generate_assistant_response(
        "What is the current AQI status right now?",
        routed=routed_aqi,
        app_config=_qa_cfg(groq_key=""),
    )
    assert "ITO, Delhi, India" in chat_aqi.answer

    rep = generate_environmental_report("Daily", reference_date=base_dt.date(), db_path=db_file)
    assert rep.sufficient_data is True
    assert report_to_pdf_bytes(rep).startswith(b"%PDF")
    assert b"ITO, Delhi, India" in report_to_csv_bytes(rep)


def test_fault_tolerance_and_degraded_modes(tmp_path: Path) -> None:
    # 1. Offline / WAQI failure raises typed WaqiClientError without unhandled crash
    bad_session = MagicMock()
    bad_session.get.side_effect = requests.ConnectionError("Offline")
    waqi = WaqiClient(app_config=_qa_cfg(), session=bad_session)
    try:
        waqi.get_city_aqi("Delhi")
        assert False
    except WaqiClientError:
        pass

    # 2. Weather failure is isolated from WAQI
    weather = WeatherClient(app_config=_qa_cfg(), session=bad_session)
    try:
        weather.get_current_weather(28.61, 77.20)
        assert False
    except WeatherClientError:
        pass

    # 3. Missing pollutants & insufficient history handled safely
    partial_reading = AqiReading(
        query="Delhi",
        station_name="Partial Station",
        aqi=None,
        aqi_raw=None,
        dominant_pollutant=None,
        pollutants={"pm25": None, "pm10": None, "no2": None, "so2": None, "co": None, "o3": None},
        latitude=None,
        longitude=None,
        observation_time=None,
    )
    val = validate_aqi_reading(partial_reading)
    assert val.is_valid is False
    act = advise_activity_from_reading("Running", partial_reading)
    assert "Unavailable" in act.aqi_category

    comp_empty = compare_station_observations([])
    assert comp_empty.stations_compared == 0

    alerts = list_stored_alerts(db_path=tmp_path / "empty_alerts.db")
    assert alerts == []


def test_security_gitignore_and_env_hygiene() -> None:
    root = Path(__file__).resolve().parent.parent
    gitignore = root / ".gitignore"
    assert gitignore.exists()
    gi_text = gitignore.read_text(encoding="utf-8")
    assert ".env" in gi_text
    assert "*.db" in gi_text or "data/" in gi_text

    env_example = root / ".env.example"
    assert env_example.exists()
    ex_text = env_example.read_text(encoding="utf-8")
    assert "WAQI_API_TOKEN=" in ex_text
    assert "GROQ_API_KEY=" in ex_text
    # Ensure .env.example never contains real secret tokens
    assert "gsk_" not in ex_text