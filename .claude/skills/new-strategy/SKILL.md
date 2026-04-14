---
name: new-strategy
description: Create a new strategy directory and return its strategy_id. Optionally copies a template spec.yaml.
---

# new-strategy

Create a fresh strategy directory under `strategies/` and return its ID.

## Usage

From the project root:

```bash
python scripts/new_strategy.py --name <short_slug>
# or copy from an example template:
python scripts/new_strategy.py --name <short_slug> --from strategies/_examples/obi_momentum.yaml
```

Prints the new `strategy_id` (format: `strat_YYYYMMDD_NNNN_<slug>`) on stdout.

## Notes

- `<short_slug>` should be 1–4 lowercase words describing the idea (e.g. `obi_momentum`, `microprice_reversion`).
- Without `--from`, a minimal stub spec.yaml is written — fill it in via the `spec-writer` agent.
- Creation is idempotent per-day: the counter auto-increments inside `YYYYMMDD`.
