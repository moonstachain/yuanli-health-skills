"""Deterministic prose vocabulary shared by product runtime and JSON Schemas."""

import re
from typing import Any


APPROVED_GUIDANCE_BY_LANGUAGE = {
    "zh": "请携带证据摘要，由临床专业人员评估。",
    "en": "Bring the evidence summary for clinician review.",
}
APPROVED_GUIDANCE = frozenset(APPROVED_GUIDANCE_BY_LANGUAGE.values())
SAFE_PROSE_WORDS = tuple(
    sorted(
        {
            "a", "and", "another", "as", "candidate", "consistent", "conflicts", "current",
            "declining", "down", "evidence", "freshness", "habits", "health", "improving",
            "insufficient", "makes", "or", "pattern", "ratio", "recovery", "remains", "reported",
            "review", "rhythm", "routine", "sleep", "source", "stable", "stale", "stress", "summary",
            "synthetic", "the", "trend", "unknown", "unresolved", "use", "was", "wind-down", "with",
        }
    )
)

_SAFE_TOKEN_PATTERN = "(" + "|".join((*SAFE_PROSE_WORDS, "[0-9]{1,3}/[0-9]{1,3}")) + ")"
_SAFE_BODY_PATTERN = _SAFE_TOKEN_PATTERN + "(( +|/)" + _SAFE_TOKEN_PATTERN + ")* *\\.(?![\\s\\S])"
EVIDENCE_PROSE_PATTERN = "^Synthetic " + _SAFE_BODY_PATTERN
ACTION_PROSE_PATTERN = "^Use a synthetic " + _SAFE_BODY_PATTERN
EVIDENCE_PROSE = re.compile(EVIDENCE_PROSE_PATTERN)
ACTION_PROSE = re.compile(ACTION_PROSE_PATTERN)

_PRODUCT_SCHEMA_NAMES = frozenset(
    {
        "health-evidence-view-v1",
        "recovery-compass-snapshot-v1",
        "quarter-health-campaign-v1",
        "weekly-experiment-v1",
        "professional-escalation-v1",
    }
)


def product_schema_prose_policy_errors(schema_name: str, schema: Any) -> tuple[str, ...]:
    """Return stable policy drift descriptions for a decoded source schema."""

    if schema_name not in _PRODUCT_SCHEMA_NAMES:
        return (f"unsupported product schema: {schema_name}",)
    if type(schema) is not dict or type(schema.get("$defs")) is not dict:
        return (f"{schema_name}: missing $defs",)

    definitions = schema["$defs"]
    errors: list[str] = []
    text = definitions.get("text")
    if type(text) is not dict or text.get("pattern") != EVIDENCE_PROSE_PATTERN:
        errors.append(f"{schema_name}: $defs.text.pattern")
    if schema_name == "weekly-experiment-v1":
        action_text = definitions.get("action_text")
        if type(action_text) is not dict or action_text.get("pattern") != ACTION_PROSE_PATTERN:
            errors.append(f"{schema_name}: $defs.action_text.pattern")
    if schema_name == "professional-escalation-v1":
        guidance = definitions.get("guidance")
        properties = guidance.get("properties") if type(guidance) is dict else None
        for language, approved in APPROVED_GUIDANCE_BY_LANGUAGE.items():
            language_schema = properties.get(language) if type(properties) is dict else None
            if type(language_schema) is not dict or language_schema.get("const") != approved:
                errors.append(f"{schema_name}: $defs.guidance.properties.{language}.const")
    return tuple(errors)
