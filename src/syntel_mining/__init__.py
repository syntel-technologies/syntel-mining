"""syntel-mining: process mining from published methods, in the standard library.

A clean-room implementation (Apache-2.0) of the algorithms Orbis needs and the permissive ecosystem does not
provide on every platform: the inductive miner (infrequent variant) producing process trees, optimal alignments
of traces against a tree, DECLARE constraint checking with per-constraint evidence and discovery, and OCEL 2.0
JSON import and export. No code from pm4py (AGPL-3.0-or-later) was read into, copied into or refactored into it.
"""

from syntel_mining.alignments import Alignment, Conformance, align, conformance
from syntel_mining.declare import Check, Constraint, check
from syntel_mining.declare import discover as discover_constraints
from syntel_mining.inductive import discover
from syntel_mining.log import Log, as_log
from syntel_mining.tree import TAU, Tree, act, language, loop, par, seq, xor

__version__ = "0.1.0"

__all__ = [
    "TAU",
    "Alignment",
    "Check",
    "Conformance",
    "Constraint",
    "Log",
    "Tree",
    "act",
    "align",
    "as_log",
    "check",
    "conformance",
    "discover",
    "discover_constraints",
    "language",
    "loop",
    "par",
    "seq",
    "xor",
]
