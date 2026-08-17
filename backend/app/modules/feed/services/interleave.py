from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TypeVar

_T = TypeVar("_T")

TRENDING_PATTERN: tuple[str, ...] = (
    "spot",
    "cafe",
    "spot",
    "food",
    "spot",
    "cafe",
    "festa",
    "spot",
    "cafe",
    "food",
)

NEARBY_PATTERN: tuple[str, ...] = (
    "spot",
    "cafe",
    "spot",
    "food",
    "spot",
    "cafe",
    "spot",
    "food",
    "cafe",
    "spot",
)


def interleave(
    pools: Mapping[str, Sequence[_T]],
    pattern: Sequence[str],
    *,
    limit: int,
    key_of: Callable[[_T], object] = id,
) -> list[_T]:
    queues = {name: list(items) for name, items in pools.items()}
    seen: set[object] = set()
    out: list[_T] = []

    def take(name: str) -> _T | None:
        queue = queues.get(name)
        while queue:
            item = queue.pop(0)
            key = key_of(item)
            if key in seen:
                continue
            seen.add(key)
            return item
        return None

    for slot in pattern:
        if len(out) >= limit:
            return out
        item = take(slot)
        if item is None:
            for fallback in pattern:
                item = take(fallback)
                if item is not None:
                    break
        if item is not None:
            out.append(item)

    remaining = True
    while len(out) < limit and remaining:
        remaining = False
        for slot in pattern:
            if len(out) >= limit:
                break
            item = take(slot)
            if item is not None:
                out.append(item)
                remaining = True
    return out
