from dataclasses import dataclass, field
import json
from typing import Any
import requests

from config import AppConfig, config
from src.chatbot.intent_router import QueryIntent, RoutedContext

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"

# Ordered fallback list of Groq production models so an account/tier restriction never triggers a 404 fallback
GROQ_FALLBACK_MODELS: tuple[str, ...] = (
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
)

STRICT_SYSTEM_PROMPT = """You are an intelligent Environmental Health & Air Quality Analyst embedded inside a live monitoring platform.
Synthesize the deterministic telemetry, multi-module analytics, and retrieved scientific references into a clear, natural, insightful response.

Mandatory grounding rules:
1. Never invent missing pollutant measurements, timestamps, coordinates, or AQI thresholds.
2. Never recalculate or override AQI numbers; use the exact deterministic values provided.
3. Never give medical diagnoses or clinical treatment prescriptions.
4. Never claim pollutant combinations or weather patterns prove a specific emission source—frame them as evidence-graded associations.
5. Explicitly state when historical data, model artifacts, or sensor fields are insufficient.
6. Cite the retrieved knowledge base titles/sources naturally when explaining health effects or mechanisms.
7. Answer follow-up questions using prior conversation context plus the latest station snapshot."""


@dataclass
class AssistantResponse:
    intent: QueryIntent
    answer: str
    used_llm: bool
    model_name: str | None = None
    fallback_reason: str | None = None
    sources_used: list[str] = field(default_factory=list)


def _build_grounded_prompt(user_query: str, routed: RoutedContext) -> str:
    facts_json = json.dumps(routed.structured_facts, indent=2, default=str)
    if routed.retrieved_docs:
        rag_blocks = "\n\n".join(
            f"- Title: {d.title}\n  Source: {d.source}\n  Excerpt: {d.text}"
            for d in routed.retrieved_docs
        )
    else:
        rag_blocks = "None retrieved."

    return (
        f"Primary Routed Intent: {routed.intent.value}\n"
        f"Sufficient System Evidence: {routed.has_sufficient_evidence}\n\n"
        f"Live & Multi-Module System Summary:\n{routed.deterministic_summary}\n\n"
        f"Structured Telemetry & Analytics Context (JSON):\n{facts_json}\n\n"
        f"Retrieved Knowledge Base Context:\n{rag_blocks}\n\n"
        f"User Question:\n{user_query}\n\n"
        "Respond directly, clearly, and helpfully using only the verified facts and retrieved references above."
    )


def _format_deterministic_fallback(routed: RoutedContext, reason: str) -> str:
    lines = [routed.deterministic_summary]
    if routed.retrieved_docs:
        lines.append("\n**Referenced Knowledge Base Context:**")
        for doc in routed.retrieved_docs:
            lines.append(f"- **{doc.title}** ({doc.source}): {doc.text}")
    lines.append(f"\n_Note: Displayed deterministic application output directly ({reason})._")
    return "\n".join(lines)


def _candidate_models(configured_model: str) -> list[str]:
    ordered: list[str] = []
    for m in (configured_model, *GROQ_FALLBACK_MODELS):
        cleaned = (m or "").strip()
        if cleaned and cleaned not in ordered:
            ordered.append(cleaned)
    return ordered


def generate_assistant_response(
    user_query: str,
    routed: RoutedContext,
    app_config: AppConfig = config,
    session: requests.Session | None = None,
    chat_history: list[dict[str, Any]] | None = None,
) -> AssistantResponse:
    sources = list(dict.fromkeys(f"{d.title} — {d.source}" for d in routed.retrieved_docs))

    if not app_config.has_groq_api_key:
        reason = "GROQ_API_KEY is not configured in .env"
        return AssistantResponse(
            intent=routed.intent,
            answer=_format_deterministic_fallback(routed, reason),
            used_llm=False,
            fallback_reason=reason,
            sources_used=sources,
        )

    http = session or requests.Session()
    headers = {
        "Authorization": f"Bearer {app_config.groq_api_key}",
        "Content-Type": "application/json",
    }

    messages: list[dict[str, str]] = [{"role": "system", "content": STRICT_SYSTEM_PROMPT}]
    if chat_history:
        # Include up to the last 4 prior turns so follow-up questions maintain conversational memory
        for turn in chat_history[-4:]:
            role = str(turn.get("role", ""))
            content = str(turn.get("content", "")).strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": _build_grounded_prompt(user_query, routed)})

    last_reason = "Groq API request failed"
    for model_id in _candidate_models(app_config.groq_model):
        payload: dict[str, Any] = {
            "model": model_id,
            "temperature": 0.25,
            "max_tokens": 750,
            "messages": messages,
        }
        try:
            resp = http.post(
                GROQ_CHAT_COMPLETIONS_URL,
                headers=headers,
                json=payload,
                timeout=app_config.request_timeout_seconds,
            )
        except requests.Timeout:
            last_reason = f"Groq API timed out after {app_config.request_timeout_seconds}s"
            break
        except requests.RequestException as exc:
            last_reason = f"Groq API network error: {exc}"
            break

        if resp.status_code in (400, 404):
            # Model unavailable or deprecated on this key—try next candidate model
            try:
                err_msg = resp.json().get("error", {}).get("message", f"HTTP {resp.status_code}")
            except Exception:
                err_msg = f"HTTP {resp.status_code}"
            last_reason = f"Model '{model_id}' unavailable ({err_msg})"
            continue

        if resp.status_code >= 400:
            try:
                err_msg = resp.json().get("error", {}).get("message", f"HTTP {resp.status_code}")
            except Exception:
                err_msg = f"HTTP {resp.status_code}"
            last_reason = f"Groq API error ({err_msg})"
            break

        try:
            data = resp.json()
            choices = data.get("choices") or []
            content = choices[0]["message"]["content"].strip()
            if not content:
                raise ValueError("Empty assistant message content.")
            return AssistantResponse(
                intent=routed.intent,
                answer=content,
                used_llm=True,
                model_name=model_id,
                sources_used=sources,
            )
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            last_reason = f"Malformed Groq API response: {exc}"
            break

    return AssistantResponse(
        intent=routed.intent,
        answer=_format_deterministic_fallback(routed, last_reason),
        used_llm=False,
        fallback_reason=last_reason,
        sources_used=sources,
    )