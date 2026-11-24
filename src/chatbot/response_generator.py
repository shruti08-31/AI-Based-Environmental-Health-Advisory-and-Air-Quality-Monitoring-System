from dataclasses import dataclass, field
import json
from typing import Any
import requests

from config import AppConfig, config
from src.chatbot.intent_router import QueryIntent, RoutedContext

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"

STRICT_SYSTEM_PROMPT = """You are an Environmental Health & Air Quality Assistant.
Follow these mandatory rules strictly:
1. Never invent missing pollutant measurements, timestamps, coordinates, or AQI thresholds.
2. Never compute or override AQI numbers; rely exclusively on the provided deterministic system outputs.
3. Never generate medical diagnoses or clinical treatment advice.
4. Never claim that pollutant patterns or weather correlations prove an emission source or cause.
5. Explicitly state when data or evidence is insufficient to answer part of a question.
6. Ground environmental explanations in the provided Retrieved Knowledge Base Context and cite document titles/sources when used.
7. Keep responses clear, concise, factual, and directly tied to the supplied context."""


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
        f"Detected Intent: {routed.intent.value}\n"
        f"Sufficient System Evidence: {routed.has_sufficient_evidence}\n\n"
        f"Deterministic Application Summary:\n{routed.deterministic_summary}\n\n"
        f"Structured Application Facts (JSON):\n{facts_json}\n\n"
        f"Retrieved Knowledge Base Context:\n{rag_blocks}\n\n"
        f"User Question:\n{user_query}\n\n"
        "Provide a grounded explanation following all system rules."
    )


def _format_deterministic_fallback(routed: RoutedContext, reason: str) -> str:
    lines = [routed.deterministic_summary]
    if routed.retrieved_docs:
        lines.append("\n**Referenced Knowledge Base Context:**")
        for doc in routed.retrieved_docs:
            lines.append(f"- **{doc.title}** ({doc.source}): {doc.text}")
    lines.append(f"\n_Note: Displayed deterministic application output directly ({reason})._")
    return "\n".join(lines)


def generate_assistant_response(
    user_query: str,
    routed: RoutedContext,
    app_config: AppConfig = config,
    session: requests.Session | None = None,
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
    payload: dict[str, Any] = {
        "model": app_config.groq_model,
        "temperature": 0.2,
        "max_tokens": 650,
        "messages": [
            {"role": "system", "content": STRICT_SYSTEM_PROMPT},
            {"role": "user", "content": _build_grounded_prompt(user_query, routed)},
        ],
    }

    try:
        resp = http.post(
            GROQ_CHAT_COMPLETIONS_URL,
            headers=headers,
            json=payload,
            timeout=app_config.request_timeout_seconds,
        )
    except requests.Timeout:
        reason = f"Groq API timed out after {app_config.request_timeout_seconds}s"
        return AssistantResponse(
            intent=routed.intent,
            answer=_format_deterministic_fallback(routed, reason),
            used_llm=False,
            fallback_reason=reason,
            sources_used=sources,
        )
    except requests.RequestException as exc:
        reason = f"Groq API network error: {exc}"
        return AssistantResponse(
            intent=routed.intent,
            answer=_format_deterministic_fallback(routed, reason),
            used_llm=False,
            fallback_reason=reason,
            sources_used=sources,
        )

    if resp.status_code >= 400:
        reason = f"Groq API returned HTTP {resp.status_code}"
        return AssistantResponse(
            intent=routed.intent,
            answer=_format_deterministic_fallback(routed, reason),
            used_llm=False,
            fallback_reason=reason,
            sources_used=sources,
        )

    try:
        data = resp.json()
        choices = data.get("choices") or []
        content = choices[0]["message"]["content"].strip()
        if not content:
            raise ValueError("Empty assistant message content.")
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        reason = f"Malformed Groq API response: {exc}"
        return AssistantResponse(
            intent=routed.intent,
            answer=_format_deterministic_fallback(routed, reason),
            used_llm=False,
            fallback_reason=reason,
            sources_used=sources,
        )

    return AssistantResponse(
        intent=routed.intent,
        answer=content,
        used_llm=True,
        model_name=app_config.groq_model,
        sources_used=sources,
    )