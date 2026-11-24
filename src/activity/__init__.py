from typing import Any

from src.activity.activity_advisor import (
    SAFETY_DISCLAIMER,
    SUPPORTED_ACTIVITIES,
    ActivityGuidance,
    advise_activity,
    advise_activity_from_reading,
)

try:
    from src.activity.activity_advisor import enrich_guidance_with_llm  # type: ignore[attr-defined]
except ImportError:
    try:
        from src.activity.llm_enrichment import enrich_guidance_with_llm  # type: ignore[import-not-found]
    except ImportError:
        def enrich_guidance_with_llm(guidance: Any, *args: Any, **kwargs: Any) -> Any:
            """Deterministic pass-through when optional LLM enrichment is not configured."""
            return guidance

__all__ = [
    "ActivityGuidance",
    "SAFETY_DISCLAIMER",
    "SUPPORTED_ACTIVITIES",
    "advise_activity",
    "advise_activity_from_reading",
    "enrich_guidance_with_llm",
]