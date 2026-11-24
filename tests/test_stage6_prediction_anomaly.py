from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.intelligence.anomaly_detection import detect_anomalies
from src.prediction.predict import load_mlp_artifact, predict_next_severity
from src.prediction.preprocessing import build_supervised_severity_dataset, clean_historical_observations
from src.prediction.train import train_and_save_mlp_model


def _make_history(count: int = 12) -> list[dict]:
    start = datetime(2026, 11, 20, 0, 0, 0, tzinfo=timezone.utc)
    rows: list[dict] = []
    for i in range(count):
        # Alternate between Good/Satisfactory and Moderate/Poor regimes across real chronological rows
        pm25 = 22.0 if i % 3 == 0 else (75.0 if i % 3 == 1 else 105.0)
        pm10 = 40.0 if i % 3 == 0 else (120.0 if i % 3 == 1 else 180.0)
        rows.append(
            {
                "station_name": "Test Station",
                "query_city": "Delhi",
                "observation_time": (start + timedelta(hours=i * 3)).isoformat(),
                "pm25": pm25,
                "pm10": pm10,
                "no2": 35.0 + (i % 4) * 10.0,
                "so2": 12.0,
                "co": 1.1,
                "o3": 45.0,
                "is_valid": 1,
            }
        )
    return rows


def test_preprocessing_train_save_load_predict_evaluate(tmp_path: Path) -> None:
    history = _make_history(count=12)
    cleaned_df, _ = clean_historical_observations(history)
    assert len(cleaned_df) == 12

    ds = build_supervised_severity_dataset(history)
    assert ds.total_supervised_pairs >= 4
    assert len(ds.X_train) > 0 and len(ds.X_test) > 0

    model_path = tmp_path / "mlp_test.joblib"
    artifact = train_and_save_mlp_model(history, artifact_path=model_path, max_iter=150)
    assert model_path.exists()
    assert 0.0 <= artifact.evaluation.accuracy <= 1.0
    assert len(artifact.evaluation.confusion_matrix) > 0

    reloaded = load_mlp_artifact(model_path)
    pred = predict_next_severity(
        reloaded,
        latest_observation=history[-1],
        previous_observation=history[-2],
    )
    assert pred.predicted_next_severity in reloaded.model.classes_
    assert 0.0 <= pred.confidence <= 1.0
    assert sum(pred.class_probabilities.values()) > 0.99


def test_anomaly_detection_sudden_jump_and_invalid_exclusion() -> None:
    start = datetime(2026, 11, 24, 0, 0, 0, tzinfo=timezone.utc)
    obs = [
        {
            "station_name": "Station X",
            "observation_time": start.isoformat(),
            "pm25": 20.0,
            "pm10": 35.0,
            "no2": 20.0,
            "so2": 10.0,
            "co": 0.8,
            "o3": 30.0,
            "is_valid": 1,
        },
        {
            "station_name": "Station X",
            "observation_time": (start + timedelta(hours=1)).isoformat(),
            "pm25": 180.0,
            "pm10": 290.0,
            "no2": 95.0,
            "so2": 25.0,
            "co": 2.5,
            "o3": 50.0,
            "is_valid": 1,
        },
        {
            "station_name": "Station X",
            "observation_time": (start + timedelta(hours=2)).isoformat(),
            "pm25": -999.0,
            "is_valid": 0,
        },
    ]

    findings = detect_anomalies(obs, aqi_jump_threshold=50.0)
    # Invalid row excluded
    assert len(findings) == 2
    assert findings[1].is_anomaly is True
    assert findings[1].aqi_delta is not None and findings[1].aqi_delta > 50.0
    assert findings[1].evidence_strength in ("Low", "Moderate", "High")