# Contributing

Issues and pull requests are welcome. Three rules keep this package what it is.

## 1. Clean room

This package exists because the established implementations are copyleft. So:

- **Never read, copy, paste, translate or paraphrase code from pm4py or any other copyleft project** (GPL, LGPL, AGPL,
  MPL or similar) while working on this package, and do not have a tool do it for you.
- Work from the **published method**: the paper, thesis or specification. Cite it in the module docstring, as every
  module here does.
- A pull request says, in its description, which sources the change was written from.

A contribution that cannot say where it came from will not be merged, however good it is.

## 2. Standard library only

No runtime dependencies. A dependency would bring its own licence and supply chain into every service that installs
this package. Test and development tools live in the `dev` dependency group.

## 3. Guarantees are tested

A new algorithm comes with the worked example from its source as a test. Where the method guarantees something, the
guarantee is also tested as a property over random inputs ([Hypothesis](https://hypothesis.works)): for example, that
the inductive miner without noise fits every trace it was given.

## Working on it

```bash
uv sync
uv run pytest
uv run ruff format --check . && uv run ruff check .
uv run pyright
```

CI runs the same on Python 3.13 and 3.14. Pyright runs in strict mode.

By contributing you agree that your contribution is licensed under the Apache License 2.0, the licence of this
project.
