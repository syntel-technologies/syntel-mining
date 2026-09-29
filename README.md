# syntel-mining

Process mining from published methods, in the Python standard library. Apache-2.0, clean-room: no code from
pm4py (AGPL-3.0-or-later) was read into, copied into or refactored into this package; each module names the
paper it was written from.

| Module | What it does | Written from |
|---|---|---|
| `tree` | Process trees (→ sequence, × choice, ∧ parallel, ↺ loop, τ silent), normalised on construction; the language of a small tree | Leemans, Fahland, van der Aalst 2013 |
| `inductive` | The inductive miner, infrequent variant (IMf): cuts on the directly-follows graph, IMf filtering and log splitting, the fall-throughs down to the flower model. With `noise=0` every trace of the log fits | Leemans, Fahland, van der Aalst, BPM Workshops 2013; Leemans, thesis 2017 |
| `alignments` | Optimal alignments of a trace against a tree, through its workflow net and a bounded Dijkstra over the synchronous product; log fitness with the inserted and skipped activities | Adriansyah, thesis 2014; van der Aalst 2016 ch. 8 |
| `treecost` | The optimal alignment cost on a tree whose operators have disjoint child alphabets (every inductive-miner tree), by composition: parallel sums its children, choice takes the cheapest, sequence and loop split the trace by dynamic programming. Equal to the searched optimum (a Hypothesis property), and polynomial where a state search explodes on wide parallel blocks | the definitions above; the dynamic-programming idea of alignments on process trees |
| `declare` | DECLARE templates checked per trace with the events that fulfil or violate each, responses `within` a time (a promised duration), and discovery by support and confidence | Pesic, van der Aalst 2006; Maggi et al. 2012; Di Ciccio, Mecella (MINERful) |
| `ocel` | OCEL 2.0 JSON: read with every reference checked, written in a canonical order, flattened per object type | Berti et al., OCEL 2.0 specification, 2024 |

```python
from syntel_mining import discover, conformance, check, Constraint

log = {("submit", "check", "approve"): 40, ("submit", "approve"): 3}
tree = discover(log, noise=0.2)          # →(submit, check, approve): 3 in 43 skipping the check is noise at 0.2
report = conformance(tree, log)          # fitness, fitting traces, inserted and skipped activities
gate = check(Constraint("precedence", "check", "approve"), ("submit", "approve"))
gate.violated                            # (1,): the approval that no check preceded
```

The guarantees are tested as properties over random logs (Hypothesis): the miner without noise fits every trace it
was given, every trace a discovered tree allows aligns against it at no cost, and the compositional cost equals the
searched optimum on random disjoint-alphabet trees.

Development runs on the Syntel workbench, never on a laptop: `uv sync && uv run pytest && uv run ruff check src tests
&& uv run pyright`.
