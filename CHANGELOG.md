# Changelog

This project follows [Semantic Versioning](https://semver.org). While the version is 0.x, a minor version may
change the API; every change is listed here.

## 0.1.0 — 2026-09-29

The first release.

- `tree`: process trees with sequence, exclusive choice, parallel and loop operators and the silent step, normalised
  on construction, with the language of a small tree.
- `inductive`: the inductive miner, infrequent variant (IMf), with its cuts, filtering, log splitting and
  fall-throughs.
- `alignments`: optimal alignments through the tree's workflow net, with a state budget (`align_within` reports the
  states explored), and log conformance with the inserted and skipped activities.
- `treecost`: the optimal alignment cost of a trace against a tree with disjoint child alphabets, computed by
  composition.
- `declare`: seventeen DECLARE templates with per-event evidence, timed responses, and discovery by support and
  confidence.
- `ocel`: OCEL 2.0 JSON read with every reference checked, written canonically, and flattened per object type.
