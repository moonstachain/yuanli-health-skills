"""Deterministic CTX -> EVD -> DEC First Health Session Gold Slice."""

import re
from collections.abc import Mapping
from typing import Any

from .envelope import build_candidate_envelope


_CASE_FIELDS = (
    "case_id",
    "synthetic",
    "family",
    "coverage_tags",
    "jtbd",
    "goal",
    "constraints",
    "declared_unknowns",
    "assumptions",
    "evidence",
    "candidates",
    "request_type",
    "risk_flags",
    "expected",
)
_EVIDENCE_FIELDS = ("reference", "fact", "source", "status")
_CANDIDATE_FIELDS = (
    "candidate_kind",
    "candidate_id",
    "label",
    "evidence_references",
    "dependency_blockers",
)
_SOURCES = frozenset({"self_report", "wearable", "clinical"})
_STATUSES = frozenset({"supports", "contradicts", "unverified"})
_RED_REQUESTS = frozenset({"diagnosis", "medication_change", "emergency"})
_DOWNSTREAM_REQUESTS = frozenset(
    {"outcome_adjudication", "learning_claim", "reuse_claim", "formal_plan"}
)
_REQUEST_TYPES = _RED_REQUESTS | _DOWNSTREAM_REQUESTS | {"non_clinical"}
_RISK_FLAGS = frozenset({"clinical_escalation", "emergency", "guardrail_requested"})
_CANDIDATE_ID_PATTERN = re.compile(r"CAND-[0-9]{3}-[A-Z]")
_CANDIDATE_LABEL_PATTERN = re.compile(r"abstract_candidate_[a-z]+")
_RESERVED_CANDIDATE_LABELS = frozenset(
    {
        "abstract_candidate_diagnosis",
        "abstract_candidate_medication",
        "abstract_candidate_emergency",
    }
)


def _error(code: str, path: str) -> dict[str, str]:
    return {"code": code, "path": path}


def _error_result(errors: list[dict[str, str]]) -> dict[str, Any]:
    return {"schema": "gold-slice-error-v1", "ok": False, "errors": errors}


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _validate_case(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, Mapping):
        return [_error("INVALID_CASE", "$")]
    if any(type(key) is not str for key in value):
        return [_error("INVALID_INERT_JSON_KEY", "$")]
    errors = [
        _error("MISSING_REQUIRED_FIELD", field)
        for field in _CASE_FIELDS
        if field not in value
    ]
    errors.extend(
        _error("UNKNOWN_FIELD", field)
        for field in sorted(set(value) - set(_CASE_FIELDS))
    )
    if errors:
        return errors
    if value["synthetic"] is not True:
        errors.append(_error("SYNTHETIC_CASE_REQUIRED", "synthetic"))
    for field in ("case_id", "family", "jtbd", "request_type"):
        if not isinstance(value[field], str) or not value[field]:
            errors.append(_error("INVALID_FIELD_TYPE", field))
    if value["goal"] is not None and (
        not isinstance(value["goal"], str) or not value["goal"]
    ):
        errors.append(_error("INVALID_FIELD_TYPE", "goal"))
    for field in (
        "coverage_tags",
        "constraints",
        "declared_unknowns",
        "assumptions",
        "risk_flags",
    ):
        if not _is_string_list(value[field]):
            errors.append(_error("INVALID_STRING_ARRAY", field))
    if (
        isinstance(value["request_type"], str)
        and value["request_type"]
        and value["request_type"] not in _REQUEST_TYPES
    ):
        errors.append(_error("INVALID_REQUEST_TYPE", "request_type"))
    if _is_string_list(value["risk_flags"]):
        for index, flag in enumerate(value["risk_flags"]):
            if flag not in _RISK_FLAGS:
                errors.append(_error("INVALID_RISK_FLAG", f"risk_flags[{index}]"))
    evidence = value["evidence"]
    if not isinstance(evidence, list):
        errors.append(_error("INVALID_EVIDENCE", "evidence"))
    else:
        references: list[str] = []
        for index, entry in enumerate(evidence):
            path = f"evidence[{index}]"
            if not isinstance(entry, Mapping) or set(entry) != set(_EVIDENCE_FIELDS):
                errors.append(_error("INVALID_EVIDENCE", path))
                continue
            valid_reference = isinstance(entry["reference"], str) and bool(entry["reference"])
            if not valid_reference or not isinstance(entry["fact"], str) or not entry["fact"]:
                errors.append(_error("INVALID_EVIDENCE", path))
            if (
                not isinstance(entry["source"], str)
                or entry["source"] not in _SOURCES
                or not isinstance(entry["status"], str)
                or entry["status"] not in _STATUSES
            ):
                errors.append(_error("INVALID_EVIDENCE", path))
            if valid_reference:
                references.append(entry["reference"])
        if len(references) != len(set(references)):
            errors.append(_error("DUPLICATE_EVIDENCE_REFERENCE", "evidence"))
    candidates = value["candidates"]
    if not isinstance(candidates, list):
        errors.append(_error("INVALID_CANDIDATES", "candidates"))
    else:
        identifiers: list[str] = []
        for index, candidate in enumerate(candidates):
            path = f"candidates[{index}]"
            if not isinstance(candidate, Mapping):
                errors.append(_error("INVALID_CANDIDATE", path))
                continue
            missing_fields = set(_CANDIDATE_FIELDS) - set(candidate)
            unknown_fields = set(candidate) - set(_CANDIDATE_FIELDS)
            if missing_fields or unknown_fields:
                if missing_fields == {"candidate_kind"} and not unknown_fields:
                    errors.append(
                        _error("INVALID_CANDIDATE_KIND", f"{path}.candidate_kind")
                    )
                else:
                    errors.append(_error("INVALID_CANDIDATE", path))
                continue
            if candidate["candidate_kind"] != "non_clinical":
                errors.append(
                    _error("INVALID_CANDIDATE_KIND", f"{path}.candidate_kind")
                )
            valid_identifier = (
                isinstance(candidate["candidate_id"], str)
                and _CANDIDATE_ID_PATTERN.fullmatch(candidate["candidate_id"])
                is not None
            )
            if not valid_identifier:
                errors.append(_error("INVALID_CANDIDATE_ID", f"{path}.candidate_id"))
            valid_label = (
                isinstance(candidate["label"], str)
                and _CANDIDATE_LABEL_PATTERN.fullmatch(candidate["label"]) is not None
                and candidate["label"] not in _RESERVED_CANDIDATE_LABELS
            )
            if not valid_label:
                errors.append(_error("INVALID_CANDIDATE_LABEL", f"{path}.label"))
            if not _is_string_list(candidate["evidence_references"]):
                errors.append(_error("INVALID_CANDIDATE", f"{path}.evidence_references"))
            if not _is_string_list(candidate["dependency_blockers"]):
                errors.append(_error("INVALID_CANDIDATE", f"{path}.dependency_blockers"))
            if valid_identifier:
                identifiers.append(candidate["candidate_id"])
        if len(identifiers) != len(set(identifiers)):
            errors.append(_error("DUPLICATE_CANDIDATE_ID", "candidates"))
    if not isinstance(value["expected"], Mapping):
        errors.append(_error("INVALID_EXPECTED_ASSERTIONS", "expected"))
    if not errors:
        known_facts = set(value["constraints"])
        if value["goal"]:
            known_facts.add(value["goal"])
        known_facts.update(
            entry["fact"]
            for entry in value["evidence"]
            if entry["status"] == "supports"
        )
        for index, assumption in enumerate(value["assumptions"]):
            if assumption in known_facts:
                errors.append(
                    _error("ASSUMPTION_KNOWN_OVERLAP", f"assumptions[{index}]")
                )
                break
    return errors


def _clone_json(value: Any) -> Any:
    if value is None or type(value) in {bool, int, float, str}:
        return value
    if type(value) is list:
        return [_clone_json(item) for item in value]
    if type(value) is dict:
        return {key: _clone_json(item) for key, item in value.items()}
    raise TypeError("value is outside the inert JSON algebra")


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _ctx_envelope(case: Mapping[str, Any]) -> dict[str, Any]:
    known: list[dict[str, str]] = []
    unknown = list(case["declared_unknowns"])
    if case["goal"]:
        known.append({"fact": case["goal"], "evidence_reference": "input:goal"})
    else:
        unknown.append("goal_not_supplied")
    known.extend(
        {"fact": fact, "evidence_reference": f"input:constraint:{index}"}
        for index, fact in enumerate(case["constraints"], start=1)
    )
    return build_candidate_envelope(
        source_capability_id="yuanli.health.kernel.ctx",
        known=known,
        unknown=_unique(unknown),
        assumptions=case["assumptions"],
        authority_gate="YELLOW" if not case["goal"] else "GREEN",
        escalation=["request_subject_context"] if not case["goal"] else [],
        guardrail=["non_clinical_candidate_only"],
    )


def _has_contradiction(evidence: list[Mapping[str, str]]) -> bool:
    return any(entry["status"] == "contradicts" for entry in evidence)


def _has_clinical_wearable_conflict(evidence: list[Mapping[str, str]]) -> bool:
    by_fact: dict[str, list[Mapping[str, str]]] = {}
    for entry in evidence:
        by_fact.setdefault(entry["fact"], []).append(entry)
    for entries in by_fact.values():
        sources = {entry["source"] for entry in entries}
        statuses = {entry["status"] for entry in entries}
        if {"clinical", "wearable"}.issubset(sources) and "contradicts" in statuses:
            return True
    return False


def _evidence_known(evidence: list[Mapping[str, str]]) -> list[dict[str, str]]:
    return [
        {"fact": entry["fact"], "evidence_reference": entry["reference"]}
        for entry in evidence
        if entry["status"] == "supports"
    ]


def _evd_envelope(case: Mapping[str, Any]) -> dict[str, Any]:
    evidence = case["evidence"]
    unknown = list(case["declared_unknowns"])
    unknown.extend(
        f"evidence_unresolved:{entry['reference']}"
        for entry in evidence
        if entry["status"] != "supports"
    )
    if not evidence:
        unknown.append("evidence_not_supplied")
    conflict = _has_contradiction(evidence)
    clinical_conflict = _has_clinical_wearable_conflict(evidence)
    gate = "RED" if clinical_conflict else "YELLOW" if conflict or not _evidence_known(evidence) else "GREEN"
    return build_candidate_envelope(
        source_capability_id="yuanli.health.kernel.evd",
        known=_evidence_known(evidence),
        unknown=_unique(unknown),
        assumptions=case["assumptions"],
        authority_gate=gate,
        escalation=["consult_clinician"] if clinical_conflict else [],
        guardrail=["organize_evidence_without_priority"],
    )


def _eligible_candidate(
    candidate: Mapping[str, Any], evidence_by_reference: Mapping[str, Mapping[str, str]]
) -> bool:
    references = candidate["evidence_references"]
    return bool(references) and all(
        reference in evidence_by_reference
        and evidence_by_reference[reference]["status"] == "supports"
        for reference in references
    )


def _decision(case: Mapping[str, Any]) -> tuple[str, str | None, list[str], list[str]]:
    evidence = case["evidence"]
    emergency = case["request_type"] == "emergency" or "emergency" in case["risk_flags"]
    clinical_red = (
        emergency
        or case["request_type"] in _RED_REQUESTS
        or "clinical_escalation" in case["risk_flags"]
        or _has_clinical_wearable_conflict(evidence)
    )
    if clinical_red:
        escalation = ["seek_emergency_help"] if emergency else ["consult_clinician"]
        return "RED", None, [], escalation
    if _has_contradiction(evidence) or case["request_type"] in _DOWNSTREAM_REQUESTS:
        return "YELLOW", None, [], []
    by_reference = {entry["reference"]: entry for entry in evidence}
    primary = next(
        (
            candidate
            for candidate in case["candidates"]
            if _eligible_candidate(candidate, by_reference)
        ),
        None,
    )
    if primary is None:
        return "YELLOW", None, [], []
    return (
        "GREEN",
        primary["candidate_id"],
        list(primary["dependency_blockers"][:2]),
        [],
    )


def _dec_envelope(
    case: Mapping[str, Any], gate: str, primary: str | None, escalation: list[str]
) -> dict[str, Any]:
    unknown = list(case["declared_unknowns"])
    if _has_contradiction(case["evidence"]):
        unknown.append("contradictory_evidence_unresolved")
    if primary is None:
        unknown.append("primary_bottleneck_not_selected")
    return build_candidate_envelope(
        source_capability_id="yuanli.health.kernel.dec",
        known=_evidence_known(case["evidence"]),
        unknown=_unique(unknown),
        assumptions=case["assumptions"],
        authority_gate=gate,
        escalation=escalation,
        guardrail=["decision_candidate_not_formal_act"],
    )


def _learner_view(
    case: Mapping[str, Any], gate: str, primary: str | None, evidence: list[Mapping[str, str]]
) -> dict[str, str]:
    if gate == "RED":
        conclusion = "No clinical conclusion is produced; escalation is required."
        reason = "A safety boundary requires external human authority."
        if case["request_type"] == "emergency" or "emergency" in case["risk_flags"]:
            guardrail = "请立即联系当地急救服务 / Contact local emergency services now."
        else:
            guardrail = "请联系临床专业人员 / Contact a clinician."
    elif primary is None:
        conclusion = "No decision candidate is ready; uncertainty remains explicit."
        reason = "Supplied evidence or scope is insufficient for candidate selection."
        guardrail = "Non-clinical candidate boundary; keep unknowns explicit."
    else:
        conclusion = "A non-clinical decision candidate is ready."
        reason = "The first input-ordered candidate with supported evidence was selected."
        guardrail = "Non-clinical candidate only; subject authority remains final."
    action_candidate = (
        f"Discuss {primary} with the supplied evidence."
        if primary
        else "Discuss missing evidence and escalation before any next candidate."
    )
    evidence_entry = evidence[0]["reference"] if evidence else "no_supplied_evidence"
    return {
        "conclusion": conclusion,
        "reason": reason,
        "action_candidate": action_candidate,
        "guardrail": guardrail,
        "evidence_entry": evidence_entry,
    }


def process_first_health_session(case: Any) -> dict[str, Any]:
    """Process a declared synthetic case, returning a bundle or stable errors."""

    errors = _validate_case(case)
    if errors:
        return _error_result(errors)
    gate, primary, blockers, escalation = _decision(case)
    evidence = _clone_json(case["evidence"])
    return {
        "schema": "first-health-session-bundle-v1",
        "experience_source_capability_id": "yuanli.health.experience.first-health-session",
        "experience_state": "decision_candidate_ready",
        "stage_order": ["ctx", "evd", "dec"],
        "stage_envelopes": {
            "ctx": _ctx_envelope(case),
            "evd": _evd_envelope(case),
            "dec": _dec_envelope(case, gate, primary, escalation),
        },
        "evidence_catalog": evidence,
        "decision_candidate": {
            "primary_bottleneck": primary,
            "dependency_blockers": blockers,
        },
        "learner_view": _learner_view(case, gate, primary, evidence),
        "authority_gate": gate,
        "canonical_write": False,
        "persistence": "none",
        "formal_wpk_generated": False,
        "formal_act_generated": False,
        "out_generated": False,
        "lrn_generated": False,
        "reuse_claimed": False,
    }
