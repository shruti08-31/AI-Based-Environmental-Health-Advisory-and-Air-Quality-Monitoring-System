import streamlit as st

from config import config
from src.api import AqiReading
from src.chatbot import generate_assistant_response, route_query_to_services
from src.rag import get_or_build_vector_store
from src.utils import render_page_header, render_warning_banner


@st.cache_resource(show_spinner=False)
def _load_cached_rag_store():
    return get_or_build_vector_store()


EXAMPLE_QUESTIONS: tuple[str, ...] = (
    "What is the current AQI and dominant pollutant?",
    "What are the health effects of PM2.5 and how can I reduce exposure?",
    "What health precautions apply for sensitive groups right now?",
    "What is the historical AQI trend across stored observations?",
    "Is outdoor running or walking advisable right now?",
)


def main() -> None:
    render_page_header(
        title="AI Environmental Assistant",
        subtitle="Context-aware assistant combining deterministic AQI services, FAISS knowledge retrieval, and Groq LLM explanations.",
        is_placeholder=False,
    )

    # Ensure persisted FAISS index is loaded once without rebuilding on every rerun
    _load_cached_rag_store()

    if not config.has_groq_api_key:
        render_warning_banner(
            "GROQ_API_KEY is not configured in .env. The assistant will still route queries and answer using deterministic services and RAG excerpts.",
            is_placeholder=False,
        )

    top_left, top_right = st.columns([3, 1])
    with top_left:
        reading: AqiReading | None = st.session_state.get("waqi_last_reading")
        if reading is not None:
            st.caption(
                f"Active station context: **{reading.station_name or reading.query}** "
                f"(Observation: {reading.observation_time or 'N/A'})"
            )
        else:
            st.caption("No live station reading loaded yet (knowledge-base questions still work; fetch a station for live context).")
    with top_right:
        if st.button("Clear Conversation", width="stretch", key="btn_clear_chat_history"):
            st.session_state["assistant_chat_history"] = []
            st.rerun()

    st.markdown("**Example Questions**")
    ex_cols = st.columns(len(EXAMPLE_QUESTIONS))
    selected_example: str | None = None
    for idx, (col, q_text) in enumerate(zip(ex_cols, EXAMPLE_QUESTIONS)):
        with col:
            if st.button(q_text, width="stretch", key=f"example_q_{idx}"):
                selected_example = q_text

    history: list[dict[str, object]] = st.session_state.setdefault("assistant_chat_history", [])

    for msg in history:
        role = str(msg.get("role", "assistant"))
        with st.chat_message(role):
            st.markdown(str(msg.get("content", "")))
            meta = msg.get("meta")
            if isinstance(meta, dict):
                st.caption(
                    f"Routed Intent: `{meta.get('intent')}` | "
                    f"Engine: `{meta.get('engine')}`"
                )
                sources = meta.get("sources") or []
                if sources:
                    with st.expander("Retrieved Knowledge Sources"):
                        for src in sources:
                            st.write(f"• {src}")

    typed_prompt = st.chat_input("Ask about current AQI, pollutants, health precautions, trends, weather, or activities...")
    active_prompt = typed_prompt or selected_example

    if active_prompt:
        history.append({"role": "user", "content": active_prompt})
        with st.chat_message("user"):
            st.markdown(active_prompt)

        routed = route_query_to_services(
            user_query=active_prompt,
            current_reading=st.session_state.get("waqi_last_reading"),
        )
        assistant_res = generate_assistant_response(
            user_query=active_prompt,
            routed=routed,
            app_config=config,
            chat_history=history[:-1],
        )

        engine_label = (
            f"Groq ({assistant_res.model_name}) + Deterministic + RAG"
            if assistant_res.used_llm
            else "Deterministic + RAG Fallback"
        )
        meta_info = {
            "intent": assistant_res.intent.value,
            "engine": engine_label,
            "sources": assistant_res.sources_used,
        }
        history.append(
            {
                "role": "assistant",
                "content": assistant_res.answer,
                "meta": meta_info,
            }
        )

        with st.chat_message("assistant"):
            st.markdown(assistant_res.answer)
            st.caption(f"Routed Intent: `{meta_info['intent']}` | Engine: `{meta_info['engine']}`")
            if assistant_res.sources_used:
                with st.expander("Retrieved Knowledge Sources"):
                    for src in assistant_res.sources_used:
                        st.write(f"• {src}")


main()