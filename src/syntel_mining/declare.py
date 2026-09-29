"""DECLARE: a process as constraints, checked per trace with the events that fulfil or violate each.

Written from the published templates and their finite-trace semantics (M. Pesic, W. M. P. van der Aalst,
"A declarative approach for flexible business processes management", 2006; F. M. Maggi et al., "Efficient
discovery of understandable declarative process models from event logs", 2012; C. Di Ciccio, M. Mecella,
MINERful, 2013/2015). A procedure is a set of constraints rather than a flowchart: an SOP step becomes an
ordering, a gate becomes a precedence, a promised duration a response `within` a time. Checking a constraint
answers, per trace, whether it was activated, and which events fulfilled or violated it, so a finding can cite
the events on the other side.

Discovery counts, for each candidate constraint, its support (traces that satisfy it) and confidence (traces
that satisfy it among those that activate it), and keeps what clears both thresholds and was activated often
enough not to be vacuous.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import permutations
from typing import Literal

from syntel_mining.log import as_log

Template = Literal[
    "existence", "absence", "exactly_one", "init", "end",
    "responded_existence", "co_existence", "response", "precedence", "succession",
    "alternate_response", "alternate_precedence", "chain_response", "chain_precedence",
    "not_co_existence", "not_succession", "not_chain_succession",
]  # fmt: skip
UNARY: frozenset[str] = frozenset({"existence", "absence", "exactly_one", "init", "end"})
BINARY: tuple[str, ...] = (
    "responded_existence", "co_existence", "response", "precedence", "succession", "alternate_response",
    "alternate_precedence", "chain_response", "chain_precedence", "not_co_existence", "not_succession",
    "not_chain_succession",
)  # fmt: skip


@dataclass(frozen=True)
class Constraint:
    template: Template
    a: str
    b: str | None = None
    #: For response, chain response and succession: b must follow a within this time (a promised duration).
    within: timedelta | None = None

    def __str__(self) -> str:
        args = self.a if self.b is None else f"{self.a}, {self.b}"
        return f"{self.template}({args}{f', within {self.within}' if self.within else ''})"


@dataclass(frozen=True)
class Check:
    """One constraint against one trace: activations, and the events (indices) that fulfilled or violated it."""

    satisfied: bool
    activations: int
    fulfilled: tuple[int, ...] = ()
    violated: tuple[int, ...] = ()

    @property
    def vacuous(self) -> bool:
        return self.satisfied and self.activations == 0


def _late(times: Sequence[datetime] | None, i: int, j: int, within: timedelta | None) -> bool:
    return within is not None and times is not None and times[j] - times[i] > within


def check(c: Constraint, trace: Sequence[str], times: Sequence[datetime] | None = None) -> Check:
    """Whether the trace satisfies the constraint, with its evidence. `times`, when given, are the events'
    instants (same length as the trace), needed only for a `within`."""
    if times is not None and len(times) != len(trace):
        raise ValueError("times and trace differ in length")
    a, b = c.a, c.b
    at_a = [i for i, x in enumerate(trace) if x == a]
    at_b = [i for i, x in enumerate(trace) if x == b] if b is not None else []
    t = c.template
    if t == "existence":
        return Check(bool(at_a), 1, tuple(at_a[:1]))
    if t == "absence":
        return Check(not at_a, len(at_a), violated=tuple(at_a))
    if t == "exactly_one":
        return Check(len(at_a) == 1, len(at_a), tuple(at_a) if len(at_a) == 1 else (), tuple(at_a[1:]))
    if t == "init":
        ok = bool(trace) and trace[0] == a
        return Check(ok, 1, (0,) if ok else (), () if ok or not trace else (0,))
    if t == "end":
        ok = bool(trace) and trace[-1] == a
        last = len(trace) - 1
        return Check(ok, 1, (last,) if ok else (), () if ok or not trace else (last,))
    if b is None:
        raise ValueError(f"{t} needs two activities")
    if t == "responded_existence":
        return _each(at_a, lambda i: bool(at_b))
    if t == "co_existence":
        if bool(at_a) == bool(at_b):
            return Check(True, len(at_a) + len(at_b), tuple(at_a + at_b))
        return Check(False, len(at_a) + len(at_b), violated=tuple(at_a + at_b))
    if t == "response":
        return _each(at_a, lambda i: any(j > i and not _late(times, i, j, c.within) for j in at_b))
    if t == "precedence":
        return _each(at_b, lambda j: any(i < j for i in at_a))
    if t == "succession":
        forward = check(Constraint("response", a, b, c.within), trace, times)
        backward = check(Constraint("precedence", a, b), trace, times)
        return Check(
            forward.satisfied and backward.satisfied,
            forward.activations + backward.activations,
            tuple(sorted(set(forward.fulfilled) | set(backward.fulfilled))),
            tuple(sorted(set(forward.violated) | set(backward.violated))),
        )
    if t == "alternate_response":
        return _each(at_a, lambda i: _next_of(trace, i, b, stop=a) is not None)
    if t == "alternate_precedence":
        return _each(at_b, lambda j: _previous_of(trace, j, a, stop=b) is not None)
    if t == "chain_response":
        return _each(at_a, lambda i: i + 1 < len(trace) and trace[i + 1] == b and not _late(times, i, i + 1, c.within))
    if t == "chain_precedence":
        return _each(at_b, lambda j: j > 0 and trace[j - 1] == a)
    if t == "not_co_existence":
        if at_a and at_b:
            return Check(False, len(at_a), violated=tuple(at_b))
        return Check(True, len(at_a))
    if t == "not_succession":
        return _each(at_a, lambda i: not any(j > i for j in at_b))
    if t == "not_chain_succession":
        return _each(at_a, lambda i: not (i + 1 < len(trace) and trace[i + 1] == b))
    raise ValueError(f"unknown template {t}")


def _each(activations: list[int], holds: Callable[[int], bool]) -> Check:
    """Every activation must hold; the ones that do fulfil the constraint, the others violate it."""
    ok = [i for i in activations if holds(i)]
    bad = [i for i in activations if i not in ok]
    return Check(not bad, len(activations), tuple(ok), tuple(bad))


def _next_of(trace: Sequence[str], i: int, target: str, *, stop: str) -> int | None:
    for j in range(i + 1, len(trace)):
        if trace[j] == target:
            return j
        if trace[j] == stop:
            return None
    return None


def _previous_of(trace: Sequence[str], j: int, target: str, *, stop: str) -> int | None:
    for i in range(j - 1, -1, -1):
        if trace[i] == target:
            return i
        if trace[i] == stop:
            return None
    return None


@dataclass(frozen=True)
class Found:
    constraint: Constraint
    support: float
    confidence: float
    activated_in: float


def discover(
    log: Mapping[tuple[str, ...], int] | Iterable[Sequence[str]],
    *,
    templates: Iterable[str] = ("existence", "exactly_one", "init", "end", "response", "precedence",
                                "chain_response", "not_succession"),
    min_support: float = 0.95,
    min_confidence: float = 0.95,
    min_activation: float = 0.1,
) -> list[Found]:  # fmt: skip
    """The constraints the log supports, strongest first. Support is over all traces; confidence over the traces
    that activate the constraint; a constraint activated in fewer than `min_activation` of the traces is vacuous
    here and left out."""
    variants = as_log(log)
    total = sum(variants.values())
    if total == 0:
        return []
    alphabet = sorted({x for t in variants for x in t})
    candidates: list[Constraint] = []
    for template in templates:
        if template in UNARY:
            candidates.extend(Constraint(template, a) for a in alphabet)  # type: ignore[arg-type]
        else:
            candidates.extend(Constraint(template, a, b) for a, b in permutations(alphabet, 2))  # type: ignore[arg-type]
    out: list[Found] = []
    for c in candidates:
        satisfied = activated = satisfied_when_activated = 0
        for trace, n in variants.items():
            result = check(c, trace)
            satisfied += n if result.satisfied else 0
            if result.activations:
                activated += n
                satisfied_when_activated += n if result.satisfied else 0
        support = satisfied / total
        confidence = satisfied_when_activated / activated if activated else 0.0
        if support >= min_support and confidence >= min_confidence and activated / total >= min_activation:
            out.append(Found(c, support, confidence, activated / total))
    out.sort(key=lambda f: (-f.support, -f.confidence, str(f.constraint)))
    return out


__all__ = ["BINARY", "UNARY", "Check", "Constraint", "Found", "Template", "check", "discover"]
