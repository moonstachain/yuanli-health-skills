"""Deterministic, network-free validators for the public health-skill ABI."""

from dataclasses import dataclass
from typing import Any, Mapping

from .projection import allowed_domain_objects, allowed_health_clocks


@dataclass(frozen=True)
class ValidationError:
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[ValidationError, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


_CONTRACT_REQUIRED = (
    "schema",
    "source_capability_id",
    "registry_capability_id",
    "class",
    "profile_of",
    "transition_intent",
    "mutates_canon",
    "authority",
    "privacy",
    "runtime_requirements",
    "lifecycle",
    "qualification",
    "objects",
    "health_clock",
    "claims",
)
_CLINICAL_OVERREACH = frozenset(
    {
        "clinical_diagnosis",
        "prescription",
        "medication_change",
        "emergency_adjudication",
        "final_canon_authority",
    }
)


def _error(code: str, path: str, message: str) -> ValidationError:
    return ValidationError(code, path, message)


def _required_and_strict(data: Mapping[str, Any], required: tuple[str, ...]) -> list[ValidationError]:
    errors = [
        _error("MISSING_REQUIRED_FIELD", field, f"required field is missing: {field}")
        for field in required
        if field not in data
    ]
    allowed = frozenset(required)
    errors.extend(
        _error("STRICT_SCHEMA_VIOLATION", field, f"unknown field: {field}")
        for field in sorted(set(data) - allowed)
    )
    return errors


def _nested_shape(value: Any, path: str, required: tuple[str, ...]) -> list[ValidationError]:
    if not isinstance(value, Mapping):
        return []
    errors = [
        _error("MISSING_REQUIRED_FIELD", f"{path}.{field}", f"required field is missing: {field}")
        for field in required
        if field not in value
    ]
    errors.extend(
        _error("STRICT_SCHEMA_VIOLATION", f"{path}.{field}", f"unknown field: {field}")
        for field in sorted(set(value) - frozenset(required))
    )
    return errors


def validate_contract(value: Any) -> ValidationResult:
    if not isinstance(value, Mapping):
        return ValidationResult((_error("INVALID_DOCUMENT", "$", "contract must be an object"),))
    errors = _required_and_strict(value, _CONTRACT_REQUIRED)
    if value.get("schema") != "health-skill-contract-v1":
        errors.append(_error("INVALID_SCHEMA", "schema", "unexpected contract schema"))
    source_id = value.get("source_capability_id")
    if not isinstance(source_id, str) or not source_id.startswith("yuanli.health."):
        errors.append(_error("INVALID_SOURCE_CAPABILITY_ID", "source_capability_id", "invalid source capability ID"))
    if value.get("class") not in {"kernel", "experience", "meta"}:
        errors.append(_error("INVALID_CLASS", "class", "class must be kernel, experience, or meta"))
    transition = value.get("transition_intent")
    if not isinstance(transition, str) or not transition.strip():
        errors.append(_error("TRANSITION_INTENT_SINGLE_STRING", "transition_intent", "transition intent must be one non-empty string"))
    if value.get("mutates_canon") is not False:
        errors.append(_error("CANON_WRITE_FORBIDDEN", "mutates_canon", "candidate capabilities cannot mutate Canon"))
    authority = value.get("authority")
    errors.extend(_nested_shape(authority, "authority", ("final_authority", "ai", "device", "automation", "router")))
    if not isinstance(authority, Mapping):
        errors.append(_error("INVALID_AUTHORITY", "authority", "authority must be an object"))
    else:
        forbidden = {"ai", "device", "automation", "router"}
        if authority.get("final_authority") in forbidden or any(authority.get(role) == "final" for role in forbidden):
            errors.append(_error("FINAL_AUTHORITY_FORBIDDEN", "authority", "AI, device, automation, and Router cannot be final authority"))
    privacy = value.get("privacy")
    errors.extend(_nested_shape(privacy, "privacy", ("repository_phi",)))
    if not isinstance(privacy, Mapping) or privacy.get("repository_phi") != "forbidden":
        errors.append(_error("REPOSITORY_PHI_FORBIDDEN", "privacy.repository_phi", "repository PHI policy must be forbidden"))
    runtime = value.get("runtime_requirements")
    errors.extend(_nested_shape(runtime, "runtime_requirements", ("ephemeral", "persistence", "logs")))
    if not isinstance(runtime, Mapping):
        errors.append(_error("INVALID_RUNTIME_REQUIREMENTS", "runtime_requirements", "runtime requirements must be an object"))
    else:
        if runtime.get("ephemeral") is not True:
            errors.append(_error("RUNTIME_EPHEMERAL_REQUIRED", "runtime_requirements.ephemeral", "runtime must be ephemeral"))
        if runtime.get("persistence") != "none":
            errors.append(_error("RUNTIME_PERSISTENCE_FORBIDDEN", "runtime_requirements.persistence", "runtime persistence must be none"))
        if runtime.get("logs") != "none":
            errors.append(_error("RUNTIME_LOGGING_FORBIDDEN", "runtime_requirements.logs", "runtime logs must be none"))
    if value.get("lifecycle") not in {"proposed", "qualified", "human_review_ready"}:
        errors.append(_error("INVALID_LIFECYCLE", "lifecycle", "invalid candidate lifecycle"))
    qualification = value.get("qualification")
    errors.extend(_nested_shape(qualification, "qualification", ("basis", "status")))
    if not isinstance(qualification, Mapping) or qualification.get("basis") != "synthetic_only":
        errors.append(_error("SYNTHETIC_QUALIFICATION_REQUIRED", "qualification.basis", "qualification must use synthetic inputs only"))
    objects = value.get("objects")
    profiles = value.get("profile_of")
    object_values = list(objects) if isinstance(objects, list) else []
    profile_values = list(profiles) if isinstance(profiles, list) else []
    if not isinstance(objects, list) or not isinstance(profiles, list):
        errors.append(_error("INVALID_DOMAIN_OBJECTS", "objects", "objects and profile_of must be arrays"))
    elif any(item not in allowed_domain_objects() for item in object_values + profile_values):
        errors.append(_error("UNKNOWN_DOMAIN_OBJECT", "objects", "domain object is absent from the frozen projection"))
    if value.get("health_clock") not in allowed_health_clocks():
        errors.append(_error("UNKNOWN_HEALTH_CLOCK", "health_clock", "health clock is absent from the frozen projection"))
    claims = value.get("claims")
    if not isinstance(claims, list):
        errors.append(_error("INVALID_CLAIMS", "claims", "claims must be an array"))
    elif value.get("class") == "kernel" and _CLINICAL_OVERREACH.intersection(claims):
        errors.append(_error("CLINICAL_OVERREACH", "claims", "kernel capability makes a forbidden clinical or Canon claim"))
    order = {
        "CANON_WRITE_FORBIDDEN": 20,
        "REGISTRY_ID_BEFORE_ADMISSION": 30,
    }
    if value.get("registry_capability_id") is not None:
        errors.append(_error("REGISTRY_ID_BEFORE_ADMISSION", "registry_capability_id", "registry ID must be null before admission"))
    errors.sort(key=lambda item: (order.get(item.code, 10), item.path, item.code))
    return ValidationResult(tuple(errors))


_ENVELOPE_REQUIRED = (
    "schema",
    "source_capability_id",
    "known",
    "unknown",
    "assumption",
    "evidence_references",
    "authority_gate",
    "candidate_state",
    "canonical_write",
    "persistence",
    "escalation",
    "guardrail",
)


def validate_envelope(value: Any) -> ValidationResult:
    if not isinstance(value, Mapping):
        return ValidationResult((_error("INVALID_DOCUMENT", "$", "envelope must be an object"),))
    errors = _required_and_strict(value, _ENVELOPE_REQUIRED)
    if value.get("schema") != "typed-candidate-envelope-v1":
        errors.append(_error("INVALID_SCHEMA", "schema", "unexpected envelope schema"))
    if value.get("canonical_write") is not False:
        errors.append(_error("CANON_WRITE_FORBIDDEN", "canonical_write", "candidate envelope cannot write Canon"))
    if value.get("persistence") != "none":
        errors.append(_error("RUNTIME_PERSISTENCE_FORBIDDEN", "persistence", "candidate envelope cannot persist"))
    if value.get("candidate_state") not in {"proposed", "qualified", "human_review_ready"}:
        errors.append(_error("INVALID_LIFECYCLE", "candidate_state", "invalid candidate state"))
    if value.get("authority_gate") not in {"GREEN", "YELLOW", "RED"}:
        errors.append(_error("INVALID_AUTHORITY_GATE", "authority_gate", "invalid authority gate"))
    known = value.get("known")
    references = value.get("evidence_references")
    assumptions = value.get("assumption")
    if not isinstance(known, list) or not isinstance(references, list):
        errors.append(_error("INVALID_KNOWN", "known", "known and evidence references must be arrays"))
    else:
        known_facts: set[str] = set()
        for entry in known:
            if not isinstance(entry, Mapping):
                errors.append(_error("INVALID_KNOWN", "known", "known entries must be objects"))
                continue
            errors.extend(_nested_shape(entry, "known", ("fact", "evidence_reference")))
            fact = entry.get("fact")
            reference = entry.get("evidence_reference")
            if isinstance(fact, str):
                known_facts.add(fact)
            if not isinstance(reference, str) or not reference or reference not in references:
                errors.append(_error("KNOWN_EVIDENCE_REQUIRED", "known", "every known entry requires a listed evidence reference"))
                break
        if isinstance(assumptions, list) and known_facts.intersection(assumptions):
            errors.append(_error("ASSUMPTION_PROMOTED_TO_KNOWN", "known", "assumptions cannot be silently promoted to known"))
    for field in ("unknown", "assumption", "evidence_references", "escalation", "guardrail"):
        if not isinstance(value.get(field), list):
            errors.append(_error("INVALID_ARRAY", field, f"{field} must be an array"))
    errors.sort(key=lambda item: (item.path, item.code))
    return ValidationResult(tuple(errors))


_RECEIPT_REQUIRED = (
    "schema",
    "source_capability_id",
    "qualification_basis",
    "claims",
    "candidate_state",
    "canonical_write",
)


def validate_receipt(value: Any) -> ValidationResult:
    if not isinstance(value, Mapping):
        return ValidationResult((_error("INVALID_DOCUMENT", "$", "receipt must be an object"),))
    errors = _required_and_strict(value, _RECEIPT_REQUIRED)
    if value.get("schema") != "qualification-receipt-v1":
        errors.append(_error("INVALID_SCHEMA", "schema", "unexpected receipt schema"))
    if value.get("qualification_basis") != "synthetic_only":
        errors.append(_error("SYNTHETIC_QUALIFICATION_REQUIRED", "qualification_basis", "qualification must use synthetic inputs only"))
    claims = value.get("claims")
    if not isinstance(claims, list) or any(claim not in {"non_clinical", "non_release"} for claim in claims):
        errors.append(_error("INVALID_QUALIFICATION_CLAIM", "claims", "receipt may make non-claims only"))
    if value.get("candidate_state") not in {"proposed", "qualified", "human_review_ready"}:
        errors.append(_error("INVALID_LIFECYCLE", "candidate_state", "invalid candidate state"))
    if value.get("canonical_write") is not False:
        errors.append(_error("CANON_WRITE_FORBIDDEN", "canonical_write", "receipt cannot authorize Canon writes"))
    errors.sort(key=lambda item: (item.path, item.code))
    return ValidationResult(tuple(errors))


def validate_source_registry(value: Any) -> ValidationResult:
    expected = (
        "yuanli.health.kernel.ctx",
        "yuanli.health.kernel.evd",
        "yuanli.health.kernel.dec",
        "yuanli.health.kernel.wpk",
        "yuanli.health.kernel.act",
        "yuanli.health.kernel.out",
        "yuanli.health.kernel.lrn",
        "yuanli.health.experience.first-health-session",
        "yuanli.health.experience.ninety-day-health-experiment",
        "yuanli.health.experience.weekly-health-checkpoint",
        "yuanli.health.experience.doctor-visit-prep",
        "yuanli.health.experience.outcome-review",
        "yuanli.health.experience.learning-reuse",
        "yuanli.health.meta.build",
        "yuanli.health.meta.review",
        "yuanli.health.meta.qualify",
    )
    if not isinstance(value, Mapping):
        return ValidationResult((_error("INVALID_DOCUMENT", "$", "registry must be an object"),))
    required = (
        "schema",
        "source_suite_id",
        "catalog_suite_id",
        "name",
        "version",
        "member_count",
        "license",
        "release_basis",
        "members",
    )
    members = value.get("members")
    errors = _required_and_strict(value, required)
    if value.get("schema") != "suite-source-manifest-v1":
        errors.append(_error("INVALID_SCHEMA", "schema", "unexpected source suite schema"))
    if not isinstance(members, list):
        errors.append(_error("INVALID_SUITE_MEMBERS", "members", "members must be an array"))
    else:
        for index, item in enumerate(members):
            errors.extend(_nested_shape(item, f"members[{index}]", ("source_capability_id", "registry_capability_id")))
        ids = tuple(item.get("source_capability_id") for item in members if isinstance(item, Mapping))
        if ids != expected or len(members) != 16:
            errors.append(_error("SOURCE_SUITE_IDENTITY_MISMATCH", "members", "source suite members must match the frozen 16-member order"))
        if any(not isinstance(item, Mapping) or item.get("registry_capability_id") is not None for item in members):
            errors.append(_error("REGISTRY_ID_BEFORE_ADMISSION", "members", "all pre-admission registry IDs must be null"))
    frozen = {
        "source_suite_id": "YL-SUITE-HEALTH-20260823-0001",
        "catalog_suite_id": "zk:suite:yuanli-health",
        "name": "yuanli-health",
        "version": "0.1.0",
        "member_count": 16,
        "license": "Apache-2.0",
        "release_basis": "synthetic_qualification_only",
    }
    for field, expected_value in frozen.items():
        if value.get(field) != expected_value:
            errors.append(_error("SOURCE_SUITE_IDENTITY_MISMATCH", field, f"unexpected suite field: {field}"))
    errors.sort(key=lambda item: (item.path, item.code))
    return ValidationResult(tuple(errors))
