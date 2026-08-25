"""Host-neutral, zero-persistence runner for the First Health Session."""

from typing import Any

from .ephemeral import EphemeralSessionContext
from .gold_slice import process_first_health_session
from .router import route_jtbd


_AVAILABLE_EXPERIENCES = ["yuanli.health.experience.first-health-session"]


def _error(code: str, path: str = "$") -> dict[str, Any]:
    return {
        "schema": "gold-slice-error-v1",
        "ok": False,
        "errors": [{"code": code, "path": path}],
    }


def run_first_health_session(
    case: Any, *, context: EphemeralSessionContext | None = None
) -> dict[str, Any]:
    """Run route -> CTX -> EVD -> DEC and clear session state in all paths."""

    session = context if context is not None else EphemeralSessionContext()
    try:
        try:
            session.set("input", case)
        except (TypeError, ValueError):
            return _error("INVALID_INERT_JSON")
        isolated_case = session.get("input")
        if not isinstance(isolated_case, dict):
            return _error("INVALID_CASE")
        route = route_jtbd(isolated_case.get("jtbd"), _AVAILABLE_EXPERIENCES)
        session.set("route", route)
        if route["route_state"] != "selected":
            malformed = process_first_health_session(isolated_case)
            if malformed.get("schema") == "gold-slice-error-v1":
                return malformed
            return _error("NO_ROUTE", "jtbd")
        result = process_first_health_session(isolated_case)
        session.set("result", result)
        return session.get("result")
    finally:
        session.clear()
