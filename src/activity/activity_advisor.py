from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.api.waqi_client import AqiReading
from src.core.aqi_engine import AqiEngineResult, evaluate_aqi_from_reading
from src.core.health_engine import SensitivityGroup

try:
    from src.rag.web_search import search_trusted_environmental_websites
except ImportError:  # pragma: no cover
    search_trusted_environmental_websites = None  # type: ignore[assignment]

SUPPORTED_ACTIVITIES: tuple[str, ...] = (
    "Walking",
    "Running",
    "Cycling",
    "Outdoor exercise",
    "Indoor exercise",
)

SAFETY_DISCLAIMER = (
    "Guidance only; air quality conditions change and this advisor does not guarantee "
    "that any activity is free from health risk."
)


def _load_dotenv_if_needed() -> None:
    """Populate os.environ from project .env without overriding existing env vars."""
    if os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return
    env_path = Path(".env")
    if not env_path.exists():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except OSError:
        return


@dataclass(frozen=True)
class ActivityGuidance:
    activity: str
    aqi_category: str
    calculated_aqi: int | None
    sensitivity_group: str
    recommendation: str
    precautions: list[str] = field(default_factory=list)
    alternative_activity: str = ""
    explanation: str = ""
    disclaimer: str = SAFETY_DISCLAIMER


def advise_activity(
    activity: str,
    aqi_category: str,
    calculated_aqi: int | None = None,
    pollutants: dict[str, Any] | None = None,
    sensitivity_group: SensitivityGroup | str = SensitivityGroup.GENERAL,
) -> ActivityGuidance:
    act_norm = activity if activity in SUPPORTED_ACTIVITIES else "Outdoor exercise"
    cat_norm = (
        aqi_category
        if aqi_category in ("Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe")
        else "Unavailable"
    )

    group_label = (
        sensitivity_group.value
        if isinstance(sensitivity_group, SensitivityGroup)
        else str(sensitivity_group or SensitivityGroup.GENERAL.value)
    )
    is_sensitive = "sensitive" in group_label.lower()
    is_high_exertion = act_norm in ("Running", "Cycling", "Outdoor exercise")
    is_indoor = act_norm == "Indoor exercise"

    available_pols = [
        k.upper()
        for k, v in (pollutants or {}).items()
        if v is not None and not isinstance(v, bool)
    ]
    pol_note = (
        f"Available pollutants considered: {', '.join(available_pols)}."
        if available_pols
        else "Limited or no individual pollutant measurements available."
    )
    aqi_label = str(calculated_aqi) if calculated_aqi is not None else "N/A"

    if cat_norm == "Unavailable":
        recommendation = "Exercise Caution / Defer High Exertion"
        alternative = "Low-intensity Indoor exercise in a clean, well-ventilated space until valid AQI data is available."
        explanation = f"Severity category is unavailable due to missing or invalid AQI readings. {pol_note}"
        precautions = [
            "Avoid assuming outdoor air is clean when AQI readings are unavailable.",
            "Keep exertion moderate and monitor how you feel.",
        ]
    elif is_indoor:
        if cat_norm in ("Good", "Satisfactory", "Moderate"):
            recommendation = "Suitable for Indoor Exercise"
            alternative = "Brisk Walking or light outdoor activity if indoor air is comfortable."
            explanation = f"Indoor exercise avoids direct outdoor exposure during {cat_norm} conditions. {pol_note}"
            precautions = [
                "Maintain steady indoor airflow without drawing in polluted outdoor air.",
                "Stay hydrated and pace sessions appropriately.",
            ]
        else:
            recommendation = "Preferred Option During Elevated Outdoor AQI"
            alternative = "Gentle indoor mobility or stretching in filtered/clean indoor air."
            explanation = f"Outdoor AQI is {cat_norm}, making controlled indoor exercise preferable to outdoor exertion. {pol_note}"
            precautions = [
                "Keep windows and doors closed to limit outdoor pollutant infiltration.",
                "Avoid indoor smoke, incense, or unvented combustion sources during workouts.",
            ]
    elif cat_norm in ("Good", "Satisfactory"):
        recommendation = (
            "Generally Favorable" if not is_sensitive else "Generally Favorable With Routine Care"
        )
        alternative = "Indoor exercise if weather or personal comfort makes outdoors inconvenient."
        explanation = f"Calculated AQI category is {cat_norm} (AQI: {aqi_label}). {pol_note}"
        precautions = [
            "Choose routes away from heavy traffic or active construction dust where possible.",
            "Stop and rest if unusual shortness of breath or irritation occurs.",
        ]
    elif cat_norm == "Moderate":
        if is_high_exertion or is_sensitive:
            recommendation = "Moderate Intensity / Shorten Duration"
            alternative = "Indoor exercise or lighter Walking instead of vigorous Running or Cycling."
            explanation = f"Moderate AQI ({aqi_label}) increases respiratory ventilation during exertion. {pol_note}"
            precautions = [
                "Reduce workout intensity and duration, especially for sensitive individuals.",
                "Avoid peak traffic hours and busy arterial roads.",
            ]
        else:
            recommendation = "Acceptable With Pacing"
            alternative = "Indoor exercise if feeling mild throat or airway sensitivity."
            explanation = f"Moderate AQI allows paced walking with basic exposure awareness. {pol_note}"
            precautions = [
                "Keep walking pace comfortable and avoid dusty roadside corridors.",
            ]
    else:
        recommendation = (
            "Limit or Avoid Outdoor Exertion"
            if cat_norm == "Poor"
            else "Avoid Outdoor Activity; Move Indoors"
        )
        alternative = "Indoor exercise in a clean, enclosed space rather than outdoor Running, Cycling, or Walking."
        explanation = f"Elevated AQI tier ({cat_norm}, AQI: {aqi_label}) poses higher respiratory/cardiovascular load. {pol_note}"
        precautions = [
            "Postpone strenuous outdoor exercise such as running or cycling.",
            "If brief outdoor travel is unavoidable, consider a well-fitted particulate respirator (e.g., N95/FFP2).",
            "Sensitive groups should stay indoors and follow clinician guidance if symptoms arise.",
        ]

    if is_sensitive and cat_norm in ("Moderate", "Poor", "Very Poor", "Severe"):
        precautions.insert(
            0,
            f"Sensitivity profile ({group_label}) is active: prioritize indoor options and watch for symptoms.",
        )

    return ActivityGuidance(
        activity=act_norm,
        aqi_category=cat_norm,
        calculated_aqi=calculated_aqi,
        sensitivity_group=group_label,
        recommendation=recommendation,
        precautions=precautions,
        alternative_activity=alternative,
        explanation=explanation,
        disclaimer=SAFETY_DISCLAIMER,
    )


def advise_activity_from_reading(
    activity: str,
    reading: AqiReading,
    aqi_result: AqiEngineResult | None = None,
    sensitivity_group: SensitivityGroup | str = SensitivityGroup.GENERAL,
) -> ActivityGuidance:
    eng = aqi_result or evaluate_aqi_from_reading(reading)
    return advise_activity(
        activity=activity,
        aqi_category=eng.category,
        calculated_aqi=eng.calculated_aqi,
        pollutants=reading.pollutants,
        sensitivity_group=sensitivity_group,
    )


def _format_pollutants_for_prompt(pollutants: dict[str, Any] | None) -> str:
    if not pollutants:
        return "None reported"
    parts = [
        f"{k.upper()}: {v}"
        for k, v in pollutants.items()
        if v is not None and not isinstance(v, bool)
    ]
    return ", ".join(parts) if parts else "None reported"


def _parse_json_object(raw_text: str) -> dict[str, Any] | None:
    text = (raw_text or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _get_timeout_seconds() -> float:
    try:
        val = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "12").strip())
        return max(5.0, min(val, 25.0))
    except ValueError:
        return 12.0


def _call_openai_compatible_for_guidance(
    prompt: str,
    api_key: str,
    base_url: str = "https://api.groq.com/openai/v1/chat/completions",
    model: str = "llama-3.3-70b-versatile",
) -> dict[str, Any] | None:
    payload = {
        "model": model,
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a friendly, clear environmental health advisor. Keep all numeric AQI and pollutant values "
                    "exact as provided. Write warm, plain-language guidance tailored to the user's location, activity, "
                    "and sensitivity group. Return strictly valid JSON with keys: "
                    '"explanation" (string), "precautions" (list of 3 concise user-friendly strings), '
                    '"alternative_activity" (string).'
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    req = Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "EcoHealth-Activity-Advisor/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=_get_timeout_seconds()) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        choices = body.get("choices", [{}])
        content = choices[0].get("message", {}).get("content", "") if choices else ""
        return _parse_json_object(content)
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, IndexError):
        return None


def _call_gemini_for_guidance(prompt: str, api_key: str) -> dict[str, Any] | None:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
        },
    }
    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=_get_timeout_seconds()) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
        text_out = parts[0].get("text", "") if parts else ""
        return _parse_json_object(text_out)
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, IndexError):
        return None


def _clean_snippet_text(snippet: str) -> str:
    txt = " ".join((snippet or "").split()).strip()
    if " · " in txt[:35]:
        txt = txt.split(" · ", 1)[1].strip()
    if len(txt) > 180:
        cut = txt[:180].rsplit(" ", 1)[0].rstrip(".,;:")
        txt = f"{cut}..."
    return txt


def _build_web_grounded_guidance(
    guidance: ActivityGuidance,
    station_label: str,
    pollutants: dict[str, Any] | None,
) -> tuple[str, list[str], str, str] | None:
    if search_trusted_environmental_websites is None:
        return None

    pol_hint = ""
    if pollutants:
        present = [k.upper() for k, v in pollutants.items() if v is not None and not isinstance(v, bool)]
        if present:
            pol_hint = f" {' '.join(present[:2])}"

    query = f"{guidance.activity} {guidance.aqi_category} AQI outdoor exposure{pol_hint}"
    snippets = search_trusted_environmental_websites(query, max_sources=3)
    if not snippets:
        return None

    domains = [s.domain for s in snippets]
    source_label = "Trusted Web Search (" + ", ".join(domains) + ")"
    aqi_part = f" (AQI {guidance.calculated_aqi})" if guidance.calculated_aqi is not None else ""

    top_clean = _clean_snippet_text(snippets[0].snippet)
    explanation = (
        f"Around {station_label}, air quality is currently {guidance.aqi_category}{aqi_part}, "
        f"so {guidance.recommendation.lower()} is recommended for {guidance.activity.lower()} "
        f"({guidance.sensitivity_group.lower()}). Reference guidance ({snippets[0].domain}): {top_clean}"
    )

    precautions = list(guidance.precautions or [])
    for s in snippets[:2]:
        cleaned = _clean_snippet_text(s.snippet)
        if cleaned:
            line = f"Guidance from {s.site_name}: {cleaned}"
            if line not in precautions:
                precautions.append(line)

    alternative = (
        f"{guidance.alternative_activity.rstrip('.')} around {station_label} "
        f"for {guidance.sensitivity_group.lower()}."
    )
    return explanation, precautions, alternative, source_label


def enrich_guidance_with_llm(
    guidance: ActivityGuidance,
    station_label: str,
    pollutants: dict[str, Any] | None,
    use_llm: bool = True,
) -> tuple[str, list[str], str, str]:
    """
    Returns (explanation, precautions_list, alternative_activity, source_label).
    Preserves exact AQI, category, and recommendation values from `guidance`.
    """
    _load_dotenv_if_needed()

    fallback_exp = str(guidance.explanation)
    fallback_precs = list(guidance.precautions or [])
    fallback_alt = str(guidance.alternative_activity)

    if not use_llm:
        return fallback_exp, fallback_precs, fallback_alt, "Rule Engine (Deterministic)"

    aqi_txt = str(guidance.calculated_aqi) if guidance.calculated_aqi is not None else "Unavailable"
    pol_txt = _format_pollutants_for_prompt(pollutants)

    web_snippets = (
        search_trusted_environmental_websites(
            f"{guidance.activity} {guidance.aqi_category} AQI health guidance",
            max_sources=3,
        )
        if search_trusted_environmental_websites is not None
        else []
    )
    web_context_block = "\n".join(
        f"- {s.site_name} ({s.url}): {s.snippet}" for s in web_snippets
    )

    prompt = (
        "Provide clear, friendly, practical activity guidance aligned with standard public air-quality "
        "advisory practices (such as CPCB / AirNow / WHO-style exposure awareness) while keeping "
        "every AQI and pollutant number identical to the input.\n"
        f"Station: {station_label}\n"
        f"Activity: {guidance.activity}\n"
        f"Sensitivity Group: {guidance.sensitivity_group}\n"
        f"Calculated AQI: {aqi_txt}\n"
        f"Severity Category: {guidance.aqi_category}\n"
        f"Deterministic Recommendation: {guidance.recommendation}\n"
        f"Pollutants: {pol_txt}\n"
        + (f"Trusted Web Snippets:\n{web_context_block}\n\n" if web_context_block else "\n")
        + 'Respond ONLY with JSON matching: {"explanation": "...", "precautions": ["...", "..."], "alternative_activity": "..."}'
    )

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile"
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()

    parsed: dict[str, Any] | None = None
    source_label: str | None = None

    if groq_key and groq_key != "your_groq_api_key_here":
        parsed = _call_openai_compatible_for_guidance(
            prompt,
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1/chat/completions",
            model=groq_model,
        )
        if parsed:
            source_label = (
                f"LLM (Groq {groq_model}) + Web Search"
                if web_snippets
                else f"LLM (Groq {groq_model})"
            )

    if not parsed and gemini_key and gemini_key != "your_gemini_api_key_here":
        parsed = _call_gemini_for_guidance(prompt, gemini_key)
        if parsed:
            source_label = "LLM (Gemini) + Web Search" if web_snippets else "LLM (Gemini)"

    if parsed and source_label:
        exp = str(parsed.get("explanation") or "").strip() or fallback_exp
        raw_precs = parsed.get("precautions")
        if isinstance(raw_precs, list) and raw_precs:
            precs = [str(item).strip() for item in raw_precs if str(item).strip()] or fallback_precs
        else:
            precs = fallback_precs
        alt = str(parsed.get("alternative_activity") or "").strip() or fallback_alt
        return exp, precs, alt, source_label

    web_grounded = _build_web_grounded_guidance(guidance, station_label, pollutants)
    if web_grounded is not None:
        return web_grounded

    return fallback_exp, fallback_precs, fallback_alt, "Rule Engine (Fallback)"