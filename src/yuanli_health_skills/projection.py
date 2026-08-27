"""Read-only access to the committed public Canon projection."""

import hashlib
import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any


EXPECTED_SHA256 = "2700652ec1eea62bf98e0a303470162d32310b8859f3379ebeaa00396f951a40"
_SNAPSHOT = Path(__file__).with_name("data") / "health-skill-public-projection-v1.json"


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@lru_cache(maxsize=1)
def _private_projection() -> Mapping[str, Any]:
    raw = _SNAPSHOT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED_SHA256:
        raise ValueError("projection snapshot digest mismatch")
    projection = json.loads(raw)
    if projection.get("schema") != "yuanli-health-skill-public-projection-v1":
        raise ValueError("projection snapshot schema mismatch")
    return _freeze(projection)


def load_projection() -> dict[str, Any]:
    """Return a fresh mutable copy without exposing the private frozen cache."""

    return _thaw(_private_projection())


def allowed_domain_objects() -> tuple[str, ...]:
    return tuple(_private_projection()["domain_objects"])


def allowed_health_clocks() -> tuple[str, ...]:
    return tuple(_private_projection()["health_clock"])


def allowed_effects(clock: str) -> tuple[str, ...]:
    try:
        return tuple(_private_projection()["health_clock"][clock]["allowed_effects"])
    except KeyError as exc:
        raise ValueError(f"unknown health clock: {clock}") from exc


def authority_rules() -> dict[str, Any]:
    rules = _thaw(_private_projection()["authority_semantics"])
    rules["never_final_authority"] = ("ai", "device", "automation", "router")
    return rules
