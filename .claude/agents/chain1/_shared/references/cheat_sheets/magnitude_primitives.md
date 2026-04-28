# Magnitude Primitives — Net-PnL Objective Companion

**Purpose**: Under the net-PnL objective (`net_expectancy = expectancy_bps − fee_bps_rt > 0`), pure WR maximisation is insufficient. A directionally-correct spec with WR=0.96 but expectancy=9 bps is still capped post-fee at KRX 23 bps RT. To deploy, gross expectancy must EXCEED the round-trip fee. This sheet maps each primitive / helper to the magnitude axis it serves.

> *2026-04-27 addition. Read alongside `regime_primitives.md`, `direction_semantics.md`, and `time_of_day_regimes.md`.*

---

## The 3 Axes of Magnitude

A spec's per-fill |Δmid| can be increased along three orthogonal axes:

| Axis | Mechanism | Lever |
|---|---|---|
| **A. Horizon scaling** | √h scaling of |Δmid| — longer hold → larger expected move | `prediction_horizon_ticks ↑` |
| **B. Regime concentration** | Conditioning on windows where |Δmid| is empirically larger | Multiplicative gate by a regime indicator |
| **C. Tail selection** | Restricting to extreme percentiles where mean |Δmid| is larger | `zscore(primitive, W) > N` with N ≥ 2.0 |

Combine 2 or more axes for compounding gain. Top-tier specs typically use **A × B** (longer horizon + regime gate) or **B × C** (regime + tail).

---

## Axis A — Horizon scaling

**Rule of thumb**: If a signal predicts direction with WR > 0.55, then `|E[Δmid] | h ticks ahead| ≈ σ_per_tick × √h × (2·WR − 1)`. Doubling horizon raises expected magnitude by √2 ≈ 1.41×.

**Levers:**
- `prediction_horizon_ticks`: cycle 1 → 5 → 20 → 50 → 100 → 200. KRX empirical sweet spot for compounding gross magnitude vs predictive decay: **20–50 ticks**.
- Cost: predictive accuracy declines. WR typically falls 1–5 percentage points per doubling of h.

**No specific primitive needed** — this is purely a hyperparameter axis. But MUST be paired with at least one of B or C, because pure horizon scaling alone hits a noise ceiling.

---

## Axis B — Regime concentration

Multiply a directional signal by a regime indicator that flags windows of empirically larger |Δmid|. Mathematically: `signal_gated = signal × regime_flag`. Trades only fire when the gate is 1.

### Volatility regime — primary lever

| Helper | What it captures | Use |
|---|---|---|
| `rolling_realized_vol(mid_px, W)` | RMS of mid diffs over W ticks | High-vol regime gate. Threshold: `rolling_realized_vol(mid_px, 100) > 30` (KRW units; tune per symbol price level) |
| `rolling_range_bps(mid_px, W)` | Parkinson high-low range in bps | Tail-aware vol — more sensitive than RMS to single large moves. Threshold: `rolling_range_bps(mid_px, 200) > 15` |
| `spread_change_bps` (primitive) | Δspread tick-over-tick | Spread widening often precedes large directional move (information arrival) |

### Time-of-day regime — boolean gates

| Primitive | Window (KST) | Use |
|---|---|---|
| `is_opening_burst` | 09:00–09:30 | Highest-magnitude window. Multiply directional signal by this to concentrate on overnight-information unwind. |
| `is_closing_burst` | 14:30–15:30 | Second-highest. Closing-auction inventory rebalancing. |
| `is_lunch_lull` | 11:30–13:00 | NEGATION filter: `(1 - is_lunch_lull) * signal` to suppress trades in the lowest-magnitude window. |

See `time_of_day_regimes.md` for measured magnitudes per window.

### Liquidity regime

| Primitive | What it signals |
|---|---|
| `book_thickness` | LOW thickness ⇒ higher |Δmid| per fill (thin book = price moves on small volume). Threshold: `book_thickness < median_book_thickness * 0.5` |
| `bid_depth_concentration`, `ask_depth_concentration` | Wall presence — large walls cause reversion-on-break (B1) or absorption (gradual move). High concentration ⇒ sharper magnitude on resolution. |

### Composition pattern

```
signal × is_opening_burst × (rolling_realized_vol(mid_px, 100) > threshold)
```

---

## Axis C — Tail selection

Restrict entries to the extreme tail of a primitive's distribution. The mean |Δmid| in the tail is mechanically larger than the unconditional mean.

| Helper | Tail rule | When |
|---|---|---|
| `zscore(primitive, W) > 2.0` | Top ~2.5% (1 in 40 ticks) | Standard tightening |
| `zscore(primitive, W) > 2.5` | Top ~0.6% (1 in 160 ticks) | Aggressive — bigger magnitude per fill, fewer trades |
| `zscore(primitive, W) > 3.0` | Top ~0.13% (1 in 750 ticks) | Extreme — paper-grade rare events |
| `rolling_range_bps(mid_px, W) > rolling_mean(rolling_range_bps, 5×W)` | Range > recent average | Magnitude-direct tail (NOT direction-direct) |

**Tail vs threshold**: a raw-value threshold (e.g., `obi_1 > 0.7`) is a tail rule too, but it doesn't adapt to per-symbol or per-regime variability. Z-score-based tail rules are recommended for portfolio-level deployment.

---

## Forbidden patterns (these CAN raise WR but rarely raise magnitude)

| Anti-pattern | Why it fails the net-PnL objective |
|---|---|
| Tightening threshold without horizon change | Climbs WR toward 1, but magnitude stays ~constant. Net is unchanged. |
| Dropping a feature without adding a magnitude lever | Reduces noise in WR estimate, but doesn't expand magnitude reach. |
| Pure ensemble vote with no axis-A/B/C component | Reduces variance, doesn't raise expected per-fill magnitude. |

If `feedback-analyst` recommends one of these (`tighten_threshold`, `drop_feature`, `ensemble_vote`) and the parent has `net_expectancy ≤ 0`, the recommendation will systematically waste budget. Under the new objective, the decision tree explicitly skips these for fee-capped parents.

---

## Hypothesis-text template (REQUIRED under net-PnL objective)

Every spec hypothesis MUST include a sentence of the form:

> *"Expected expectancy_bps target: ≥ N where N > fee_bps_rt. Mechanism: axis [A/B/C], specifically <horizon-extension OR regime-gating OR tail-selection> via <primitive list>."*

This forces post-hoc calibration: the calibration check compares stated N against measured `expectancy_bps`, so consistent over-claiming is detected.

Example (good):
> *"Expected expectancy_bps target ≥ 25 (vs 23 bps fee). Mechanism: axis A (horizon=100 vs default 20) × axis B (is_opening_burst gate). Lever: √5 ≈ 2.2× scaling × 1.5× burst-window multiplier ≈ 3.3× baseline magnitude."*

Example (bad — 90% of v3 hypotheses):
> *"This signal should improve WR by tightening the threshold from 2.0 to 2.5."*

---

## Quick reference — magnitude primitive list

```
Axis A  : prediction_horizon_ticks (hyperparameter)
Axis B  : is_opening_burst, is_closing_burst, is_lunch_lull,
          rolling_realized_vol(mid_px, W), rolling_range_bps(mid_px, W),
          book_thickness, bid_depth_concentration, ask_depth_concentration,
          spread_change_bps
Axis C  : zscore(primitive, W) > 2.0/2.5/3.0,
          rolling_range_bps(mid_px, W) > rolling_mean(rolling_range_bps, 5×W)
```

Pair at least 2 axes per spec.
