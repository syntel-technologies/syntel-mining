"""DECLARE templates on hand-made traces, with the events that fulfil or violate them."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from syntel_mining.declare import Constraint, check, discover


def c(template: str, a: str, b: str | None = None, **kw: object) -> Constraint:
    return Constraint(template, a, b, **kw)  # type: ignore[arg-type]


@pytest.mark.parametrize(("constraint", "trace", "ok", "violated"), [
    (c("existence", "a"), "bc", False, ()),
    (c("absence", "x"), "axbx", False, (1, 3)),
    (c("exactly_one", "a"), "aba", False, (2,)),
    (c("init", "a"), "ba", False, (0,)),
    (c("end", "a"), "ba", True, ()),
    (c("responded_existence", "a", "b"), "ca", False, (1,)),
    (c("response", "a", "b"), "acb", True, ()),
    (c("response", "a", "b"), "abca", False, (3,)),
    (c("precedence", "a", "b"), "ba", False, (0,)),
    (c("precedence", "a", "b"), "cab", True, ()),
    (c("succession", "a", "b"), "bab", False, (0,)),
    (c("alternate_response", "a", "b"), "aab", False, (0,)),
    (c("alternate_precedence", "a", "b"), "abb", False, (2,)),
    (c("chain_response", "a", "b"), "abac", False, (2,)),
    (c("chain_precedence", "a", "b"), "acb", False, (2,)),
    (c("not_succession", "a", "b"), "cba", True, ()),
    (c("not_succession", "a", "b"), "ab", False, (0,)),
    (c("not_co_existence", "a", "b"), "ab", False, (1,)),
    (c("not_chain_succession", "a", "b"), "acb", True, ()),
])  # fmt: skip
def test_each_template(constraint: Constraint, trace: str, ok: bool, violated: tuple[int, ...]) -> None:
    result = check(constraint, tuple(trace))
    assert result.satisfied is ok
    assert result.violated == violated


def test_a_constraint_nobody_activated_is_vacuously_satisfied() -> None:
    result = check(c("response", "a", "b"), ("c", "d"))
    assert result.satisfied
    assert result.vacuous


def test_a_promised_duration_is_a_response_within_a_time() -> None:
    t0 = datetime(2026, 9, 1, 9)
    times = [t0, t0 + timedelta(days=1), t0 + timedelta(days=9)]
    sla = c("response", "submitted", "decided", within=timedelta(days=5))
    assert not check(sla, ("submitted", "reviewed", "decided"), times).satisfied
    assert check(sla, ("submitted", "decided", "archived"), times).satisfied


def test_discovery_keeps_what_the_log_supports() -> None:
    log = {("a", "b", "c"): 8, ("a", "c", "b"): 2}
    found = {str(f.constraint) for f in discover(log)}
    assert "init(a)" in found
    assert "response(a, b)" in found
    assert "precedence(a, c)" in found
    assert "chain_response(a, b)" not in found, "only 80% of traces"
