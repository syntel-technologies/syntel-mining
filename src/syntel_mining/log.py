"""A log as the miners read it: each distinct trace (variant) with how many cases followed it."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import cast

Trace = tuple[str, ...]
Log = Counter[Trace]


def as_log(traces: Iterable[Sequence[str]] | Mapping[Trace, int]) -> Log:
    """Variants and their counts, from traces or from an existing variant count."""
    if isinstance(traces, Mapping):
        counted = cast("Mapping[Trace, int]", traces)
        return Counter({tuple(k): int(v) for k, v in counted.items() if v > 0})
    return Counter(tuple(t) for t in traces)


__all__ = ["Log", "Trace", "as_log"]
