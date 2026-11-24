import html
import streamlit as st

from config import config
from src.api import AqiReading
from src.chatbot import generate_assistant_response, route_query_to_services
from src.rag import get_or_build_vector_store
from src.utils import render_warning_banner


@st.cache_resource(show_spinner=False)
def _load_cached_rag_store():
    return get_or_build_vector_store()


EXAMPLE_QUESTIONS: tuple[tuple[str, str], ...] = (
    ("Current AQI & Pollutant", "What is the current AQI and dominant pollutant?"),
    ("PM2.5 & Exposure Tips", "What are the health effects of PM2.5 and how can I reduce exposure?"),
    ("Sensitive Groups Care", "What health precautions apply for sensitive groups right now?"),
    ("Historical Trend", "What is the historical AQI trend across stored observations?"),
    ("Running or Walking?", "Is outdoor running or walking advisable right now?"),
)


def _inject_assistant_gemini_theme() -> None:
    st.markdown(
        """
        <style>
        /* Remove Streamlit's default top dark header bar */
        [data-testid="stHeader"],
        header[data-testid="stHeader"],
        [data-testid="stDecoration"],
        [data-testid="stToolbar"] {
            display: none !important;
        }

        /* Main canvas & typography */
        .stApp {
            background-color: #F7F9F8;
            color: #16261E;
        }
        .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 6.5rem !important;
            max-width: 980px;
        }

        /* Deep forest-green sidebar */
        [data-testid="stSidebar"] {
            background-color: #133A2A !important;
            border-right: 1px solid #0E2C20;
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
            background-color: #315B48 !important;
            font-weight: 600;
        }

        /* Top breadcrumb & context strip */
        .eco-topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
            padding-bottom: 0.55rem;
            border-bottom: 1px solid #E4ECE7;
        }
        .eco-breadcrumb {
            font-size: 0.92rem;
            color: #5E7167;
        }
        .eco-breadcrumb strong {
            color: #16261E;
            font-weight: 600;
        }
        .eco-pill {
            background: #EAF3EC;
            border: 1px solid #CBE0D1;
            border-radius: 999px;
            padding: 4px 12px;
            font-size: 0.77rem;
            font-weight: 600;
            color: #1A4D38;
        }
        .eco-dot {
            display: inline-block;
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: #22A06B;
            margin-right: 6px;
        }

        /* Gemini-inspired Hero Greeting (shown on empty chat) */
        .gem-welcome {
            background: linear-gradient(135deg, #F1F7F2 0%, #E3EFE6 100%);
            border: 1px solid #D5E5DA;
            border-radius: 22px;
            padding: 28px 32px;
            margin: 0.75rem 0 1.1rem 0;
        }
        .gem-sparkle {
            display: inline-block;
            font-size: 1.2rem;
            color: #1F7A5A;
            margin-bottom: 6px;
        }
        .gem-greeting {
            font-size: 1.75rem;
            font-weight: 700;
            color: #133A2A;
            line-height: 1.22;
            margin: 0 0 6px 0;
        }
        .gem-sub {
            font-size: 0.92rem;
            color: #4A6055;
            margin: 0;
        }

        /* Starter Suggestion Chips */
        div.stButton > button {
            background-color: #FFFFFF;
            color: #133A2A;
            border: 1px solid #CFE0D5;
            border-radius: 999px;
            font-size: 0.80rem;
            font-weight: 600;
            padding: 0.42rem 0.85rem;
            transition: all 0.15s ease;
            box-shadow: 0 1px 3px rgba(19, 58, 42, 0.04);
        }
        div.stButton > button:hover {
            background-color: #EAF4EC;
            border-color: #1F7A5A;
            color: #0E2C20;
        }

        /* Toggle text color */
        [data-testid="stToggle"] label,
        [data-testid="stToggle"] label p {
            color: #1B5E3F !important;
            font-weight: 600 !important;
            font-size: 0.82rem !important;
        }

        /* Chat Message Styling (Gemini-like clean bubbles) */
        [data-testid="stChatMessage"] {
            background-color: #FFFFFF;
            border: 1px solid #E3ECE6;
            border-radius: 18px;
            padding: 16px 20px;
            margin-bottom: 0.85rem;
            box-shadow: 0 2px 8px rgba(19, 58, 42, 0.03);
        }
        [data-testid="stChatMessage"] p,
        [data-testid="stChatMessage"] li,
        [data-testid="stChatMessage"] span {
            color: #16261E !important;
            line-height: 1.6;
        }
        [data-testid="stChatMessage"] a {
            color: #1B6B4A !important;
            font-weight: 600;
            text-decoration: underline;
        }

        /* Metadata badge row inside assistant bubble */
        .gem-meta-bar {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
            padding-top: 8px;
            border-top: 1px solid #EEF3F0;
        }
        .gem-meta-chip {
            background: #F2F7F4;
            border: 1px solid #DCE8E0;
            border-radius: 999px;
            padding: 2px 10px;
            font-size: 0.72rem;
            font-weight: 600;
            color: #2B4C3C;
        }

        /* Bottom Chat Input Container (light green pill bar) */
        [data-testid="stBottom"],
        [data-testid="stBottom"] > div {
            background-color: #F7F9F8 !important;
        }
        [data-testid="stChatInput"] {
            background-color: #EAF4EC !important;
            border: 1.5px solid #B4D6BE !important;
            border-radius: 26px !important;
            box-shadow: 0 4px 16px rgba(19, 58, 42, 0.07) !important;
        }
        [data-testid="stChatInput"] textarea {
            background-color: transparent !important;
            color: #133A2A !important;
            -webkit-text-fill-color: #133A2A !important;
            font-weight: 500 !important;
        }
        [data-testid="stChatInput"] textarea::placeholder {
            color: #547363 !important;
            -webkit-text-fill-color: #547363 !important;
        }
        [data-testid="stChatInput"] button {
            background-color: #133A2A !important;
            color: #FFFFFF !important;
            border-radius: 50% !important;
        }
        [data-testid="stChatInput"] button svg {
            fill: #FFFFFF !important;
            color: #FFFFFF !important;
        }

        /* Sources Expander */
        [data-testid="stExpander"] {
            background-color: #F8FAF9 !important;
            border: 1px solid #E2ECE6 !important;
            border-radius: 12px !important;
            margin-top: 8px;
        }
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary p {
            color: #1B5E3F !important;
            font-weight: 600 !important;
            font-size: 0.80rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_assistant_meta(meta: dict[str, object]) -> None:
    intent_txt = html.escape(str(meta.get("intent") or "General"))
    engine_txt = html.escape(str(meta.get("engine") or "Deterministic + RAG"))
    st.markdown(
        f"""
        <div class="gem-meta-bar">
            <span class="gem-meta-chip">Intent: {intent_txt}</span>
            <span class="gem-meta-chip">Engine: {engine_txt}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    sources = meta.get("sources") or []
    if sources:
        with st.expander("Sources Cited (Gov / Health Websites & Knowledge Base)"):
            for src in sources:
                st.markdown(f"- {src}")


def main() -> None:
    _inject_assistant_gemini_theme()

    # Ensure persisted FAISS index is loaded once without rebuilding on every rerun
    _load_cached_rag_store()

    reading: AqiReading | None = st.session_state.get("waqi_last_reading")
    station_label = (
        f"{reading.station_name or reading.query} ({reading.observation_time or 'Live'})"
        if reading is not None
        else "No live station loaded"
    )

    st.markdown(
        f"""
        <div class="eco-topbar">
            <div class="eco-breadcrumb">EcoHealth &nbsp;/&nbsp; <strong>AI Environmental Assistant</strong></div>
            <div class="eco-pill"><span class="eco-dot"></span>{html.escape(station_label)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not config.has_groq_api_key:
        render_warning_banner(
            "GROQ_API_KEY is not configured in .env. The assistant will still route queries and answer using deterministic services and RAG excerpts.",
            is_placeholder=False,
        )

    ctrl_left, ctrl_right = st.columns([3.2, 1.1])
    with ctrl_left:
        enable_web_sources = st.toggle(
            "Search Gov & Health Websites (WHO, EPA, CPCB)",
            value=True,
            key="toggle_rag_web_search",
        )
    with ctrl_right:
        if st.button("New Chat", width="stretch", key="btn_clear_chat_history"):
            st.session_state["assistant_chat_history"] = []
            st.rerun()

    history: list[dict[str, object]] = st.session_state.setdefault("assistant_chat_history", [])
    typed_prompt = st.chat_input("Ask EcoHealth about live AQI, pollutants, health guidance, trends, or outdoor plans...")

    selected_prompt: str | None = None

    # Gemini-inspired centered welcome + prompt chips when conversation is empty
    if not history and not typed_prompt:
        station_hint = (
            f"Currently monitoring <strong>{html.escape(reading.station_name or reading.query)}</strong>."
            if reading is not None
            else "Fetch a station on <strong>Live AQI Monitoring</strong> for real-time telemetry, or ask any air-quality question below."
        )
        st.markdown(
            f"""
            <div class="gem-welcome">
                <div class="gem-sparkle">&#10022; EcoHealth Intelligence</div>
                <div class="gem-greeting">Hello! How can I help with today's air quality?</div>
                <p class="gem-sub">{station_hint}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Two clean rows of pill suggestions (3 + 2) so labels never truncate
        row1 = st.columns(3)
        for idx in range(3):
            btn_label, full_q = EXAMPLE_QUESTIONS[idx]
            with row1[idx]:
                if st.button(btn_label, width="stretch", key=f"example_q_{idx}"):
                    selected_prompt = full_q

        row2 = st.columns([0.5, 1.5, 1.5, 0.5])
        for offset, idx in enumerate((3, 4), start=1):
            btn_label, full_q = EXAMPLE_QUESTIONS[idx]
            with row2[offset]:
                if st.button(btn_label, width="stretch", key=f"example_q_{idx}"):
                    selected_prompt = full_q

    active_prompt = typed_prompt or selected_prompt

    # Render prior messages
    for msg in history:
        role = str(msg.get("role", "assistant"))
        avatar = "🌿" if role == "assistant" else "👤"
        with st.chat_message(role, avatar=avatar):
            st.markdown(str(msg.get("content", "")))
            meta = msg.get("meta")
            if role == "assistant" and isinstance(meta, dict):
                _render_assistant_meta(meta)

    if active_prompt:
        prior_turns = list(history)
        history.append({"role": "user", "content": active_prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(active_prompt)

        with st.chat_message("assistant", avatar="🌿"):
            with st.spinner("Analyzing station telemetry & trusted environmental sources..."):
                routed = route_query_to_services(
                    user_query=active_prompt,
                    current_reading=st.session_state.get("waqi_last_reading"),
                    use_web_search=enable_web_sources,
                )
                assistant_res = generate_assistant_response(
                    user_query=active_prompt,
                    routed=routed,
                    app_config=config,
                    chat_history=prior_turns,
                )

            engine_label = (
                f"Groq ({assistant_res.model_name}) + Deterministic + RAG"
                if assistant_res.used_llm
                else "Deterministic + RAG Fallback"
            )
            meta_info: dict[str, object] = {
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

            st.markdown(assistant_res.answer)
            _render_assistant_meta(meta_info)


main()