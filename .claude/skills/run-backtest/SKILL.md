---
name: run-backtest
description: Execute a strategy backtest via engine.runner and return the metrics JSON. Writes report.json under the strategy directory.
---

# run-backtest

## Usage

```bash
python -m engine.runner \
  --spec strategies/<strategy_id>/spec.yaml \
  --out  strategies/<strategy_id>/report.json \
  --summary
```

The `--summary` flag makes the runner print the full report JSON to stdout in addition to writing `report.json`. Parse that stdout directly — do NOT re-read `report.json`.

## Key report fields

| field | meaning |
|---|---|
| `spec_name` | strategy name from spec |
| `return_pct` | total PnL / starting cash × 100 |
| `total_pnl` | realized + unrealized − fees |
| `realized_pnl` | closed position PnL |
| `unrealized_pnl` | mark-to-mid on open positions |
| `total_fees` | commission + tax sum (KRW) |
| `n_trades` | number of fills |
| `per_symbol` | per-symbol breakdown (first/last mid, position, realized, mark-to-mid) |

## Cost optimization

- Do not print `per_symbol` unless necessary — it grows with universe size.
- Surface only `spec_name`, `return_pct`, `n_trades`, `total_pnl`, `total_fees` to callers by default.
- On runner error, capture only the first line of the traceback.
