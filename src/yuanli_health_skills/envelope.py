"""Constructor for the typed candidate envelope ABI."""

from copy import deepcopy
from typing import Any, Iterable, Mapping


def build_candidate_envelope(
    *,
    source_capability_id: str,
    known: Iterable[Mapping[str, str]],
    unknown: Iterable[str],
    assumptions: Iterable[str],
    authority_gate: str,
    escalation: Iterable[str],
    guardrail: Iterable[str],
    candidate_state: str = "proposed",
) -> dict[str, Any]:
    """Build a non-canonical, non-persistent candidate envelope."""

    known_entries = [deepcopy(dict(entry)) for entry in known]
    evidence_references = list(
        dict.fromkeys(
            entry.get("evidence_reference", "")
            for entry in known_entries
            if entry.get("evidence_reference")
        )
    )
    return {
        "schema": "typed-candidate-envelope-v1",
        "source_capability_id": source_capability_id,
        "known": known_entries,
        "unknown": list(unknown),
        "assumption": list(assumptions),
        "evidence_references": evidence_references,
        "authority_gate": authority_gate,
        "candidate_state": candidate_state,
        "canonical_write": False,
        "persistence": "none",
        "escalation": list(escalation),
        "guardrail": list(guardrail),
    }
