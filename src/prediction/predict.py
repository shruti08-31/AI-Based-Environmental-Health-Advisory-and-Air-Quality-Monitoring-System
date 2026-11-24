from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import joblib
import numpy as np

from src.api.waqi_client import POLLUTANT_KEYS
from src.prediction.train import DEFAULT_MODEL_ARTIFACT_PATH, MODEL_LIMITATIONS, TrainingArtifact


@dataclass
class SeverityPredictionResult:
    predicted_next_severity: str
    confidence: float
    confidence_label: str
    class_probabilities: dict[str, float] = field(default_factory=dict)
    trained_at_utc: str = ""
    used_lag_features: bool = False
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=lambda: list(MODEL_LIMITATIONS))


def load_mlp_artifact(artifact_path: Path | str | None = None) -> TrainingArtifact:
    path = Path(artifact_path) if artifact_path is not None else DEFAULT_MODEL_ARTIFACT_PATH
    if not path.exists():
        raise FileNotFoundError(f"Trained MLP model artifact not found at '{path}'.")
    loaded = joblib.load(path)
    if not isinstance(loaded, TrainingArtifact):
        raise ValueError("Invalid model artifact format.")
    return loaded


def _confidence_tier(prob: float) -> str:
    if prob >= 0.75:
        return "High"
    if prob >= 0.50:
        return "Moderate"
    return "Low"


def predict_next_severity(
    artifact: TrainingArtifact,
    latest_observation: dict[str, Any],
    previous_observation: dict[str, Any] | None = None,
) -> SeverityPredictionResult:
    warnings: list[str] = list(artifact.warnings)

    def _clean_num(val: Any) -> float:
        if val is None or isinstance(val, bool):
            return np.nan
        try:
            f = float(val)
            return f if np.isfinite(f) and f >= 0.0 else np.nan
        except (TypeError, ValueError):
            return np.nan

    feature_vector: list[float] = []
    missing_inputs: list[str] = []

    for fname in artifact.feature_names:
        if fname in POLLUTANT_KEYS:
            v = _clean_num(latest_observation.get(fname))
            if np.isnan(v):
                missing_inputs.append(fname.upper())
            feature_vector.append(v)
        elif fname.endswith("_lag1") and fname != "prev_aqi_lag1":
            base_k = fname[: -len("_lag1")]
            prev_v = _clean_num(previous_observation.get(base_k)) if previous_observation else np.nan
            if np.isnan(prev_v):
                prev_v = _clean_num(latest_observation.get(base_k))
            feature_vector.append(prev_v)
        elif fname == "prev_aqi_lag1":
            prev_aqi = (
                _clean_num(previous_observation.get("calculated_aqi"))
                if previous_observation
                else np.nan
            )
            if np.isnan(prev_aqi) and previous_observation:
                prev_aqi = _clean_num(previous_observation.get("waqi_reported_aqi"))
            if np.isnan(prev_aqi):
                prev_aqi = _clean_num(latest_observation.get("calculated_aqi"))
            feature_vector.append(prev_aqi)
        else:
            feature_vector.append(np.nan)

    if missing_inputs:
        warnings.append(
            "Missing current pollutant inputs imputed via training median: " + ", ".join(missing_inputs)
        )

    X_arr = np.array([feature_vector], dtype=float)
    X_imp = artifact.imputer.transform(X_arr)
    X_scaled = artifact.scaler.transform(X_imp)

    probs = artifact.model.predict_proba(X_scaled)[0]
    classes = [str(c) for c in artifact.model.classes_]
    prob_map = {cls: round(float(p), 4) for cls, p in zip(classes, probs)}

    best_idx = int(np.argmax(probs))
    pred_label = classes[best_idx]
    top_prob = round(float(probs[best_idx]), 4)

    return SeverityPredictionResult(
        predicted_next_severity=pred_label,
        confidence=top_prob,
        confidence_label=_confidence_tier(top_prob),
        class_probabilities=prob_map,
        trained_at_utc=artifact.trained_at_utc,
        used_lag_features=artifact.used_lag_features,
        warnings=warnings,
        limitations=list(artifact.limitations),
    )