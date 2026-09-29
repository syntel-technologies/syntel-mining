# syntel-mining

Process mining from published methods, in the Python standard library: the inductive miner, optimal alignments,
DECLARE and OCEL 2.0.

```bash
pip install syntel-mining
```

Python 3.13+. No dependencies. Apache-2.0.

## Why this exists

The established Python library for these methods, pm4py, is licensed AGPL-3.0-or-later, which a proprietary service
cannot take on. This package is a **clean-room implementation** written from the papers each module cites. No code
from pm4py or any other copyleft project was read into, copied into or refactored into it. It is small, typed
(`py.typed`, pyright strict) and has no runtime dependencies, so it adds no licence obligations beyond Apache-2.0.

## Usage

```python
from syntel_mining import Constraint, check, conformance, discover

# A log is its variants and how many cases followed each.
log = {
    ("submit", "check", "approve"): 40,
    ("submit", "approve"): 3,
}

tree = discover(log, noise=0.2)
print(tree)  # →(submit, check, approve): 3 in 43 skipping the check is noise at 0.2
print(discover(log, noise=0))  # →(submit, ×(τ, check), approve): without noise, every trace fits

report = conformance(tree, log)
print(report.fitting_traces, report.skipped)  # 40 {'check': 3}

gate = check(Constraint("precedence", "check", "approve"), ("submit", "approve"))
print(gate.satisfied, gate.violated)  # False (1,): the approval no check preceded
```

Read an OCEL 2.0 log and mine one object type:

```python
from syntel_mining import discover, ocel

log = ocel.load(open("orders.jsonocel", "rb").read())  # every reference checked; OcelError names each problem
tree = discover(ocel.variants(log, "order"))
```

## What is in it

| Module | What it does | Written from |
|---|---|---|
| `tree` | Process trees (→ sequence, × choice, ∧ parallel, ↺ loop, τ silent), normalised on construction; the language of a small tree | Leemans, Fahland, van der Aalst (2013) |
| `inductive` | The inductive miner, infrequent variant (IMf): exclusive-choice, sequence, parallel and loop cuts on the directly-follows graph, IMf filtering and log splitting, and the fall-throughs down to the flower model | Leemans, Fahland, van der Aalst (2013); Leemans (2017) |
| `alignments` | Optimal alignments of a trace against a tree, through its workflow net and a Dijkstra search over the synchronous product bounded by a state budget; log fitness with the inserted and skipped activities | Adriansyah (2014); van der Aalst (2016), ch. 8 |
| `treecost` | The optimal alignment cost on a tree whose operators have disjoint child alphabets (every inductive-miner tree), by composition: parallel sums its children, choice takes the cheapest, sequence and loop split the trace by dynamic programming. Polynomial where a state search explodes on wide parallel blocks | the alignment cost's definition, applied to the tree's structure |
| `declare` | DECLARE templates checked per trace, with the events that fulfil or violate each; responses `within` a time (a promised duration); discovery by support and confidence | Pesic, van der Aalst (2006); Maggi et al. (2012); Di Ciccio, Mecella (2015) |
| `ocel` | OCEL 2.0 JSON: read with every reference checked, written in a canonical order, flattened per object type | Berti et al. (2024), the OCEL 2.0 specification |

## Guarantees, tested

The test suite checks these as properties over random logs and trees ([Hypothesis](https://hypothesis.works)):

- the inductive miner without noise fits every trace it was given;
- every trace a discovered tree allows aligns against it at no cost;
- the compositional cost equals the searched optimum.

The worked examples of the literature, every DECLARE template, and OCEL round trips and refusals are tested as cases.

## Status

0.x: the API may change between minor versions, and each change is listed in [CHANGELOG.md](CHANGELOG.md). Syntel's
Orbis runs on it. Issues and pull requests are welcome; [CONTRIBUTING.md](CONTRIBUTING.md) has the clean-room rule
every contribution follows.

## References

- S. J. J. Leemans, D. Fahland, W. M. P. van der Aalst. *Discovering block-structured process models from event logs
  containing infrequent behaviour.* BPM Workshops 2013.
- S. J. J. Leemans. *Robust process mining with guarantees.* PhD thesis, Eindhoven University of Technology, 2017.
- A. Adriansyah. *Aligning observed and modeled behavior.* PhD thesis, Eindhoven University of Technology, 2014.
- W. M. P. van der Aalst. *Process Mining: Data Science in Action.* Springer, 2016.
- M. Pesic, W. M. P. van der Aalst. *A declarative approach for flexible business processes management.* BPM
  Workshops 2006.
- F. M. Maggi et al. *Efficient discovery of understandable declarative process models from event logs.* CAiSE 2012.
- C. Di Ciccio, M. Mecella. *On the discovery of declarative control flows for artful processes.* ACM TMIS, 2015.
- A. Berti et al. *OCEL (Object-Centric Event Log) 2.0 Specification.* 2024. <https://www.ocel-standard.org>

## Licence

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). Copyright 2026 Syntel Technologies, Inc.
