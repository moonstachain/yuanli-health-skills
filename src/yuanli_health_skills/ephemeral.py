"""Process-local session context with no persistence or output side effects."""

from copy import deepcopy
from typing import Any


class EphemeralSessionContext:
    """Hold isolated candidate state for the lifetime of one Python object."""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._values[key] = deepcopy(value)

    def get(self, key: str, default: Any = None) -> Any:
        return deepcopy(self._values.get(key, default))

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self._values)

    def clear(self) -> None:
        self._values.clear()
