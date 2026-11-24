import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.database import get_observations, list_stations
from src.prediction import (
    DEFAULT_MODEL_ARTIFACT_PATH,
    load_mlp_artifact,
    predict_next_severity,
    train_and_save_mlp_model,
)
from src.utils import (
    render_aqi_indicator,
    render_info_panel,
    render_metric_card,
    render_page_header,
    render_warning_banner,
)


def main() -> None:
    render_page_header(
        title="AQI Prediction (MLP Next-Step Severity)",
        subtitle="Train and evaluate a scikit-learn MLPClassifier on historical observations to predict next-observation severity.",
        is_placeholder=False,
    )

    stations = list_stations()
    station_options = ["All Locations"] + [str(s["station_name"]) for s in stations]

    c_loc, c_btn = st.columns([2.5, 1.5])
    with c_loc:
        selected_loc = st.selectbox(
            "Historical Training Scope",
            options=station_options,
            index=0,
            key="mlp_train_station_scope",
        )
    with c_btn:
        st.write("")
        train_clicked = st.button("Train & Evaluate MLP", width="stretch", key="btn_train_mlp")

    obs_rows = get_observations(location=selected_loc, limit=1000)

    if train_clicked:
        try:
            artifact = train_and_save_mlp_model(obs_rows, artifact_path=DEFAULT_MODEL_ARTIFACT_PATH)
            st.session_state["mlp_artifact"] = artifact
            st.success(
                f"Trained MLP on {artifact.training_rows} samples and evaluated on {artifact.test_rows} chronological test samples."
            )
        except ValueError as exc:
            st.error(f"Cannot train MLP yet: {exc}")

    artifact = st.session_state.get("mlp_artifact")
    if artifact is None and DEFAULT_MODEL_ARTIFACT_PATH.exists():
        try:
            artifact = load_mlp_artifact(DEFAULT_MODEL_ARTIFACT_PATH)
            st.session_state["mlp_artifact"] = artifact
        except Exception as exc:
            st.warning(f"Saved model artifact could not be loaded: {exc}")

    if artifact is None:
        render_warning_banner(
            "No trained MLP model available yet. Collect at least 4 valid historical observations on 'Live AQI Monitoring' and click 'Train & Evaluate MLP'.",
            is_placeholder=False,
        )
        return

    ev = artifact.evaluation
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_metric_card("Test Accuracy", f"{ev.accuracy * 100:.1f}%", f"n={ev.test_sample_count} test rows", is_placeholder=False)
    with m2:
        render_metric_card("Macro Precision", f"{ev.macro_precision:.2f}", "Unweighted class mean", is_placeholder=False)
    with m3:
        render_metric_card("Macro Recall", f"{ev.macro_recall:.2f}", "Unweighted class mean", is_placeholder=False)
    with m4:
        render_metric_card("Macro F1-Score", f"{ev.macro_f1:.2f}", f"Weighted F1: {ev.weighted_f1:.2f}", is_placeholder=False)

    if obs_rows:
        latest_obs = obs_rows[-1]
        prev_obs = obs_rows[-2] if len(obs_rows) >= 2 else None
        pred_res = predict_next_severity(artifact, latest_observation=latest_obs, previous_observation=prev_obs)

        p1, p2 = st.columns([1, 2])
        with p1:
            render_aqi_indicator(
                severity=pred_res.predicted_next_severity,
                status_text=(
                    f"Next-observation prediction (not current AQI) • "
                    f"Confidence: {pred_res.confidence * 100:.1f}% ({pred_res.confidence_label})"
                ),
                is_placeholder=False,
            )
        with p2:
            prob_df = pd.DataFrame(
                [{"Severity Class": k, "Probability": v} for k, v in pred_res.class_probabilities.items()]
            )
            with st.container(border=True):
                st.markdown("**Predicted Class Probabilities (Next Observation)**")
                if not prob_df.empty:
                    fig_prob = go.Figure(
                        go.Bar(x=prob_df["Severity Class"], y=prob_df["Probability"], marker_color="#0284C7")
                    )
                    fig_prob.update_layout(
                        height=240,
                        margin={"l": 40, "r": 20, "t": 15, "b": 35},
                        yaxis={"range": [0, 1], "title": "Probability"},
                    )
                    st.plotly_chart(fig_prob, width="stretch", key="mlp_class_probs_chart")

    st.markdown("### Class-Wise Evaluation & Confusion Matrix")
    c_cls, c_cm = st.columns(2)
    with c_cls:
        cls_rows = [
            {"Category": k, **v}
            for k, v in ev.per_class.items()
        ]
        if cls_rows:
            st.dataframe(pd.DataFrame(cls_rows), width="stretch", hide_index=True)
    with c_cm:
        if ev.confusion_matrix and ev.labels:
            cm_df = pd.DataFrame(ev.confusion_matrix, index=ev.labels, columns=ev.labels)
            st.caption("Rows: True Next Severity | Columns: Predicted Next Severity")
            st.dataframe(cm_df, width="stretch")

    render_info_panel(
        title="Model Metadata, Confidence & Limitations",
        body=(
            f"**Trained At:** {artifact.trained_at_utc}<br>"
            f"**Features Used:** {', '.join(f.upper() for f in artifact.feature_names)}<br>"
            f"**Lagged Features Active:** {'Yes' if artifact.used_lag_features else 'No'}<br>"
            + "<br>".join(f"• {lim}" for lim in artifact.limitations)
        ),
        is_placeholder=False,
    )


main()