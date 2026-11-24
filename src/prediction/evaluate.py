from dataclasses import dataclass, field
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support


@dataclass
class EvaluationReport:
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    weighted_f1: float
    labels: list[str] = field(default_factory=list)
    confusion_matrix: list[list[int]] = field(default_factory=list)
    per_class: dict[str, dict[str, float | int]] = field(default_factory=dict)
    test_sample_count: int = 0


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> EvaluationReport:
    if len(y_true) == 0 or len(y_pred) == 0:
        raise ValueError("Evaluation requires non-empty ground-truth and predicted arrays.")

    labels = sorted({str(x) for x in y_true} | {str(x) for x in y_pred})
    acc = float(accuracy_score(y_true, y_pred))
    prec_m, rec_m, f1_m, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="macro", zero_division=0
    )
    _, _, f1_w, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="weighted", zero_division=0
    )
    prec_c, rec_c, f1_c, sup_c = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average=None, zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=labels)

    per_class: dict[str, dict[str, float | int]] = {}
    for idx, lbl in enumerate(labels):
        per_class[lbl] = {
            "precision": round(float(prec_c[idx]), 4),
            "recall": round(float(rec_c[idx]), 4),
            "f1_score": round(float(f1_c[idx]), 4),
            "support": int(sup_c[idx]),
        }

    return EvaluationReport(
        accuracy=round(acc, 4),
        macro_precision=round(float(prec_m), 4),
        macro_recall=round(float(rec_m), 4),
        macro_f1=round(float(f1_m), 4),
        weighted_f1=round(float(f1_w), 4),
        labels=labels,
        confusion_matrix=cm.astype(int).tolist(),
        per_class=per_class,
        test_sample_count=int(len(y_true)),
    )