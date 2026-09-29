"""Optimal alignment cost on a process tree whose operators have disjoint child alphabets, in polynomial time.

The inductive miner cuts the activities of a log into disjoint parts at every operator, so in the trees it
discovers no activity appears under two children of one operator. For such a tree the optimal alignment cost
(log and visible model moves cost 1, synchronous and silent moves 0; the same cost `alignments` searches for)
composes over the tree, written here from the definitions:

- an activity `a` against a word costs its length minus one when the word holds `a` (one synchronous move, the
  rest log moves), and its length plus one when it does not (every event a log move, `a` a model move);
- τ costs the word's length;
- a choice costs its cheapest child on the word's events of that child's alphabet, plus the other events;
- a parallel block costs each child on its own events (their orders are independent), plus the events of none;
- a sequence splits the word into consecutive segments, one per child, by dynamic programming over split points;
- a loop splits it into do, redo, do, ..., do segments, each redo-and-do round consuming at least one event
  (an empty round never lowers the cost).

A state-space search over a wide parallel block explores every interleaving of its silent moves and can need
millions of states for one trace; this needs a few thousand small subproblems. `tree_cost` answers None when a
tree breaks the disjointness it relies on, and the caller uses the search instead.
"""

from __future__ import annotations

from collections.abc import Sequence

from syntel_mining.tree import Tree

Word = tuple[str, ...]


def disjoint(tree: Tree) -> bool:
    """Whether no activity appears under two children of any operator (true of every inductive-miner tree)."""
    for node in tree.nodes():
        seen: set[str] = set()
        for child in node.children:
            labels = child.activities()
            if seen & labels:
                return False
            seen |= labels
    return True


class _Coster:
    def __init__(self, tree: Tree) -> None:
        self.alphabet = {id(n): n.activities() for n in tree.nodes()}
        #: (node, word) → cost, keyed by the node's identity: a frozen tree hashes its whole subtree on every lookup.
        self.memo: dict[tuple[int, Word], int] = {}

    def restricted(self, node: Tree, word: Word) -> int:
        """The node aligned to the word's events of its alphabet; every other event is a log move."""
        mine = tuple(a for a in word if a in self.alphabet[id(node)])
        return self.cost(node, mine) + len(word) - len(mine)

    def cost(self, node: Tree, word: Word) -> int:
        key = (id(node), word)
        found = self.memo.get(key)
        if found is None:
            found = self.memo[key] = self._cost(node, word)
        return found

    def _cost(self, node: Tree, word: Word) -> int:
        if node.op == "tau":
            return len(word)
        if node.op == "act":
            return len(word) - 1 if node.label in word else len(word) + 1
        if node.op == "xor":
            return min(self.restricted(c, word) for c in node.children)
        if node.op == "and":
            inside = set[str]().union(*(self.alphabet[id(c)] for c in node.children))
            own = sum(self.cost(c, tuple(a for a in word if a in self.alphabet[id(c)])) for c in node.children)
            return own + sum(a not in inside for a in word)
        if node.op == "seq":
            return self._seq(node.children, word)
        return self._loop(node.children[0], node.children[1], word)

    def _seq(self, children: Sequence[Tree], word: Word) -> int:
        n = len(word)
        # best[p]: the cheapest alignment of word[p:] with the children from the current one on, built backwards.
        best = [self.restricted(children[-1], word[p:]) for p in range(n + 1)]
        for child in reversed(children[:-1]):
            best = [min(self.restricted(child, word[p:q]) + best[q] for q in range(p, n + 1)) for p in range(n + 1)]
        return best[0]

    def _loop(self, body: Tree, redo: Tree, word: Word) -> int:
        n = len(word)
        # rest[p]: the cheapest alignment of word[p:] as body (redo body)*, built backwards. A redo-and-body round
        # must consume an event (r > p): a round that consumes none only adds a cost that is never negative.
        rest = [0] * (n + 1)
        for p in range(n, -1, -1):
            best = self.restricted(body, word[p:])
            for q in range(p, n + 1):
                head = self.restricted(body, word[p:q])
                if head >= best:
                    continue
                for r in range(max(q, p + 1), n + 1):
                    best = min(best, head + self.restricted(redo, word[q:r]) + rest[r])
            rest[p] = best
        return rest[0]


class TreeCost:
    """Costs many traces against one tree, sharing the subproblems they have in common (the variants of a log
    repeat most of their segments). `usable` is False when the tree's children share an activity."""

    def __init__(self, tree: Tree, *, max_length: int = 60) -> None:
        self.tree, self.max_length = tree, max_length
        self.usable = disjoint(tree)
        self._coster = _Coster(tree) if self.usable else None
        self.shortest = self._coster.cost(tree, ()) if self._coster is not None else None

    def __call__(self, trace: Sequence[str]) -> int | None:
        """The optimal alignment cost, or None when the tree is not usable or the trace is too long."""
        if self._coster is None or len(trace) > self.max_length:
            return None
        if len(self._coster.memo) > 2_000_000:  # bound the shared memo on a very varied log
            self._coster.memo.clear()
        return self._coster.cost(self.tree, tuple(trace))


def tree_cost(tree: Tree, trace: Sequence[str], *, max_length: int = 60) -> int | None:
    """The optimal alignment cost of the trace against the tree, or None when the tree's children share an
    activity or the trace is longer than `max_length` (a loop's split points grow as the cube of its length)."""
    return TreeCost(tree, max_length=max_length)(trace)


__all__ = ["TreeCost", "disjoint", "tree_cost"]
