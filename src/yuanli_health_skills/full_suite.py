"""Deterministic, platform-neutral dispatcher for the twelve Task 3 skills."""

import hashlib
import json
import math
import re
from copy import deepcopy
from typing import Any

from .envelope import build_candidate_envelope


_CASE_FIELDS = (
    "schema",
    "case_id",
    "synthetic",
    "capability_source_id",
    "category",
    "coverage_tags",
    "request_type",
    "risk_flags",
    "artifacts",
    "declared_unknowns",
    "assumptions",
    "expected",
)
_REQUEST_TYPES = frozenset(
    {
        "diagnosis",
        "emergency",
        "formal_plan",
        "learning_claim",
        "medication_change",
        "non_clinical",
        "outcome_adjudication",
        "reuse_claim",
        "appointment_logistics",
    }
)
_RISK_FLAGS = frozenset({"clinical_escalation", "emergency", "guardrail_requested"})
_CLINICAL_REQUESTS = frozenset({"diagnosis", "medication_change", "emergency"})
_CLINICAL_RISKS = frozenset({"clinical_escalation", "emergency"})
_TOKEN_PATTERN = re.compile(r"SYN-[A-Z0-9]+(?:-[A-Z0-9]+)*")
_DOCTOR_VISIT = "yuanli.health.experience.doctor-visit-prep"
_MAX_INERT_JSON_DEPTH = 128
# Finite public range keeps exact known-fact decimal conversion safely bounded.
_MAX_SYNTHETIC_CASE_COUNT = 1_000_000

_CAPABILITIES: dict[str, dict[str, Any]] = {
    "yuanli.health.kernel.wpk": {
        "required": ("decision_candidate_id",),
        "state": "work_packet_candidate_ready",
        "transition": "emit_wpk",
        "outputs": ("wpk_candidate_id",),
    },
    "yuanli.health.kernel.act": {
        "required": ("wpk_candidate_id",),
        "state": "action_candidate_ready",
        "transition": "emit_act",
        "outputs": ("act_candidate_id",),
    },
    "yuanli.health.kernel.out": {
        "required": ("act_candidate_id", "observation_reference"),
        "state": "outcome_candidate_ready",
        "transition": "adjudicate_out",
        "outputs": ("out_candidate_id",),
    },
    "yuanli.health.kernel.lrn": {
        "required": ("out_candidate_id",),
        "state": "learning_candidate_ready",
        "transition": "emit_lrn",
        "outputs": ("lrn_candidate_id",),
    },
    "yuanli.health.experience.ninety-day-health-experiment": {
        "required": ("decision_candidate_id",),
        "state": "experiment_candidate_ready",
        "transition": "orchestrate_ninety_day_experiment",
        "outputs": ("wpk_candidate_id", "act_candidate_id"),
    },
    "yuanli.health.experience.weekly-health-checkpoint": {
        "required": ("act_candidate_id",),
        "optional": ("observation_reference",),
        "state": "checkpoint_candidate_ready",
        "transition": "orchestrate_weekly_checkpoint",
        "outputs": (),
    },
    _DOCTOR_VISIT: {
        "required": ("visit_questions",),
        "state": "visit_prep_candidate_ready",
        "transition": "prepare_doctor_visit",
        "outputs": ("visit_questions",),
    },
    "yuanli.health.experience.outcome-review": {
        "required": ("act_candidate_id", "observation_reference"),
        "state": "outcome_candidate_ready",
        "transition": "orchestrate_outcome_review",
        "outputs": ("out_candidate_id",),
    },
    "yuanli.health.experience.learning-reuse": {
        "required": ("lrn_candidate_id", "task2_preload_receipt", "task2_use_receipt"),
        "state": "reuse_candidate_ready",
        "transition": "orchestrate_learning_reuse",
        "outputs": (),
    },
    "yuanli.health.meta.build": {
        "required": ("draft_capability_id",),
        "state": "build_candidate_ready",
        "transition": "build_capability_candidate",
        "outputs": ("built_candidate_id",),
    },
    "yuanli.health.meta.review": {
        "required": ("built_candidate_id",),
        "state": "review_candidate_ready",
        "transition": "review_capability_candidate",
        "outputs": ("review_candidate_id",),
    },
    "yuanli.health.meta.qualify": {
        "required": ("review_candidate_id", "synthetic_case_count"),
        "state": "qualified_candidate_ready",
        "transition": "qualify_synthetic_candidate",
        "outputs": (),
    },
}

_ARTIFACT_KEYS = frozenset(
    {
        "decision_candidate_id",
        "wpk_candidate_id",
        "act_candidate_id",
        "observation_reference",
        "out_candidate_id",
        "lrn_candidate_id",
        "task2_preload_receipt",
        "task2_use_receipt",
        "visit_questions",
        "draft_capability_id",
        "built_candidate_id",
        "review_candidate_id",
        "synthetic_case_count",
    }
)


def _base_result() -> dict[str, Any]:
    return {
        "canonical_write": False,
        "persistence": "none",
        "registry_admission": False,
        "release_published": False,
        "health_outcome_claimed": False,
        "clinical_effectiveness_claimed": False,
        "runtime_observed": False,
    }


def _error(
    code: str,
    path: str,
    *,
    authority_gate: str | None = None,
    transition_intent: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": "full-suite-error-v1",
        "candidate_state": None,
        "transition_intent": transition_intent,
        "transition_executed": False,
        "authority_gate": authority_gate,
        "output_artifacts": {},
        "errors": [{"code": code, "path": path}],
        **_base_result(),
    }


def _capability_error(spec: dict[str, Any], code: str, path: str) -> dict[str, Any]:
    return _error(
        code,
        path,
        authority_gate="YELLOW",
        transition_intent=spec["transition"],
    )


def _inert_json_issue(value: Any) -> str | None:
    """Iteratively validate inert JSON and bound nesting before recursive cloning."""

    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > _MAX_INERT_JSON_DEPTH:
            return "INERT_JSON_DEPTH_EXCEEDED"
        item_type = type(item)
        if item is None or item_type in {bool, int, str}:
            continue
        if item_type is float:
            if not math.isfinite(item):
                return "INVALID_INERT_JSON"
            continue
        if item_type is list:
            pending.extend((nested, depth + 1) for nested in item)
            continue
        if item_type is dict:
            for key, nested in item.items():
                if type(key) is not str:
                    return "INVALID_INERT_JSON"
                pending.append((nested, depth + 1))
            continue
        return "INVALID_INERT_JSON"
    return None


def _valid_string_array(value: Any) -> bool:
    return type(value) is list and all(type(item) is str and bool(item) for item in value)


def _artifact_facts(artifacts: dict[str, Any]) -> tuple[list[dict[str, str]], set[str]]:
    known: list[dict[str, str]] = []
    facts: set[str] = set()
    for key, value in artifacts.items():
        values = value if type(value) is list else [value]
        for index, item in enumerate(values):
            fact = str(item)
            if not fact:
                continue
            reference = f"artifact:{key}" if type(value) is not list else f"artifact:{key}:{index}"
            known.append({"fact": fact, "evidence_reference": reference})
            facts.add(fact)
    return known, facts


def _validate_artifact_value(key: str, value: Any) -> tuple[str, str] | None:
    path = f"artifacts.{key}"
    if key == "visit_questions":
        if not _valid_string_array(value) or not value or any(_TOKEN_PATTERN.fullmatch(item) is None for item in value):
            return "INVALID_VISIT_QUESTIONS", path
        return None
    if key == "synthetic_case_count":
        if type(value) is not int or not 0 <= value <= _MAX_SYNTHETIC_CASE_COUNT:
            return "INVALID_ARTIFACT", path
        return None
    if type(value) is not str or _TOKEN_PATTERN.fullmatch(value) is None:
        return "INVALID_ARTIFACT", path
    return None


def _opaque_id(source_id: str, output_key: str, artifacts: dict[str, Any]) -> str:
    material = json.dumps(
        {"source_capability_id": source_id, "output_key": output_key, "artifacts": artifacts},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "SYN-" + hashlib.sha256(material).hexdigest()[:20].upper()


def _candidate(
    case: dict[str, Any],
    spec: dict[str, Any],
    *,
    authority_gate: str,
    output_artifacts: dict[str, Any],
    guardrail: list[str] | None = None,
    escalation: list[str] | None = None,
) -> dict[str, Any]:
    known, _ = _artifact_facts(case["artifacts"])
    envelope = build_candidate_envelope(
        source_capability_id=case["capability_source_id"],
        known=known,
        unknown=case["declared_unknowns"],
        assumptions=case["assumptions"],
        authority_gate=authority_gate,
        escalation=escalation or [],
        guardrail=guardrail or [],
        candidate_state="proposed",
    )
    return {
        "schema": "full-suite-candidate-v1",
        "source_capability_id": case["capability_source_id"],
        "candidate_state": spec["state"],
        "transition_intent": spec["transition"],
        "transition_executed": True,
        "envelope": envelope,
        "output_artifacts": deepcopy(output_artifacts),
        "authority_gate": authority_gate,
        **_base_result(),
    }


def process_full_suite_case(value: Any) -> dict[str, Any]:
    """Validate and execute one inert synthetic case without side effects."""

    if type(value) is not dict:
        return _error("INVALID_CASE", "$")
    inert_issue = _inert_json_issue(value)
    if inert_issue is not None:
        return _error(inert_issue, "$")
    for field in _CASE_FIELDS:
        if field not in value:
            return _error("MISSING_REQUIRED_FIELD", field)
    unknown_fields = sorted(set(value) - set(_CASE_FIELDS))
    if unknown_fields:
        return _error("UNKNOWN_FIELD", unknown_fields[0])
    if value["schema"] != "full-suite-synthetic-case-v1":
        return _error("INVALID_SCHEMA", "schema")
    if value["synthetic"] is not True:
        return _error("SYNTHETIC_CASE_REQUIRED", "synthetic")
    if type(value["case_id"]) is not str or re.fullmatch(r"SYN-FS-[0-9]{3}", value["case_id"]) is None:
        return _error("INVALID_CASE_ID", "case_id")
    source_id = value["capability_source_id"]
    if type(source_id) is not str or source_id not in _CAPABILITIES:
        return _error("UNSUPPORTED_CAPABILITY", "capability_source_id")
    spec = _CAPABILITIES[source_id]
    if type(value["category"]) is not str or value["category"] not in {
        "gold",
        "boundary",
        "adversarial",
    }:
        return _error("INVALID_CATEGORY", "category")
    for field in ("coverage_tags", "declared_unknowns", "assumptions", "risk_flags"):
        if not _valid_string_array(value[field]):
            return _error("INVALID_STRING_ARRAY", field)
    if type(value["request_type"]) is not str or value["request_type"] not in _REQUEST_TYPES:
        return _error("INVALID_REQUEST_TYPE", "request_type")
    for index, flag in enumerate(value["risk_flags"]):
        if flag not in _RISK_FLAGS:
            return _error("INVALID_RISK_FLAG", f"risk_flags[{index}]")
        if flag in value["risk_flags"][:index]:
            return _error("DUPLICATE_RISK_FLAG", f"risk_flags[{index}]")
    artifacts = value["artifacts"]
    if type(artifacts) is not dict:
        return _error("INVALID_ARTIFACTS", "artifacts")
    unknown_artifacts = sorted(set(artifacts) - _ARTIFACT_KEYS)
    if unknown_artifacts:
        return _error("UNKNOWN_ARTIFACT", f"artifacts.{unknown_artifacts[0]}")
    for key in spec["required"]:
        if key not in artifacts:
            return _capability_error(spec, "MISSING_REQUIRED_ARTIFACT", f"artifacts.{key}")
    allowed_for_capability = set(spec["required"]) | set(spec.get("optional", ()))
    unexpected = sorted(set(artifacts) - allowed_for_capability)
    if unexpected:
        return _capability_error(spec, "UNEXPECTED_ARTIFACT", f"artifacts.{unexpected[0]}")
    for key, artifact in artifacts.items():
        error = _validate_artifact_value(key, artifact)
        if error is not None:
            return _capability_error(spec, *error)
    if source_id == "yuanli.health.meta.qualify" and artifacts["synthetic_case_count"] < 10:
        return _capability_error(spec, "PREREQUISITE_NOT_MET", "artifacts.synthetic_case_count")
    if source_id == "yuanli.health.experience.learning-reuse" and artifacts["task2_preload_receipt"] == artifacts["task2_use_receipt"]:
        return _capability_error(spec, "INDEPENDENT_RECEIPTS_REQUIRED", "artifacts.task2_use_receipt")
    _, known_facts = _artifact_facts(artifacts)
    for index, unknown in enumerate(value["declared_unknowns"]):
        if unknown in known_facts:
            return _capability_error(spec, "UNKNOWN_KNOWN_OVERLAP", f"declared_unknowns[{index}]")
    for index, assumption in enumerate(value["assumptions"]):
        if assumption in known_facts:
            return _capability_error(spec, "ASSUMPTION_KNOWN_OVERLAP", f"assumptions[{index}]")

    clinical = value["request_type"] in _CLINICAL_REQUESTS or bool(
        set(value["risk_flags"]) & _CLINICAL_RISKS
    )
    if clinical and source_id != _DOCTOR_VISIT:
        return _error(
            "CLINICAL_ESCALATION_REQUIRED",
            "request_type" if value["request_type"] in _CLINICAL_REQUESTS else "risk_flags",
            authority_gate="RED",
            transition_intent=spec["transition"],
        )
    if value["request_type"] == "appointment_logistics" and source_id != _DOCTOR_VISIT:
        return _error(
            "APPOINTMENT_DELEGATION_REQUIRED",
            "request_type",
            authority_gate="YELLOW",
            transition_intent=spec["transition"],
        )

    if source_id == _DOCTOR_VISIT:
        outputs: dict[str, Any] = {"visit_questions": deepcopy(artifacts["visit_questions"])}
        if clinical:
            guardrails = [
                "请向临床医生确认 / Confirm with a clinician.",
                "紧急情况请联系当地急救服务 / For emergencies, contact local emergency services.",
            ]
            outputs["guardrails"] = guardrails
            return _candidate(
                value,
                spec,
                authority_gate="RED",
                output_artifacts=outputs,
                guardrail=guardrails,
                escalation=["clinician_review", "local_emergency_services"],
            )
        if value["request_type"] == "appointment_logistics":
            outputs["delegation"] = "yuanli-medical-appointment-operator"
            return _candidate(
                value,
                spec,
                authority_gate="YELLOW",
                output_artifacts=outputs,
                escalation=["yuanli-medical-appointment-operator"],
            )
        return _candidate(value, spec, authority_gate="GREEN", output_artifacts=outputs)

    outputs = {
        key: _opaque_id(source_id, key, artifacts)
        for key in spec["outputs"]
    }
    return _candidate(value, spec, authority_gate="GREEN", output_artifacts=outputs)
