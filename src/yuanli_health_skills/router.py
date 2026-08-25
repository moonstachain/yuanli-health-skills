"""Experience-only routing for the public Health Skills source suite."""

from typing import Any


_FIRST_SESSION = "yuanli.health.experience.first-health-session"


def route_jtbd(jtbd: Any, available_source_ids: Any) -> dict[str, Any]:
    """Return a deterministic route without making a health-priority decision."""

    reason_code = "UNSUPPORTED_JTBD"
    selected = None
    if not isinstance(jtbd, str) or not jtbd:
        reason_code = "INVALID_JTBD"
    elif not isinstance(available_source_ids, list) or any(
        not isinstance(source_id, str) for source_id in available_source_ids
    ):
        reason_code = "INVALID_AVAILABLE_SOURCE_IDS"
    elif jtbd == "first_health_session" and _FIRST_SESSION in available_source_ids:
        reason_code = "ROUTE_SELECTED"
        selected = _FIRST_SESSION
    elif jtbd == "first_health_session":
        reason_code = "EXPERIENCE_UNAVAILABLE"
    return {
        "schema": "health-jtbd-route-v1",
        "jtbd": jtbd if isinstance(jtbd, str) else None,
        "route_state": "selected" if selected else "no_route",
        "source_capability_id": selected,
        "reason_code": reason_code,
        "health_priority_decided": False,
    }
