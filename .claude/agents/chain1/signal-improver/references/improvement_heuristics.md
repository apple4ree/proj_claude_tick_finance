# Improvement Heuristics — Mutation recipes

For each `recommended_next_direction` produced by feedback-analyst, this file lists concrete atomic mutations to propose.

> **2026-04-27 paradigm shift (regime-state)**: Mutations now affect **signal duty cycle** and **regime structure**, not per-tick trade counts. See `_shared/references/cheat_sheets/regime_state_paradigm.md`. `change_horizon` is largely deprecated (no fixed exit). New axis: **signal stickiness** (how long signal stays True per regime).

---

## `tighten_threshold` (regime-state interpretation)

Recipe: `threshold_new = threshold_old * k`, k ∈ {1.2, 1.5, 2.0}. Propose one value.
Rationale: higher threshold → **lower duty cycle, fewer regimes, higher per-regime conviction**. Use when current spec has duty > 0.5 with good gross.
Proposal string format: `"threshold 0.50 → 0.75 (narrows duty cycle)"`

## `loosen_threshold` (regime-state interpretation)

Recipe: `threshold_new = threshold_old * k`, k ∈ {0.8, 0.6, 0.4}.
Rationale: lower threshold → **higher duty cycle, more regimes**. Use when feedback flags "signal too rare" (n_regimes/sessions < 1.5).
Proposal string: `"threshold 0.50 → 0.30 (widens duty cycle for sample power)"`

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

## `change_horizon` ⚠️ DEPRECATED under regime-state paradigm (2026-04-27)

**In regime-state mode, exit timing is determined by signal transition, not fixed horizon.** When this direction is recommended (legacy behavior or v3 spec mutation), reinterpret as **"extend signal stickiness"**:
  - Add a rolling smoother around the formula: e.g., `obi_1 > 0.5` → `rolling_mean(obi_1, 30) > 0.5`. This makes the signal stay True longer (longer regime duration).
  - Or add a regime gate that's slow-moving: e.g., `(obi_1 > 0.5) AND (rolling_realized_vol > 30)` keeps signal True during whole vol regime.
  - DO NOT modify `prediction_horizon_ticks` — it has no effect on backtest under regime-state.

Proposal string format under regime-state:
```
"extend hold: wrap formula with rolling_mean(..., 30) — signal stickiness +"
```

### Legacy fixed-H content (preserved for reference; do NOT use under regime-state)

### Theoretical basis
Almgren-Chriss (2001) optimal execution horizon:
```
T*_seconds = sqrt(η / (λ · σ²))
  η  ≈ temporary price impact coefficient (bps per unit size)
  λ  ≈ risk aversion parameter
  σ  ≈ midprice volatility (bps per second)
```

### KRX 005930 / 000660 large-cap calibration (empirical)
```
σ ≈ 15 bps/sec        (intraday mid-price volatility, stable)
λ ≈ 1e-5              (retail-scale risk aversion; tune per project)
η ≈ 0.5 bps/share     (for 1-share orders; near-zero impact)
```

Working values:
```
T*_seconds ≈ sqrt(0.5 / (1e-5 × 225)) ≈ sqrt(222) ≈ 15 seconds
T*_ticks   ≈ 150 ticks (at 100ms cadence)
```

### Recipe

**Step 1**: Compute T*_ticks (default 150 for KRX large caps).

**Step 2**: Based on current horizon `H_old` and viability_tag from feedback:

| Current state | Proposed horizons |
|---|---|
| H_old < 0.5·T* (too short, i.e. < 75 ticks) | {0.5·T*, T*, 1.5·T*} = {75, 150, 225} |
| H_old ∈ [0.5·T*, 2·T*] (near optimum) | {H_old × 0.7, H_old × 1.3} (slight variation) |
| H_old > 2·T* (too long, > 300 ticks) | {T*, T*/1.5} (shorten toward optimum) |
| viability_tag == `capped_post_fee` | Override: propose largest feasible horizon {200, 500, 1000}. Rationale: avg_|Δmid| cannot beat 30bps fee at tick scale; only multi-tick drift gives any chance. |
| viability_tag == `marginal_post_fee` | Stay near T*: {T*·0.7, T*, T*·1.3} = {105, 150, 195} |
| viability_tag == `deployable_post_fee` | FREEZE horizon — do not mutate; propose `tighten_threshold` or `combine` instead. |

**Step 3**: Proposal string format (include T* reasoning):
```
"horizon 5 → 150 ticks (AC T*=150 for KRX 005930 σ=15bps/sec λ=1e-5)"
```

### Anti-patterns for change_horizon
- Blindly cycling `1 → 5 → 20` without considering AC T* is **now deprecated**.
- Proposing horizon < 10 ticks is almost never optimal for KRX large caps — entry noise dominates.
- Proposing horizon > 500 ticks only useful under `capped_post_fee` — otherwise signal decays faster than avg_|Δmid| grows.

### Empirical anchoring
Our iter012~014 Chain 1 horizon sweep showed expectancy peaking at h≈20 on small-sample runs. This is **below** AC T*=150, which is consistent with AC's "risk-aversion" term dominating at high λ — i.e., the signal's internal noise reverses any advantage of longer hold. Use AC T* as **upper bound**, not universal optimum.

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

### `multiplicative_interaction` (NEW 2026-04-26)

Combine two existing high-merit specs A, B (or a spec + a transform) using continuous multiplication / non-linear combination instead of Boolean AND.

Recipe types (see `direction_semantics.md §D4`):
- **P1 sign-modulated**: `A_primitive * sign(B_primitive)` — directional agreement filter
- **P2 magnitude**: `sqrt(A**2 + B**2)` — total imbalance vector length
- **P3 rational**: `A / (1 + B/k)` — A discounted by B
- **P4 exponential**: `A * exp(-B/k)` — smooth filter version
- **P5 where()**: `where(cond, A, 0)` — same as A * (cond) but more readable

Proposal string examples:
- `"sign-modulated: obi_1 * sign(zscore(trade_imbalance_signed, 300))"`
- `"magnitude: sqrt(obi_1**2 + obi_ex_bbo**2)"`
- `"rational: obi_1 / (1 + spread_bps/5)"`
- `"smooth filter: obi_1 * exp(-spread_bps/3)"`

Direction inheritance: see direction_semantics §D4 §"Direction inheritance for multiplicative compounds".

When to propose:
- Two specs with Boolean AND already tried, mixed performance — try sign-modulated.
- Spec performance varies strongly by `spread_bps` regime — try rational discount.
- Two correlated primitives (e.g., obi_1 & obi_ex_bbo) — try magnitude vector.

Use this recipe when feedback contains `combine_with_other_spec` or when prior iterations explored `add_filter` exhaustively.

### `add_regime_filter`

Add a regime filter AND-clause using Block A primitives (realized vol / time-of-day / book thickness).

Proposal string examples:
- `"AND rolling_realized_vol(mid_px, 100) > 40"` — high-volatility regime only
- `"AND minute_of_session > 350"` — closing zone only (14:50-15:30)
- `"AND book_thickness > 800000"` — deep-book regime only

Rationale: microstructure signals typically stronger in specific regimes. Block A primitives make this programmable.

---

---

## Viability-tag-driven priority (2026-04-23)

feedback-analyst attaches one of {`deployable_post_fee`, `marginal_post_fee`, `capped_post_fee`} to each Feedback (see `feedback-analyst/references/analysis_framework.md §Post-fee deployment sanity`). Use these to override default decision tree:

| viability_tag | Most impactful mutations | Skip these |
|---|---|---|
| `deployable_post_fee` | `combine_with_other_spec` (portfolio Sharpe uplift), `ensemble_vote` | `change_horizon` (don't disturb a working signal) |
| `marginal_post_fee` | `add_filter` (esp. `add_regime_filter` with shape primitives per Bouchaud-MP), `change_horizon` (tight around T*) | `loosen_threshold` (expanding n_trades won't help magnitude) |
| `capped_post_fee` | `change_horizon` (push toward max H=200~1000), `swap_feature` to different category | `tighten_threshold` (improves WR but not avg_win), minor variants |

### Mandatory override rules

- If parent Feedback has `capped_post_fee`: produce AT LEAST ONE `change_horizon` mutation with target horizon ≥ 200 ticks.
- If parent Feedback has `marginal_post_fee`: produce AT LEAST ONE `add_filter` proposal targeting shape primitives (`ask_depth_concentration`, `bid_depth_concentration`, `book_thickness`) per Bouchaud-MP 2002.
- If parent Feedback has `deployable_post_fee` AND iteration_idx ≥ 3: prefer `combine_with_other_spec` over solo mutations. Chain 1.5 will handle exit, Chain 2 will handle fees — diversification is the remaining lever.

### Direction check for mutations involving new primitives

Before finalizing any mutation that introduces a new primitive:
1. Classify the new primitive per `../_shared/references/cheat_sheets/direction_semantics.md` (Category A/B1/B2/B3/C).
2. Set default `direction` accordingly.
3. Cite category in mutation string: e.g., `"add primitive: ask_depth_concentration (Category B1) → direction long_if_neg"`.

---

## Anti-patterns to avoid

- **Large simultaneous multi-axis mutations** (e.g., threshold + horizon + feature all at once). Stay atomic.
- **Re-proposing a mutation that matches a retired entry in `prior_iterations_index.md`**.
- **Jumping across primitive families without recording reasoning** — always cite why the new family is expected to be different (cite references).
- **Ignoring viability_tag** — if parent Feedback carries `capped_post_fee`, proposing `tighten_threshold` is a **waste of iteration budget** (WR improvement cannot overcome fee wall). Feedback tag must drive recipe selection.
- **Cycling horizon without AC T* context** — see `change_horizon` section. Pure `1 → 5 → 20` heuristic is deprecated.

## Budget adherence

`ImprovementProposal` list length ≤ `next_iteration_budget`. If heuristic would produce more, drop the lowest-expectancy parents' proposals first.
