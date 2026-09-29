"""Properties over random logs: the inductive miner without noise fits every trace it was given, and what a tree
allows aligns against it at no cost."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from syntel_mining.alignments import align
from syntel_mining.inductive import discover
from syntel_mining.tree import TAU, Tree, act, language, loop, par, seq, xor
from syntel_mining.treecost import tree_cost

traces = st.lists(st.text(alphabet="abcd", min_size=0, max_size=6).map(tuple), min_size=1, max_size=8)


@settings(max_examples=150, deadline=None)
@given(traces)
def test_the_inductive_miner_without_noise_fits_every_trace(log: list[tuple[str, ...]]) -> None:
    tree = discover(log, noise=0)
    for trace in set(log):
        result = align(tree, trace, max_states=400_000)
        assert result is not None
        assert result.cost == 0, f"{trace} does not fit {tree}"


@settings(max_examples=60, deadline=None)
@given(traces)
def test_what_a_discovered_tree_allows_aligns_at_no_cost(log: list[tuple[str, ...]]) -> None:
    tree = discover(log, noise=0.2)
    allowed = sorted(language(tree, max_repeats=1), key=lambda t: (len(t), t))[:20]
    for trace in allowed:
        result = align(tree, trace, max_states=400_000)
        assert result is not None
        assert result.cost == 0


@st.composite
def trees(draw: st.DrawFn, alphabet: tuple[str, ...] = ("a", "b", "c", "d", "e")) -> Tree:
    """A random tree whose operators split their activities into disjoint parts, as the inductive miner's do."""
    labels = list(draw(st.permutations(alphabet)))[: draw(st.integers(1, len(alphabet)))]

    def build(names: list[str], depth: int) -> Tree:
        if len(names) == 1 or depth > 3:
            leaf = act(names[0]) if len(names) == 1 else xor(*(act(n) for n in names))
            return xor(leaf, TAU) if draw(st.booleans()) and depth > 0 else leaf
        cut = draw(st.integers(1, len(names) - 1))
        left, right = build(names[:cut], depth + 1), build(names[cut:], depth + 1)
        op = draw(st.sampled_from(["seq", "xor", "and", "loop"]))
        return {"seq": seq, "xor": xor, "and": par}.get(op, loop)(left, right)

    return build(labels, 0)


@settings(max_examples=300, deadline=None)
@given(trees(), st.text(alphabet="abcdef", max_size=6).map(tuple))
def test_the_compositional_cost_is_the_searched_optimum(tree: Tree, trace: tuple[str, ...]) -> None:
    searched = align(tree, trace, max_states=400_000)
    assert searched is not None
    assert tree_cost(tree, trace) == searched.cost, f"{tree} on {trace}"
