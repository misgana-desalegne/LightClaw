from __future__ import annotations

from collections import defaultdict
from typing import Any


class Context:
    def __init__(self) -> None:
        self._state: dict[str, Any] = {}
        self._memory: dict[str, list[Any]] = defaultdict(list)

    def set(self, key: str, value: Any) -> None:
        self._state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def remove(self, key: str) -> None:
        self._state.pop(key, None)

    def append_memory(self, bucket: str, value: Any) -> None:
        self._memory[bucket].append(value)

    def get_memory(self, bucket: str) -> list[Any]:
        return list(self._memory.get(bucket, []))

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": dict(self._state),
            "memory": {key: list(values) for key, values in self._memory.items()},
        }

    def clear(self) -> None:
        self._state.clear()
        self._memory.clear()