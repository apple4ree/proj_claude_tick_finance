# Formula Validity Rules

Deterministic checks to apply in signal-evaluator §6 Reasoning Flow. Each check either PASSes or adds a concern.

---

## Hard-fail (valid=false) checks

1. **Primitive identifier not in whitelist** — strictly reject.
   - Whitelist = union of primitives in the following cheat sheets (updated 2026-04-21):
     - `obi_family_formulas.md` (obi_1/3/5/10, obi_total, microprice, vamp_*, spread_bps, book_slope_*)
     - `ofi_family_formulas.md` (ofi_proxy, ofi_cks_1, **ofi_depth_5, ofi_depth_10**, vol_flow)
     - `regime_primitives.md` (**mid_px, minute_of_session, book_thickness**)
   - Stateful helpers (callable in formula, NOT listed in `primitives_used`):
     rolling_mean, rolling_std, zscore, **rolling_realized_vol, rolling_momentum**.
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

## Duplicate-detection rule

Two specs A, B are considered duplicates iff all hold:
1. `set(A.primitives_used) == set(B.primitives_used)`
2. `|A.threshold - B.threshold| / max(A.threshold, B.threshold, 1e-6) ≤ 0.05`
3. `A.direction == B.direction`
4. `A.prediction_horizon_ticks == B.prediction_horizon_ticks`

If A's feedback tag is `retire`, mark B as `valid: false` with `duplicate_of: A.spec_id`.

## Expected-merit heuristic

- `high`: cites ≥ 2 references, novel primitive combination vs prior index, theoretically motivated
- `medium`: cites ≥ 1 reference, mild variation of prior high/medium spec
- `low`: minimal citations, mechanically composed, high chance of being noise-level
- `unknown`: insufficient information to rank
