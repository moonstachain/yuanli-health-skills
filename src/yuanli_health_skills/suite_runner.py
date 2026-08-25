"""Ephemeral host-neutral runner for Task 3 Experience capabilities."""

from typing import Any

from .ephemeral import EphemeralSessionContext
from .full_suite import _inert_json_issue, process_full_suite_case
from .router import route_jtbd


_SOURCE_TO_JTBD = {
    "yuanli.health.experience.ninety-day-health-experiment": "ninety_day_health_experiment",
    "yuanli.health.experience.weekly-health-checkpoint": "weekly_health_checkpoint",
    "yuanli.health.experience.doctor-visit-prep": "doctor_visit_prep",
    "yuanli.health.experience.outcome-review": "outcome_review",
    "yuanli.health.experience.learning-reuse": "learning_reuse",
}
_AVAILABLE_EXPERIENCES = list(_SOURCE_TO_JTBD)


def _no_route_error() -> dict[str, Any]:
    return {
        "schema": "full-suite-error-v1",
        "candidate_state": None,
        "transition_intent": None,
        "transition_executed": False,
        "authority_gate": None,
        "output_artifacts": {},
        "errors": [{"code": "NO_ROUTE", "path": "capability_source_id"}],
        "canonical_write": False,
        "persistence": "none",
        "registry_admission": False,
        "release_published": False,
        "health_outcome_claimed": False,
        "clinical_effectiveness_claimed": False,
        "runtime_observed": False,
    }


def run_full_suite(
    case: Any,
    *,
    context: EphemeralSessionContext | None = None,
) -> dict[str, Any]:
    """Route an Experience case, execute it, isolate the result, and always clear state."""

    session = context if context is not None else EphemeralSessionContext()
    try:
        if _inert_json_issue(case) is not None:
            return process_full_suite_case(case)
        try:
            session.set("input", case)
        except (TypeError, ValueError):
            return process_full_suite_case(case)
        isolated_case = session.get("input")
        if type(isolated_case) is not dict:
            return process_full_suite_case(isolated_case)
        source_id = isolated_case.get("capability_source_id")
        if type(source_id) is not str:
            return process_full_suite_case(isolated_case)
        jtbd = _SOURCE_TO_JTBD.get(source_id)
        if jtbd is None:
            return _no_route_error()
        route = route_jtbd(jtbd, _AVAILABLE_EXPERIENCES)
        session.set("route", route)
        if route["source_capability_id"] != source_id:
            return _no_route_error()
        result = process_full_suite_case(isolated_case)
        session.set("result", result)
        return session.get("result")
    finally:
        session.clear()
