"""Process-local session context with no persistence or output side effects."""

import math
from typing import Any


def _clone_inert_json(value: Any) -> Any:
    value_type = type(value)
    if value is None or value_type in {bool, int, str}:
        return value
    if value_type is float:
        if not math.isfinite(value):
            raise ValueError("ephemeral values require finite numbers")
        return value
    if value_type is list:
        return [_clone_inert_json(item) for item in value]
    if value_type is dict:
        cloned: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("ephemeral object keys must be strings")
            cloned[key] = _clone_inert_json(item)
        return cloned
    raise TypeError("ephemeral values must use the inert JSON value algebra")


def _require_string_key(key: Any) -> str:
    if type(key) is not str:
        raise TypeError("ephemeral context keys must be strings")
    return key


class EphemeralSessionContext:
    """Hold isolated candidate state for the lifetime of one Python object."""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._values[_require_string_key(key)] = _clone_inert_json(value)

    def get(self, key: str, default: Any = None) -> Any:
        checked_key = _require_string_key(key)
        if checked_key in self._values:
            return _clone_inert_json(self._values[checked_key])
        return _clone_inert_json(default)

    def snapshot(self) -> dict[str, Any]:
        return _clone_inert_json(self._values)

    def clear(self) -> None:
        self._values.clear()
