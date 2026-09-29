"""Optimal alignments of a trace against a process tree: the deviations a process owner can argue with.

Written from the published method (A. Adriansyah, "Aligning observed and modeled behavior", PhD thesis, TU
Eindhoven, 2014; W. M. P. van der Aalst, "Process Mining: Data Science in Action", 2016, ch. 8). The tree is
translated to its workflow net (a safe, sound net, one block per operator) and a shortest path is searched
through the synchronous product of the trace and the net: a synchronous move (the trace and the model agree)
costs 0, a silent model step costs 0, a log move (the trace did something the model does not allow here) and a
visible model move (the model needed something the trace skipped) cost 1 each. Dijkstra over the product finds
an optimal alignment; the search is bounded by `max_states` so a pathological trace ends with `None` rather
than exhausting memory, and the caller reports it as not aligned.

Fitness is 1 − cost / (length of the trace + cost of the model's shortest run), the usual normalisation.
"""

from __future__ import annotations

import heapq
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import count

from syntel_mining.log import as_log
from syntel_mining.tree import Tree

Marking = frozenset[int]


@dataclass(frozen=True)
class Transition:
    label: str | None  # None is silent
    consumes: frozenset[int]
    produces: frozenset[int]


@dataclass
class Net:
    """The workflow net of a tree: places are integers, one initial and one final place."""

    transitions: list[Transition] = field(default_factory=list[Transition])
    places: int = 0
    initial: Marking = frozenset()
    final: Marking = frozenset()
    #: The cost of the model's shortest run (the empty trace's alignment), computed once per net.
    shortest: int | None = None

    def place(self) -> int:
        self.places += 1
        return self.places - 1

    def add(self, label: str | None, consumes: Iterable[int], produces: Iterable[int]) -> None:
        self.transitions.append(Transition(label, frozenset(consumes), frozenset(produces)))


def to_net(tree: Tree) -> Net:
    net = Net()
    source, sink = net.place(), net.place()
    _block(net, tree, source, sink)
    net.initial, net.final = frozenset({source}), frozenset({sink})
    return net


def _block(net: Net, tree: Tree, src: int, dst: int) -> None:
    if tree.op in ("act", "tau"):
        net.add(tree.label if tree.op == "act" else None, {src}, {dst})
    elif tree.op == "seq":
        here = src
        for i, child in enumerate(tree.children):
            there = dst if i == len(tree.children) - 1 else net.place()
            _block(net, child, here, there)
            here = there
    elif tree.op == "xor":
        for child in tree.children:
            # Each branch gets its own entry and exit so a branch that loops cannot leak into another.
            enter, leave = net.place(), net.place()
            net.add(None, {src}, {enter})
            _block(net, child, enter, leave)
            net.add(None, {leave}, {dst})
    elif tree.op == "and":
        ins = [net.place() for _ in tree.children]
        outs = [net.place() for _ in tree.children]
        net.add(None, {src}, ins)
        for child, a, b in zip(tree.children, ins, outs, strict=True):
            _block(net, child, a, b)
        net.add(None, outs, {dst})
    else:  # loop: enter, body, then either leave or redo and run the body again
        start, middle = net.place(), net.place()
        body, redo = tree.children
        net.add(None, {src}, {start})
        _block(net, body, start, middle)
        _block(net, redo, middle, start)
        net.add(None, {middle}, {dst})


@dataclass(frozen=True)
class Alignment:
    """The moves, each `(trace activity or None, model activity or None)`; a silent step is not listed."""

    cost: int
    moves: tuple[tuple[str | None, str | None], ...]
    fitness: float

    @property
    def log_moves(self) -> list[str]:
        """Activities the trace did where the model does not allow them (inserted)."""
        return [log for log, model in self.moves if log is not None and model is None]

    @property
    def model_moves(self) -> list[str]:
        """Activities the model needed that the trace skipped (skipped)."""
        return [model for log, model in self.moves if log is None and model is not None]


def _fire(marking: Marking, t: Transition) -> Marking | None:
    if not t.consumes <= marking:
        return None
    return (marking - t.consumes) | t.produces


Moves = tuple[tuple[str | None, str | None], ...]


def _search(net: Net, trace: Sequence[str], max_states: int) -> tuple[tuple[int, Moves] | None, int]:
    """The cheapest path to the final marking with the whole trace consumed, and how many states it took."""
    tie = count()
    start = (net.initial, 0)
    frontier: list[tuple[int, int, int, Marking, int, tuple[tuple[str | None, str | None], ...]]] = [
        (0, 0, next(tie), net.initial, 0, ())
    ]
    best: dict[tuple[Marking, int], int] = {start: 0}
    explored = 0
    while frontier:
        cost, _, _, marking, i, moves = heapq.heappop(frontier)
        if best.get((marking, i), cost) < cost:
            continue
        if marking == net.final and i == len(trace):
            return (cost, moves), explored
        explored += 1
        if explored > max_states:
            return None, explored

        def push(
            new_cost: int,
            new_marking: Marking,
            new_i: int,
            move: tuple[str | None, str | None] | None,
            moves: tuple[tuple[str | None, str | None], ...] = moves,
        ) -> None:
            key = (new_marking, new_i)
            if new_cost < best.get(key, new_cost + 1):
                best[key] = new_cost
                heapq.heappush(
                    frontier,
                    (new_cost, -new_i, next(tie), new_marking, new_i, moves if move is None else (*moves, move)),
                )

        if i < len(trace):
            push(cost + 1, marking, i + 1, (trace[i], None))
        for t in net.transitions:
            after = _fire(marking, t)
            if after is None:
                continue
            if t.label is None:
                push(cost, after, i, None)
            else:
                if i < len(trace) and trace[i] == t.label:
                    push(cost, after, i + 1, (t.label, t.label))
                push(cost + 1, after, i, (None, t.label))
    return None, explored


def align_within(tree: Tree | Net, trace: Sequence[str], *, max_states: int = 200_000) -> tuple[Alignment | None, int]:
    """An optimal alignment, or None past `max_states`, with the states the search explored: a caller aligning
    many traces spends one budget across them and stops when it is gone, the same way on every machine."""
    net = tree if isinstance(tree, Net) else to_net(tree)
    found, explored = _search(net, trace, max_states)
    if found is None:
        return None, explored
    if net.shortest is None:
        empty, _ = _search(net, (), max_states)
        net.shortest = empty[0] if empty is not None else 0
    cost, moves = found
    worst = len(trace) + net.shortest
    return Alignment(cost=cost, moves=moves, fitness=1.0 if worst == 0 else 1 - cost / worst), explored


def align(tree: Tree | Net, trace: Sequence[str], *, max_states: int = 200_000) -> Alignment | None:
    """An optimal alignment of the trace against the model, or None when the search passed `max_states`."""
    return align_within(tree, trace, max_states=max_states)[0]


@dataclass(frozen=True)
class Conformance:
    fitness: float
    fitting_traces: int
    traces: int
    unaligned: int
    #: Per activity: how many times the trace did it where the model does not allow it, and how often skipped.
    inserted: Mapping[str, int]
    skipped: Mapping[str, int]


def conformance(tree: Tree, log: Mapping[tuple[str, ...], int] | Iterable[Sequence[str]], *,
                max_states: int = 200_000) -> Conformance:  # fmt: skip
    """Log fitness weighted by variant counts, with where the log and the model part."""
    variants = as_log(log)
    net = to_net(tree)
    total = sum(variants.values())
    weighted, fitting, unaligned = 0.0, 0, 0
    inserted: Counter[str] = Counter()
    skipped: Counter[str] = Counter()
    for trace, n in variants.items():
        result = align(net, trace, max_states=max_states)
        if result is None:
            unaligned += n
            continue
        weighted += result.fitness * n
        fitting += n if result.cost == 0 else 0
        for a in result.log_moves:
            inserted[a] += n
        for a in result.model_moves:
            skipped[a] += n
    aligned = total - unaligned
    return Conformance(
        fitness=weighted / aligned if aligned else 0.0,
        fitting_traces=fitting,
        traces=total,
        unaligned=unaligned,
        inserted=dict(inserted),
        skipped=dict(skipped),
    )


__all__ = ["Alignment", "Conformance", "Net", "align", "align_within", "conformance", "to_net"]
