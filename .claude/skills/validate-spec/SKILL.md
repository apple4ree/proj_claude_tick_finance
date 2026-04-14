---
name: validate-spec
description: Validate a spec.yaml loads and uses only registered signal primitives. Fast sanity check before a backtest.
---

# validate-spec

## Usage

```bash
python scripts/validate_spec.py strategies/<strategy_id>/spec.yaml
```

- Exit 0 + prints `ok: <spec_name>` → ready for backtest.
- Exit 1 + error lines on stderr → fix the spec first.

## What it checks

1. YAML parses.
2. `load_spec()` succeeds (all required keys present).
3. Every signal references a primitive in `engine/signals.py::SIGNAL_REGISTRY`.
4. `entry.when` / `exit.when` parse as valid Python expressions.
5. `universe.symbols` and `universe.dates` are non-empty.

## When to use

Call this after `spec-writer` writes a new `spec.yaml`, before handing off to `backtest-runner`. Catches typos and bad primitive names without paying for a full backtest run.
