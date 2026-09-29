"""Properties over random logs: the inductive miner without noise fits every trace it was given, and what a tree
allows aligns against it at no cost."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from syntel_mining.alignments import align
from syntel_mining.inductive import discover
from syntel_mining.tree import language

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
