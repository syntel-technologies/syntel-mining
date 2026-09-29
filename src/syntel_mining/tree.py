"""Process trees: block-structured models that are sound by construction.

A tree is an activity, the silent step τ, or an operator over children: sequence (→), exclusive choice (×),
parallel (∧) and loop (↺). A loop has exactly two children, the body and the redo part: the body runs, then
any number of times the redo part followed by the body again. Trees are immutable and normalised on
construction (a sequence inside a sequence is flattened, an operator with one child is that child), so two
trees with the same structure compare equal and print the same.

The notation follows the process-mining literature (Leemans, Fahland and van der Aalst, 2013).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product
from typing import Literal

Op = Literal["act", "tau", "seq", "xor", "and", "loop"]
SYMBOL: dict[str, str] = {"seq": "→", "xor": "×", "and": "∧", "loop": "↺"}


@dataclass(frozen=True)
class Tree:
    op: Op
    label: str | None = None
    children: tuple[Tree, ...] = ()

    def __str__(self) -> str:
        if self.op == "act":
            return str(self.label)
        if self.op == "tau":
            return "τ"
        return f"{SYMBOL[self.op]}({', '.join(str(c) for c in self.children)})"

    def activities(self) -> frozenset[str]:
        """Every visible activity the tree can execute."""
        if self.op == "act":
            return frozenset({str(self.label)})
        return frozenset[str]().union(*(c.activities() for c in self.children))

    def nodes(self) -> Iterator[Tree]:
        yield self
        for child in self.children:
            yield from child.nodes()


TAU = Tree("tau")


def act(label: str) -> Tree:
    return Tree("act", label)


def _op(op: Op, children: tuple[Tree, ...]) -> Tree:
    flat: list[Tree] = []
    for child in children:
        flat.extend(child.children if child.op == op and op != "loop" else (child,))
    if op == "xor":
        # τ once is enough in a choice, and the same branch twice is the same choice.
        seen: list[Tree] = []
        for child in flat:
            if child not in seen:
                seen.append(child)
        flat = seen
    if op in ("seq", "and"):
        flat = [c for c in flat if c.op != "tau"] or [TAU]
    return flat[0] if len(flat) == 1 else Tree(op, children=tuple(flat))


def seq(*children: Tree) -> Tree:
    return _op("seq", children)


def xor(*children: Tree) -> Tree:
    return _op("xor", children)


def par(*children: Tree) -> Tree:
    return _op("and", children)


def loop(body: Tree, redo: Tree) -> Tree:
    """↺(body, redo): body, then zero or more times redo followed by body."""
    return Tree("loop", children=(body, redo))


def _interleavings(parts: tuple[tuple[str, ...], ...]) -> set[tuple[str, ...]]:
    if not parts:
        return {()}
    live = [p for p in parts if p]
    if not live:
        return {()}
    out: set[tuple[str, ...]] = set()
    for i, part in enumerate(live):
        rest = (*live[:i], part[1:], *live[i + 1 :])
        out.update((part[0], *tail) for tail in _interleavings(rest))
    return out


def language(tree: Tree, *, max_repeats: int = 1) -> set[tuple[str, ...]]:
    """The traces the tree allows, with each loop's redo taken at most `max_repeats` times (for tests and small
    models: parallel blocks grow as their interleavings)."""
    if tree.op == "act":
        return {(str(tree.label),)}
    if tree.op == "tau":
        return {()}
    langs = [language(c, max_repeats=max_repeats) for c in tree.children]
    if tree.op == "xor":
        return set[tuple[str, ...]]().union(*langs)
    if tree.op == "seq":
        return {tuple(x for part in combo for x in part) for combo in product(*langs)}
    if tree.op == "and":
        out: set[tuple[str, ...]] = set()
        for combo in product(*langs):
            out |= _interleavings(tuple(combo))
        return out
    body, redo = langs
    out = set(body)
    frontier = set(body)
    for _ in range(max_repeats):
        frontier = {b + r + b2 for b in frontier for r in redo for b2 in body}
        out |= frontier
    return out


__all__ = ["TAU", "Tree", "act", "language", "loop", "par", "seq", "xor"]
