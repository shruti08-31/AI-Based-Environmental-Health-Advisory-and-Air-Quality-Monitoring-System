from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import joblib
from sklearn.neural_network import MLPClassifier

from config import config
from src.prediction.evaluate import EvaluationReport, evaluate_predictions
from src.prediction.preprocessing import PreprocessedDataset, build_supervised_severity_dataset

DEFAULT_MODEL_ARTIFACT_PATH = config.data_dir / "mlp_aqi_severity_model.joblib"

MODEL_LIMITATIONS: list[str] = [
    "Trained strictly on historical observation sequences; never uses fabricated rows or a single point-in-time reading.",
    "Predicts the next-observation severity category only—it does not replace deterministic CPCB AQI calculation for current air quality.",
    "Small or single-city historical datasets may have class imbalance or limited regime coverage; treat predictions as probabilistic decision support.",
]


@dataclass
class TrainingArtifact:
    model: MLPClassifier
    imputer: Any
    scaler: Any
    feature_names: list[str]
    used_lag_features: bool
    trained_at_utc: str
    training_rows: int
    test_rows: int
    evaluation: EvaluationReport
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=lambda: list(MODEL_LIMITATIONS))


def train_and_save_mlp_model(
    observations: list[dict[str, Any]],
    artifact_path: Path | str | None = None,
    hidden_layer_sizes: tuple[int, ...] = (32, 16),
    max_iter: int = 400,
    random_state: int = 42,
) -> TrainingArtifact:
    dataset: PreprocessedDataset = build_supervised_severity_dataset(observations)

    clf = MLPClassifier(
        hidden_layer_sizes=hidden_layer_sizes,
        activation="relu",
        solver="adam",
        max_iter=max_iter,
        random_state=random_state,
        early_stopping=len(dataset.X_train) >= 12,
    )
    clf.fit(dataset.X_train, dataset.y_train)

    y_pred = clf.predict(dataset.X_test)
    eval_report = evaluate_predictions(dataset.y_test, y_pred)

    artifact = TrainingArtifact(
        model=clf,
        imputer=dataset.imputer,
        scaler=dataset.scaler,
        feature_names=dataset.feature_names,
        used_lag_features=dataset.used_lag_features,
        trained_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        training_rows=int(len(dataset.X_train)),
        test_rows=int(len(dataset.X_test)),
        evaluation=eval_report,
        warnings=dataset.warnings,
        limitations=list(MODEL_LIMITATIONS),
    )

    out_path = Path(artifact_path) if artifact_path is not None else DEFAULT_MODEL_ARTIFACT_PATH
    if str(out_path) != ":memory:":
        out_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(artifact, out_path)

    return artifact