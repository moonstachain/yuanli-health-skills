"""Read-only access to the committed public Canon projection."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


EXPECTED_SHA256 = "2700652ec1eea62bf98e0a303470162d32310b8859f3379ebeaa00396f951a40"
_SNAPSHOT = Path(__file__).with_name("data") / "health-skill-public-projection-v1.json"


@lru_cache(maxsize=1)
def load_projection() -> dict[str, Any]:
    raw = _SNAPSHOT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED_SHA256:
        raise ValueError("projection snapshot digest mismatch")
    projection = json.loads(raw)
    if projection.get("schema") != "yuanli-health-skill-public-projection-v1":
        raise ValueError("projection snapshot schema mismatch")
    return projection


def allowed_domain_objects() -> tuple[str, ...]:
    return tuple(load_projection()["domain_objects"])


def allowed_health_clocks() -> tuple[str, ...]:
    return tuple(load_projection()["health_clock"])


def allowed_effects(clock: str) -> tuple[str, ...]:
    try:
        return tuple(load_projection()["health_clock"][clock]["allowed_effects"])
    except KeyError as exc:
        raise ValueError(f"unknown health clock: {clock}") from exc


def authority_rules() -> dict[str, Any]:
    rules = load_projection()["authority_semantics"]
    return {
        **rules,
        "never_final_authority": tuple(rules["never_final_authority"]),
    }
