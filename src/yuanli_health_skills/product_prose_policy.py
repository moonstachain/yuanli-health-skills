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

_TEXT_DEFINITION_POLICY = (
    (("$defs", "text", "type"), "string"),
    (("$defs", "text", "minLength"), 1),
    (("$defs", "text", "maxLength"), 280),
    (("$defs", "text", "pattern"), EVIDENCE_PROSE_PATTERN),
)
_TEXT_ARRAY_POLICY = (
    (("$defs", "text_array", "type"), "array"),
    (("$defs", "text_array", "uniqueItems"), True),
    (("$defs", "text_array", "items", "$ref"), "#/$defs/text"),
)
_COMMON_PROSE_POLICY = (
    (("properties", "unknowns", "$ref"), "#/$defs/text_array"),
    *_TEXT_DEFINITION_POLICY,
    *_TEXT_ARRAY_POLICY,
)
_ACTION_TEXT_DEFINITION_POLICY = (
    (("$defs", "action_text", "type"), "string"),
    (("$defs", "action_text", "minLength"), 1),
    (("$defs", "action_text", "maxLength"), 280),
    (("$defs", "action_text", "pattern"), ACTION_PROSE_PATTERN),
)
_GUIDANCE_DEFINITION_POLICY = (
    (("$defs", "guidance_text", "type"), "string"),
    (("$defs", "guidance_text", "minLength"), 1),
    (("$defs", "guidance_text", "maxLength"), 160),
    (("$defs", "guidance", "type"), "object"),
    (("$defs", "guidance", "additionalProperties"), False),
    (("$defs", "guidance", "required"), ["zh", "en"]),
    (("$defs", "guidance", "properties"), frozenset(APPROVED_GUIDANCE_BY_LANGUAGE)),
    *(
        (
            ("$defs", "guidance", "properties", language, "const"),
            approved,
        )
        for language, approved in APPROVED_GUIDANCE_BY_LANGUAGE.items()
    ),
)
_PRODUCT_SCHEMA_PROSE_POLICY = {
    "health-evidence-view-v1": (
        (("properties", "fact", "$ref"), "#/$defs/text"),
        *_COMMON_PROSE_POLICY,
    ),
    "recovery-compass-snapshot-v1": (
        (
            ("properties", "season_focus", "oneOf"),
            [{"type": "null"}, {"$ref": "#/$defs/focus"}],
        ),
        (("$defs", "focus", "properties", "rationale", "$ref"), "#/$defs/text"),
        *_COMMON_PROSE_POLICY,
    ),
    "quarter-health-campaign-v1": _COMMON_PROSE_POLICY,
    "weekly-experiment-v1": (
        (("properties", "action_candidate", "$ref"), "#/$defs/action_candidate"),
        (
            ("$defs", "action_candidate", "properties", "description", "$ref"),
            "#/$defs/action_text",
        ),
        *_COMMON_PROSE_POLICY,
        *_ACTION_TEXT_DEFINITION_POLICY,
    ),
    "professional-escalation-v1": (
        (("properties", "guidance", "$ref"), "#/$defs/guidance"),
        *_COMMON_PROSE_POLICY,
        *_GUIDANCE_DEFINITION_POLICY,
    ),
}
_MISSING = object()


def _schema_value(schema: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = schema
    for segment in path:
        if type(value) is not dict or segment not in value:
            return _MISSING
        value = value[segment]
    return value


def _policy_value_matches(value: Any, expected: Any) -> bool:
    if type(expected) is frozenset:
        return type(value) is dict and frozenset(value) == expected
    if type(value) is not type(expected):
        return False
    if type(expected) is list:
        return len(value) == len(expected) and all(
            _policy_value_matches(item, expected_item)
            for item, expected_item in zip(value, expected)
        )
    if type(expected) is dict:
        return value.keys() == expected.keys() and all(
            _policy_value_matches(value[key], expected_item)
            for key, expected_item in expected.items()
        )
    return value == expected


def product_schema_prose_policy_errors(schema_name: str, schema: Any) -> tuple[str, ...]:
    """Return stable policy drift descriptions for a decoded source schema."""

    policy = _PRODUCT_SCHEMA_PROSE_POLICY.get(schema_name)
    if policy is None:
        return (f"unsupported product schema: {schema_name}",)
    if type(schema) is not dict or type(schema.get("$defs")) is not dict:
        return (f"{schema_name}: missing $defs",)

    errors: list[str] = []
    for path, expected in policy:
        if not _policy_value_matches(_schema_value(schema, path), expected):
            errors.append(f"{schema_name}: {'.'.join(path)}")
    return tuple(errors)
