from pathlib import Path
from unittest.mock import MagicMock
import requests

from config import AppConfig
from src.api.waqi_client import AqiReading
from src.chatbot.intent_router import QueryIntent, classify_intent, route_query_to_services
from src.chatbot.response_generator import STRICT_SYSTEM_PROMPT, generate_assistant_response
from src.rag.retrieval import get_or_build_vector_store, retrieve_relevant_knowledge


def _cfg(groq_key: str = "gsk_test_key") -> AppConfig:
    base = Path(__file__).resolve().parent.parent
    return AppConfig(
        app_name="Test App",
        app_env="test",
        waqi_api_token="waqi_tok",
        groq_api_key=groq_key,
        groq_model="llama-3.3-70b-versatile",
        request_timeout_seconds=5,
        default_location="Delhi",
        base_dir=base,
        data_dir=base / "data",
        assets_dir=base / "assets",
    )


def test_rag_document_processing_persistence_and_retrieval(tmp_path: Path) -> None:
    kb_dir = tmp_path / "kb"
    idx_dir = tmp_path / "idx"

    store1 = get_or_build_vector_store(kb_dir=kb_dir, index_dir=idx_dir)
    assert len(store1.chunks) >= 9
    assert (idx_dir / "knowledge.faiss").exists()

    # Second call reloads persisted index cleanly
    store2 = get_or_build_vector_store(kb_dir=kb_dir, index_dir=idx_dir)
    assert len(store2.chunks) == len(store1.chunks)

    hits = retrieve_relevant_knowledge(
        "How does PM2.5 affect asthma and lungs?",
        top_k=3,
        kb_dir=kb_dir,
        index_dir=idx_dir,
    )
    assert len(hits) >= 1
    assert any("pm2" in h.title.lower() or "sensitive" in h.title.lower() for h in hits)


def test_intent_classification_all_10_categories() -> None:
    assert classify_intent("What is the current AQI right now?") == QueryIntent.CURRENT_AQI
    assert classify_intent("Which pollutant has the highest sub-index?") == QueryIntent.POLLUTANT_ANALYSIS
    assert classify_intent("What health precautions should asthma patients take?") == QueryIntent.HEALTH_PRECAUTIONS
    assert classify_intent("What is ground-level ozone?") == QueryIntent.ENVIRONMENTAL_KNOWLEDGE
    assert classify_intent("Show historical average AQI trend over time") == QueryIntent.HISTORICAL_ANALYSIS
    assert classify_intent("Compare air quality across stations") == QueryIntent.LOCATION_COMPARISON
    assert classify_intent("Predict the next observation severity") == QueryIntent.PREDICTION
    assert classify_intent("Explain any sudden jump or anomaly detected") == QueryIntent.ANOMALY_EXPLANATION
    assert classify_intent("How does wind speed and humidity relate today?") == QueryIntent.WEATHER_CONTEXT
    assert classify_intent("Is outdoor running or walking safe right now?") == QueryIntent.ACTIVITY_RECOMMENDATIONS


def test_groq_response_and_graceful_failure_fallback(tmp_path: Path) -> None:
    reading = AqiReading(
        query="Delhi",
        station_name="ITO, Delhi",
        aqi=185,
        aqi_raw=185,
        dominant_pollutant="pm25",
        pollutants={"pm25": 95.0, "pm10": None, "no2": 40.0, "so2": 12.0, "co": 1.4, "o3": 35.0},
        latitude=28.6289,
        longitude=77.2405,
        observation_time="2026-11-24T08:00:00+00:00",
    )
    routed = route_query_to_services(
        "Analyze current pollutants and missing data",
        current_reading=reading,
        db_path=tmp_path / "db.sqlite",
        kb_dir=tmp_path / "kb",
        index_dir=tmp_path / "idx",
    )
    assert "pm10" in routed.structured_facts["missing_pollutants"]

    # 1. Successful mocked Groq response
    session = MagicMock()
    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.json.return_value = {
        "choices": [{"message": {"content": "PM2.5 is dominant; PM10 is missing and not invented."}}]
    }
    session.post.return_value = ok_resp

    res_ok = generate_assistant_response("Analyze pollutants", routed, app_config=_cfg(), session=session)
    assert res_ok.used_llm is True
    assert "PM2.5" in res_ok.answer
    sent_payload = session.post.call_args.kwargs["json"]
    assert sent_payload["messages"][0]["content"] == STRICT_SYSTEM_PROMPT

    # 2. Groq network timeout falls back to deterministic output without crashing
    session.post.side_effect = requests.Timeout("Groq timeout")
    res_fallback = generate_assistant_response("Analyze pollutants", routed, app_config=_cfg(), session=session)
    assert res_fallback.used_llm is False
    assert "PM25" in res_fallback.answer
    assert "PM10" in res_fallback.answer