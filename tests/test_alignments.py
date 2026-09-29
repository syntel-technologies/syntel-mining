"""Optimal alignments: synchronous moves are free, a skipped or an inserted activity costs one."""

from __future__ import annotations

from syntel_mining.alignments import align, conformance
from syntel_mining.tree import act, loop, par, seq, xor

ABC = seq(act("a"), act("b"), act("c"))


def test_a_fitting_trace_costs_nothing() -> None:
    result = align(ABC, ("a", "b", "c"))
    assert result is not None
    assert (result.cost, result.fitness) == (0, 1.0)


def test_a_skipped_activity_is_a_model_move() -> None:
    result = align(ABC, ("a", "c"))
    assert result is not None
    assert result.cost == 1
    assert result.model_moves == ["b"]
    assert result.fitness == 1 - 1 / 5


def test_an_inserted_activity_is_a_log_move() -> None:
    result = align(ABC, ("a", "b", "x", "c"))
    assert result is not None
    assert result.log_moves == ["x"]
    assert result.cost == 1


def test_parallel_and_loops_allow_what_they_should() -> None:
    both = par(act("a"), act("b"))
    assert align(both, ("b", "a")).cost == 0  # type: ignore[union-attr]
    redo = loop(act("a"), act("b"))
    assert align(redo, ("a", "b", "a", "b", "a")).cost == 0  # type: ignore[union-attr]
    assert align(redo, ("a", "b")).cost == 1  # type: ignore[union-attr]


def test_the_empty_trace_against_a_sequence_costs_the_whole_model() -> None:
    result = align(ABC, ())
    assert result is not None
    assert (result.cost, result.fitness) == (3, 0.0)


def test_a_bounded_search_says_it_could_not_align() -> None:
    wide = par(*(act(c) for c in "abcdefgh"))
    assert align(wide, tuple("hgfedcbaxyz"), max_states=50) is None


def test_log_conformance_weights_variants_and_names_the_deviations() -> None:
    model = seq(act("a"), xor(act("b"), act("c")), act("d"))
    result = conformance(model, {("a", "b", "d"): 8, ("a", "d"): 2})
    assert result.fitting_traces == 8
    assert result.traces == 10
    assert result.skipped == {"b": 2} or result.skipped == {"c": 2}
    assert 0.9 < result.fitness < 1.0
