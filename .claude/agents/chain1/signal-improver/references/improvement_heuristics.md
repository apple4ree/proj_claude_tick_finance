# Improvement Heuristics — Mutation recipes

For each `recommended_next_direction` produced by feedback-analyst, this file lists concrete atomic mutations to propose.

---

## `tighten_threshold`

Recipe: `threshold_new = threshold_old * k`, k ∈ {1.2, 1.5, 2.0}. Propose one value.
Rationale: higher threshold → fewer but higher-conviction trades.
Proposal string format: `"threshold 0.50 → 0.75"`

## `loosen_threshold`

Recipe: `threshold_new = threshold_old * k`, k ∈ {0.8, 0.6, 0.4}.
Rationale: lower threshold → more trades (increases n_trades for statistical power).
Proposal string: `"threshold 0.50 → 0.30"`

## `add_filter`

Candidate filters (AND-clauses):
- `spread_bps < X` with X ∈ {5, 10, 15}
- `|obi_5| > 0.3` (depth confirmation)
- `rolling_mean(vol_flow, 50) > 0` (active market only)

Recipe: pick the filter from the list above that least overlaps with existing formula primitives.
Proposal string: `"add filter: AND spread_bps < 10"`

## `drop_feature`

Applies only to compound formulas. Recipe: remove the primitive whose individual WR contribution is lowest (inferred from per-bucket analysis; if unknown, drop the most complex primitive).
Proposal string: `"drop primitive obi_10; new formula = obi_1 - 0.3 * obi_5"`

## `swap_feature`

Recipe: replace primary primitive with a different family.
- obi_* → ofi_proxy / ofi_cks_1
- ofi_* → microprice_dev_bps
- microprice_dev_bps → vamp_5
Proposal string: `"swap primitive obi_1 → ofi_proxy"`

## `change_horizon`

Recipe: cycle through **{1, 5, 20, 50, 100} ticks** (expanded Block B). Pick the next value in the cycle that hasn't been tried for this lineage.
- Horizon scaling: expected |Δmid| grows as √h (random-walk). Longer h → larger absolute edge but signal predictive power decays.
- Sweet spot empirically h=20-50 for KRX microstructure (CKS 2014 Fig 5).
- Proposal string: `"horizon 1 → 5 ticks"`

## `combine_with_other_spec`

Recipe: AND two high-merit specs from the same iteration batch. Propose `SignalSpec` with `formula = formula_A AND formula_B`. Primitives used = union. Threshold defaults to `min(A.threshold, B.threshold)`.
Proposal string: `"combine with iter003_microdev_pos: new formula = (obi_1 > 0.5) AND (microprice_dev_bps > 1)"`

## `retire`

No mutation. Proposal is skipped (spec-improver does not generate a proposal for retired parents).

---

## Block B additions — 4 new recipes (2026-04-21)

### `ensemble_vote`

Require majority of 3 thresholded primitives to agree before entry. Smooths single-signal noise.

Proposal string example:
`"ensemble: (obi_1>0.5 AND ofi_proxy>0) OR (obi_1>0.5 AND microprice_dev_bps>2)"` (2-of-3 majority)

Rationale: single primitive near threshold often flips on noise. Requiring ≥2/3 agreement trades n_trades for WR stability.

### `extreme_quantile`

Replace static threshold with z-score extreme threshold (p99+). Uses `zscore()` stateful helper with large window.

Proposal string: `"tighten to extreme: zscore(obi_1, 300) > 2.5"` (top 0.6% of observations)

Rationale: intrinsic alpha often concentrated in extreme signal tail. Trade density drops dramatically (100-500/day/sym) but per-trade expectancy can 3-5×.

### `timevarying_threshold`

Replace static threshold with adaptive `N × rolling_std(primitive, W)`. Auto-adjusts to regime shifts (morning vs. afternoon volatility).

Proposal string: `"timevarying: obi_1 > 2 * rolling_std(obi_1, 300)"` (2-sigma dynamic)

Rationale: static threshold overfits a single regime. Adaptive threshold follows local volatility → robust across sessions/days.

### `add_regime_filter`

Add a regime filter AND-clause using Block A primitives (realized vol / time-of-day / book thickness).

Proposal string examples:
- `"AND rolling_realized_vol(mid_px, 100) > 40"` — high-volatility regime only
- `"AND minute_of_session > 350"` — closing zone only (14:50-15:30)
- `"AND book_thickness > 800000"` — deep-book regime only

Rationale: microstructure signals typically stronger in specific regimes. Block A primitives make this programmable.

---

## Anti-patterns to avoid

- **Large simultaneous multi-axis mutations** (e.g., threshold + horizon + feature all at once). Stay atomic.
- **Re-proposing a mutation that matches a retired entry in `prior_iterations_index.md`**.
- **Jumping across primitive families without recording reasoning** — always cite why the new family is expected to be different (cite references).

## Budget adherence

`ImprovementProposal` list length ≤ `next_iteration_budget`. If heuristic would produce more, drop the lowest-expectancy parents' proposals first.
