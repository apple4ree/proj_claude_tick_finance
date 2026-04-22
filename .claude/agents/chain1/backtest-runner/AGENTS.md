---
name: backtest-runner
version: 0.1.0
last_updated: 2026-04-20
owner_chain: chain1
stage: "3_backtest"
input_schema: "input_schema.py:BacktestInput"
output_schema: "output_schema.py:BacktestOutput"
required_components:
  - system_prompt
  - user_prompt
  - reference
  - input_schema
  - output_schema
  - reasoning_flow
---

# backtest-runner

## 1. System Prompt

You are the **backtest-runner** for Chain 1. You are fully deterministic — no LLM reasoning. Your job is to execute a generated `signal()` function against KRX data under the execution=1 rule and compute per-tick WR / expectancy.

Absolute constraints:

- **Execution=1 rule** — the only permissible trade logic:
  1. For each tick t in universe's (symbol, date) pairs, compute `s = signal(snap_t)`.
  2. If `s > THRESHOLD`: predict UP; if `s < -THRESHOLD`: predict DOWN; else no trade.
  3. Exit at `t + HORIZON_TICKS`.
  4. Win if predicted direction matches sign of `mid_{t+H} - mid_t`; loss otherwise; zero-change ticks count as "zero" (not included in WR denom).
- **No LLM calls**: this agent is pure Python.
- **Determinism**: same (spec, universe) pair must always produce byte-identical `BacktestResult`.
- **No fee / no spread in Chain 1**: we measure signal accuracy only. Chain 2 will re-backtest with realistic execution costs.

## 2. User Prompt (template)

_Not applicable — this agent is invoked programmatically, not via LLM prompt._

The orchestrator calls `run_backtest(spec, code_path, universe)` directly.

## 3. Reference

- `../_shared/references/cheat_sheets/krx_data_columns.md` — valid data-access patterns
- `adapters/krx_to_hftbacktest.py` (project root) — data loading path (reused for consistency)
- `engine/data_loader.py` — OrderBookSnapshot format

## 4. Input Schema

`input_schema.py:BacktestInput` — SignalSpec + GeneratedCode path + universe (symbols × dates).

## 5. Output Schema

`output_schema.py:BacktestOutput` — wraps `BacktestResult` from `_shared/schemas.py`, with per-symbol-date breakdowns + aggregate.

## 6. Reasoning Flow

Purely procedural:

1. **Load generated code** — import `signal()` from `code.code_path`.
2. **Iterate universe pairs** — for each (symbol, date) in `universe`:
   a. Load CSV via `engine.data_loader.load_csv(path)`.
   b. Filter regular session + valid top-of-book (per cheat-sheet).
   c. Build snapshots iterator (yields OrderBookSnapshot).
   d. Initialize rolling state if signal needs prev-tick primitives.
3. **Per-tick loop**:
   a. `s = signal(snap_t)`
   b. If `|s| <= THRESHOLD`: record as no-trade, continue.
   c. Predict direction: `+1` if `s > THRESHOLD` XOR `direction == long_if_neg`; `-1` otherwise.
   d. Look ahead `HORIZON_TICKS` to get `mid_{t+H}`; if out-of-range (near session end), skip.
   e. Compute actual move: `delta_mid_bps = (mid_{t+H} - mid_t) / mid_t * 1e4`.
   f. Classify: win if `sign(predicted) == sign(delta_mid_bps) AND delta_mid_bps != 0`; loss if signs differ; zero if `delta_mid_bps == 0`.
4. **Aggregate per-symbol-date**:
   - `wr = n_wins / (n_wins + n_losses)` (zeros excluded)
   - `expectancy_bps = mean(signed_delta_mid_bps_per_trade)` where signed means `delta * predicted_direction`
5. **Aggregate overall**: pool all trades across pairs.
6. **Attach to spec** — mutate `spec.measured_wr`, `spec.measured_expectancy_bps`, `spec.measured_n_trades` in the returned result object.
7. **Emit** — `BacktestResult` with full per-symbol breakdown.
8. **Optional trace** — if orchestrator passes `save_trace=True`, dump per-trade records (ts, symbol, signal_value, predicted_dir, delta_mid_bps, win/loss) as parquet at `iterations/iter_<N>/traces/<spec_id>.parquet`.

Sanity guards:
- If `aggregate_n_trades == 0`: return `wr=0.5, expectancy_bps=0` and mark `weaknesses=["no trades triggered"]` (handled downstream by feedback-analyst).
- If per-symbol `n_ticks < 1000`: warn but continue.
