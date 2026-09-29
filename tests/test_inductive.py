"""The inductive miner on the worked examples of the literature, and its guarantees."""

from __future__ import annotations

from collections import Counter

from syntel_mining.alignments import conformance
from syntel_mining.inductive import discover
from syntel_mining.tree import TAU, act, language, loop, par, seq, xor


def log(*pairs: tuple[str, int]) -> Counter[tuple[str, ...]]:
    return Counter({tuple(t): n for t, n in pairs})


def test_sequence_choice_and_parallel_are_found() -> None:
    # van der Aalst, Process Mining (2016), the running example of the inductive miner.
    tree = discover(log(("abcd", 3), ("acbd", 2), ("aed", 1)), noise=0)
    assert tree == seq(act("a"), xor(par(act("b"), act("c")), act("e")), act("d"))
    assert str(tree) == "→(a, ×(∧(b, c), e), d)"


def test_a_loop_is_found_with_its_redo_part() -> None:
    assert discover(log(("a", 5), ("aba", 3), ("ababa", 1)), noise=0) == loop(act("a"), act("b"))


def test_an_optional_activity_is_a_choice_with_tau() -> None:
    assert discover(log(("abc", 4), ("ac", 2)), noise=0) == seq(act("a"), xor(TAU, act("b")), act("c"))


def test_a_repeated_single_activity_is_a_loop() -> None:
    assert discover(log(("aa", 1), ("a", 1)), noise=0) == loop(act("a"), TAU)


def test_empty_traces_are_kept_without_noise_and_dropped_as_noise() -> None:
    assert discover(log(("", 1), ("ab", 9)), noise=0) == xor(TAU, seq(act("a"), act("b")))
    assert discover(log(("", 1), ("ab", 99)), noise=0.2) == seq(act("a"), act("b"))


def test_infrequent_behaviour_is_filtered_and_the_main_flow_kept() -> None:
    noisy = log(("abcd", 60), ("acbd", 30), ("abd", 1), ("adbc", 1))
    tree = discover(noisy, noise=0.2)
    assert ("a", "b", "c", "d") in language(tree)
    assert ("a", "c", "b", "d") in language(tree)
    assert conformance(tree, noisy).fitness > 0.95


def test_no_structure_falls_back_to_a_model_that_still_fits() -> None:
    chaotic = log(("abc", 1), ("cab", 1), ("bca", 1), ("acb", 1), ("ba", 1), ("c", 1))
    tree = discover(chaotic, noise=0)
    assert conformance(tree, chaotic).fitting_traces == 6
