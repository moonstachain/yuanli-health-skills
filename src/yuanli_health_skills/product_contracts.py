"""Strict, platform-neutral public product contract runtime."""

import math
import re
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .product_prose_policy import ACTION_PROSE, APPROVED_GUIDANCE, EVIDENCE_PROSE
from .validator import ValidationError, ValidationResult


@dataclass(frozen=True)
class ProductContractBuildResult:
    """A total builder result containing either isolated JSON or ordered errors."""

    value: dict[str, Any] | None
    errors: tuple[ValidationError, ...]

    @property
    def ok(self) -> bool:
        return self.value is not None and not self.errors


_HEALTH_EVIDENCE_FIELDS = (
    "schema",
    "synthetic",
    "canonical_write",
    "persistence",
    "evidence_id",
    "source_type",
    "observed_window",
    "status",
    "fact",
    "provenance_reference",
    "freshness",
    "conflicts_with",
    "unknowns",
)
_RECOVERY_COMPASS_FIELDS = (
    "schema", "synthetic", "canonical_write", "persistence", "directions",
    "season_focus", "unknowns", "conflicts", "authority_gate", "guardrails",
)
_QUARTER_CAMPAIGN_FIELDS = (
    "schema", "synthetic", "canonical_write", "persistence", "decision_candidate_id",
    "phases", "active_phase", "current_weekly_experiment_reference", "candidate_state",
    "claims", "unknowns", "conflicts", "authority_gate",
)
_WEEKLY_EXPERIMENT_FIELDS = (
    "schema", "synthetic", "canonical_write", "persistence", "experiment_id",
    "action_candidate", "observation_window", "expected_evidence_references",
    "stop_conditions", "escalation_conditions", "authority_gate", "unknowns", "conflicts",
)
_PROFESSIONAL_ESCALATION_FIELDS = (
    "schema", "synthetic", "canonical_write", "persistence", "escalation_id", "level",
    "trigger_category", "evidence_references", "final_authority", "guidance", "unknowns",
    "conflicts",
)
_FORBIDDEN_SCORE_FIELDS = frozenset(
    {"score", "readiness_score", "health_score", "wellness_score", "performance_score"}
)
_OPAQUE_TOKEN = re.compile(r"^synthetic:[a-z0-9][a-z0-9._:-]{0,127}$")
_SENSITIVE_FIELDS = frozenset(
    {
        "raw_file", "file", "file_path", "meeting_content", "name", "contact_data",
        "health_record_id", "health_record_identifier", "date_of_birth", "clinical_conclusion",
    }
)
_OUTCOME_FIELDS = frozenset({"out", "lrn", "effectiveness", "outcome", "outcome_adjudication"})
_CLINICAL_FIELDS = frozenset({"diagnosis", "medication", "medication_change", "treatment", "treatment_recommendation"})
_SERVICE_FIELDS = frozenset({"provider_selection", "provider", "booking", "payment"})
_FATAL_JSON_CODES = frozenset({"NON_JSON_VALUE", "CYCLIC_JSON", "MAX_DEPTH_EXCEEDED"})
_PROSE_PATH_SUFFIXES = (".fact", ".rationale", ".description", ".guidance.zh", ".guidance.en")
_URI_CONTENT = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s]+")
_ABSOLUTE_PATH_CONTENT = re.compile(
    r"(?:^|[\s\"'(])(?:[A-Za-z]:[\\/][^\s]+|\\\\[^\s\\/]+\\[^\s]+|/[A-Za-z0-9._~-][^\s]*)"
)
_DOT_PATH_CONTENT = re.compile(
    r"(?:^|[\s\"'(])\.\.?[\\/][^\s]+|(?:^|[\\/])\.\.(?=[\\/]|$)"
)
_RELATIVE_FILE_PATH_CONTENT = re.compile(
    r"(?:^|[\s\"'(])(?:[A-Za-z0-9._-]+[\\/])+(?:[A-Za-z0-9._-]+\.[A-Za-z0-9]{1,12})"
    r"(?=$|[\s.,;:!?\"')])"
)
_IDENTIFIER_CONTENT = re.compile(
    r"(?i)\b(?:dob|date of birth|(?:health|medical) record(?: id| identifier)?|record id|(?:full )?name|phone)\s*[:#]"
    r"|\bmrn\s*[:#-]?\s*[A-Za-z0-9]{4,}\b"
    r"|(?:出生日期|出生年月|健康记录|病历号|病例号|姓名|电话)\s*[：:#]"
)
_DOMESTIC_MOBILE_CONTENT = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_PERSON_NAME_CONTENT = re.compile(
    r"\b(?:(?:Dr|Doctor|Mr|Mrs|Ms|Prof)\.?\s+[A-Z][a-z]{1,40}(?:\s+[A-Z][a-z]{1,40}){0,2}|"
    r"[A-Z][a-z]{1,40}\s+[A-Z][a-z]{1,40}(?:\s+[A-Z][a-z]{1,40})?)\b"
)
_CLINICAL_PROSE = re.compile(
    r"(?i)\b(?:diagnos(?:is|ed|tic)|prescrib(?:e|ed|ing)|prescription|effectiveness|effective|"
    r"medicat(?:e|ed|ion)|treatment)\b|treatment recommendation|medication change|"
    r"诊断|确诊|治疗|疗效|处方|用药|服用|药物|药品|开药"
)
_SERVICE_PROSE = re.compile(
    r"(?i)\b(?:provider|book(?:ing|ed)?|schedule|arrange|appointment|payment|pay|billing|"
    r"visit with|see (?:a )?(?:doctor|dr\.)|"
    r"select(?:ing|ed)? (?:a )?doctor|choose (?:a )?doctor|doctor selection)\b|"
    r"预约|挂号|支付|付款|缴费|(?:选择|推荐)[^，。；]{0,12}(?:医生|医师|医院|机构)|服务商"
)
_TREATMENT_INSTRUCTION = re.compile(
    r"(?i)^\s*(?:please\s+)?(?:take|consume|swallow|apply|inject|start|stop|increase|decrease)\b|"
    r"(?:每天|每日|每晚|每次)[^，。；]{0,24}(?:吃|喝|口服|吞服|注射|涂抹|使用)"
)
def _shape_errors(value: dict[str, Any], fields: tuple[str, ...]) -> list[ValidationError]:
    errors = [
        ValidationError("MISSING_REQUIRED_FIELD", field, f"required field is missing: {field}")
        for field in fields
        if field not in value
    ]
    errors.extend(
        ValidationError("STRICT_SCHEMA_VIOLATION", str(field), f"unknown field: {field}")
        for field in value
        if field not in fields
    )
    return sorted(errors, key=lambda error: (error.path, error.code))


def _basic_validate(value: Any, schema: str, fields: tuple[str, ...], label: str) -> ValidationResult:
    json_errors = _json_boundary_errors(value)
    if type(value) is not dict:
        errors = [*json_errors, ValidationError("INVALID_DOCUMENT", "$", f"{label} must be an object")]
        errors.sort(key=lambda error: (error.path, error.code))
        return ValidationResult(tuple(errors))
    if json_errors:
        return ValidationResult(tuple(json_errors))
    errors = [*_shape_errors(value, fields), *_content_boundary_errors(value)]
    if value.get("schema") != schema:
        errors.append(ValidationError("INVALID_SCHEMA", "schema", "unexpected product contract schema"))
    if value.get("synthetic") is not True:
        errors.append(ValidationError("SYNTHETIC_REQUIRED", "synthetic", "product contracts require synthetic input"))
    if value.get("canonical_write") is not False:
        errors.append(ValidationError("CANON_WRITE_FORBIDDEN", "canonical_write", "product contracts cannot write Canon"))
    if value.get("persistence") != "none":
        errors.append(ValidationError("RUNTIME_PERSISTENCE_FORBIDDEN", "persistence", "product contracts cannot persist"))
    errors.sort(key=lambda error: (error.path, error.code))
    return ValidationResult(tuple(errors))


def _invalid(code: str, path: str, message: str) -> ValidationError:
    return ValidationError(code, path, message)


def _json_boundary_errors(value: Any, *, max_depth: int = 32) -> list[ValidationError]:
    errors: list[ValidationError] = []
    active: set[int] = set()
    stack: list[tuple[str, Any, str, int]] = [("visit", value, "$", 0)]
    while stack:
        operation, current, path, depth = stack.pop()
        if operation == "leave":
            active.remove(id(current))
            continue
        if current is None or type(current) in (str, bool, int):
            continue
        if type(current) is float:
            if not math.isfinite(current):
                errors.append(_invalid("NON_JSON_VALUE", path, "non-finite numbers are not JSON"))
            continue
        if type(current) not in (dict, list):
            errors.append(_invalid("NON_JSON_VALUE", path, "value is not inert JSON"))
            continue
        if depth > max_depth:
            errors.append(_invalid("MAX_DEPTH_EXCEEDED", path, "JSON nesting exceeds the public boundary"))
            continue
        identity = id(current)
        if identity in active:
            errors.append(_invalid("CYCLIC_JSON", path, "cyclic values are not JSON"))
            continue
        active.add(identity)
        stack.append(("leave", current, path, depth))
        if type(current) is list:
            for index in range(len(current) - 1, -1, -1):
                stack.append(("visit", current[index], f"{path}[{index}]", depth + 1))
        else:
            keys = tuple(current.keys())
            if any(type(key) is not str for key in keys):
                errors.append(_invalid("NON_JSON_VALUE", path, "JSON object keys must be strings"))
                continue
            string_keys = list(keys)
            for key in sorted(string_keys, reverse=True):
                stack.append(("visit", current[key], f"{path}.{key}", depth + 1))
    return sorted(errors, key=lambda error: (error.path, error.code))


def _contains_path_structure(value: str) -> bool:
    return any(
        pattern.search(value) is not None
        for pattern in (
            _URI_CONTENT,
            _ABSOLUTE_PATH_CONTENT,
            _DOT_PATH_CONTENT,
            _RELATIVE_FILE_PATH_CONTENT,
        )
    )


def _is_approved_prose(value: str, path: str) -> bool:
    if path.endswith((".guidance.zh", ".guidance.en")):
        return value in APPROVED_GUIDANCE
    if path.endswith(".action_candidate.description"):
        return ACTION_PROSE.fullmatch(value) is not None
    return EVIDENCE_PROSE.fullmatch(value) is not None


def _content_boundary_errors(value: Any) -> list[ValidationError]:
    """Recursively gate forbidden fields and prose without interpreting content."""

    errors: list[ValidationError] = []
    stack: list[tuple[Any, str]] = [(value, "$")]
    while stack:
        current, path = stack.pop()
        if isinstance(current, dict):
            for key in sorted(current, reverse=True):
                child_path = f"{path}.{key}"
                normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).replace("-", "_").lower()
                if normalized in _FORBIDDEN_SCORE_FIELDS or normalized.endswith("_score"):
                    errors.append(_invalid("FORBIDDEN_AGGREGATE_SCORE", child_path, "aggregate health scores are forbidden"))
                if normalized in _SENSITIVE_FIELDS:
                    errors.append(_invalid("FORBIDDEN_SENSITIVE_FIELD", child_path, "sensitive or raw health fields are forbidden"))
                if normalized in _OUTCOME_FIELDS:
                    errors.append(_invalid("FORBIDDEN_OUTCOME_ADJUDICATION", child_path, "outcome adjudication fields are forbidden"))
                if normalized in _CLINICAL_FIELDS:
                    errors.append(_invalid("CLINICAL_OVERREACH", child_path, "clinical decision fields are forbidden"))
                if normalized in _SERVICE_FIELDS:
                    errors.append(_invalid("FORBIDDEN_SERVICE_OPERATION", child_path, "provider selection, booking, and payment are forbidden"))
                stack.append((current[key], child_path))
        elif isinstance(current, list):
            for index in range(len(current) - 1, -1, -1):
                stack.append((current[index], f"{path}[{index}]"))
        elif isinstance(current, str) and (
            _contains_path_structure(current)
            or re.search(r"\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b", current)
            or re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", current)
            or re.search(r"(?<!\w)\+\d{1,3}(?:[ .-]?\d){7,14}(?!\d)", current)
            or _IDENTIFIER_CONTENT.search(current)
            or _DOMESTIC_MOBILE_CONTENT.search(current)
            or _PERSON_NAME_CONTENT.search(current)
        ):
            errors.append(_invalid("FORBIDDEN_SENSITIVE_CONTENT", path, "paths, contact data, and exact personal dates are forbidden"))
        is_prose = isinstance(current, str) and (
            path.endswith(_PROSE_PATH_SUFFIXES) or re.search(r"\.unknowns\[\d+\]$", path) is not None
        )
        has_clinical_content = is_prose and (
            _CLINICAL_PROSE.search(current) is not None or _TREATMENT_INSTRUCTION.search(current) is not None
        )
        has_service_content = is_prose and _SERVICE_PROSE.search(current) is not None
        if has_clinical_content:
            errors.append(_invalid("CLINICAL_OVERREACH", path, "clinical conclusions and treatment guidance are forbidden"))
        if has_service_content:
            errors.append(_invalid("FORBIDDEN_SERVICE_OPERATION", path, "provider selection, booking, and payment guidance are forbidden"))
        if is_prose and not has_clinical_content and not has_service_content and not _is_approved_prose(current, path):
            errors.append(_invalid("UNSAFE_PROSE", path, "prose must use an approved synthetic non-clinical form"))
        if isinstance(current, str) and path.endswith(".action_candidate.description") and re.search(
            r"\b(?:OUT|LRN)\b",
            current,
        ):
            errors.append(_invalid("FORBIDDEN_OUTCOME_ADJUDICATION", path, "OUT and LRN are forbidden in weekly experiments"))
    return sorted(errors, key=lambda error: (error.path, error.code))


def _validate_string(value: Any, path: str, errors: list[ValidationError], *, limit: int = 280) -> None:
    if type(value) is not str or not value or len(value) > limit:
        errors.append(_invalid("INVALID_STRING", path, f"{path} must be a bounded non-empty string"))


def _validate_token(value: Any, path: str, errors: list[ValidationError]) -> None:
    if type(value) is not str or _OPAQUE_TOKEN.fullmatch(value) is None:
        errors.append(_invalid("INVALID_OPAQUE_TOKEN", path, f"{path} must be an opaque synthetic token"))


def _validate_array(
    value: Any,
    path: str,
    errors: list[ValidationError],
    *,
    tokens: bool = False,
) -> None:
    if type(value) is not list:
        errors.append(_invalid("INVALID_ARRAY", path, f"{path} must be an array"))
        return
    if any(type(item) is not str or not item or (not tokens and len(item) > 280) for item in value):
        errors.append(_invalid("INVALID_ARRAY_ITEM", path, f"{path} items must be bounded non-empty strings"))
        return
    if tokens and any(_OPAQUE_TOKEN.fullmatch(item) is None for item in value):
        errors.append(_invalid("INVALID_OPAQUE_TOKEN", path, f"{path} items must be opaque synthetic tokens"))
    if len(value) != len(set(value)):
        errors.append(_invalid("DUPLICATE_REFERENCE" if tokens else "DUPLICATE_ARRAY_ITEM", path, f"{path} items must be unique"))
    if value != sorted(value):
        errors.append(_invalid("NON_DETERMINISTIC_ORDER", path, f"{path} items must use lexical order"))


def _nested_shape_errors(value: Any, path: str, fields: tuple[str, ...]) -> list[ValidationError]:
    if not isinstance(value, dict):
        return [_invalid("INVALID_OBJECT", path, f"{path} must be an object")]
    errors = [
        _invalid("MISSING_REQUIRED_FIELD", f"{path}.{field}", f"required field is missing: {field}")
        for field in fields
        if field not in value
    ]
    errors.extend(
        _invalid("STRICT_SCHEMA_VIOLATION", f"{path}.{field}", f"unknown field: {field}")
        for field in value
        if field not in fields
    )
    return errors


def _validate_authority_gate(value: Any, path: str, errors: list[ValidationError]) -> None:
    errors.extend(_nested_shape_errors(value, path, ("level", "final_authority")))
    if not isinstance(value, dict):
        return
    if type(value.get("level")) is not str or value.get("level") not in {"GREEN", "YELLOW"}:
        errors.append(_invalid("INVALID_AUTHORITY_GATE", f"{path}.level", "non-clinical authority gate must be GREEN or YELLOW"))
    if value.get("final_authority") != "subject":
        errors.append(_invalid("WRONG_AUTHORITY", f"{path}.final_authority", "subject is final authority for non-clinical decisions"))


def validate_health_evidence_view(value: Any) -> ValidationResult:
    """Validate one HealthEvidenceView without side effects."""

    result = _basic_validate(value, "health-evidence-view-v1", _HEALTH_EVIDENCE_FIELDS, "health evidence view")
    if type(value) is not dict or any(error.code in _FATAL_JSON_CODES for error in result.errors):
        return result
    errors = list(result.errors)
    for field, allowed in (
        ("source_type", {"self_report", "wearable_summary", "clinical_summary", "critical_campaign_calendar"}),
        ("status", {"supports", "contradicts", "unverified"}),
        ("freshness", {"current", "stale", "unknown"}),
    ):
        if field in value and (type(value.get(field)) is not str or value.get(field) not in allowed):
            errors.append(_invalid("INVALID_ENUM", field, f"invalid {field}"))
    for field in ("evidence_id", "observed_window", "provenance_reference"):
        if field in value:
            _validate_token(value.get(field), field, errors)
    if "fact" in value:
        _validate_string(value.get("fact"), "fact", errors)
    if "conflicts_with" in value:
        _validate_array(value.get("conflicts_with"), "conflicts_with", errors, tokens=True)
        conflicts = value.get("conflicts_with")
        if value.get("status") == "contradicts" and isinstance(conflicts, list) and not conflicts:
            errors.append(_invalid("CONFLICT_REFERENCE_REQUIRED", "conflicts_with", "contradicting evidence requires a conflict reference"))
        if isinstance(conflicts, list) and value.get("evidence_id") in conflicts:
            errors.append(_invalid("SELF_REFERENCE", "conflicts_with", "evidence cannot conflict with itself"))
    if "unknowns" in value:
        _validate_array(value.get("unknowns"), "unknowns", errors)
    errors.sort(key=lambda error: (error.path, error.code))
    return ValidationResult(tuple(errors))


def validate_recovery_compass_snapshot(value: Any) -> ValidationResult:
    result = _basic_validate(value, "recovery-compass-snapshot-v1", _RECOVERY_COMPASS_FIELDS, "recovery compass snapshot")
    if type(value) is not dict or any(error.code in _FATAL_JSON_CODES for error in result.errors):
        return result
    errors = list(result.errors)
    directions = value.get("directions")
    expected_directions = ("sleep", "recovery", "stress_rhythm", "health_habits")
    if not isinstance(directions, list):
        errors.append(_invalid("INVALID_DIRECTIONS", "directions", "directions must be an ordered array"))
    else:
        actual = tuple(item.get("direction") for item in directions if isinstance(item, dict))
        if len(directions) != 4 or actual != expected_directions:
            errors.append(_invalid("INVALID_DIRECTIONS", "directions", "directions must use the exact four-direction order"))
        for index, direction in enumerate(directions):
            path = f"directions[{index}]"
            errors.extend(_nested_shape_errors(direction, path, ("direction", "trend", "evidence_references")))
            if not isinstance(direction, dict):
                continue
            trend = direction.get("trend")
            if type(trend) is not str or trend not in {"improving", "stable", "declining", "insufficient_evidence"}:
                errors.append(_invalid("INVALID_ENUM", f"{path}.trend", "invalid direction trend"))
            references = direction.get("evidence_references")
            _validate_array(references, f"{path}.evidence_references", errors, tokens=True)
            if isinstance(references, list):
                if trend != "insufficient_evidence" and not references:
                    errors.append(_invalid("EVIDENCE_REQUIRED", f"{path}.evidence_references", "supported trends require evidence"))
                if trend == "insufficient_evidence" and references:
                    errors.append(_invalid("EVIDENCE_FOR_INSUFFICIENT_TREND", f"{path}.evidence_references", "insufficient trend cannot cite supporting evidence"))
    focus = value.get("season_focus")
    if isinstance(focus, list):
        errors.append(_invalid("MULTIPLE_ACTIVE_FOCUS", "season_focus", "at most one season focus is allowed"))
    elif focus is not None:
        errors.extend(
            _nested_shape_errors(
                focus,
                "season_focus",
                ("direction", "bottleneck_candidate", "rationale", "evidence_references"),
            )
        )
        if isinstance(focus, dict):
            if type(focus.get("direction")) is not str or focus.get("direction") not in set(expected_directions):
                errors.append(_invalid("INVALID_ENUM", "season_focus.direction", "invalid focus direction"))
            _validate_token(focus.get("bottleneck_candidate"), "season_focus.bottleneck_candidate", errors)
            _validate_string(focus.get("rationale"), "season_focus.rationale", errors)
            _validate_array(focus.get("evidence_references"), "season_focus.evidence_references", errors, tokens=True)
            if isinstance(focus.get("evidence_references"), list) and not focus["evidence_references"]:
                errors.append(_invalid("EVIDENCE_REQUIRED", "season_focus.evidence_references", "focus requires evidence"))
    for field in ("unknowns", "conflicts", "guardrails"):
        if field in value:
            _validate_array(value.get(field), field, errors, tokens=field == "conflicts")
    if "guardrails" in value and value.get("guardrails") != ["no_aggregate_score", "non_clinical"]:
        errors.append(_invalid("REQUIRED_GUARDRAIL", "guardrails", "Recovery Compass requires score and clinical guardrails"))
    if "authority_gate" in value:
        _validate_authority_gate(value.get("authority_gate"), "authority_gate", errors)
    errors.sort(key=lambda error: (error.path, error.code))
    return ValidationResult(tuple(errors))


def validate_quarter_health_campaign(value: Any) -> ValidationResult:
    result = _basic_validate(value, "quarter-health-campaign-v1", _QUARTER_CAMPAIGN_FIELDS, "quarter health campaign")
    if type(value) is not dict or any(error.code in _FATAL_JSON_CODES for error in result.errors):
        return result
    errors = list(result.errors)
    if "decision_candidate_id" in value:
        _validate_token(value.get("decision_candidate_id"), "decision_candidate_id", errors)
    phases = value.get("phases")
    expected_phases = ((1, "起盘与稳定"), (2, "实验与校准"), (3, "证据复盘与沉淀"))
    if not isinstance(phases, list):
        errors.append(_invalid("INVALID_CAMPAIGN_PHASES", "phases", "campaign phases must be an ordered array"))
    else:
        exact_phase_types = all(
            type(item) is dict and type(item.get("phase")) is int and type(item.get("label")) is str
            for item in phases
        )
        actual_phases = tuple((item.get("phase"), item.get("label")) for item in phases if type(item) is dict)
        if len(phases) != 3 or not exact_phase_types or actual_phases != expected_phases:
            errors.append(_invalid("INVALID_CAMPAIGN_PHASES", "phases", "campaign requires the exact three ordered phases"))
        for index, phase in enumerate(phases):
            errors.extend(_nested_shape_errors(phase, f"phases[{index}]", ("phase", "label")))
    if "active_phase" in value and (type(value.get("active_phase")) is not int or value.get("active_phase") not in {1, 2, 3}):
        errors.append(_invalid("INVALID_ACTIVE_PHASE", "active_phase", "active phase must be 1, 2, or 3"))
    current = value.get("current_weekly_experiment_reference")
    if isinstance(current, list):
        errors.append(_invalid("MULTIPLE_ACTIVE_EXPERIMENT", "current_weekly_experiment_reference", "at most one weekly experiment may be current"))
    elif current is not None:
        _validate_token(current, "current_weekly_experiment_reference", errors)
    if "candidate_state" in value and value.get("candidate_state") != "decision_candidate":
        errors.append(_invalid("INVALID_CANDIDATE_STATE", "candidate_state", "campaign must remain a decision candidate"))
    expected_claims = ["non_clinical", "not_treatment_plan", "outcome_not_adjudicated"]
    if "claims" in value and value.get("claims") != expected_claims:
        errors.append(_invalid("FORBIDDEN_OUTCOME_CLAIM", "claims", "campaign cannot claim treatment or outcomes"))
    for field in ("unknowns", "conflicts"):
        if field in value:
            _validate_array(value.get(field), field, errors, tokens=field == "conflicts")
    if "authority_gate" in value:
        _validate_authority_gate(value.get("authority_gate"), "authority_gate", errors)
    errors.sort(key=lambda error: (error.path, error.code))
    return ValidationResult(tuple(errors))


def validate_weekly_experiment(value: Any) -> ValidationResult:
    result = _basic_validate(value, "weekly-experiment-v1", _WEEKLY_EXPERIMENT_FIELDS, "weekly experiment")
    if type(value) is not dict or any(error.code in _FATAL_JSON_CODES for error in result.errors):
        return result
    errors = list(result.errors)
    if "experiment_id" in value:
        _validate_token(value.get("experiment_id"), "experiment_id", errors)
    action = value.get("action_candidate")
    if isinstance(action, list):
        errors.append(_invalid("MULTIPLE_ACTION_CANDIDATES", "action_candidate", "exactly one action candidate is allowed"))
    else:
        errors.extend(
            _nested_shape_errors(
                action,
                "action_candidate",
                ("action_id", "description", "evidence_references"),
            )
        )
        if isinstance(action, dict):
            _validate_token(action.get("action_id"), "action_candidate.action_id", errors)
            _validate_string(action.get("description"), "action_candidate.description", errors)
            references = action.get("evidence_references")
            _validate_array(references, "action_candidate.evidence_references", errors, tokens=True)
            if isinstance(references, list) and not references:
                errors.append(_invalid("EVIDENCE_REQUIRED", "action_candidate.evidence_references", "action candidate requires evidence"))
    if "observation_window" in value:
        _validate_token(value.get("observation_window"), "observation_window", errors)
    expected_evidence = value.get("expected_evidence_references")
    if "expected_evidence_references" in value:
        _validate_array(expected_evidence, "expected_evidence_references", errors, tokens=True)
        if isinstance(expected_evidence, list) and not expected_evidence:
            errors.append(_invalid("EVIDENCE_REQUIRED", "expected_evidence_references", "experiment requires expected evidence"))
    for field, required_code in (
        ("stop_conditions", "STOP_CONDITION_REQUIRED"),
        ("escalation_conditions", "ESCALATION_CONDITION_REQUIRED"),
    ):
        if field in value:
            field_value = value.get(field)
            _validate_array(field_value, field, errors)
            if isinstance(field_value, list) and not field_value:
                errors.append(_invalid(required_code, field, f"{field} must not be empty"))
            allowed_conditions = {
                "stop_conditions": {"new_or_worsening_symptom", "safety_concern", "subject_stops"},
                "escalation_conditions": {"clinical_device_conflict", "clinical_request", "medication_change", "urgent_risk"},
            }[field]
            if isinstance(field_value, list) and any(
                not isinstance(item, str) or item not in allowed_conditions for item in field_value
            ):
                errors.append(_invalid("INVALID_ENUM", field, f"invalid {field} item"))
    if "authority_gate" in value:
        _validate_authority_gate(value.get("authority_gate"), "authority_gate", errors)
    for field in ("unknowns", "conflicts"):
        if field in value:
            _validate_array(value.get(field), field, errors, tokens=field == "conflicts")
    errors.sort(key=lambda error: (error.path, error.code))
    return ValidationResult(tuple(errors))


def validate_professional_escalation(value: Any) -> ValidationResult:
    result = _basic_validate(value, "professional-escalation-v1", _PROFESSIONAL_ESCALATION_FIELDS, "professional escalation")
    if type(value) is not dict or any(error.code in _FATAL_JSON_CODES for error in result.errors):
        return result
    errors = list(result.errors)
    if "escalation_id" in value:
        _validate_token(value.get("escalation_id"), "escalation_id", errors)
    level = value.get("level")
    if "level" in value and (type(level) is not str or level not in {"clinician", "emergency"}):
        errors.append(_invalid("INVALID_ENUM", "level", "invalid escalation level"))
    trigger = value.get("trigger_category")
    if "trigger_category" in value and (
        type(trigger) is not str
        or trigger not in {"clinical_request", "medication_change", "urgent_risk", "clinical_device_conflict"}
    ):
        errors.append(_invalid("INVALID_ENUM", "trigger_category", "invalid escalation trigger"))
    references = value.get("evidence_references")
    if "evidence_references" in value:
        _validate_array(references, "evidence_references", errors, tokens=True)
        if isinstance(references, list) and not references:
            errors.append(_invalid("EVIDENCE_REQUIRED", "evidence_references", "professional escalation requires supplied evidence"))
    expected_authority = (
        {"clinician": "clinician", "emergency": "emergency_services"}.get(level)
        if type(level) is str
        else None
    )
    if expected_authority is not None and value.get("final_authority") != expected_authority:
        errors.append(_invalid("WRONG_AUTHORITY", "final_authority", "final authority must match escalation level"))
    guidance = value.get("guidance")
    errors.extend(_nested_shape_errors(guidance, "guidance", ("zh", "en")))
    if isinstance(guidance, dict):
        if "zh" in guidance:
            _validate_string(guidance.get("zh"), "guidance.zh", errors, limit=160)
            if isinstance(guidance.get("zh"), str) and re.search(r"[\u3400-\u9fff]", guidance["zh"]) is None:
                errors.append(_invalid("INVALID_GUIDANCE_LANGUAGE", "guidance.zh", "Chinese guidance must contain Chinese text"))
        if "en" in guidance:
            _validate_string(guidance.get("en"), "guidance.en", errors, limit=160)
            if isinstance(guidance.get("en"), str) and re.search(r"[A-Za-z]", guidance["en"]) is None:
                errors.append(_invalid("INVALID_GUIDANCE_LANGUAGE", "guidance.en", "English guidance must contain English text"))
    for field in ("unknowns", "conflicts"):
        if field in value:
            _validate_array(value.get(field), field, errors, tokens=field == "conflicts")
    errors.sort(key=lambda error: (error.path, error.code))
    return ValidationResult(tuple(errors))


def _build(
    payload: Any,
    schema: str,
    fields: tuple[str, ...],
    validate: Callable[[Any], ValidationResult],
) -> ProductContractBuildResult:
    json_errors = _json_boundary_errors(payload)
    if type(payload) is not dict:
        errors = [*json_errors, _invalid("INVALID_DOCUMENT", "$", "builder payload must be an object")]
        errors.sort(key=lambda error: (error.path, error.code))
        return ProductContractBuildResult(None, tuple(errors))
    if json_errors:
        return ProductContractBuildResult(None, tuple(json_errors))
    supplied = deepcopy(payload)
    supplied.update(
        {
            "schema": schema,
            "synthetic": True,
            "canonical_write": False,
            "persistence": "none",
        }
    )
    document = {field: supplied[field] for field in fields if field in supplied}
    for field in supplied:
        if field not in document:
            document[field] = supplied[field]
    result = validate(document)
    return ProductContractBuildResult(document if result.ok else None, result.errors)


def build_health_evidence_view(payload: Any) -> ProductContractBuildResult:
    return _build(payload, "health-evidence-view-v1", _HEALTH_EVIDENCE_FIELDS, validate_health_evidence_view)


def build_recovery_compass_snapshot(payload: Any) -> ProductContractBuildResult:
    return _build(payload, "recovery-compass-snapshot-v1", _RECOVERY_COMPASS_FIELDS, validate_recovery_compass_snapshot)


def build_quarter_health_campaign(payload: Any) -> ProductContractBuildResult:
    return _build(payload, "quarter-health-campaign-v1", _QUARTER_CAMPAIGN_FIELDS, validate_quarter_health_campaign)


def build_weekly_experiment(payload: Any) -> ProductContractBuildResult:
    return _build(payload, "weekly-experiment-v1", _WEEKLY_EXPERIMENT_FIELDS, validate_weekly_experiment)


def build_professional_escalation(payload: Any) -> ProductContractBuildResult:
    return _build(payload, "professional-escalation-v1", _PROFESSIONAL_ESCALATION_FIELDS, validate_professional_escalation)
