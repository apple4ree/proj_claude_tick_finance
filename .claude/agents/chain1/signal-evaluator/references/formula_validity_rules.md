# Formula Validity Rules

Deterministic checks to apply in signal-evaluator §6 Reasoning Flow. Each check either PASSes or adds a concern.

---

## Hard-fail (valid=false) checks

1. **Primitive identifier not in whitelist** — strictly reject.
   - Whitelist = union of primitives in the following cheat sheets (updated 2026-04-27):
     - `obi_family_formulas.md` (obi_1/3/5/10, obi_total, microprice, vamp_*, spread_bps, book_slope_*)
     - `ofi_family_formulas.md` (ofi_proxy, ofi_cks_1, **ofi_depth_5, ofi_depth_10**, vol_flow)
     - `regime_primitives.md` (**mid_px, minute_of_session, book_thickness**)
     - `microstructure_advanced.md` (Block C–E: trade_imbalance_signed, bid/ask_depth_concentration, obi_ex_bbo, queue_imbalance_best, microprice_velocity, spread_change_bps, book_imbalance_velocity, signed_volume_cumulative, book_pressure_asymmetry, lee_ready_proper, transaction_power_signal, aggressive_buy_indicator, trade_price_dev_bps, vpin_proxy_per_tick)
     - `time_of_day_regimes.md` (Block F, **2026-04-27**: is_opening_burst, is_lunch_lull, is_closing_burst)
   - Stateful helpers (callable in formula, NOT listed in `primitives_used`):
     rolling_mean, rolling_std, zscore, **rolling_realized_vol, rolling_momentum**, rolling_max, rolling_min, rolling_sum, **rolling_range_bps (2026-04-27)**.
2. **Lookahead pattern found** — reject on any regex match of `/_?(t\+|next_|fwd_|future_|post_)/i` in formula string.
3. **Non-existent reference path** — if any path in `spec.references` does not resolve on disk.
4. **Measured fields non-null on first submission** — `measured_wr`, `measured_expectancy_bps`, `measured_n_trades` must be None.
5. **spec_id malformed** — must match `^iter\d{3}_[a-z0-9_]+$`.
6. **iteration_idx mismatch** — spec's `iteration_idx` must equal evaluator's input `iteration_idx`.

## Soft-fail (concern recorded, valid may stay true)

- **Hypothesis < 50 chars or lacks mechanism verb** ("predicts", "implies", "drives", "anticipates")
- **Single-primitive signal with threshold at extreme quantile** (e.g., `obi_1 > 0.99`) — low trade count likely
- **Compound formula without intermediate justification** (long AND chain without rationale)
- **Threshold magnitude exceeds primitive's realistic domain** (e.g., `obi_1 > 5` — obi_1 is bounded [-1, 1])
- **Regime-state hypothesis missing target metrics (v5+)**: hypothesis lacks expected `signal_duty_cycle`, `mean_duration_ticks`, or `gross_expectancy_bps target` — flag soft concern. Per `_shared/references/cheat_sheets/regime_state_paradigm.md` §3, these targets are required for verifiable post-hoc calibration.
- **Regime-state design red flag**: formula likely to produce flickering signal (raw single-primitive without smoothing) — e.g., `obi_1 > 0`, `microprice_dev_bps > 0` — flag soft concern recommending rolling smoother (`zscore(..., W)`) or compound regime gate.

## Duplicate-detection rule (REVISED 2026-04-23 — loosened)

### Exact-replica test (hard reject)
A spec B is a duplicate of prior A iff **ALL** of the following hold:

1. **Formula strings equal after normalization**:
   - Strip all whitespace
   - Lowercase all keywords (AND/OR/NOT → and/or/not)
   - Compare: `normalize(A.formula) == normalize(B.formula)`
2. `set(A.primitives_used) == set(B.primitives_used)`
3. `|A.threshold - B.threshold| / max(A.threshold, B.threshold, 1e-6) ≤ 0.01` (1%, not 5%)
4. `A.direction == B.direction`
5. `A.prediction_horizon_ticks == B.prediction_horizon_ticks`

### Reject only retired duplicates
Even if all 5 conditions hold, **reject (valid=false, duplicate_of=A.spec_id) ONLY IF**:
- A's feedback tag is `retire`, OR
- A's `measured_expectancy_bps < 1.0` with `measured_n_trades > 500` (proven weak)

Otherwise: set `duplicate_of=A.spec_id` but leave `valid=true`. This lets the orchestrator note redundancy without blocking progression.

### Near-variants are ENCOURAGED
Specs that differ only slightly from good prior specs (e.g., threshold adjusted by >1%, horizon changed, filter added) are **welcome** — they are exactly how the iterative framework improves. Reject them is a framework bug, not a feature.

**Concrete examples**:
- Prior: `obi_1` thr=0.5 H=20 long_if_pos. New: `obi_1` thr=0.5 H=50 long_if_pos. **Accept (different H)**.
- Prior: `obi_1` thr=0.5. New: `obi_1` thr=0.55. **Accept (1.1% > 1% threshold change)** (thr-delta 10%).
- Prior formula: `obi_1 > 0.5 AND microprice_dev_bps > 1`. New: `obi_1 > 0.5 AND microprice_dev_bps > 1.0`. **Reject** (identical after normalization).
- Prior (retired): `obi_10` thr=0.5. New: `obi_10` thr=0.5. **Reject** (retired weak spec).

### Rationale
iter_007 showed that over-aggressive duplicate rejection **stops exploration prematurely**. The framework's autonomous loop depends on iterative variation; variations should not be confused with duplicates. The above rules require **literal duplicates** only.

## Expected-merit heuristic

- `high`: cites ≥ 2 references, novel primitive combination vs prior index, theoretically motivated
- `medium`: cites ≥ 1 reference, mild variation of prior high/medium spec
- `low`: minimal citations, mechanically composed, high chance of being noise-level
- `unknown`: insufficient information to rank
