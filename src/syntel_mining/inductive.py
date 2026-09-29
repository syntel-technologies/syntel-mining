"""The inductive miner, infrequent variant (IMf): a process tree from an event log, sound by construction.

Written from the published method (S. J. J. Leemans, D. Fahland, W. M. P. van der Aalst, "Discovering
block-structured process models from event logs containing infrequent behaviour", BPM Workshops 2013, and
Leemans' thesis, 2017). The miner looks at the directly-follows graph of the log and tries, in order, an
exclusive-choice, a sequence, a parallel and a loop cut; it splits the log along the cut and recurses. When no
cut exists it tries again on the graph with its infrequent edges removed (an edge rarer than `noise` times the
most frequent edge leaving the same activity), splitting the log so events that contradict the cut are dropped.
When still no cut exists, a fall-through keeps the model sound and every observed trace possible: an activity
that occurs once per trace or runs concurrently to the rest, a τ-loop, and at last the flower model.

With `noise=0` the discovered tree allows every trace of the log (perfect fitness): the property tests check
it with alignments.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from itertools import pairwise

from syntel_mining.log import Log, Trace, as_log
from syntel_mining.tree import TAU, Tree, act, loop, par, seq, xor

Parts = list[set[str]]


class Dfg:
    """The directly-follows graph: edge, start and end frequencies."""

    def __init__(self, log: Log) -> None:
        self.edges: Counter[tuple[str, str]] = Counter()
        self.starts: Counter[str] = Counter()
        self.ends: Counter[str] = Counter()
        self.activities: Counter[str] = Counter()
        for trace, n in log.items():
            if not trace:
                continue
            self.starts[trace[0]] += n
            self.ends[trace[-1]] += n
            for a in trace:
                self.activities[a] += n
            for a, b in pairwise(trace):
                self.edges[(a, b)] += n

    def filtered(self, noise: float) -> Dfg:
        """IMf's filter: drop an edge rarer than `noise` times the strongest edge leaving its source, and a start
        or end activity rarer than `noise` times the strongest start or end."""
        out = Dfg(Counter())
        out.activities = Counter(self.activities)
        strongest: dict[str, int] = {}
        for (a, _), n in self.edges.items():
            strongest[a] = max(strongest.get(a, 0), n)
        out.edges = Counter({(a, b): n for (a, b), n in self.edges.items() if n >= noise * strongest[a]})
        top_start, top_end = max(self.starts.values(), default=0), max(self.ends.values(), default=0)
        out.starts = Counter({a: n for a, n in self.starts.items() if n >= noise * top_start})
        out.ends = Counter({a: n for a, n in self.ends.items() if n >= noise * top_end})
        return out

    def successors(self, a: str) -> set[str]:
        return {y for (x, y) in self.edges if x == a}


# ── Cuts ──────────────────────────────────────────────────────────────────────────────────────────────


def _components(nodes: Iterable[str], linked: Iterable[tuple[str, str]]) -> list[set[str]]:
    """Connected components of an undirected graph, in first-seen order."""
    parent = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in linked:
        if a in parent and b in parent:
            parent[find(a)] = find(b)
    groups: dict[str, set[str]] = {}
    for n in parent:
        groups.setdefault(find(n), set()).add(n)
    return list(groups.values())


def _reach(dfg: Dfg, nodes: set[str]) -> dict[str, set[str]]:
    """Every node reachable from each node by one or more edges."""
    out: dict[str, set[str]] = {}
    for start in nodes:
        seen: set[str] = set()
        stack = [b for b in dfg.successors(start) if b in nodes]
        while stack:
            x = stack.pop()
            if x not in seen:
                seen.add(x)
                stack.extend(b for b in dfg.successors(x) if b in nodes and b not in seen)
        out[start] = seen
    return out


def xor_cut(dfg: Dfg, nodes: set[str]) -> list[set[str]] | None:
    parts = _components(sorted(nodes), dfg.edges)
    return parts if len(parts) > 1 else None


def seq_cut(dfg: Dfg, nodes: set[str]) -> list[set[str]] | None:
    """Groups such that every activity of an earlier group reaches every activity of a later one and never back.
    Strongly connected components are merged with every component they are incomparable to; what remains must be
    a chain."""
    reach = _reach(dfg, nodes)
    order = sorted(nodes)
    incomparable = [
        (a, b) for i, a in enumerate(order) for b in order[i + 1 :] if (b in reach[a]) == (a in reach[b])
    ]  # mutually reachable (one component) or mutually unreachable (incomparable): one group either way
    groups = _components(order, incomparable)
    if len(groups) < 2:
        return None
    groups.sort(key=lambda g: -len(set[str]().union(*(reach[a] for a in g)) - g))
    for i, earlier in enumerate(groups):
        for later in groups[i + 1 :]:
            for a in earlier:
                if not later <= reach[a] or any(a in reach[b] for b in later):
                    return None
    return groups


def par_cut(dfg: Dfg, nodes: set[str]) -> list[set[str]] | None:
    """Groups whose activities follow each other in both directions across groups, each group holding a start and
    an end activity."""
    order = sorted(nodes)
    apart = [
        (a, b) for i, a in enumerate(order) for b in order[i + 1 :] if not ((a, b) in dfg.edges and (b, a) in dfg.edges)
    ]
    groups = _components(order, apart)
    whole = [g for g in groups if g & set(dfg.starts) and g & set(dfg.ends)]
    partial = [g for g in groups if g not in whole]
    if not whole:
        return None
    for g in partial:  # a group without a start or an end cannot stand alone: it joins the first whole group
        whole[0] |= g
    return whole if len(whole) > 1 else None


def loop_cut(dfg: Dfg, nodes: set[str]) -> list[set[str]] | None:
    """The body (every start and end activity, and whatever cannot be a redo part) and redo parts: entered only
    from end activities and from all of them, left only to start activities and to all of them, and unconnected
    to each other. A part that breaks a condition joins the body, until nothing changes."""
    starts, ends = set(dfg.starts) & nodes, set(dfg.ends) & nodes
    body = starts | ends
    if not body:
        return None
    rest = nodes - body
    redo = _components(sorted(rest), [(a, b) for (a, b) in dfg.edges if a in rest and b in rest])
    changed = True
    while changed:
        changed = False
        for part in list(redo):
            if any(_breaks_loop(dfg, x, body, starts, ends) for x in part):
                body |= part
                redo.remove(part)
                changed = True
    return [body, *redo] if redo else None


def _breaks_loop(dfg: Dfg, x: str, body: set[str], starts: set[str], ends: set[str]) -> bool:
    if any((x, b) in dfg.edges and b not in starts for b in body):
        return True
    if any((b, x) in dfg.edges and b not in ends for b in body):
        return True
    to_starts = {s for s in starts if (x, s) in dfg.edges}
    from_ends = {e for e in ends if (e, x) in dfg.edges}
    return bool((to_starts and to_starts != starts) or (from_ends and from_ends != ends))


# ── Splitting the log ─────────────────────────────────────────────────────────────────────────────────


def split_xor(log: Log, parts: Parts) -> list[Log]:
    out: list[Log] = [Counter() for _ in parts]
    for trace, n in log.items():
        i = max(range(len(parts)), key=lambda k: (sum(a in parts[k] for a in trace), -k))
        out[i][tuple(a for a in trace if a in parts[i])] += n
    return out


def split_seq(log: Log, parts: Parts) -> list[Log]:
    out: list[Log] = [Counter() for _ in parts]
    for trace, n in log.items():
        start = 0
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                end = len(trace)
            else:
                # The cut that drops the fewest events: those of other parts before it, of this part after it.
                costs = [
                    (sum(a not in part for a in trace[start:p]) + sum(a in part for a in trace[p:]), p)
                    for p in range(start, len(trace) + 1)
                ]
                end = min(costs)[1]
            out[i][tuple(a for a in trace[start:end] if a in part)] += n
            start = end
    return out


def split_par(log: Log, parts: Parts) -> list[Log]:
    out: list[Log] = [Counter() for _ in parts]
    for trace, n in log.items():
        for i, part in enumerate(parts):
            out[i][tuple(a for a in trace if a in part)] += n
    return out


def split_loop(log: Log, parts: Parts) -> list[Log]:
    """Each run of body activities goes to the body's log, each run of a redo part to that part's; a trace that
    starts or ends with a redo run, or has two redo runs in a row, gains empty body traces where the body ran
    silently."""
    out: list[Log] = [Counter() for _ in parts]
    where = {a: i for i, part in enumerate(parts) for a in part}
    for trace, n in log.items():
        runs: list[tuple[int, Trace]] = []
        for a in trace:
            i = where.get(a)
            if i is None:
                continue
            if runs and runs[-1][0] == i:
                runs[-1] = (i, (*runs[-1][1], a))
            else:
                runs.append((i, (a,)))
        previous_was_body = False
        for i, run in runs:
            if i == 0:
                out[0][run] += n
                previous_was_body = True
            else:
                if not previous_was_body:
                    out[0][()] += n
                out[i][run] += n
                previous_was_body = False
        if not previous_was_body:
            out[0][()] += n
    return out


# ── The miner ─────────────────────────────────────────────────────────────────────────────────────────

Finder = Callable[[Dfg, set[str]], Parts | None]
Splitter = Callable[[Log, Parts], list[Log]]
_CUTS: tuple[tuple[str, Finder, Splitter], ...] = (
    ("xor", xor_cut, split_xor),
    ("seq", seq_cut, split_seq),
    ("and", par_cut, split_par),
    ("loop", loop_cut, split_loop),
)


def _build(kind: str, children: list[Tree]) -> Tree:
    if kind == "xor":
        return xor(*children)
    if kind == "seq":
        return seq(*children)
    if kind == "and":
        return par(*children)
    body, *redo = children
    return loop(body, xor(*redo))


def _find_cut(dfg: Dfg, nodes: set[str]) -> tuple[str, Parts, Splitter] | None:
    for kind, find, split in _CUTS:
        parts = find(dfg, nodes)
        if parts:
            return kind, parts, split
    return None


def discover(traces: Iterable[Sequence[str]] | Mapping[Trace, int], *, noise: float = 0.2) -> Tree:
    """A process tree for the log. `noise` in [0, 1): 0 is the plain inductive miner (every trace fits); the
    customary 0.2 drops behaviour rarer than a fifth of its strongest alternative."""
    if not 0 <= noise < 1:
        raise ValueError("noise is a fraction in [0, 1)")
    return _mine(as_log(traces), noise, depth=0)


def _mine(log: Log, noise: float, depth: int) -> Tree:
    total = sum(log.values())
    if total == 0 or all(not t for t in log):
        return TAU
    empty = log.get((), 0)
    if empty:
        rest = Counter({t: n for t, n in log.items() if t})
        if noise > 0 and empty / total < noise:
            return _mine(rest, noise, depth + 1)
        return xor(TAU, _mine(rest, noise, depth + 1))
    alphabet = {a for t in log for a in t}
    if len(alphabet) == 1:
        (a,) = alphabet
        return act(a) if all(len(t) == 1 for t in log) else loop(act(a), TAU)
    if depth > 200:
        return _flower(alphabet)
    dfg = Dfg(log)
    found = _find_cut(dfg, alphabet)
    if found is None and noise > 0:
        found = _find_cut(dfg.filtered(noise), alphabet)
    if found is not None:
        kind, parts, split = found
        sublogs = split(log, parts)
        return _build(kind, [_mine(sub, noise, depth + 1) for sub in sublogs])
    return _fall_through(log, alphabet, noise, depth)


def _project(log: Log, keep: Callable[[str], bool]) -> Log:
    out: Log = Counter()
    for t, n in log.items():
        out[tuple(x for x in t if keep(x))] += n
    return out


def _fall_through(log: Log, alphabet: set[str], noise: float, depth: int) -> Tree:
    # An activity that occurs exactly once in every trace runs in parallel with the rest.
    for a in sorted(alphabet):
        if all(t.count(a) == 1 for t in log):
            return par(act(a), _mine(_project(log, lambda x, a=a: x != a), noise, depth + 1))
    # An activity whose removal leaves a log with a cut runs concurrently to it, as often as it occurred.
    for a in sorted(alphabet):
        rest = _project(log, lambda x, a=a: x != a)
        if _find_cut(Dfg(rest), alphabet - {a}) is not None:
            alone = _mine(_project(log, lambda x, a=a: x == a), noise, depth + 1)
            return par(alone, _mine(rest, noise, depth + 1))
    # A τ-loop: the log is several runs of one process back to back, split where an end is followed by a start.
    dfg = Dfg(log)
    split: Log = Counter()
    for t, n in log.items():
        piece: list[str] = []
        for i, a in enumerate(t):
            if piece and a in dfg.starts and t[i - 1] in dfg.ends:
                split[tuple(piece)] += n
                piece = []
            piece.append(a)
        split[tuple(piece)] += n
    if split != log:
        return loop(_mine(split, noise, depth + 1), TAU)
    return _flower(alphabet)


def _flower(alphabet: set[str]) -> Tree:
    """↺(τ, ×(a₁…aₙ)): anything, in any order: sound, and it fits every trace."""
    return loop(TAU, xor(*(act(a) for a in sorted(alphabet))))


__all__ = ["Dfg", "Log", "Trace", "as_log", "discover", "loop_cut", "par_cut", "seq_cut", "xor_cut"]
